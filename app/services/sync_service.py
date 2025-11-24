"""Sync service for orchestrating configuration synchronization."""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import asyncio

from app.models.sync_record import SyncRecord
from app.services.config_generator import ConfigurationGenerator
from app.services.model_service import ModelService
from app.services.provider_service import ProviderService

logger = logging.getLogger(__name__)


class SyncService:
    """Service for orchestrating configuration synchronization to GPT-Load and uni-api."""

    # Class-level lock to prevent concurrent syncs
    _sync_lock = asyncio.Lock()
    _current_sync_id: Optional[int] = None

    def __init__(
        self,
        config_generator: ConfigurationGenerator,
        model_service: ModelService,
        provider_service: ProviderService
    ):
        """Initialize sync service.
        
        Args:
            config_generator: Configuration generator service.
            model_service: Model service.
            provider_service: Provider service.
        """
        self.config_generator = config_generator
        self.model_service = model_service
        self.provider_service = provider_service

    async def sync_configuration(
        self,
        db: Session,
        provider_ids: Optional[List[int]] = None,
        export_yaml_path: Optional[str] = None
    ) -> SyncRecord:
        """Coordinate full configuration sync to GPT-Load and uni-api.
        
        This method orchestrates the complete sync process:
        1. Create a sync record with 'in_progress' status
        2. Generate GPT-Load configuration (create groups via API)
        3. Generate uni-api YAML configuration
        4. Optionally export YAML to file
        5. Update sync record with results
        
        Args:
            db: Database session.
            provider_ids: Optional list of provider IDs to sync.
                         If None, syncs all providers.
            export_yaml_path: Optional path to export uni-api YAML file.
            
        Returns:
            SyncRecord with sync results.
            
        Raises:
            RuntimeError: If another sync is already in progress.
        """
        # Check if sync is already in progress
        if self._sync_lock.locked():
            logger.warning("Sync already in progress")
            raise RuntimeError("A sync operation is already in progress")
        
        async with self._sync_lock:
            # Create sync record
            sync_record = SyncRecord(
                status="in_progress",
                started_at=datetime.utcnow()
            )
            db.add(sync_record)
            db.commit()
            db.refresh(sync_record)
            
            # Store current sync ID
            self._current_sync_id = sync_record.id
            
            logger.info(f"Starting sync operation {sync_record.id}")
            
            try:
                # Step 1: Generate GPT-Load configuration
                logger.info("Step 1: Generating GPT-Load configuration")
                gptload_result = await self.config_generator.generate_gptload_configuration(
                    db,
                    provider_ids
                )
                
                # Check for errors in GPT-Load generation
                if gptload_result.get("errors"):
                    error_summary = "; ".join(gptload_result["errors"])
                    logger.error(f"Errors during GPT-Load configuration: {error_summary}")
                    
                    # If there are errors but some groups were created, continue
                    if not gptload_result.get("standard_groups") and not gptload_result.get("aggregate_groups"):
                        raise Exception(f"GPT-Load configuration failed: {error_summary}")
                
                # Step 2: Generate uni-api YAML
                logger.info("Step 2: Generating uni-api YAML configuration")
                yaml_content = self.config_generator.generate_uniapi_yaml(db)
                
                # Step 3: Export YAML if path provided
                if export_yaml_path:
                    logger.info(f"Step 3: Exporting uni-api YAML to {export_yaml_path}")
                    self.config_generator.export_uniapi_yaml_to_file(
                        db,
                        export_yaml_path
                    )
                
                # Build changes summary
                changes_summary = self._build_changes_summary(gptload_result, yaml_content)
                
                # Update sync record with success
                sync_record.status = "success"
                sync_record.completed_at = datetime.utcnow()
                sync_record.changes_summary = changes_summary
                db.commit()
                db.refresh(sync_record)
                
                logger.info(f"Sync operation {sync_record.id} completed successfully")
                
                return sync_record
                
            except Exception as e:
                # Update sync record with failure
                error_message = str(e)
                logger.error(f"Sync operation {sync_record.id} failed: {error_message}")
                
                sync_record.status = "failed"
                sync_record.completed_at = datetime.utcnow()
                sync_record.error_message = error_message
                db.commit()
                db.refresh(sync_record)
                
                return sync_record
                
            finally:
                # Clear current sync ID
                self._current_sync_id = None

    def _build_changes_summary(
        self,
        gptload_result: Dict[str, Any],
        yaml_content: str
    ) -> str:
        """Build a human-readable summary of sync changes.
        
        Args:
            gptload_result: Result from GPT-Load configuration generation.
            yaml_content: Generated uni-api YAML content.
            
        Returns:
            Summary string.
        """
        standard_count = len(gptload_result.get("standard_groups", []))
        aggregate_count = len(gptload_result.get("aggregate_groups", []))
        error_count = len(gptload_result.get("errors", []))
        
        # Count providers in YAML
        yaml_lines = yaml_content.split('\n')
        provider_lines = [line for line in yaml_lines if line.strip().startswith('- provider:')]
        yaml_provider_count = len(provider_lines)
        
        summary_parts = [
            f"GPT-Load: {standard_count} standard groups, {aggregate_count} aggregate groups created"
        ]
        
        if error_count > 0:
            summary_parts.append(f"{error_count} errors encountered")
        
        summary_parts.append(f"uni-api: {yaml_provider_count} provider entries generated")
        
        return "; ".join(summary_parts)

    def get_sync_status(self, db: Session) -> Optional[Dict[str, Any]]:
        """Get status of current sync operation.
        
        Args:
            db: Database session.
            
        Returns:
            Dictionary with sync status information, or None if no sync in progress.
            Format:
                - sync_id: Sync record ID
                - status: Current status
                - started_at: Start timestamp
                - duration_seconds: Elapsed time in seconds
        """
        if not self._current_sync_id:
            return None
        
        sync_record = db.query(SyncRecord).filter(
            SyncRecord.id == self._current_sync_id
        ).first()
        
        if not sync_record:
            return None
        
        # Calculate duration
        duration = (datetime.utcnow() - sync_record.started_at).total_seconds()
        
        return {
            "sync_id": sync_record.id,
            "status": sync_record.status,
            "started_at": sync_record.started_at.isoformat(),
            "duration_seconds": duration
        }

    def get_sync_history(
        self,
        db: Session,
        limit: int = 10,
        offset: int = 0
    ) -> List[SyncRecord]:
        """Get history of past sync operations.
        
        Args:
            db: Database session.
            limit: Maximum number of records to return.
            offset: Number of records to skip.
            
        Returns:
            List of SyncRecord instances, ordered by most recent first.
        """
        return db.query(SyncRecord).order_by(
            SyncRecord.started_at.desc()
        ).limit(limit).offset(offset).all()

    def get_sync_record(self, db: Session, sync_id: int) -> Optional[SyncRecord]:
        """Get a specific sync record by ID.
        
        Args:
            db: Database session.
            sync_id: Sync record ID.
            
        Returns:
            SyncRecord instance or None if not found.
        """
        return db.query(SyncRecord).filter(SyncRecord.id == sync_id).first()

    async def retry_failed_sync(
        self,
        db: Session,
        sync_id: int,
        export_yaml_path: Optional[str] = None
    ) -> SyncRecord:
        """Retry a failed sync operation.
        
        This creates a new sync operation with the same parameters.
        
        Args:
            db: Database session.
            sync_id: ID of the failed sync to retry.
            export_yaml_path: Optional path to export uni-api YAML file.
            
        Returns:
            New SyncRecord with retry results.
            
        Raises:
            ValueError: If sync record not found or not in failed status.
            RuntimeError: If another sync is already in progress.
        """
        # Get the failed sync record
        failed_sync = self.get_sync_record(db, sync_id)
        
        if not failed_sync:
            raise ValueError(f"Sync record {sync_id} not found")
        
        if failed_sync.status != "failed":
            raise ValueError(f"Sync record {sync_id} is not in failed status (current: {failed_sync.status})")
        
        logger.info(f"Retrying failed sync {sync_id}")
        
        # Perform a new sync (syncs all providers by default)
        return await self.sync_configuration(db, export_yaml_path=export_yaml_path)

    def is_sync_in_progress(self) -> bool:
        """Check if a sync operation is currently in progress.
        
        Returns:
            True if sync is in progress, False otherwise.
        """
        return self._sync_lock.locked()

