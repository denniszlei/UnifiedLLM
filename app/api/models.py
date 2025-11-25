"""Model API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services.model_service import ModelService

router = APIRouter(prefix="/api", tags=["models"])


class ModelResponse(BaseModel):
    """Model response."""

    id: int
    provider_id: int
    original_name: str
    normalized_name: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: str


class NormalizeModelRequest(BaseModel):
    """Normalize model request."""

    normalized_name: str


class BatchNormalizeRequest(BaseModel):
    """Batch normalize models request."""

    updates: List[dict]  # List of {model_id: int, normalized_name: str}


class BatchNormalizeResponse(BaseModel):
    """Batch normalize response."""

    updated_count: int


class BulkDeleteRequest(BaseModel):
    """Bulk delete models request."""

    model_ids: List[int]
    provider_id: Optional[int] = None


class BulkDeleteResponse(BaseModel):
    """Bulk delete response."""

    deleted_count: int
    warning: Optional[str] = None


def get_model_service() -> ModelService:
    """Get model service instance."""
    return ModelService()


@router.get("/providers/{provider_id}/models", response_model=List[ModelResponse])
async def list_models(
    provider_id: int,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    service: ModelService = Depends(get_model_service)
):
    """List models for a provider.
    
    Requirements: 3.1
    """
    try:
        models = service.get_models_by_provider(db, provider_id, include_inactive)
        
        return [
            ModelResponse(
                id=m.id,
                provider_id=m.provider_id,
                original_name=m.original_name,
                normalized_name=m.normalized_name,
                is_active=m.is_active,
                created_at=m.created_at.isoformat(),
                updated_at=m.updated_at.isoformat()
            )
            for m in models
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


@router.put("/models/{model_id}/normalize", response_model=ModelResponse)
async def normalize_model(
    model_id: int,
    request: NormalizeModelRequest,
    db: Session = Depends(get_db),
    service: ModelService = Depends(get_model_service)
):
    """Normalize a model name.
    
    Updates the model mapping with a new normalized name while preserving
    the original provider model name for API calls.
    
    Requirements: 3.1
    """
    try:
        # Allow duplicates - they will trigger provider splitting
        model = service.normalize_model(
            db,
            model_id,
            request.normalized_name,
            allow_duplicates=True
        )
        
        return ModelResponse(
            id=model.id,
            provider_id=model.provider_id,
            original_name=model.original_name,
            normalized_name=model.normalized_name,
            is_active=model.is_active,
            created_at=model.created_at.isoformat(),
            updated_at=model.updated_at.isoformat()
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to normalize model: {str(e)}")


@router.delete("/models/batch-delete", response_model=BulkDeleteResponse)
async def batch_delete_models(
    request: BulkDeleteRequest,
    db: Session = Depends(get_db),
    service: ModelService = Depends(get_model_service)
):
    """Batch delete models with atomicity.
    
    All models are deleted in a single transaction. If any error occurs,
    all changes are rolled back.
    
    Requirements: 14.5, 15.3
    """
    try:
        result = service.bulk_delete_models(
            db,
            request.model_ids,
            request.provider_id
        )
        
        return BulkDeleteResponse(
            deleted_count=result["deleted_count"],
            warning=result.get("warning")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to batch delete models: {str(e)}")


@router.delete("/models/{model_id}", status_code=204)
async def delete_model(
    model_id: int,
    db: Session = Depends(get_db),
    service: ModelService = Depends(get_model_service)
):
    """Delete a model by marking it as inactive.
    
    Requirements: 4.1
    """
    try:
        deleted = service.delete_model(db, model_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete model: {str(e)}")


@router.post("/models/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_models(
    request: BulkDeleteRequest,
    db: Session = Depends(get_db),
    service: ModelService = Depends(get_model_service)
):
    """Bulk delete models with atomicity.
    
    All models are deleted in a single transaction. If any error occurs,
    all changes are rolled back.
    
    Requirements: 4.5
    """
    try:
        result = service.bulk_delete_models(
            db,
            request.model_ids,
            request.provider_id
        )
        
        return BulkDeleteResponse(
            deleted_count=result["deleted_count"],
            warning=result.get("warning")
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bulk delete models: {str(e)}")


@router.post("/models/{model_id}/reset", response_model=ModelResponse)
async def reset_model_name(
    model_id: int,
    db: Session = Depends(get_db),
    service: ModelService = Depends(get_model_service)
):
    """Reset a model name to its original provider name.
    
    Requirements: 3.5
    """
    try:
        model = service.reset_model_name(db, model_id)
        
        return ModelResponse(
            id=model.id,
            provider_id=model.provider_id,
            original_name=model.original_name,
            normalized_name=model.normalized_name,
            is_active=model.is_active,
            created_at=model.created_at.isoformat(),
            updated_at=model.updated_at.isoformat()
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset model name: {str(e)}")


@router.put("/models/batch-normalize", response_model=BatchNormalizeResponse)
async def batch_normalize_models(
    request: BatchNormalizeRequest,
    db: Session = Depends(get_db),
    service: ModelService = Depends(get_model_service)
):
    """Batch normalize model names.
    
    Updates multiple model names in a single transaction. All updates are
    applied atomically - if any error occurs, all changes are rolled back.
    
    Requirements: 15.3
    """
    try:
        result = service.batch_normalize_models(db, request.updates)
        
        return BatchNormalizeResponse(
            updated_count=result["updated_count"]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to batch normalize models: {str(e)}")


class NormalizedNameInfo(BaseModel):
    """Normalized name information."""

    name: str
    provider_count: int
    model_count: int


@router.get("/models/normalized-names", response_model=List[NormalizedNameInfo])
async def get_normalized_names(
    db: Session = Depends(get_db),
    service: ModelService = Depends(get_model_service)
):
    """Get all unique normalized model names with usage counts.
    
    Returns a list of normalized model names across all providers, ordered by
    provider count (descending) then name (ascending).
    
    Requirements: 20.1, 20.4
    """
    try:
        normalized_names = service.get_normalized_names_with_counts(db)
        
        return [
            NormalizedNameInfo(
                name=name,
                provider_count=counts["provider_count"],
                model_count=counts["model_count"]
            )
            for name, counts in normalized_names.items()
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get normalized names: {str(e)}")
