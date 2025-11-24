"""Tests for encryption service."""

import pytest
import os
import sys
from unittest.mock import patch
from cryptography.fernet import Fernet


def get_test_env(encryption_key: str) -> dict:
    """Get test environment with all required settings."""
    return {
        "ENCRYPTION_KEY": encryption_key,
        "GPTLOAD_AUTH_KEY": "test-auth-key",
        "DATABASE_URL": "sqlite:///./test.db",
    }


def test_encryption_service_encrypt_decrypt():
    """Test that encryption service can encrypt and decrypt data."""
    # Set a valid encryption key for testing
    test_key = Fernet.generate_key().decode()
    
    with patch.dict(os.environ, get_test_env(test_key), clear=True):
        # Clear any cached imports
        if 'app.config' in sys.modules:
            del sys.modules['app.config']
        if 'app.services.encryption_service' in sys.modules:
            del sys.modules['app.services.encryption_service']
        
        # Import after patching environment
        from app.services.encryption_service import EncryptionService
        
        service = EncryptionService()
        
        # Test encryption and decryption
        plaintext = "sk-test-api-key-12345"
        encrypted = service.encrypt(plaintext)
        
        # Encrypted should be different from plaintext
        assert encrypted != plaintext
        
        # Decryption should return original
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext


def test_encryption_service_multiple_values():
    """Test that encryption service handles multiple different values."""
    test_key = Fernet.generate_key().decode()
    
    with patch.dict(os.environ, get_test_env(test_key), clear=True):
        # Clear any cached imports
        if 'app.config' in sys.modules:
            del sys.modules['app.config']
        if 'app.services.encryption_service' in sys.modules:
            del sys.modules['app.services.encryption_service']
        
        from app.services.encryption_service import EncryptionService
        
        service = EncryptionService()
        
        values = [
            "sk-openai-key-123",
            "sk-anthropic-key-456",
            "very-long-api-key-" + "x" * 100,
            "short",
        ]
        
        for value in values:
            encrypted = service.encrypt(value)
            decrypted = service.decrypt(encrypted)
            assert decrypted == value


def test_encryption_service_missing_key():
    """Test that service exits when encryption key is missing."""
    with patch.dict(os.environ, get_test_env(""), clear=True):
        # Clear any cached imports
        if 'app.config' in sys.modules:
            del sys.modules['app.config']
        if 'app.services.encryption_service' in sys.modules:
            del sys.modules['app.services.encryption_service']
        
        with pytest.raises(SystemExit) as exc_info:
            from app.services.encryption_service import EncryptionService
            EncryptionService()
        
        assert exc_info.value.code == 1


def test_encryption_service_invalid_key():
    """Test that service exits when encryption key is invalid."""
    with patch.dict(os.environ, get_test_env("invalid-key-format"), clear=True):
        # Clear any cached imports
        if 'app.config' in sys.modules:
            del sys.modules['app.config']
        if 'app.services.encryption_service' in sys.modules:
            del sys.modules['app.services.encryption_service']
        
        with pytest.raises(SystemExit) as exc_info:
            from app.services.encryption_service import EncryptionService
            EncryptionService()
        
        assert exc_info.value.code == 1
