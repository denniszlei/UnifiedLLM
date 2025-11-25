"""Tests for normalized names API endpoint."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.database import Base
from app.models.provider import Provider
from app.models.model import Model
from app.services.model_service import ModelService


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
def sample_providers(db_session):
    """Create sample providers."""
    provider1 = Provider(
        name="Provider A",
        base_url="https://api.provider-a.com/v1/chat/completions",
        api_key_encrypted="encrypted_key_1",
        channel_type="openai"
    )
    provider2 = Provider(
        name="Provider B",
        base_url="https://api.provider-b.com/v1/chat/completions",
        api_key_encrypted="encrypted_key_2",
        channel_type="openai"
    )
    db_session.add(provider1)
    db_session.add(provider2)
    db_session.commit()
    return [provider1, provider2]


@pytest.fixture
def sample_models_with_normalization(db_session, sample_providers):
    """Create sample models with normalized names."""
    models = [
        # Provider A models
        Model(
            provider_id=sample_providers[0].id,
            original_name="gpt-4o",
            normalized_name="gpt-4o",
            is_active=True
        ),
        Model(
            provider_id=sample_providers[0].id,
            original_name="gpt-4o-mini",
            normalized_name="gpt-4o-mini",
            is_active=True
        ),
        Model(
            provider_id=sample_providers[0].id,
            original_name="deepseek-v3.1",
            normalized_name="deepseek-v3",
            is_active=True
        ),
        # Provider B models
        Model(
            provider_id=sample_providers[1].id,
            original_name="gpt-4o-latest",
            normalized_name="gpt-4o",
            is_active=True
        ),
        Model(
            provider_id=sample_providers[1].id,
            original_name="deepseek-v3.1-preview",
            normalized_name="deepseek-v3",
            is_active=True
        ),
    ]
    for model in models:
        db_session.add(model)
    db_session.commit()
    return models


class TestNormalizedNamesAPI:
    """Test normalized names API endpoint."""

    def test_get_normalized_names_with_counts(
        self, db_session, sample_models_with_normalization
    ):
        """Test getting normalized names with provider and model counts."""
        service = ModelService()
        
        result = service.get_normalized_names_with_counts(db_session)
        
        # Should have 3 unique normalized names
        assert len(result) == 3
        
        # Check gpt-4o (appears in 2 providers, 2 models)
        assert "gpt-4o" in result
        assert result["gpt-4o"]["provider_count"] == 2
        assert result["gpt-4o"]["model_count"] == 2
        
        # Check deepseek-v3 (appears in 2 providers, 2 models)
        assert "deepseek-v3" in result
        assert result["deepseek-v3"]["provider_count"] == 2
        assert result["deepseek-v3"]["model_count"] == 2
        
        # Check gpt-4o-mini (appears in 1 provider, 1 model)
        assert "gpt-4o-mini" in result
        assert result["gpt-4o-mini"]["provider_count"] == 1
        assert result["gpt-4o-mini"]["model_count"] == 1

    def test_normalized_names_ordering(
        self, db_session, sample_models_with_normalization
    ):
        """Test that normalized names are ordered by provider_count DESC, then name ASC."""
        service = ModelService()
        
        result = service.get_normalized_names_with_counts(db_session)
        
        # Convert to list to check ordering
        names_list = list(result.keys())
        
        # First two should be the ones with 2 providers (gpt-4o and deepseek-v3)
        # They should be alphabetically ordered
        assert names_list[0] in ["deepseek-v3", "gpt-4o"]
        assert names_list[1] in ["deepseek-v3", "gpt-4o"]
        assert names_list[0] != names_list[1]
        
        # Last one should be gpt-4o-mini (only 1 provider)
        assert names_list[2] == "gpt-4o-mini"

    def test_normalized_names_with_inactive_models(
        self, db_session, sample_models_with_normalization
    ):
        """Test that inactive models are excluded from normalized names."""
        service = ModelService()
        
        # Mark one model as inactive
        sample_models_with_normalization[0].is_active = False
        db_session.commit()
        
        result = service.get_normalized_names_with_counts(db_session)
        
        # gpt-4o should now only have 1 provider and 1 model
        assert result["gpt-4o"]["provider_count"] == 1
        assert result["gpt-4o"]["model_count"] == 1

    def test_normalized_names_empty_database(self, db_session):
        """Test getting normalized names from empty database."""
        service = ModelService()
        
        result = service.get_normalized_names_with_counts(db_session)
        
        assert result == {}
