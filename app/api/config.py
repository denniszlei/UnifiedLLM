"""Configuration API endpoints."""

import os
import logging
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

logger = logging.getLogger(__name__)

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
    incremental: bool = True,
    db: Session = Depends(get_db),
    sync_service: SyncService = Depends(get_sync_service)
):
    """Trigger configuration sync to GPT-Load and uni-api.
    
    This endpoint orchestrates the complete sync process:
    1. Create a sync record with 'in_progress' status
    2. Generate GPT-Load configuration (incremental or full)
    3. Generate uni-api YAML configuration
    4. Optionally export YAML to file
    5. Update sync record with results
    
    Args:
        request: Sync request with optional provider_ids and export_yaml_path
        incremental: If True (default), uses smart diff-based updates.
                    If False, performs full recreation of all groups.
    
    Requirements: 11.1, 11.2, 17.1-17.12
    """
    try:
        # Use incremental sync by default (smart diff-based updates)
        if incremental:
            sync_record = await sync_service.sync_configuration_incremental(
                db,
                provider_ids=request.provider_ids,
                export_yaml_path=request.export_yaml_path
            )
        else:
            # Fall back to full sync if requested
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
    """Get uni-api YAML configuration from disk.
    
    Returns the existing api.yaml file from disk if it exists,
    otherwise generates a new one from current GPT-Load groups.
    """
    try:
        # Try to read existing file from disk first
        yaml_path = os.getenv("UNIAPI_CONFIG_PATH", "/app/uni-api-config/api.yaml")
        
        if os.path.exists(yaml_path):
            # Read existing file
            with open(yaml_path, 'r', encoding='utf-8') as f:
                yaml_content = f.read()
            logger.info(f"Read existing uni-api YAML from {yaml_path}")
        else:
            # File doesn't exist, generate new one
            yaml_content = config_gen.generate_uniapi_yaml(db)
            logger.info("Generated new uni-api YAML (file doesn't exist on disk)")
        
        return Response(content=yaml_content, media_type="text/yaml")
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get uni-api YAML: {str(e)}")


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



@router.post("/sync-gptload")
async def sync_gptload_only(
    request: SyncRequest = SyncRequest(),
    db: Session = Depends(get_db),
    sync_service: SyncService = Depends(get_sync_service)
):
    """Sync configuration to GPT-Load only (does not generate uni-api YAML).
    
    This endpoint only creates/updates GPT-Load groups without generating
    the uni-api configuration file.
    
    Requirements: 5.1, 5.2, 5.3, 5.4
    """
    try:
        # Use incremental sync but don't export YAML
        sync_record = await sync_service.sync_configuration_incremental(
            db,
            provider_ids=request.provider_ids,
            export_yaml_path=None  # Don't export YAML
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
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GPT-Load sync failed: {str(e)}")


@router.post("/sync-uniapi")
async def sync_uniapi_only(
    db: Session = Depends(get_db),
    config_gen: ConfigurationGenerator = Depends(get_config_generator)
):
    """Generate and export uni-api YAML configuration only.
    
    This endpoint generates the uni-api configuration based on existing
    GPT-Load groups without modifying GPT-Load.
    
    Requirements: 6.1, 21.1, 22.1
    """
    try:
        # Generate YAML
        yaml_content = config_gen.generate_uniapi_yaml(db)
        
        # Export to default path
        export_path = os.getenv("UNIAPI_CONFIG_PATH", "/app/uni-api-config/api.yaml")
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        
        file_path = config_gen.export_uniapi_yaml_to_file(db, export_path)
        
        return {
            "success": True,
            "file_path": file_path,
            "message": f"uni-api configuration generated and exported to {file_path}"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write configuration file: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate uni-api configuration: {str(e)}")
