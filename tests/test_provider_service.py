"""Tests for provider service."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from cryptography.fernet import Fernet

from app.database.database import Base
from app.models.provider import Provider
from app.models.model import Model
from app.services.encryption_service import EncryptionService
from app.services.provider_service import ProviderService


@pytest.fixture
def test_db():
    """Create a test database."""
    from sqlalchemy import event
    
    engine = create_engine("sqlite:///:memory:")
    
    # Enable foreign key constraints for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture
def encryption_service():
    """Create encryption service with test key."""
    import os
    import sys
    
    # Generate a test encryption key
    test_key = Fernet.generate_key().decode()
    
    # Set environment and clear module cache
    with patch.dict(os.environ, {
        "ENCRYPTION_KEY": test_key,
        "GPTLOAD_AUTH_KEY": "test-auth-key",
        "DATABASE_URL": "sqlite:///:memory:",
    }, clear=True):
        # Clear any cached imports
        if 'app.config' in sys.modules:
            del sys.modules['app.config']
        if 'app.services.encryption_service' in sys.modules:
            del sys.modules['app.services.encryption_service']
        
        # Import after patching environment
        from app.services.encryption_service import EncryptionService
        
        service = EncryptionService()
        yield service


@pytest.fixture
def provider_service(encryption_service):
    """Create provider service."""
    return ProviderService(encryption_service)


class TestProviderCRUD:
    """Test provider CRUD operations."""

    @pytest.mark.asyncio
    async def test_add_provider_success(self, test_db, provider_service):
        """Test adding a provider successfully."""
        # Mock validation to succeed
        with patch.object(provider_service, 'validate_provider', return_value=True):
            provider = await provider_service.add_provider(
                test_db,
                name="TestProvider",
                base_url="https://api.test.com",
                api_key="sk-test-key-123",
                channel_type="openai"
            )
            
            assert provider.id is not None
            assert provider.name == "TestProvider"
            assert provider.base_url == "https://api.test.com"
            assert provider.channel_type == "openai"
            assert provider.api_key_encrypted != "sk-test-key-123"  # Should be encrypted
            
            # Verify it's in the database
            db_provider = test_db.query(Provider).filter(Provider.id == provider.id).first()
            assert db_provider is not None
            assert db_provider.name == "TestProvider"

    @pytest.mark.asyncio
    async def test_add_provider_validation_failure(self, test_db, provider_service):
        """Test adding a provider with validation failure."""
        # Mock validation to fail
        with patch.object(provider_service, 'validate_provider', return_value=False):
            with pytest.raises(ValueError, match="validation failed"):
                await provider_service.add_provider(
                    test_db,
                    name="TestProvider",
                    base_url="https://api.test.com",
                    api_key="sk-invalid-key",
                    channel_type="openai"
                )

    @pytest.mark.asyncio
    async def test_add_provider_duplicate_name(self, test_db, provider_service):
        """Test adding a provider with duplicate name."""
        # Mock validation to succeed
        with patch.object(provider_service, 'validate_provider', return_value=True):
            # Add first provider
            await provider_service.add_provider(
                test_db,
                name="TestProvider",
                base_url="https://api.test.com",
                api_key="sk-test-key-123",
                channel_type="openai"
            )
            
            # Try to add duplicate
            with pytest.raises(ValueError, match="already exists"):
                await provider_service.add_provider(
                    test_db,
                    name="TestProvider",
                    base_url="https://api.other.com",
                    api_key="sk-other-key",
                    channel_type="openai"
                )

    def test_list_providers_with_masked_keys(self, test_db, provider_service, encryption_service):
        """Test listing providers with masked API keys."""
        # Add providers directly to database
        provider1 = Provider(
            name="Provider1",
            base_url="https://api.provider1.com",
            api_key_encrypted=encryption_service.encrypt("sk-provider1-key-1234567890"),
            channel_type="openai"
        )
        provider2 = Provider(
            name="Provider2",
            base_url="https://api.provider2.com",
            api_key_encrypted=encryption_service.encrypt("sk-provider2-key-0987654321"),
            channel_type="anthropic"
        )
        test_db.add(provider1)
        test_db.add(provider2)
        test_db.commit()
        
        # List providers
        providers = provider_service.list_providers(test_db)
        
        assert len(providers) == 2
        assert providers[0]["name"] == "Provider1"
        assert providers[0]["api_key_masked"].startswith("sk-")
        assert "*" in providers[0]["api_key_masked"]
        assert "provider1-key" not in providers[0]["api_key_masked"]
        
        assert providers[1]["name"] == "Provider2"
        assert providers[1]["api_key_masked"].startswith("sk-")
        assert "*" in providers[1]["api_key_masked"]

    def test_get_provider(self, test_db, provider_service, encryption_service):
        """Test getting a provider by ID."""
        # Add provider
        provider = Provider(
            name="TestProvider",
            base_url="https://api.test.com",
            api_key_encrypted=encryption_service.encrypt("sk-test-key"),
            channel_type="openai"
        )
        test_db.add(provider)
        test_db.commit()
        
        # Get provider
        retrieved = provider_service.get_provider(test_db, provider.id)
        
        assert retrieved is not None
        assert retrieved.id == provider.id
        assert retrieved.name == "TestProvider"

    def test_get_provider_not_found(self, test_db, provider_service):
        """Test getting a non-existent provider."""
        retrieved = provider_service.get_provider(test_db, 999)
        assert retrieved is None

    def test_get_provider_with_decrypted_key(self, test_db, provider_service, encryption_service):
        """Test getting a provider with decrypted API key."""
        # Add provider
        provider = Provider(
            name="TestProvider",
            base_url="https://api.test.com",
            api_key_encrypted=encryption_service.encrypt("sk-test-key-123"),
            channel_type="openai"
        )
        test_db.add(provider)
        test_db.commit()
        
        # Get provider with decrypted key
        provider_dict = provider_service.get_provider_with_decrypted_key(test_db, provider.id)
        
        assert provider_dict is not None
        assert provider_dict["api_key"] == "sk-test-key-123"
        assert provider_dict["name"] == "TestProvider"

    @pytest.mark.asyncio
    async def test_update_provider(self, test_db, provider_service, encryption_service):
        """Test updating a provider."""
        # Add provider
        provider = Provider(
            name="TestProvider",
            base_url="https://api.test.com",
            api_key_encrypted=encryption_service.encrypt("sk-test-key"),
            channel_type="openai"
        )
        test_db.add(provider)
        test_db.commit()
        
        # Mock validation
        with patch.object(provider_service, 'validate_provider', return_value=True):
            # Update provider
            updated = await provider_service.update_provider(
                test_db,
                provider.id,
                name="UpdatedProvider",
                base_url="https://api.updated.com"
            )
            
            assert updated is not None
            assert updated.name == "UpdatedProvider"
            assert updated.base_url == "https://api.updated.com"

    @pytest.mark.asyncio
    async def test_update_provider_not_found(self, test_db, provider_service):
        """Test updating a non-existent provider."""
        updated = await provider_service.update_provider(
            test_db,
            999,
            name="UpdatedProvider"
        )
        assert updated is None

    def test_delete_provider(self, test_db, provider_service, encryption_service):
        """Test deleting a provider."""
        # Add provider
        provider = Provider(
            name="TestProvider",
            base_url="https://api.test.com",
            api_key_encrypted=encryption_service.encrypt("sk-test-key"),
            channel_type="openai"
        )
        test_db.add(provider)
        test_db.commit()
        provider_id = provider.id
        
        # Delete provider
        result = provider_service.delete_provider(test_db, provider_id)
        
        assert result is True
        
        # Verify it's deleted
        deleted = test_db.query(Provider).filter(Provider.id == provider_id).first()
        assert deleted is None

    def test_delete_provider_cascade(self, test_db, provider_service, encryption_service):
        """Test deleting a provider cascades to models."""
        # Add provider
        provider = Provider(
            name="TestProvider",
            base_url="https://api.test.com",
            api_key_encrypted=encryption_service.encrypt("sk-test-key"),
            channel_type="openai"
        )
        test_db.add(provider)
        test_db.commit()
        
        # Add models
        model1 = Model(provider_id=provider.id, original_name="model-1")
        model2 = Model(provider_id=provider.id, original_name="model-2")
        test_db.add(model1)
        test_db.add(model2)
        test_db.commit()
        
        provider_id = provider.id
        
        # Delete provider
        result = provider_service.delete_provider(test_db, provider_id)
        
        assert result is True
        
        # Verify models are also deleted
        models = test_db.query(Model).filter(Model.provider_id == provider_id).all()
        assert len(models) == 0

    def test_delete_provider_not_found(self, test_db, provider_service):
        """Test deleting a non-existent provider."""
        result = provider_service.delete_provider(test_db, 999)
        assert result is False


class TestProviderValidation:
    """Test provider validation."""

    @pytest.mark.asyncio
    async def test_validate_provider_success(self, provider_service):
        """Test successful provider validation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await provider_service.validate_provider(
                "https://api.test.com",
                "sk-test-key",
                "openai"
            )
            
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_provider_timeout(self, provider_service):
        """Test provider validation with timeout."""
        import httpx
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )
            
            result = await provider_service.validate_provider(
                "https://api.test.com",
                "sk-test-key",
                "openai"
            )
            
            assert result is False

    @pytest.mark.asyncio
    async def test_validate_provider_request_error(self, provider_service):
        """Test provider validation with request error."""
        import httpx
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )
            
            result = await provider_service.validate_provider(
                "https://api.test.com",
                "sk-test-key",
                "openai"
            )
            
            assert result is False


class TestModelFetching:
    """Test model fetching from providers."""

    @pytest.mark.asyncio
    async def test_fetch_models_success(self, test_db, provider_service, encryption_service):
        """Test fetching models successfully."""
        # Add provider
        provider = Provider(
            name="TestProvider",
            base_url="https://api.test.com",
            api_key_encrypted=encryption_service.encrypt("sk-test-key"),
            channel_type="openai"
        )
        test_db.add(provider)
        test_db.commit()
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "gpt-4"},
                {"id": "gpt-3.5-turbo"},
                {"id": "text-davinci-003"}
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            models = await provider_service.fetch_models(test_db, provider.id)
            
            assert len(models) == 3
            assert models[0].original_name == "gpt-4"
            assert models[1].original_name == "gpt-3.5-turbo"
            assert models[2].original_name == "text-davinci-003"
            
            # Verify last_fetched_at is updated
            test_db.refresh(provider)
            assert provider.last_fetched_at is not None

    @pytest.mark.asyncio
    async def test_fetch_models_empty_list(self, test_db, provider_service, encryption_service):
        """Test fetching models with empty response."""
        # Add provider
        provider = Provider(
            name="TestProvider",
            base_url="https://api.test.com",
            api_key_encrypted=encryption_service.encrypt("sk-test-key"),
            channel_type="openai"
        )
        test_db.add(provider)
        test_db.commit()
        
        # Mock empty API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            models = await provider_service.fetch_models(test_db, provider.id)
            
            assert len(models) == 0
            
            # Verify last_fetched_at is still updated
            test_db.refresh(provider)
            assert provider.last_fetched_at is not None

    @pytest.mark.asyncio
    async def test_fetch_models_provider_not_found(self, test_db, provider_service):
        """Test fetching models for non-existent provider."""
        with pytest.raises(ValueError, match="not found"):
            await provider_service.fetch_models(test_db, 999)

    @pytest.mark.asyncio
    async def test_fetch_models_updates_existing(self, test_db, provider_service, encryption_service):
        """Test fetching models updates existing models."""
        # Add provider
        provider = Provider(
            name="TestProvider",
            base_url="https://api.test.com",
            api_key_encrypted=encryption_service.encrypt("sk-test-key"),
            channel_type="openai"
        )
        test_db.add(provider)
        test_db.commit()
        
        # Add existing model
        existing_model = Model(
            provider_id=provider.id,
            original_name="gpt-4",
            is_active=False
        )
        test_db.add(existing_model)
        test_db.commit()
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "gpt-4"},
                {"id": "gpt-3.5-turbo"}
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            models = await provider_service.fetch_models(test_db, provider.id)
            
            assert len(models) == 2
            
            # Verify existing model is reactivated
            test_db.refresh(existing_model)
            assert existing_model.is_active is True
