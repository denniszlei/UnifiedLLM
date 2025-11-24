"""Encryption service for securing API keys."""

import sys
from cryptography.fernet import Fernet, InvalidToken
from app.config import settings


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""

    def __init__(self):
        """Initialize encryption service with key from settings."""
        self._validate_encryption_key()
        self._fernet = Fernet(settings.encryption_key.encode())

    def _validate_encryption_key(self) -> None:
        """Validate that encryption key is properly configured.
        
        Raises:
            SystemExit: If encryption key is missing or invalid.
        """
        if not settings.encryption_key:
            print("ERROR: ENCRYPTION_KEY environment variable is not set.", file=sys.stderr)
            print("The service cannot start without a valid encryption key.", file=sys.stderr)
            print("Generate a key with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"", file=sys.stderr)
            sys.exit(1)
        
        try:
            # Validate that the key is a valid Fernet key
            Fernet(settings.encryption_key.encode())
        except Exception as e:
            print(f"ERROR: Invalid ENCRYPTION_KEY format: {e}", file=sys.stderr)
            print("Generate a valid key with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"", file=sys.stderr)
            sys.exit(1)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string.
        
        Args:
            plaintext: The string to encrypt.
            
        Returns:
            The encrypted string (base64 encoded).
        """
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext string.
        
        Args:
            ciphertext: The encrypted string (base64 encoded).
            
        Returns:
            The decrypted plaintext string.
            
        Raises:
            InvalidToken: If the ciphertext is invalid or corrupted.
        """
        return self._fernet.decrypt(ciphertext.encode()).decode()
