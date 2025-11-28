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
            name="test-provider-no-aggregate-models",
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
    # Standard groups must end with '-no-aggregate-models' to be included
    assert "test-provider-no-aggregate-models" in yaml_content
    assert "http://localhost:3001/proxy/test-aggregate" in yaml_content
    assert "http://localhost:3001/proxy/test-provider-no-aggregate-models" in yaml_content
    assert "api_keys:" in yaml_content
    assert "preferences:" in yaml_content
    # Verify the gptload all-models API key is added
    assert "sk-all-models-from-gptload" in yaml_content
    assert "test-aggregate/*" in yaml_content
    assert "test-provider-no-aggregate-models/*" in yaml_content


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
    # Must end with '-no-aggregate-models' to be included in uni-api config
    standard_unique = GPTLoadGroup(
        gptload_group_id=3,
        name="provider-no-aggregate-models",
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
    
    # Verify non-duplicate standard is included (must end with '-no-aggregate-models')
    assert "provider-no-aggregate-models" in yaml_content
    
    # Verify duplicate standard is NOT included (doesn't end with '-no-aggregate-models')
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


def test_build_base_url_openai(config_generator, db_session, encryption_service):
    """Test build_base_url for OpenAI channel type."""
    # Create provider with OpenAI channel type
    provider = Provider(
        name="test-openai",
        base_url="https://api.openai.com",
        api_key_encrypted=encryption_service.encrypt("test-key"),
        channel_type="openai"
    )
    db_session.add(provider)
    db_session.commit()
    
    # Create standard group
    group = GPTLoadGroup(
        gptload_group_id=1,
        name="test-openai-group",
        group_type="standard",
        provider_id=provider.id
    )
    db_session.add(group)
    db_session.commit()
    
    # Build base URL
    base_url = config_generator.build_base_url(
        db_session,
        group,
        "http://localhost:3001"
    )
    
    # Verify OpenAI format
    assert base_url == "http://localhost:3001/proxy/test-openai-group/v1/chat/completions"


def test_build_base_url_anthropic(config_generator, db_session, encryption_service):
    """Test build_base_url for Anthropic channel type."""
    # Create provider with Anthropic channel type
    provider = Provider(
        name="test-anthropic",
        base_url="https://api.anthropic.com",
        api_key_encrypted=encryption_service.encrypt("test-key"),
        channel_type="anthropic"
    )
    db_session.add(provider)
    db_session.commit()
    
    # Create standard group
    group = GPTLoadGroup(
        gptload_group_id=1,
        name="test-anthropic-group",
        group_type="standard",
        provider_id=provider.id
    )
    db_session.add(group)
    db_session.commit()
    
    # Build base URL
    base_url = config_generator.build_base_url(
        db_session,
        group,
        "http://localhost:3001"
    )
    
    # Verify Anthropic format
    assert base_url == "http://localhost:3001/proxy/test-anthropic-group/v1/messages"


def test_build_base_url_gemini(config_generator, db_session, encryption_service):
    """Test build_base_url for Gemini channel type."""
    # Create provider with Gemini channel type
    provider = Provider(
        name="test-gemini",
        base_url="https://generativelanguage.googleapis.com",
        api_key_encrypted=encryption_service.encrypt("test-key"),
        channel_type="gemini"
    )
    db_session.add(provider)
    db_session.commit()
    
    # Create standard group
    group = GPTLoadGroup(
        gptload_group_id=1,
        name="test-gemini-group",
        group_type="standard",
        provider_id=provider.id
    )
    db_session.add(group)
    db_session.commit()
    
    # Build base URL
    base_url = config_generator.build_base_url(
        db_session,
        group,
        "http://localhost:3001"
    )
    
    # Verify Gemini format
    assert base_url == "http://localhost:3001/proxy/test-gemini-group/v1beta"


def test_build_base_url_unknown_defaults_to_openai(config_generator, db_session, encryption_service):
    """Test build_base_url defaults to OpenAI format for unknown channel types."""
    # Create provider with unknown channel type
    provider = Provider(
        name="test-unknown",
        base_url="https://api.unknown.com",
        api_key_encrypted=encryption_service.encrypt("test-key"),
        channel_type="unknown"
    )
    db_session.add(provider)
    db_session.commit()
    
    # Create standard group
    group = GPTLoadGroup(
        gptload_group_id=1,
        name="test-unknown-group",
        group_type="standard",
        provider_id=provider.id
    )
    db_session.add(group)
    db_session.commit()
    
    # Build base URL
    base_url = config_generator.build_base_url(
        db_session,
        group,
        "http://localhost:3001"
    )
    
    # Verify defaults to OpenAI format
    assert base_url == "http://localhost:3001/proxy/test-unknown-group/v1/chat/completions"


def test_build_base_url_aggregate_defaults_to_openai(config_generator, db_session):
    """Test build_base_url defaults to OpenAI format for aggregate groups."""
    # Create aggregate group (no provider_id)
    group = GPTLoadGroup(
        gptload_group_id=1,
        name="test-aggregate",
        group_type="aggregate",
        provider_id=None,
        normalized_model="gpt-4"
    )
    db_session.add(group)
    db_session.commit()
    
    # Build base URL
    base_url = config_generator.build_base_url(
        db_session,
        group,
        "http://localhost:3001"
    )
    
    # Verify defaults to OpenAI format
    assert base_url == "http://localhost:3001/proxy/test-aggregate/v1/chat/completions"


def test_generate_uniapi_yaml_with_multiple_channel_types(config_generator, db_session, encryption_service):
    """Test uni-api YAML generation with multiple channel types."""
    # Create providers with different channel types
    providers = [
        Provider(
            name="openai-provider",
            base_url="https://api.openai.com",
            api_key_encrypted=encryption_service.encrypt("key1"),
            channel_type="openai"
        ),
        Provider(
            name="anthropic-provider",
            base_url="https://api.anthropic.com",
            api_key_encrypted=encryption_service.encrypt("key2"),
            channel_type="anthropic"
        ),
        Provider(
            name="gemini-provider",
            base_url="https://generativelanguage.googleapis.com",
            api_key_encrypted=encryption_service.encrypt("key3"),
            channel_type="gemini"
        )
    ]
    for provider in providers:
        db_session.add(provider)
    db_session.commit()
    
    # Create groups for each provider (must end with '-no-aggregate-models' to be included)
    groups = [
        GPTLoadGroup(
            gptload_group_id=1,
            name="openai-no-aggregate-models",
            group_type="standard",
            provider_id=providers[0].id
        ),
        GPTLoadGroup(
            gptload_group_id=2,
            name="anthropic-no-aggregate-models",
            group_type="standard",
            provider_id=providers[1].id
        ),
        GPTLoadGroup(
            gptload_group_id=3,
            name="gemini-no-aggregate-models",
            group_type="standard",
            provider_id=providers[2].id
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
    
    # Verify each channel type has correct path
    assert "http://localhost:3001/proxy/openai-no-aggregate-models/v1/chat/completions" in yaml_content
    assert "http://localhost:3001/proxy/anthropic-no-aggregate-models/v1/messages" in yaml_content
    assert "http://localhost:3001/proxy/gemini-no-aggregate-models/v1beta" in yaml_content


def test_read_existing_yaml_file_exists(config_generator, tmp_path):
    """Test reading existing YAML file when it exists."""
    # Create a test YAML file
    yaml_file = tmp_path / "api.yaml"
    yaml_content = """
providers:
  - provider: existing-provider
    base_url: http://example.com
    api: existing-key
    model: []
api_keys:
  - api: custom-key
    role: admin
    model: ["all"]
preferences:
  rate_limit: "1000/min"
"""
    yaml_file.write_text(yaml_content)
    
    # Read the file
    result = config_generator._read_existing_yaml(str(yaml_file))
    
    # Verify content
    assert result is not None
    assert "providers" in result
    assert len(result["providers"]) == 1
    assert result["providers"][0]["provider"] == "existing-provider"
    assert "api_keys" in result
    assert "preferences" in result


def test_read_existing_yaml_file_not_exists(config_generator):
    """Test reading existing YAML file when it doesn't exist."""
    result = config_generator._read_existing_yaml("/nonexistent/path/api.yaml")
    assert result is None


def test_read_existing_yaml_malformed(config_generator, tmp_path):
    """Test reading malformed YAML file."""
    # Create a malformed YAML file
    yaml_file = tmp_path / "api.yaml"
    yaml_file.write_text("invalid: yaml: content: [")
    
    # Should return None and log error
    result = config_generator._read_existing_yaml(str(yaml_file))
    assert result is None


def test_read_existing_yaml_empty_file(config_generator, tmp_path):
    """Test reading empty YAML file."""
    # Create an empty YAML file
    yaml_file = tmp_path / "api.yaml"
    yaml_file.write_text("")
    
    # Should return None
    result = config_generator._read_existing_yaml(str(yaml_file))
    assert result is None


def test_remove_dummy_providers(config_generator):
    """Test removing dummy provider entries."""
    config = {
        "providers": [
            {"provider": "provider_name", "base_url": "http://dummy.com"},
            {"provider": "real-provider", "base_url": "http://real.com"},
            {"provider": "provider_name", "base_url": "http://dummy2.com"},
            {"provider": "another-real", "base_url": "http://another.com"}
        ]
    }
    
    result = config_generator._remove_dummy_providers(config)
    
    # Verify dummy providers are removed
    assert len(result["providers"]) == 2
    assert all(p["provider"] != "provider_name" for p in result["providers"])
    assert result["providers"][0]["provider"] == "real-provider"
    assert result["providers"][1]["provider"] == "another-real"


def test_remove_dummy_providers_no_providers(config_generator):
    """Test removing dummy providers when no providers key exists."""
    config = {"api_keys": []}
    result = config_generator._remove_dummy_providers(config)
    assert result == config


def test_remove_dummy_providers_empty_list(config_generator):
    """Test removing dummy providers from empty list."""
    config = {"providers": []}
    result = config_generator._remove_dummy_providers(config)
    assert result["providers"] == []


def test_extract_api_keys_section_exists(config_generator):
    """Test extracting api_keys section when it exists."""
    config = {
        "api_keys": [
            {"api": "custom-key", "role": "admin", "model": ["all"]}
        ]
    }
    
    result = config_generator._extract_api_keys_section(config)
    
    assert len(result) == 1
    assert result[0]["api"] == "custom-key"
    assert result[0]["role"] == "admin"


def test_extract_api_keys_section_not_exists(config_generator):
    """Test extracting api_keys section when it doesn't exist."""
    config = {"providers": []}
    
    result = config_generator._extract_api_keys_section(config)
    
    # Should return default
    assert len(result) == 1
    assert result[0]["api"] == "sk-user-key"
    assert result[0]["role"] == "user"


def test_extract_api_keys_section_no_config(config_generator):
    """Test extracting api_keys section when config is None."""
    result = config_generator._extract_api_keys_section(None)
    
    # Should return default
    assert len(result) == 1
    assert result[0]["api"] == "sk-user-key"


def test_extract_preferences_section_exists(config_generator):
    """Test extracting preferences section when it exists."""
    config = {
        "preferences": {
            "rate_limit": "1000/min",
            "custom_setting": "value"
        }
    }
    
    result = config_generator._extract_preferences_section(config)
    
    assert result["rate_limit"] == "1000/min"
    assert result["custom_setting"] == "value"


def test_extract_preferences_section_not_exists(config_generator):
    """Test extracting preferences section when it doesn't exist."""
    config = {"providers": []}
    
    result = config_generator._extract_preferences_section(config)
    
    # Should return default
    assert result["rate_limit"] == "999999/min"


def test_extract_preferences_section_no_config(config_generator):
    """Test extracting preferences section when config is None."""
    result = config_generator._extract_preferences_section(None)
    
    # Should return default
    assert result["rate_limit"] == "999999/min"


def test_merge_configuration(config_generator):
    """Test merging configuration components."""
    providers = [
        {"provider": "test-provider", "base_url": "http://test.com", "api": "key", "model": []}
    ]
    api_keys = [
        {"api": "custom-key", "role": "admin"}
    ]
    preferences = {
        "rate_limit": "1000/min"
    }
    
    result = config_generator._merge_configuration(
        providers,
        api_keys,
        preferences
    )
    
    assert "providers" in result
    assert "api_keys" in result
    assert "preferences" in result
    assert result["providers"] == providers
    # Original api_keys should be preserved
    assert any(k.get("api") == "custom-key" for k in result["api_keys"])
    # New gptload key should be added
    gptload_key = next((k for k in result["api_keys"] if k.get("api") == "sk-all-models-from-gptload"), None)
    assert gptload_key is not None
    assert "test-provider/*" in gptload_key["model"]
    assert result["preferences"] == preferences


def test_build_gptload_all_models_api_key(config_generator):
    """Test building the gptload all-models API key."""
    providers = [
        {"provider": "aggregate-deepseek-v3-2", "base_url": "http://test.com", "api": "key", "model": []},
        {"provider": "hyb-0-no-aggregate-models", "base_url": "http://test2.com", "api": "key", "model": []},
    ]
    
    result = config_generator._build_gptload_all_models_api_key(providers)
    
    assert result["api"] == "sk-all-models-from-gptload"
    assert "aggregate-deepseek-v3-2/*" in result["model"]
    assert "hyb-0-no-aggregate-models/*" in result["model"]
    assert len(result["model"]) == 2


def test_build_gptload_all_models_api_key_empty_providers(config_generator):
    """Test building gptload API key with empty providers list."""
    providers = []
    
    result = config_generator._build_gptload_all_models_api_key(providers)
    
    assert result["api"] == "sk-all-models-from-gptload"
    assert result["model"] == []


def test_update_api_keys_with_gptload_key_add_new(config_generator):
    """Test adding gptload key when it doesn't exist."""
    api_keys_section = [
        {"api": "existing-key", "role": "admin"}
    ]
    gptload_key = {
        "api": "sk-all-models-from-gptload",
        "model": ["provider1/*", "provider2/*"]
    }
    
    result = config_generator._update_api_keys_with_gptload_key(api_keys_section, gptload_key)
    
    assert len(result) == 2
    assert any(k.get("api") == "existing-key" for k in result)
    assert any(k.get("api") == "sk-all-models-from-gptload" for k in result)


def test_update_api_keys_with_gptload_key_update_existing(config_generator):
    """Test updating gptload key when it already exists."""
    api_keys_section = [
        {"api": "existing-key", "role": "admin"},
        {"api": "sk-all-models-from-gptload", "model": ["old-provider/*"]}
    ]
    gptload_key = {
        "api": "sk-all-models-from-gptload",
        "model": ["new-provider1/*", "new-provider2/*"]
    }
    
    result = config_generator._update_api_keys_with_gptload_key(api_keys_section, gptload_key)
    
    # Should still have 2 keys (not 3)
    assert len(result) == 2
    # The gptload key should be updated
    gptload_entry = next(k for k in result if k.get("api") == "sk-all-models-from-gptload")
    assert "new-provider1/*" in gptload_entry["model"]
    assert "new-provider2/*" in gptload_entry["model"]
    assert "old-provider/*" not in gptload_entry["model"]


def test_generate_uniapi_yaml_with_existing_file(config_generator, db_session, tmp_path):
    """Test generating uni-api YAML with existing file merging."""
    # Create existing YAML file with custom settings
    yaml_file = tmp_path / "api.yaml"
    existing_content = """
providers:
  - provider: provider_name
    base_url: http://dummy.com
    api: dummy-key
    model: []
  - provider: existing-provider
    base_url: http://existing.com
    api: existing-key
    model: []
api_keys:
  - api: custom-admin-key
    role: admin
    model: ["all"]
preferences:
  rate_limit: "5000/min"
  custom_setting: "preserved"
"""
    yaml_file.write_text(existing_content)
    
    # Create a test group
    group = GPTLoadGroup(
        gptload_group_id=1,
        name="new-group",
        group_type="standard",
        provider_id=1
    )
    db_session.add(group)
    db_session.commit()
    
    # Generate YAML with existing file
    yaml_content = config_generator.generate_uniapi_yaml(
        db_session,
        gptload_base_url="http://localhost:3001",
        gptload_auth_key="test-key",
        existing_yaml_path=str(yaml_file)
    )
    
    # Verify dummy provider is removed
    assert "provider_name" not in yaml_content
    
    # Verify new group is added
    assert "new-group" in yaml_content
    
    # Verify custom api_keys are preserved
    assert "custom-admin-key" in yaml_content
    assert "admin" in yaml_content
    
    # Verify custom preferences are preserved
    assert "5000/min" in yaml_content
    assert "custom_setting" in yaml_content
    assert "preserved" in yaml_content


def test_export_uniapi_yaml_to_file_with_merging(config_generator, db_session, tmp_path, encryption_service):
    """Test exporting uni-api YAML to file with existing file merging."""
    # Create existing YAML file
    yaml_file = tmp_path / "api.yaml"
    existing_content = """
providers:
  - provider: provider_name
    base_url: http://dummy.com
    api: dummy-key
    model: []
api_keys:
  - api: preserved-key
    role: user
    model: ["all"]
preferences:
  rate_limit: "2000/min"
"""
    yaml_file.write_text(existing_content)
    
    # Create a test group
    group = GPTLoadGroup(
        gptload_group_id=1,
        name="test-group",
        group_type="standard",
        provider_id=1
    )
    db_session.add(group)
    db_session.commit()
    
    # Export to file (should merge with existing)
    result_path = config_generator.export_uniapi_yaml_to_file(
        db_session,
        str(yaml_file),
        gptload_base_url="http://localhost:3001",
        gptload_auth_key="test-key"
    )
    
    # Read the file
    with open(yaml_file, 'r') as f:
        content = f.read()
    
    # Verify dummy provider is removed
    assert "provider_name" not in content
    
    # Verify new group is added
    assert "test-group" in content
    
    # Verify preserved settings
    assert "preserved-key" in content
    assert "2000/min" in content


def test_generate_uniapi_yaml_no_existing_file(config_generator, db_session):
    """Test generating uni-api YAML when no existing file exists."""
    # Create a test group (must end with '-no-aggregate-models' to be included)
    group = GPTLoadGroup(
        gptload_group_id=1,
        name="test-no-aggregate-models",
        group_type="standard",
        provider_id=1
    )
    db_session.add(group)
    db_session.commit()
    
    # Generate YAML with non-existent file path
    yaml_content = config_generator.generate_uniapi_yaml(
        db_session,
        gptload_base_url="http://localhost:3001",
        gptload_auth_key="test-key",
        existing_yaml_path="/nonexistent/api.yaml"
    )
    
    # Verify default sections are used
    assert "sk-user-key" in yaml_content
    assert "999999/min" in yaml_content
    assert "test-no-aggregate-models" in yaml_content
    # Verify the gptload all-models API key is added
    assert "sk-all-models-from-gptload" in yaml_content
    assert "test-no-aggregate-models/*" in yaml_content


def test_export_uniapi_yaml_creates_directory(config_generator, db_session, tmp_path):
    """Test that export creates directory if it doesn't exist."""
    # Create a test group
    group = GPTLoadGroup(
        gptload_group_id=1,
        name="test-group",
        group_type="standard",
        provider_id=1,
        normalized_model=None
    )
    db_session.add(group)
    db_session.commit()
    
    # Use a nested directory path that doesn't exist
    nested_dir = tmp_path / "nested" / "directory" / "structure"
    file_path = nested_dir / "api.yaml"
    
    # Export should create the directory
    result_path = config_generator.export_uniapi_yaml_to_file(
        db_session,
        str(file_path),
        gptload_base_url="http://localhost:3001",
        gptload_auth_key="test-key"
    )
    
    # Verify directory was created
    assert nested_dir.exists()
    assert nested_dir.is_dir()
    
    # Verify file was written
    assert os.path.exists(result_path)
    with open(result_path, 'r') as f:
        content = f.read()
        assert "test-group" in content


def test_export_uniapi_yaml_sets_permissions(config_generator, db_session, tmp_path):
    """Test that export sets proper file permissions."""
    # Create a test group
    group = GPTLoadGroup(
        gptload_group_id=1,
        name="test-group",
        group_type="standard",
        provider_id=1,
        normalized_model=None
    )
    db_session.add(group)
    db_session.commit()
    
    # Export to file
    file_path = tmp_path / "api.yaml"
    config_generator.export_uniapi_yaml_to_file(
        db_session,
        str(file_path),
        gptload_base_url="http://localhost:3001",
        gptload_auth_key="test-key"
    )
    
    # Verify file permissions (0o644 = readable by all, writable by owner)
    # On Windows, this might not work exactly the same, so we just check the file exists
    assert os.path.exists(str(file_path))
    
    # On Unix-like systems, verify permissions
    if os.name != 'nt':  # Not Windows
        stat_info = os.stat(str(file_path))
        permissions = stat_info.st_mode & 0o777
        assert permissions == 0o644


def test_export_uniapi_yaml_handles_io_error(config_generator, db_session, tmp_path):
    """Test that export handles IOError gracefully."""
    # Create a test group
    group = GPTLoadGroup(
        gptload_group_id=1,
        name="test-group",
        group_type="standard",
        provider_id=1,
        normalized_model=None
    )
    db_session.add(group)
    db_session.commit()
    
    # Create a file and then try to write to it as if it were a directory
    # This will cause an error when trying to create a subdirectory
    file_as_dir = tmp_path / "file.txt"
    file_as_dir.write_text("test")
    invalid_path = file_as_dir / "subdir" / "api.yaml"
    
    with pytest.raises(IOError) as exc_info:
        config_generator.export_uniapi_yaml_to_file(
            db_session,
            str(invalid_path),
            gptload_base_url="http://localhost:3001",
            gptload_auth_key="test-key"
        )
    
    # Verify error message contains useful information
    assert "Failed to write" in str(exc_info.value)
