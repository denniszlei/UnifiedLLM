"""Tests for model service."""

import pytest
import os
import sys
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from cryptography.fernet import Fernet

from app.database.database import Base
from app.models.provider import Provider
from app.models.model import Model
from app.services.model_service import ModelService, ProviderSplit


def get_test_env() -> dict:
    """Get test environment with all required settings."""
    test_key = Fernet.generate_key().decode()
    return {
        "ENCRYPTION_KEY": test_key,
        "GPTLOAD_AUTH_KEY": "test-auth-key",
        "DATABASE_URL": "sqlite:///./test.db",
    }


@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def encryption_service():
    """Create encryption service for tests."""
    with patch.dict(os.environ, get_test_env(), clear=True):
        # Clear any cached imports
        if 'app.config' in sys.modules:
            del sys.modules['app.config']
        if 'app.services.encryption_service' in sys.modules:
            del sys.modules['app.services.encryption_service']
        
        from app.services.encryption_service import EncryptionService
        return EncryptionService()


@pytest.fixture
def model_service():
    """Create model service for tests."""
    return ModelService()


@pytest.fixture
def sample_provider(db_session, encryption_service):
    """Create a sample provider for testing."""
    provider = Provider(
        name="TestProvider",
        base_url="https://api.test.com",
        api_key_encrypted=encryption_service.encrypt("test-key"),
        channel_type="openai"
    )
    db_session.add(provider)
    db_session.commit()
    db_session.refresh(provider)
    return provider


@pytest.fixture
def sample_models(db_session, sample_provider):
    """Create sample models for testing."""
    models = [
        Model(
            provider_id=sample_provider.id,
            original_name="gpt-4o",
            normalized_name=None,
            is_active=True
        ),
        Model(
            provider_id=sample_provider.id,
            original_name="gpt-4o-mini",
            normalized_name=None,
            is_active=True
        ),
        Model(
            provider_id=sample_provider.id,
            original_name="deepseek-v3.1",
            normalized_name=None,
            is_active=True
        ),
    ]
    for model in models:
        db_session.add(model)
    db_session.commit()
    for model in models:
        db_session.refresh(model)
    return models


class TestModelNormalization:
    """Tests for model normalization functionality."""

    def test_normalize_model_success(self, db_session, model_service, sample_models):
        """Test successful model normalization."""
        model = sample_models[0]
        original_name = model.original_name
        
        result = model_service.normalize_model(db_session, model.id, "gpt-4-omni")
        
        assert result.id == model.id
        assert result.normalized_name == "gpt-4-omni"
        assert result.original_name == original_name  # Original preserved
        assert result.updated_at is not None

    def test_normalize_model_not_found(self, db_session, model_service):
        """Test normalizing non-existent model."""
        with pytest.raises(ValueError, match="Model 999 not found"):
            model_service.normalize_model(db_session, 999, "test-name")

    def test_normalize_model_duplicate_within_provider(
        self, db_session, model_service, sample_models
    ):
        """Test that duplicate normalized names within provider are prevented when allow_duplicates=False."""
        # Normalize first model
        model_service.normalize_model(db_session, sample_models[0].id, "unified-model")
        
        # Try to normalize second model to same name with allow_duplicates=False - should fail
        with pytest.raises(ValueError, match="Duplicate normalized name"):
            model_service.normalize_model(
                db_session, sample_models[1].id, "unified-model", allow_duplicates=False
            )

    def test_reset_model_name(self, db_session, model_service, sample_models):
        """Test resetting model name to original."""
        model = sample_models[0]
        original_name = model.original_name
        
        # First normalize it
        model_service.normalize_model(db_session, model.id, "custom-name")
        db_session.refresh(model)
        assert model.normalized_name == "custom-name"
        
        # Then reset it
        result = model_service.reset_model_name(db_session, model.id)
        
        assert result.normalized_name is None
        assert result.original_name == original_name

    def test_reset_model_name_not_found(self, db_session, model_service):
        """Test resetting non-existent model."""
        with pytest.raises(ValueError, match="Model 999 not found"):
            model_service.reset_model_name(db_session, 999)


class TestDuplicateDetection:
    """Tests for duplicate detection functionality."""

    def test_detect_duplicates_none(self, db_session, model_service, sample_models):
        """Test duplicate detection when no duplicates exist."""
        provider_id = sample_models[0].provider_id
        
        duplicates = model_service.detect_duplicates(db_session, provider_id)
        
        assert duplicates == {}

    def test_detect_duplicates_with_normalized_names(
        self, db_session, model_service, sample_models
    ):
        """Test duplicate detection with normalized names."""
        provider_id = sample_models[0].provider_id
        
        # Normalize two models to the same name
        model_service.normalize_model(db_session, sample_models[0].id, "unified-gpt")
        model_service.normalize_model(db_session, sample_models[1].id, "unified-gpt")
        
        duplicates = model_service.detect_duplicates(db_session, provider_id)
        
        assert "unified-gpt" in duplicates
        assert len(duplicates["unified-gpt"]) == 2

    def test_detect_duplicates_ignores_inactive(
        self, db_session, model_service, sample_models
    ):
        """Test that duplicate detection ignores inactive models."""
        provider_id = sample_models[0].provider_id
        
        # Normalize two models to the same name
        model_service.normalize_model(db_session, sample_models[0].id, "unified-gpt")
        model_service.normalize_model(db_session, sample_models[1].id, "unified-gpt")
        
        # Delete one model
        model_service.delete_model(db_session, sample_models[1].id)
        
        duplicates = model_service.detect_duplicates(db_session, provider_id)
        
        # Should not be detected as duplicate anymore
        assert duplicates == {}


class TestModelDeletion:
    """Tests for model deletion functionality."""

    def test_delete_model_success(self, db_session, model_service, sample_models):
        """Test successful model deletion (soft delete)."""
        model = sample_models[0]
        
        result = model_service.delete_model(db_session, model.id)
        
        assert result is True
        db_session.refresh(model)
        assert model.is_active is False

    def test_delete_model_not_found(self, db_session, model_service):
        """Test deleting non-existent model."""
        result = model_service.delete_model(db_session, 999)
        assert result is False

    def test_bulk_delete_models_success(self, db_session, model_service, sample_models):
        """Test bulk deletion of models."""
        model_ids = [m.id for m in sample_models[:2]]
        provider_id = sample_models[0].provider_id
        
        result = model_service.bulk_delete_models(db_session, model_ids, provider_id)
        
        assert result["deleted_count"] == 2
        for model in sample_models[:2]:
            db_session.refresh(model)
            assert model.is_active is False

    def test_bulk_delete_all_models_warning(
        self, db_session, model_service, sample_models
    ):
        """Test that deleting all models from provider generates warning."""
        model_ids = [m.id for m in sample_models]
        provider_id = sample_models[0].provider_id
        
        result = model_service.bulk_delete_models(db_session, model_ids, provider_id)
        
        assert result["deleted_count"] == 3
        assert "warning" in result
        assert "all" in result["warning"].lower()

    def test_bulk_delete_atomicity(self, db_session, model_service, sample_models):
        """Test that bulk delete is atomic."""
        # Include a non-existent model ID
        model_ids = [sample_models[0].id, 999]
        provider_id = sample_models[0].provider_id
        
        # Should only delete the existing model
        result = model_service.bulk_delete_models(db_session, model_ids, provider_id)
        
        # Only one model should be deleted (the existing one)
        assert result["deleted_count"] == 1

    def test_bulk_delete_wrong_provider(self, db_session, model_service, sample_models):
        """Test that bulk delete validates provider ownership."""
        model_ids = [sample_models[0].id]
        wrong_provider_id = 999
        
        with pytest.raises(ValueError, match="does not belong to provider"):
            model_service.bulk_delete_models(db_session, model_ids, wrong_provider_id)


class TestProviderSplitting:
    """Tests for provider splitting algorithm."""

    def test_split_provider_no_duplicates(
        self, db_session, model_service, sample_models
    ):
        """Test splitting provider with no duplicate normalized names."""
        provider_id = sample_models[0].provider_id
        
        splits = model_service.split_provider_by_duplicates(db_session, provider_id)
        
        # Should have one split for non-duplicate models
        assert len(splits) == 1
        assert splits[0].is_duplicate_group is False
        assert "no-aggregate_models" in splits[0].group_name
        assert len(splits[0].models) == 3

    def test_split_provider_with_duplicates(
        self, db_session, model_service, sample_models
    ):
        """Test splitting provider with duplicate normalized names."""
        provider_id = sample_models[0].provider_id
        
        # Create duplicates by normalizing to same name
        model_service.normalize_model(db_session, sample_models[0].id, "gpt-unified")
        model_service.normalize_model(db_session, sample_models[1].id, "gpt-unified")
        
        splits = model_service.split_provider_by_duplicates(db_session, provider_id)
        
        # Should have 2 splits: 2 for duplicates + 1 for non-duplicate
        assert len(splits) == 3
        
        # Check duplicate splits
        duplicate_splits = [s for s in splits if s.is_duplicate_group]
        assert len(duplicate_splits) == 2
        for split in duplicate_splits:
            assert split.normalized_name == "gpt-unified"
            assert len(split.models) == 1
        
        # Check non-duplicate split
        non_dup_splits = [s for s in splits if not s.is_duplicate_group]
        assert len(non_dup_splits) == 1
        assert len(non_dup_splits[0].models) == 1

    def test_split_provider_sanitizes_group_names(
        self, db_session, model_service, sample_models
    ):
        """Test that group names are sanitized (dots to dashes)."""
        provider_id = sample_models[0].provider_id
        
        # Normalize with dots in name
        model_service.normalize_model(db_session, sample_models[0].id, "model.v3.1")
        model_service.normalize_model(db_session, sample_models[1].id, "model.v3.1")
        
        splits = model_service.split_provider_by_duplicates(db_session, provider_id)
        
        # Check that dots are converted to dashes in group names
        duplicate_splits = [s for s in splits if s.is_duplicate_group]
        for split in duplicate_splits:
            assert "." not in split.group_name
            assert "model-v3-1" in split.group_name

    def test_provider_split_model_redirect_rules(
        self, db_session, model_service, sample_models
    ):
        """Test that ProviderSplit generates correct model redirect rules."""
        provider_id = sample_models[0].provider_id
        
        # Normalize a model
        model_service.normalize_model(db_session, sample_models[0].id, "gpt-4-omni")
        
        splits = model_service.split_provider_by_duplicates(db_session, provider_id)
        
        # Find the split containing the normalized model
        for split in splits:
            rules = split.get_model_redirect_rules()
            if "gpt-4-omni" in rules:
                # Should map normalized name to original name
                assert rules["gpt-4-omni"] == "gpt-4o"


class TestCrossProviderDuplicates:
    """Tests for cross-provider duplicate detection."""

    def test_get_cross_provider_duplicates(
        self, db_session, model_service, encryption_service
    ):
        """Test detecting models that appear across multiple providers."""
        # Create two providers
        provider1 = Provider(
            name="Provider1",
            base_url="https://api.provider1.com",
            api_key_encrypted=encryption_service.encrypt("key1"),
            channel_type="openai"
        )
        provider2 = Provider(
            name="Provider2",
            base_url="https://api.provider2.com",
            api_key_encrypted=encryption_service.encrypt("key2"),
            channel_type="openai"
        )
        db_session.add(provider1)
        db_session.add(provider2)
        db_session.commit()
        
        # Create models with same normalized name in both providers
        model1 = Model(
            provider_id=provider1.id,
            original_name="gpt-4o",
            normalized_name="gpt-4-omni",
            is_active=True
        )
        model2 = Model(
            provider_id=provider2.id,
            original_name="gpt4o",
            normalized_name="gpt-4-omni",
            is_active=True
        )
        model3 = Model(
            provider_id=provider1.id,
            original_name="unique-model",
            normalized_name=None,
            is_active=True
        )
        db_session.add_all([model1, model2, model3])
        db_session.commit()
        
        # Get cross-provider duplicates
        duplicates = model_service.get_cross_provider_duplicates(db_session)
        
        # Should find gpt-4-omni appearing in both providers
        assert "gpt-4-omni" in duplicates
        assert len(duplicates["gpt-4-omni"]) == 2
        
        # unique-model should not be in duplicates
        assert "unique-model" not in duplicates



class TestBatchNormalize:
    """Test batch normalize functionality."""
    
    def test_batch_normalize_models_success(self, db_session, sample_provider):
        """Test batch normalizing multiple models."""
        service = ModelService()
        
        # Create test models
        model1 = Model(
            provider_id=sample_provider.id,
            original_name="gpt-4-turbo",
            is_active=True
        )
        model2 = Model(
            provider_id=sample_provider.id,
            original_name="gpt-4-preview",
            is_active=True
        )
        model3 = Model(
            provider_id=sample_provider.id,
            original_name="gpt-3.5-turbo",
            is_active=True
        )
        
        db_session.add_all([model1, model2, model3])
        db_session.commit()
        
        # Batch normalize
        updates = [
            {"model_id": model1.id, "normalized_name": "gpt-4"},
            {"model_id": model2.id, "normalized_name": "gpt-4"},
            {"model_id": model3.id, "normalized_name": "gpt-3.5"}
        ]
        
        result = service.batch_normalize_models(db_session, updates)
        
        assert result["updated_count"] == 3
        
        # Verify updates
        db_session.refresh(model1)
        db_session.refresh(model2)
        db_session.refresh(model3)
        
        assert model1.normalized_name == "gpt-4"
        assert model2.normalized_name == "gpt-4"
        assert model3.normalized_name == "gpt-3.5"
    
    def test_batch_normalize_empty_list(self, db_session):
        """Test batch normalize with empty list."""
        service = ModelService()
        
        result = service.batch_normalize_models(db_session, [])
        
        assert result["updated_count"] == 0
    
    def test_batch_normalize_model_not_found(self, db_session):
        """Test batch normalize with non-existent model."""
        service = ModelService()
        
        updates = [
            {"model_id": 99999, "normalized_name": "test"}
        ]
        
        with pytest.raises(ValueError, match="Model 99999 not found"):
            service.batch_normalize_models(db_session, updates)
    
    def test_batch_normalize_missing_fields(self, db_session):
        """Test batch normalize with missing required fields."""
        service = ModelService()
        
        updates = [
            {"model_id": 1}  # Missing normalized_name
        ]
        
        with pytest.raises(ValueError, match="must have 'model_id' and 'normalized_name'"):
            service.batch_normalize_models(db_session, updates)
    
    def test_batch_normalize_atomicity(self, db_session, sample_provider):
        """Test that batch normalize is atomic - all or nothing."""
        service = ModelService()
        
        # Create test models
        model1 = Model(
            provider_id=sample_provider.id,
            original_name="model-1",
            is_active=True
        )
        model2 = Model(
            provider_id=sample_provider.id,
            original_name="model-2",
            is_active=True
        )
        
        db_session.add_all([model1, model2])
        db_session.commit()
        
        # Try to batch normalize with one invalid model
        updates = [
            {"model_id": model1.id, "normalized_name": "normalized-1"},
            {"model_id": 99999, "normalized_name": "normalized-2"}  # Invalid
        ]
        
        with pytest.raises(ValueError):
            service.batch_normalize_models(db_session, updates)
        
        # Verify no changes were made (atomicity)
        db_session.refresh(model1)
        assert model1.normalized_name is None
