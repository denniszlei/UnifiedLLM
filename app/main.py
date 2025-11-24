"""Main FastAPI application entry point."""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import os

from app.database.database import init_db, get_db
from app.api.providers import router as providers_router
from app.api.config import router as config_router
from app.api.models import router as models_router
from app.api.gptload import router as gptload_router
from app.services.encryption_service import EncryptionService
from app.models.provider import Provider
from app.models.model import Model
from app.models.gptload_group import GPTLoadGroup
from app.models.sync_record import SyncRecord

app = FastAPI(
    title="LLM Provider Manager",
    description="Configuration orchestrator for GPT-Load and uni-api",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(providers_router)
app.include_router(config_router)
app.include_router(models_router)
app.include_router(gptload_router)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str
    database: str
    encryption: str
    message: Optional[str] = None


class StatsResponse(BaseModel):
    """System statistics response."""
    
    providers_count: int
    models_count: int
    active_models_count: int
    gptload_groups_count: int
    sync_records_count: int
    last_sync_status: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    """Initialize database and validate encryption on startup."""
    # Validate encryption service (will exit if key is invalid)
    EncryptionService()
    # Initialize database
    init_db()


@app.get("/")
async def root():
    """Root endpoint - serve the UI."""
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "LLM Provider Manager API", "version": "0.1.0"}


@app.get("/api/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint.
    
    Checks database connectivity and encryption key validity.
    
    Requirements: 8.5
    """
    health_status = {
        "status": "healthy",
        "database": "connected",
        "encryption": "valid"
    }
    
    try:
        # Test database connectivity
        db.execute("SELECT 1")
        
        # Test encryption service
        encryption_service = EncryptionService()
        test_encrypted = encryption_service.encrypt("test")
        test_decrypted = encryption_service.decrypt(test_encrypted)
        
        if test_decrypted != "test":
            health_status["encryption"] = "invalid"
            health_status["status"] = "unhealthy"
            health_status["message"] = "Encryption service validation failed"
        
        return HealthResponse(**health_status)
        
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["database"] = "disconnected"
        health_status["message"] = str(e)
        return HealthResponse(**health_status)


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    """Get system statistics.
    
    Returns counts of providers, models, groups, and sync records.
    
    Requirements: 8.5
    """
    try:
        # Count providers
        providers_count = db.query(Provider).count()
        
        # Count models
        models_count = db.query(Model).count()
        active_models_count = db.query(Model).filter(Model.is_active == True).count()
        
        # Count GPT-Load groups
        gptload_groups_count = db.query(GPTLoadGroup).count()
        
        # Count sync records
        sync_records_count = db.query(SyncRecord).count()
        
        # Get last sync status
        last_sync = db.query(SyncRecord).order_by(
            SyncRecord.started_at.desc()
        ).first()
        last_sync_status = last_sync.status if last_sync else None
        
        return StatsResponse(
            providers_count=providers_count,
            models_count=models_count,
            active_models_count=active_models_count,
            gptload_groups_count=gptload_groups_count,
            sync_records_count=sync_records_count,
            last_sync_status=last_sync_status
        )
        
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
