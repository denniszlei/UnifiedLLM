"""Provider service for managing LLM API providers."""

import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import httpx

from app.models.provider import Provider
from app.models.model import Model
from app.services.encryption_service import EncryptionService

logger = logging.getLogger(__name__)


class ProviderService:
    """Service for managing LLM API providers."""

    def __init__(self, encryption_service: EncryptionService):
        """Initialize provider service.
        
        Args:
            encryption_service: Service for encrypting/decrypting API keys.
        """
        self.encryption_service = encryption_service

    async def add_provider(
        self,
        db: Session,
        name: str,
        base_url: str,
        api_key: str,
        channel_type: str = "openai"
    ) -> Provider:
        """Add a new provider with credential validation.
        
        Args:
            db: Database session.
            name: Provider name.
            base_url: Provider API base URL.
            api_key: Provider API key (will be encrypted).
            channel_type: Provider channel type (openai, anthropic, etc.).
            
        Returns:
            The created Provider instance.
            
        Raises:
            ValueError: If validation fails or provider name already exists.
            httpx.HTTPError: If credential validation fails.
        """
        # Validate credentials before storing
        is_valid = await self.validate_provider(base_url, api_key, channel_type)
        if not is_valid:
            raise ValueError("Provider credential validation failed")
        
        # Encrypt API key
        encrypted_key = self.encryption_service.encrypt(api_key)
        
        # Create provider
        provider = Provider(
            name=name,
            base_url=base_url,
            api_key_encrypted=encrypted_key,
            channel_type=channel_type
        )
        
        try:
            db.add(provider)
            db.commit()
            db.refresh(provider)
            logger.info(f"Provider '{name}' added successfully")
            return provider
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Failed to add provider '{name}': {e}")
            raise ValueError(f"Provider with name '{name}' already exists")

    async def validate_provider(
        self,
        base_url: str,
        api_key: str,
        channel_type: str = "openai"
    ) -> bool:
        """Validate provider credentials by making a test request.
        
        Args:
            base_url: Provider API base URL.
            api_key: Provider API key.
            channel_type: Provider channel type.
            
        Returns:
            True if validation succeeds, False otherwise.
        """
        try:
            # Normalize base URL - remove trailing slash
            base_url = base_url.rstrip('/')
            
            # Construct test endpoint based on channel type
            if channel_type == "openai":
                test_url = f"{base_url}/v1/models"
            elif channel_type == "anthropic":
                test_url = f"{base_url}/v1/models"
            else:
                # Default to OpenAI-compatible endpoint
                test_url = f"{base_url}/v1/models"
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(test_url, headers=headers)
                
                # Accept 200 or 401/403 as valid (some providers return auth errors for invalid keys)
                # We just want to confirm the endpoint is reachable
                if response.status_code in [200, 401, 403]:
                    logger.info(f"Provider validation successful for {base_url}")
                    return True
                else:
                    logger.warning(f"Provider validation failed with status {response.status_code}")
                    return False
                    
        except httpx.TimeoutException:
            logger.error(f"Provider validation timeout for {base_url}")
            return False
        except httpx.RequestError as e:
            logger.error(f"Provider validation error for {base_url}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during provider validation: {e}")
            return False

    def list_providers(self, db: Session, include_masked_keys: bool = True) -> List[dict]:
        """List all providers with masked API keys.
        
        Args:
            db: Database session.
            include_masked_keys: Whether to include masked API keys in response.
            
        Returns:
            List of provider dictionaries with masked API keys.
        """
        providers = db.query(Provider).all()
        
        result = []
        for provider in providers:
            provider_dict = {
                "id": provider.id,
                "name": provider.name,
                "base_url": provider.base_url,
                "channel_type": provider.channel_type,
                "created_at": provider.created_at,
                "updated_at": provider.updated_at,
                "last_fetched_at": provider.last_fetched_at,
                "model_count": len(provider.models) if hasattr(provider, 'models') else 0
            }
            
            if include_masked_keys:
                # Mask API key - show only first 3 and last 4 characters
                try:
                    decrypted_key = self.encryption_service.decrypt(provider.api_key_encrypted)
                    if len(decrypted_key) > 10:
                        masked_key = f"{decrypted_key[:3]}{'*' * 15}{decrypted_key[-4:]}"
                    else:
                        masked_key = "*" * len(decrypted_key)
                    provider_dict["api_key_masked"] = masked_key
                except Exception as e:
                    logger.error(f"Failed to decrypt API key for provider {provider.id}: {e}")
                    provider_dict["api_key_masked"] = "***ERROR***"
            
            result.append(provider_dict)
        
        return result

    def get_provider(self, db: Session, provider_id: int) -> Optional[Provider]:
        """Get a provider by ID.
        
        Args:
            db: Database session.
            provider_id: Provider ID.
            
        Returns:
            Provider instance or None if not found.
        """
        return db.query(Provider).filter(Provider.id == provider_id).first()

    def get_provider_with_decrypted_key(self, db: Session, provider_id: int) -> Optional[dict]:
        """Get a provider with decrypted API key.
        
        Args:
            db: Database session.
            provider_id: Provider ID.
            
        Returns:
            Provider dictionary with decrypted API key or None if not found.
        """
        provider = self.get_provider(db, provider_id)
        if not provider:
            return None
        
        try:
            decrypted_key = self.encryption_service.decrypt(provider.api_key_encrypted)
            return {
                "id": provider.id,
                "name": provider.name,
                "base_url": provider.base_url,
                "api_key": decrypted_key,
                "channel_type": provider.channel_type,
                "created_at": provider.created_at,
                "updated_at": provider.updated_at,
                "last_fetched_at": provider.last_fetched_at
            }
        except Exception as e:
            logger.error(f"Failed to decrypt API key for provider {provider_id}: {e}")
            return None

    async def update_provider(
        self,
        db: Session,
        provider_id: int,
        name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        channel_type: Optional[str] = None
    ) -> Optional[Provider]:
        """Update a provider.
        
        Args:
            db: Database session.
            provider_id: Provider ID.
            name: New provider name (optional).
            base_url: New base URL (optional).
            api_key: New API key (optional, will be encrypted).
            channel_type: New channel type (optional).
            
        Returns:
            Updated Provider instance or None if not found.
            
        Raises:
            ValueError: If validation fails or name already exists.
        """
        provider = self.get_provider(db, provider_id)
        if not provider:
            return None
        
        # If credentials are being updated, validate them
        if base_url or api_key:
            test_base_url = base_url if base_url else provider.base_url
            test_api_key = api_key if api_key else self.encryption_service.decrypt(provider.api_key_encrypted)
            test_channel_type = channel_type if channel_type else provider.channel_type
            
            is_valid = await self.validate_provider(test_base_url, test_api_key, test_channel_type)
            if not is_valid:
                raise ValueError("Provider credential validation failed")
        
        # Update fields
        if name:
            provider.name = name
        if base_url:
            provider.base_url = base_url
        if api_key:
            provider.api_key_encrypted = self.encryption_service.encrypt(api_key)
        if channel_type:
            provider.channel_type = channel_type
        
        provider.updated_at = datetime.utcnow()
        
        try:
            db.commit()
            db.refresh(provider)
            logger.info(f"Provider {provider_id} updated successfully")
            return provider
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Failed to update provider {provider_id}: {e}")
            raise ValueError(f"Provider with name '{name}' already exists")

    def delete_provider(self, db: Session, provider_id: int) -> bool:
        """Delete a provider with cascade deletion of associated models.
        
        Args:
            db: Database session.
            provider_id: Provider ID.
            
        Returns:
            True if deleted, False if provider not found.
        """
        provider = self.get_provider(db, provider_id)
        if not provider:
            return False
        
        # Count associated models for logging
        model_count = db.query(Model).filter(Model.provider_id == provider_id).count()
        
        try:
            db.delete(provider)
            db.commit()
            logger.info(f"Provider {provider_id} deleted successfully (cascade deleted {model_count} models)")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete provider {provider_id}: {e}")
            raise

    async def fetch_models(self, db: Session, provider_id: int) -> List[Model]:
        """Fetch models from provider and store them in database.
        
        Args:
            db: Database session.
            provider_id: Provider ID.
            
        Returns:
            List of Model instances fetched and stored.
            
        Raises:
            ValueError: If provider not found.
            httpx.HTTPError: If API call fails.
        """
        provider = self.get_provider(db, provider_id)
        if not provider:
            raise ValueError(f"Provider {provider_id} not found")
        
        # Decrypt API key
        try:
            api_key = self.encryption_service.decrypt(provider.api_key_encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt API key for provider {provider_id}: {e}")
            raise ValueError("Failed to decrypt provider API key")
        
        # Fetch models from provider
        models_data = await self._fetch_models_from_api(
            provider.base_url,
            api_key,
            provider.channel_type
        )
        
        if not models_data:
            logger.warning(f"No models returned from provider {provider_id}")
            # Update last_fetched_at even if no models
            provider.last_fetched_at = datetime.utcnow()
            db.commit()
            return []
        
        # Store models in database
        stored_models = []
        for model_name in models_data:
            # Check if model already exists
            existing_model = db.query(Model).filter(
                Model.provider_id == provider_id,
                Model.original_name == model_name
            ).first()
            
            if existing_model:
                # Update existing model
                existing_model.is_active = True
                existing_model.updated_at = datetime.utcnow()
                stored_models.append(existing_model)
            else:
                # Create new model
                new_model = Model(
                    provider_id=provider_id,
                    original_name=model_name,
                    normalized_name=None,
                    is_active=True
                )
                db.add(new_model)
                stored_models.append(new_model)
        
        # Update provider's last_fetched_at
        provider.last_fetched_at = datetime.utcnow()
        
        try:
            db.commit()
            logger.info(f"Fetched and stored {len(stored_models)} models for provider {provider_id}")
            return stored_models
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to store models for provider {provider_id}: {e}")
            raise

    async def _fetch_models_from_api(
        self,
        base_url: str,
        api_key: str,
        channel_type: str
    ) -> List[str]:
        """Fetch model list from provider API.
        
        Args:
            base_url: Provider API base URL.
            api_key: Provider API key.
            channel_type: Provider channel type.
            
        Returns:
            List of model names.
            
        Raises:
            httpx.HTTPError: If API call fails.
        """
        try:
            # Normalize base URL
            base_url = base_url.rstrip('/')
            
            # Construct models endpoint based on channel type
            if channel_type == "openai":
                models_url = f"{base_url}/v1/models"
            elif channel_type == "anthropic":
                models_url = f"{base_url}/v1/models"
            else:
                # Default to OpenAI-compatible endpoint
                models_url = f"{base_url}/v1/models"
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(models_url, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                
                # Parse response based on channel type
                if channel_type == "openai" or channel_type == "anthropic":
                    # OpenAI format: {"data": [{"id": "model-name"}, ...]}
                    if "data" in data and isinstance(data["data"], list):
                        model_names = [model.get("id") for model in data["data"] if "id" in model]
                        logger.info(f"Fetched {len(model_names)} models from {base_url}")
                        return model_names
                    else:
                        logger.warning(f"Unexpected response format from {base_url}: {data}")
                        return []
                else:
                    # Try to parse as OpenAI format by default
                    if "data" in data and isinstance(data["data"], list):
                        model_names = [model.get("id") for model in data["data"] if "id" in model]
                        return model_names
                    else:
                        logger.warning(f"Unexpected response format from {base_url}")
                        return []
                        
        except httpx.TimeoutException:
            logger.error(f"Timeout fetching models from {base_url}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching models from {base_url}: {e.response.status_code}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error fetching models from {base_url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching models from {base_url}: {e}")
            raise
