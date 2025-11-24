"""Test database models and schema."""

import os
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

# Set required environment variables before importing app modules
os.environ.setdefault("GPTLOAD_AUTH_KEY", "test-auth-key")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key")

from app.database.database import Base
from app.models import Provider, Model, GPTLoadGroup, SyncRecord


@pytest.fixture
def db_session():
    """Create a test database session."""
    # Use in-memory SQLite for testing
    engine = create_engine("sqlite:///:memory:")
    
    # Enable foreign key constraints for SQLite
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    session.close()


class TestProviderModel:
    """Test Provider model."""
    
    def test_create_provider(self, db_session):
        """Test creating a provider."""
        provider = Provider(
            name="TestProvider",
            base_url="https://api.test.com",
            api_key_encrypted="encrypted_key_123",
            channel_type="openai"
        )
        db_session.add(provider)
        db_session.commit()
        
        assert provider.id is not None
        assert provider.name == "TestProvider"
        assert provider.base_url == "https://api.test.com"
        assert provider.api_key_encrypted == "encrypted_key_123"
        assert provider.channel_type == "openai"
        assert provider.created_at is not None
        assert provider.updated_at is not None
        assert provider.last_fetched_at is None
    
    def test_provider_unique_name(self, db_session):
        """Test that provider names must be unique."""
        provider1 = Provider(
            name="TestProvider",
            base_url="https://api.test1.com",
            api_key_encrypted="key1",
            channel_type="openai"
        )
        provider2 = Provider(
            name="TestProvider",
            base_url="https://api.test2.com",
            api_key_encrypted="key2",
            channel_type="openai"
        )
        
        db_session.add(provider1)
        db_session.commit()
        
        db_session.add(provider2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestModelModel:
    """Test Model model."""
    
    def test_create_model(self, db_session):
        """Test creating a model."""
        provider = Provider(
            name="TestProvider",
            base_url="https://api.test.com",
            api_key_encrypted="encrypted_key",
            channel_type="openai"
        )
        db_session.add(provider)
        db_session.commit()
        
        model = Model(
            provider_id=provider.id,
            original_name="gpt-4o",
            normalized_name="gpt-4o",
            is_active=True
        )
        db_session.add(model)
        db_session.commit()
        
        assert model.id is not None
        assert model.provider_id == provider.id
        assert model.original_name == "gpt-4o"
        assert model.normalized_name == "gpt-4o"
        assert model.is_active is True
        assert model.created_at is not None
    
    def test_model_unique_per_provider(self, db_session):
        """Test that original_name must be unique per provider."""
        provider = Provider(
            name="TestProvider",
            base_url="https://api.test.com",
            api_key_encrypted="encrypted_key",
            channel_type="openai"
        )
        db_session.add(provider)
        db_session.commit()
        
        model1 = Model(
            provider_id=provider.id,
            original_name="gpt-4o",
            normalized_name="gpt-4o"
        )
        model2 = Model(
            provider_id=provider.id,
            original_name="gpt-4o",
            normalized_name="gpt-4o-renamed"
        )
        
        db_session.add(model1)
        db_session.commit()
        
        db_session.add(model2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_model_cascade_delete(self, db_session):
        """Test that models are deleted when provider is deleted."""
        provider = Provider(
            name="TestProvider",
            base_url="https://api.test.com",
            api_key_encrypted="encrypted_key",
            channel_type="openai"
        )
        db_session.add(provider)
        db_session.commit()
        
        model = Model(
            provider_id=provider.id,
            original_name="gpt-4o"
        )
        db_session.add(model)
        db_session.commit()
        
        model_id = model.id
        
        # Delete provider
        db_session.delete(provider)
        db_session.commit()
        
        # Model should be deleted
        deleted_model = db_session.query(Model).filter(Model.id == model_id).first()
        assert deleted_model is None


class TestGPTLoadGroupModel:
    """Test GPTLoadGroup model."""
    
    def test_create_standard_group(self, db_session):
        """Test creating a standard group."""
        provider = Provider(
            name="TestProvider",
            base_url="https://api.test.com",
            api_key_encrypted="encrypted_key",
            channel_type="openai"
        )
        db_session.add(provider)
        db_session.commit()
        
        group = GPTLoadGroup(
            gptload_group_id=1,
            name="test-provider-group",
            group_type="standard",
            provider_id=provider.id
        )
        db_session.add(group)
        db_session.commit()
        
        assert group.id is not None
        assert group.gptload_group_id == 1
        assert group.name == "test-provider-group"
        assert group.group_type == "standard"
        assert group.provider_id == provider.id
        assert group.normalized_model is None
    
    def test_create_aggregate_group(self, db_session):
        """Test creating an aggregate group."""
        group = GPTLoadGroup(
            gptload_group_id=2,
            name="gpt-4o-aggregate",
            group_type="aggregate",
            normalized_model="gpt-4o"
        )
        db_session.add(group)
        db_session.commit()
        
        assert group.id is not None
        assert group.group_type == "aggregate"
        assert group.normalized_model == "gpt-4o"
        assert group.provider_id is None
    
    def test_gptload_group_id_unique(self, db_session):
        """Test that gptload_group_id must be unique."""
        group1 = GPTLoadGroup(
            gptload_group_id=1,
            name="group1",
            group_type="standard"
        )
        group2 = GPTLoadGroup(
            gptload_group_id=1,
            name="group2",
            group_type="standard"
        )
        
        db_session.add(group1)
        db_session.commit()
        
        db_session.add(group2)
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_group_name_unique(self, db_session):
        """Test that group name must be unique."""
        group1 = GPTLoadGroup(
            gptload_group_id=1,
            name="test-group",
            group_type="standard"
        )
        group2 = GPTLoadGroup(
            gptload_group_id=2,
            name="test-group",
            group_type="aggregate"
        )
        
        db_session.add(group1)
        db_session.commit()
        
        db_session.add(group2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestSyncRecordModel:
    """Test SyncRecord model."""
    
    def test_create_sync_record(self, db_session):
        """Test creating a sync record."""
        sync = SyncRecord(
            status="pending"
        )
        db_session.add(sync)
        db_session.commit()
        
        assert sync.id is not None
        assert sync.status == "pending"
        assert sync.started_at is not None
        assert sync.completed_at is None
        assert sync.error_message is None
        assert sync.changes_summary is None
    
    def test_sync_record_complete(self, db_session):
        """Test completing a sync record."""
        sync = SyncRecord(
            status="in_progress"
        )
        db_session.add(sync)
        db_session.commit()
        
        # Update to success
        sync.status = "success"
        sync.completed_at = datetime.utcnow()
        sync.changes_summary = "Created 5 groups"
        db_session.commit()
        
        assert sync.status == "success"
        assert sync.completed_at is not None
        assert sync.changes_summary == "Created 5 groups"
    
    def test_sync_record_failed(self, db_session):
        """Test failed sync record."""
        sync = SyncRecord(
            status="failed",
            error_message="Connection timeout"
        )
        db_session.add(sync)
        db_session.commit()
        
        assert sync.status == "failed"
        assert sync.error_message == "Connection timeout"


class TestModelRelationships:
    """Test model relationships."""
    
    def test_provider_models_relationship(self, db_session):
        """Test that provider has access to its models."""
        provider = Provider(
            name="TestProvider",
            base_url="https://api.test.com",
            api_key_encrypted="encrypted_key",
            channel_type="openai"
        )
        db_session.add(provider)
        db_session.commit()
        
        model1 = Model(provider_id=provider.id, original_name="model1")
        model2 = Model(provider_id=provider.id, original_name="model2")
        db_session.add_all([model1, model2])
        db_session.commit()
        
        # Access models through relationship
        assert len(provider.models) == 2
        assert model1 in provider.models
        assert model2 in provider.models
