"""Provider API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services.provider_service import ProviderService
from app.services.encryption_service import EncryptionService

router = APIRouter(prefix="/api/providers", tags=["providers"])


class ProviderCreate(BaseModel):
    """Provider creation request."""

    name: str
    base_url: str
    api_key: str
    channel_type: str = "openai"


class ProviderUpdate(BaseModel):
    """Provider update request."""

    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    channel_type: Optional[str] = None


class ProviderResponse(BaseModel):
    """Provider response."""

    id: int
    name: str
    base_url: str
    api_key_masked: str
    channel_type: str
    created_at: str
    updated_at: str
    last_fetched_at: Optional[str] = None
    model_count: int = 0

    class Config:
        from_attributes = True


class ModelResponse(BaseModel):
    """Model response."""

    id: int
    original_name: str
    normalized_name: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: str


class FetchModelsResponse(BaseModel):
    """Fetch models response."""

    provider_id: int
    models_fetched: int
    models: List[ModelResponse]


class TestConnectivityResponse(BaseModel):
    """Test connectivity response."""

    success: bool
    message: str


class TestCredentialsRequest(BaseModel):
    """Test credentials request."""

    base_url: str
    api_key: str
    channel_type: str = "openai"


def get_provider_service(db: Session = Depends(get_db)) -> ProviderService:
    """Get provider service instance."""
    encryption_service = EncryptionService()
    return ProviderService(encryption_service)


@router.post("", response_model=ProviderResponse, status_code=201)
async def create_provider(
    provider: ProviderCreate,
    db: Session = Depends(get_db),
    service: ProviderService = Depends(get_provider_service)
):
    """Create a new provider.
    
    Validates credentials before storing. API key is encrypted.
    
    Requirements: 1.1, 1.2
    """
    try:
        new_provider = await service.add_provider(
            db=db,
            name=provider.name,
            base_url=provider.base_url,
            api_key=provider.api_key,
            channel_type=provider.channel_type,
        )
        
        # Get masked key for response
        providers_list = service.list_providers(db)
        provider_dict = next((p for p in providers_list if p["id"] == new_provider.id), None)
        
        return ProviderResponse(
            id=new_provider.id,
            name=new_provider.name,
            base_url=new_provider.base_url,
            api_key_masked=provider_dict["api_key_masked"] if provider_dict else "***",
            channel_type=new_provider.channel_type,
            created_at=new_provider.created_at.isoformat(),
            updated_at=new_provider.updated_at.isoformat(),
            last_fetched_at=new_provider.last_fetched_at.isoformat()
            if new_provider.last_fetched_at
            else None,
            model_count=0
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create provider: {str(e)}")


@router.get("", response_model=List[ProviderResponse])
async def list_providers(
    db: Session = Depends(get_db),
    service: ProviderService = Depends(get_provider_service)
):
    """List all providers with masked API keys.
    
    Requirements: 1.4
    """
    try:
        providers = service.list_providers(db)
        return [
            ProviderResponse(
                id=p["id"],
                name=p["name"],
                base_url=p["base_url"],
                api_key_masked=p["api_key_masked"],
                channel_type=p["channel_type"],
                created_at=p["created_at"].isoformat(),
                updated_at=p["updated_at"].isoformat(),
                last_fetched_at=p["last_fetched_at"].isoformat() if p["last_fetched_at"] else None,
                model_count=p.get("model_count", 0)
            )
            for p in providers
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list providers: {str(e)}")


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    service: ProviderService = Depends(get_provider_service)
):
    """Get provider details by ID.
    
    Requirements: 1.4
    """
    try:
        provider = service.get_provider(db, provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
        
        # Get masked key
        providers_list = service.list_providers(db)
        provider_dict = next((p for p in providers_list if p["id"] == provider_id), None)
        
        return ProviderResponse(
            id=provider.id,
            name=provider.name,
            base_url=provider.base_url,
            api_key_masked=provider_dict["api_key_masked"] if provider_dict else "***",
            channel_type=provider.channel_type,
            created_at=provider.created_at.isoformat(),
            updated_at=provider.updated_at.isoformat(),
            last_fetched_at=provider.last_fetched_at.isoformat() if provider.last_fetched_at else None,
            model_count=provider_dict.get("model_count", 0) if provider_dict else 0
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get provider: {str(e)}")


@router.put("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: int,
    provider_update: ProviderUpdate,
    db: Session = Depends(get_db),
    service: ProviderService = Depends(get_provider_service)
):
    """Update a provider.
    
    Validates credentials if base_url or api_key are updated.
    
    Requirements: 1.3
    """
    try:
        updated_provider = await service.update_provider(
            db=db,
            provider_id=provider_id,
            name=provider_update.name,
            base_url=provider_update.base_url,
            api_key=provider_update.api_key,
            channel_type=provider_update.channel_type
        )
        
        if not updated_provider:
            raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
        
        # Get masked key
        providers_list = service.list_providers(db)
        provider_dict = next((p for p in providers_list if p["id"] == provider_id), None)
        
        return ProviderResponse(
            id=updated_provider.id,
            name=updated_provider.name,
            base_url=updated_provider.base_url,
            api_key_masked=provider_dict["api_key_masked"] if provider_dict else "***",
            channel_type=updated_provider.channel_type,
            created_at=updated_provider.created_at.isoformat(),
            updated_at=updated_provider.updated_at.isoformat(),
            last_fetched_at=updated_provider.last_fetched_at.isoformat()
            if updated_provider.last_fetched_at
            else None,
            model_count=provider_dict.get("model_count", 0) if provider_dict else 0
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update provider: {str(e)}")


@router.delete("/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    service: ProviderService = Depends(get_provider_service)
):
    """Delete a provider with cascade deletion of associated models.
    
    Requirements: 1.5
    """
    try:
        deleted = service.delete_provider(db, provider_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete provider: {str(e)}")


@router.post("/{provider_id}/fetch-models", response_model=FetchModelsResponse)
async def fetch_models(
    provider_id: int,
    db: Session = Depends(get_db),
    service: ProviderService = Depends(get_provider_service)
):
    """Fetch models from provider and store them.
    
    Requirements: 2.1
    """
    try:
        models = await service.fetch_models(db, provider_id)
        
        return FetchModelsResponse(
            provider_id=provider_id,
            models_fetched=len(models),
            models=[
                ModelResponse(
                    id=m.id,
                    original_name=m.original_name,
                    normalized_name=m.normalized_name,
                    is_active=m.is_active,
                    created_at=m.created_at.isoformat(),
                    updated_at=m.updated_at.isoformat()
                )
                for m in models
            ]
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch models: {str(e)}")


@router.post("/test", response_model=TestConnectivityResponse)
async def test_credentials(
    credentials: TestCredentialsRequest,
    service: ProviderService = Depends(get_provider_service)
):
    """Test provider credentials before adding.
    
    Requirements: 12.1
    """
    try:
        is_valid = await service.validate_provider(
            credentials.base_url,
            credentials.api_key,
            credentials.channel_type
        )
        
        if is_valid:
            return TestConnectivityResponse(
                success=True,
                message="Connection successful"
            )
        else:
            return TestConnectivityResponse(
                success=False,
                message="Connection failed"
            )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Connection test failed: {str(e)}"
        )


@router.post("/{provider_id}/test", response_model=TestConnectivityResponse)
async def test_connectivity(
    provider_id: int,
    db: Session = Depends(get_db),
    service: ProviderService = Depends(get_provider_service)
):
    """Test provider connectivity.
    
    Requirements: 12.1
    """
    try:
        provider_dict = service.get_provider_with_decrypted_key(db, provider_id)
        if not provider_dict:
            raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
        
        is_valid = await service.validate_provider(
            provider_dict["base_url"],
            provider_dict["api_key"],
            provider_dict["channel_type"]
        )
        
        if is_valid:
            return TestConnectivityResponse(
                success=True,
                message="Provider connectivity test successful"
            )
        else:
            return TestConnectivityResponse(
                success=False,
                message="Provider connectivity test failed"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test connectivity: {str(e)}"
        )
