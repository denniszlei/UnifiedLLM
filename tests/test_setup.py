"""Test basic project setup."""

import pytest
from cryptography.fernet import Fernet


def test_encryption_key_generation():
    """Test that encryption key can be generated."""
    key = Fernet.generate_key()
    assert key is not None
    assert len(key) > 0


def test_fernet_encryption_decryption():
    """Test basic encryption/decryption works."""
    key = Fernet.generate_key()
    fernet = Fernet(key)
    
    plaintext = "test-api-key-12345"
    encrypted = fernet.encrypt(plaintext.encode())
    decrypted = fernet.decrypt(encrypted).decode()
    
    assert decrypted == plaintext


def test_project_structure():
    """Test that key project files exist."""
    import os
    
    assert os.path.exists("app/main.py")
    assert os.path.exists("app/config.py")
    assert os.path.exists("app/database/database.py")
    assert os.path.exists("app/models/provider.py")
    assert os.path.exists("app/services/encryption_service.py")
    assert os.path.exists("requirements.txt")
    assert os.path.exists("pyproject.toml")
