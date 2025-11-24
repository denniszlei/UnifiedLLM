"""Configuration API endpoints."""

import os
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services.config_generator import ConfigurationGenerator
from app.services.model_service import ModelService
from app.services.provider_service import ProviderService
from app.services.encryption_service import EncryptionService
from app.services.sync_service import SyncService
from app.config import settings

router = APIRouter(prefix="/api/config", tags=["configuration"])


class SyncRequest(BaseModel):
    """Configuration sync request."""
    
    provider_ids: Optional[List[int]] = None
    export_yaml_path: Optional[str] = None


class SyncResponse(BaseModel):
    """Configuration sync response."""
    
    sync_id: int
    status: str
    started_at: str
    completed_at: Optional[str] = None
    changes_summary: Optional[str] = None
    error_message: Optional[str] = None


class SyncStatusResponse(BaseModel):
    """Sync status response."""
    
    sync_id: Optional[int] = None
    status: Optional[str] = None
    started_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    message: Optional[str] = None
    last_sync: Optional[dict] = None


class SyncHistoryResponse(BaseModel):
    """Sync history response."""
    
    id: int
    status: str
    started_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    changes_summary: Optional[str] = None


def get_config_generator(db: Session = Depends(get_db)) -> ConfigurationGenerator:
    """Get configuration generator instance with dependencies."""
    encryption_service = EncryptionService()
    model_service = ModelService()
    provider_service = ProviderService(encryption_service)
    return ConfigurationGenerator(model_service, provider_service)


def get_sync_service(
    db: Session = Depends(get_db),
    config_gen: ConfigurationGenerator = Depends(get_config_generator)
) -> SyncService:
    """Get sync service instance with dependencies."""
    model_service = ModelService()
    encryption_service = EncryptionService()
    provider_service = ProviderService(encryption_service)
    return SyncService(config_gen, model_service, provider_service)


@router.post("/sync", response_model=SyncResponse)
async def sync_configuration(
    request: SyncRequest = SyncRequest(),
    db: Session = Depends(get_db),
    sync_service: SyncService = Depends(get_sync_service)
):
    """Trigger configuration sync to GPT-Load and uni-api.
    
    This endpoint orchestrates the complete sync process:
    1. Create a sync record with 'in_progress' status
    2. Generate GPT-Load configuration (create groups via API)
    3. Generate uni-api YAML configuration
    4. Optionally export YAML to file
    5. Update sync record with results
    
    Requirements: 11.1, 11.2
    """
    try:
        sync_record = await sync_service.sync_configuration(
            db,
            provider_ids=request.provider_ids,
            export_yaml_path=request.export_yaml_path
        )
        
        return SyncResponse(
            sync_id=sync_record.id,
            status=sync_record.status,
            started_at=sync_record.started_at.isoformat(),
            completed_at=sync_record.completed_at.isoformat() if sync_record.completed_at else None,
            changes_summary=sync_record.changes_summary,
            error_message=sync_record.error_message
        )
        
    except RuntimeError as e:
        # Concurrent sync attempt
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Configuration sync failed: {str(e)}")


@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    db: Session = Depends(get_db),
    sync_service: SyncService = Depends(get_sync_service)
):
    """Get status of current sync operation and last sync.
    
    Returns information about the currently running sync, or the last completed sync.
    
    Requirements: 11.1
    """
    try:
        status = sync_service.get_sync_status(db)
        
        # Get last sync record
        history = sync_service.get_sync_history(db, limit=1)
        last_sync = None
        
        if history:
            last = history[0]
            last_sync = {
                "id": last.id,
                "status": last.status,
                "started_at": last.started_at.isoformat(),
                "completed_at": last.completed_at.isoformat() if last.completed_at else None,
                "changes_summary": last.changes_summary,
                "error_message": last.error_message
            }
        
        if not status:
            return SyncStatusResponse(
                message="No sync operation in progress",
                last_sync=last_sync
            )
        
        return SyncStatusResponse(
            sync_id=status["sync_id"],
            status=status["status"],
            started_at=status["started_at"],
            duration_seconds=status["duration_seconds"],
            last_sync=last_sync
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync status: {str(e)}")


@router.get("/sync/history", response_model=List[SyncHistoryResponse])
async def get_sync_history(
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
    sync_service: SyncService = Depends(get_sync_service)
):
    """Get history of past sync operations.
    
    Returns a list of sync records ordered by most recent first.
    
    Requirements: 11.4
    """
    try:
        history = sync_service.get_sync_history(db, limit, offset)
        
        return [
            SyncHistoryResponse(
                id=record.id,
                status=record.status,
                started_at=record.started_at.isoformat(),
                completed_at=record.completed_at.isoformat() if record.completed_at else None,
                error_message=record.error_message,
                changes_summary=record.changes_summary
            )
            for record in history
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sync history: {str(e)}")


@router.get("/uni-api/yaml", response_class=PlainTextResponse)
async def get_uniapi_yaml(
    db: Session = Depends(get_db),
    config_gen: ConfigurationGenerator = Depends(get_config_generator)
):
    """Get uni-api YAML configuration as text.
    
    Returns the generated uni-api configuration that points to GPT-Load proxy endpoints.
    """
    try:
        yaml_content = config_gen.generate_uniapi_yaml(db)
        return Response(content=yaml_content, media_type="text/yaml")
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate uni-api YAML: {str(e)}")


@router.get("/uni-api/download")
async def download_uniapi_yaml(
    db: Session = Depends(get_db),
    config_gen: ConfigurationGenerator = Depends(get_config_generator)
):
    """Download uni-api YAML configuration file.
    
    Generates and returns the uni-api configuration as a downloadable file.
    
    Requirements: 6.6
    """
    try:
        # Generate YAML content
        yaml_content = config_gen.generate_uniapi_yaml(db)
        
        # Return as downloadable file
        return Response(
            content=yaml_content,
            media_type="application/x-yaml",
            headers={
                "Content-Disposition": "attachment; filename=api.yaml"
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate uni-api YAML: {str(e)}")


@router.post("/uni-api/export")
async def export_uniapi_yaml_to_volume(
    db: Session = Depends(get_db),
    config_gen: ConfigurationGenerator = Depends(get_config_generator)
):
    """Export uni-api YAML to shared volume for uni-api container.
    
    Writes the generated configuration to a file that can be mounted
    by the uni-api Docker container.
    """
    try:
        # Default export path (can be configured via environment)
        export_path = os.getenv("UNIAPI_CONFIG_PATH", "/app/uni-api-config/api.yaml")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        
        # Export to file
        file_path = config_gen.export_uniapi_yaml_to_file(db, export_path)
        
        return {
            "success": True,
            "file_path": file_path,
            "message": f"uni-api configuration exported to {file_path}"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write configuration file: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export uni-api YAML: {str(e)}")
