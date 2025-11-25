"""GPT-Load status API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services.gptload_client import GPTLoadClient
from app.models.gptload_group import GPTLoadGroup
from app.config import settings

router = APIRouter(prefix="/api/gptload", tags=["gptload"])


class GPTLoadStatusResponse(BaseModel):
    """GPT-Load status response."""
    
    connected: bool
    url: str
    group_count: int
    error_message: Optional[str] = None


@router.get("/status", response_model=GPTLoadStatusResponse)
async def get_gptload_status(db: Session = Depends(get_db)):
    """Get GPT-Load connection status and group count.
    
    This endpoint checks connectivity to GPT-Load and returns:
    - Connection status (connected/disconnected)
    - GPT-Load URL
    - Number of groups currently in GPT-Load
    
    Requirements: 13.1, 13.2, 13.3, 13.5
    """
    gptload_url = settings.gptload_url
    
    try:
        # Check connectivity to GPT-Load
        async with GPTLoadClient() as client:
            is_healthy = await client.health_check()
            
            if not is_healthy:
                return GPTLoadStatusResponse(
                    connected=False,
                    url=gptload_url,
                    group_count=0,
                    error_message="GPT-Load service is not responding"
                )
            
            # Get group count from GPT-Load
            try:
                groups = await client.list_groups()
                group_count = len(groups) if groups else 0
            except Exception as e:
                # If we can't get groups but health check passed, still show connected
                group_count = 0
            
            return GPTLoadStatusResponse(
                connected=True,
                url=gptload_url,
                group_count=group_count,
                error_message=None
            )
            
    except Exception as e:
        # Connection failed
        return GPTLoadStatusResponse(
            connected=False,
            url=gptload_url,
            group_count=0,
            error_message=str(e)
        )



class GPTLoadGroupResponse(BaseModel):
    """GPT-Load group response."""
    
    id: int
    name: str
    group_type: str
    provider_name: Optional[str] = None
    normalized_model: Optional[str] = None


@router.get("/groups", response_model=list[GPTLoadGroupResponse])
async def get_gptload_groups(db: Session = Depends(get_db)):
    """Get list of all GPT-Load groups from local database.
    
    Returns all groups that have been synced to GPT-Load, including:
    - Standard groups (per provider)
    - Aggregate groups (for duplicate models)
    
    Requirements: 5.1, 5.3
    """
    try:
        # Query all groups from database
        groups = db.query(GPTLoadGroup).all()
        
        # Build response with provider names
        from app.models.provider import Provider
        
        result = []
        for group in groups:
            provider_name = None
            if group.provider_id:
                provider = db.query(Provider).filter(Provider.id == group.provider_id).first()
                if provider:
                    provider_name = provider.name
            
            result.append(GPTLoadGroupResponse(
                id=group.id,
                name=group.name,
                group_type=group.group_type,
                provider_name=provider_name,
                normalized_model=group.normalized_model
            ))
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get groups: {str(e)}")
