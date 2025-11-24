"""Tests for configuration generator service."""

import pytest
import os
import sys
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from cryptography.fernet import Fernet

from app.database.database import Base
from app.models.provider import Provider
from app.models.model import Model
from app.models.gptload_group import GPTLoadGroup
from app.services.config_generator import ConfigurationGenerator
from app.services.model_service import ModelService
from app.services.provider_service import ProviderService
from app.services.encryption_service import EncryptionService


def get_test_env() -> dict:
    """Get test environment with all required settings."""
    test_key = Fernet.generate_key().decode()
    return {
        "ENCRYPTION_KEY": test_key,
        "GPTLOAD_AUTH_KEY": "test-auth-key",
        "GPTLOAD_URL": "http://localhost:3001",
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
def provider_service(encryption_service):
    """Create provider service for tests."""
    return ProviderService(encryption_service)


@pytest.fixture
def config_generator(model_service, provider_service):
    """Create configuration generator for tests."""
    return ConfigurationGenerator(model_service, provider_service)


def test_generate_uniapi_yaml_basic(config_generator, db_session):
    """Test basic uni-api YAML generation."""
    # Create some GPT-Load groups
    groups = [
        GPTLoadGroup(
            gptload_group_id=1,
            name="test-aggregate",
            group_type="aggregate",
            provider_id=None,
            normalized_model="gpt-4"
        ),
        GPTLoadGroup(
            gptload_group_id=2,
            name="test-standard",
            group_type="standard",
            provider_id=1,
            normalized_model=None
        )
    ]
    for group in groups:
        db_session.add(group)
    db_session.commit()
    
    # Generate YAML
    yaml_content = config_generator.generate_uniapi_yaml(
        db_session,
        gptload_base_url="http://localhost:3001",
        gptload_auth_key="test-key"
    )
    
    # Verify YAML contains expected content
    assert "providers:" in yaml_content
    assert "test-aggregate" in yaml_content
    assert "test-standard" in yaml_content
    assert "http://localhost:3001/proxy/test-aggregate" in yaml_content
    assert "http://localhost:3001/proxy/test-standard" in yaml_content
    assert "api_keys:" in yaml_content
    assert "preferences:" in yaml_content


def test_generate_uniapi_yaml_filters_duplicate_standards(config_generator, db_session):
    """Test that standard groups with models in aggregates are filtered out."""
    # Create aggregate group for gpt-4
    aggregate = GPTLoadGroup(
        gptload_group_id=1,
        name="gpt-4-aggregate",
        group_type="aggregate",
        provider_id=None,
        normalized_model="gpt-4"
    )
    db_session.add(aggregate)
    
    # Create standard group with gpt-4 (should be filtered)
    standard_duplicate = GPTLoadGroup(
        gptload_group_id=2,
        name="provider-0-gpt-4",
        group_type="standard",
        provider_id=1,
        normalized_model="gpt-4"
    )
    db_session.add(standard_duplicate)
    
    # Create standard group with non-duplicate models (should be included)
    standard_unique = GPTLoadGroup(
        gptload_group_id=3,
        name="provider-no-aggregate_models",
        group_type="standard",
        provider_id=1,
        normalized_model=None
    )
    db_session.add(standard_unique)
    
    db_session.commit()
    
    # Generate YAML
    yaml_content = config_generator.generate_uniapi_yaml(
        db_session,
        gptload_base_url="http://localhost:3001",
        gptload_auth_key="test-key"
    )
    
    # Verify aggregate is included
    assert "gpt-4-aggregate" in yaml_content
    
    # Verify non-duplicate standard is included
    assert "provider-no-aggregate_models" in yaml_content
    
    # Verify duplicate standard is NOT included
    assert "provider-0-gpt-4" not in yaml_content


def test_validate_uniapi_config_valid(config_generator):
    """Test validation of valid uni-api configuration."""
    valid_config = {
        "providers": [
            {
                "provider": "test-provider",
                "base_url": "http://localhost:3001/proxy/test",
                "api": "test-key",
                "model": []
            }
        ],
        "api_keys": [],
        "preferences": {}
    }
    
    # Should not raise exception
    config_generator._validate_uniapi_config(valid_config)


def test_validate_uniapi_config_missing_providers(config_generator):
    """Test validation fails when providers key is missing."""
    invalid_config = {
        "api_keys": [],
        "preferences": {}
    }
    
    with pytest.raises(ValueError, match="missing 'providers' key"):
        config_generator._validate_uniapi_config(invalid_config)


def test_validate_uniapi_config_invalid_provider(config_generator):
    """Test validation fails for invalid provider entry."""
    invalid_config = {
        "providers": [
            {
                "provider": "test-provider",
                # Missing base_url, api, model
            }
        ]
    }
    
    with pytest.raises(ValueError, match="missing required key"):
        config_generator._validate_uniapi_config(invalid_config)


def test_validate_uniapi_config_invalid_base_url(config_generator):
    """Test validation fails for invalid base URL."""
    invalid_config = {
        "providers": [
            {
                "provider": "test-provider",
                "base_url": "invalid-url",
                "api": "test-key",
                "model": []
            }
        ]
    }
    
    with pytest.raises(ValueError, match="invalid base_url"):
        config_generator._validate_uniapi_config(invalid_config)


def test_get_gptload_groups(config_generator, db_session):
    """Test retrieving GPT-Load groups from database."""
    # Create test groups
    groups = [
        GPTLoadGroup(
            gptload_group_id=1,
            name="test-standard",
            group_type="standard",
            provider_id=1
        ),
        GPTLoadGroup(
            gptload_group_id=2,
            name="test-aggregate",
            group_type="aggregate",
            provider_id=None
        )
    ]
    for group in groups:
        db_session.add(group)
    db_session.commit()
    
    # Get all groups
    all_groups = config_generator.get_gptload_groups(db_session)
    assert len(all_groups) == 2
    
    # Get only standard groups
    standard_groups = config_generator.get_gptload_groups(db_session, group_type="standard")
    assert len(standard_groups) == 1
    assert standard_groups[0].group_type == "standard"
    
    # Get only aggregate groups
    aggregate_groups = config_generator.get_gptload_groups(db_session, group_type="aggregate")
    assert len(aggregate_groups) == 1
    assert aggregate_groups[0].group_type == "aggregate"


def test_get_gptload_group_by_id(config_generator, db_session):
    """Test retrieving a specific GPT-Load group by ID."""
    group = GPTLoadGroup(
        gptload_group_id=123,
        name="test-group",
        group_type="standard",
        provider_id=1
    )
    db_session.add(group)
    db_session.commit()
    
    # Get by GPT-Load ID
    retrieved = config_generator.get_gptload_group_by_id(db_session, 123)
    assert retrieved is not None
    assert retrieved.name == "test-group"
    
    # Try non-existent ID
    not_found = config_generator.get_gptload_group_by_id(db_session, 999)
    assert not_found is None


def test_delete_gptload_group(config_generator, db_session):
    """Test deleting a GPT-Load group from database."""
    group = GPTLoadGroup(
        gptload_group_id=123,
        name="test-group",
        group_type="standard",
        provider_id=1
    )
    db_session.add(group)
    db_session.commit()
    
    # Delete the group
    result = config_generator.delete_gptload_group(db_session, 123)
    assert result is True
    
    # Verify it's deleted
    retrieved = config_generator.get_gptload_group_by_id(db_session, 123)
    assert retrieved is None
    
    # Try deleting non-existent group
    result = config_generator.delete_gptload_group(db_session, 999)
    assert result is False


def test_export_uniapi_yaml_to_file(config_generator, db_session, tmp_path):
    """Test exporting uni-api YAML to a file."""
    # Create a test group
    group = GPTLoadGroup(
        gptload_group_id=1,
        name="test-group",
        group_type="standard",
        provider_id=1
    )
    db_session.add(group)
    db_session.commit()
    
    # Export to temporary file
    file_path = tmp_path / "api.yaml"
    result_path = config_generator.export_uniapi_yaml_to_file(
        db_session,
        str(file_path),
        gptload_base_url="http://localhost:3001",
        gptload_auth_key="test-key"
    )
    
    # Verify file was created
    assert os.path.exists(result_path)
    assert result_path == str(file_path)
    
    # Verify file content
    with open(file_path, 'r') as f:
        content = f.read()
        assert "providers:" in content
        assert "test-group" in content
