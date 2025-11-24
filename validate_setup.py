"""Validate project setup."""

import os
import sys


def check_file_exists(filepath):
    """Check if a file exists."""
    exists = os.path.exists(filepath)
    status = "✓" if exists else "✗"
    print(f"{status} {filepath}")
    return exists


def main():
    """Validate project structure."""
    print("Validating LLM Provider Manager project setup...\n")
    
    required_files = [
        "pyproject.toml",
        "requirements.txt",
        "requirements-dev.txt",
        "README.md",
        ".env.example",
        ".gitignore",
        "run.py",
        "pytest.ini",
        "app/__init__.py",
        "app/main.py",
        "app/config.py",
        "app/database/__init__.py",
        "app/database/database.py",
        "app/models/__init__.py",
        "app/models/provider.py",
        "app/models/model.py",
        "app/models/sync_record.py",
        "app/models/gptload_group.py",
        "app/services/__init__.py",
        "app/services/encryption_service.py",
        "app/services/provider_service.py",
        "app/api/__init__.py",
        "app/api/providers.py",
        "tests/__init__.py",
        "tests/test_setup.py",
    ]
    
    print("Checking required files:")
    all_exist = all(check_file_exists(f) for f in required_files)
    
    print("\n" + "="*50)
    if all_exist:
        print("✓ All required files are present!")
        print("\nNext steps:")
        print("1. Create .env file: cp .env.example .env")
        print("2. Generate encryption key:")
        print('   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"')
        print("3. Update .env with your configuration")
        print("4. Install dependencies: pip install -r requirements.txt")
        print("5. Run the application: python run.py")
        return 0
    else:
        print("✗ Some required files are missing!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
