"""Tests for application startup validation."""

import pytest
import os
import sys
from unittest.mock import patch
from cryptography.fernet import Fernet


def test_app_starts_with_valid_encryption_key():
    """Test that application starts successfully with valid encryption key."""
    test_key = Fernet.generate_key().decode()
    
    env = {
        "ENCRYPTION_KEY": test_key,
        "GPTLOAD_AUTH_KEY": "test-auth-key",
        "DATABASE_URL": "sqlite:///./test.db",
    }
    
    with patch.dict(os.environ, env, clear=True):
        # Clear any cached imports
        for module in list(sys.modules.keys()):
            if module.startswith('app.'):
                del sys.modules[module]
        
        # This should not raise any exceptions
        from app.services.encryption_service import EncryptionService
        service = EncryptionService()
        
        # Verify service works
        plaintext = "test-value"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext


def test_app_fails_without_encryption_key():
    """Test that application fails to start without encryption key."""
    env = {
        "GPTLOAD_AUTH_KEY": "test-auth-key",
        "DATABASE_URL": "sqlite:///./test.db",
    }
    
    with patch.dict(os.environ, env, clear=True):
        # Clear any cached imports
        for module in list(sys.modules.keys()):
            if module.startswith('app.'):
                del sys.modules[module]
        
        # This should raise SystemExit
        with pytest.raises(SystemExit):
            from app.services.encryption_service import EncryptionService
            EncryptionService()
