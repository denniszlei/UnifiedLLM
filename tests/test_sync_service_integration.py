"""Integration tests for sync service with real database."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.models.sync_record import SyncRecord
from app.services.sync_service import SyncService


@pytest.fixture
def test_db():
    """Create a test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def sync_service():
    """Create sync service with mocked dependencies."""
    config_generator = MagicMock()
    model_service = MagicMock()
    provider_service = MagicMock()
    return SyncService(config_generator, model_service, provider_service)


class TestSyncServiceIntegration:
    """Integration tests for sync service."""

    def test_get_sync_history_empty(self, sync_service, test_db):
        """Test getting sync history when no syncs exist."""
        history = sync_service.get_sync_history(test_db)
        assert history == []

    def test_get_sync_record_not_found(self, sync_service, test_db):
        """Test getting a non-existent sync record."""
        record = sync_service.get_sync_record(test_db, 999)
        assert record is None

    def test_get_sync_status_no_sync(self, sync_service, test_db):
        """Test getting status when no sync is in progress."""
        status = sync_service.get_sync_status(test_db)
        assert status is None

    def test_is_sync_in_progress_initially_false(self, sync_service):
        """Test that initially no sync is in progress."""
        assert not sync_service.is_sync_in_progress()

    def test_create_sync_record_manually(self, test_db):
        """Test creating a sync record manually."""
        sync_record = SyncRecord(
            status="success",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            changes_summary="Test sync"
        )
        test_db.add(sync_record)
        test_db.commit()
        test_db.refresh(sync_record)
        
        assert sync_record.id is not None
        assert sync_record.status == "success"
        assert sync_record.changes_summary == "Test sync"

    def test_get_sync_history_with_records(self, sync_service, test_db):
        """Test getting sync history with existing records."""
        # Create some sync records
        for i in range(3):
            sync_record = SyncRecord(
                status="success" if i % 2 == 0 else "failed",
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                changes_summary=f"Sync {i}"
            )
            test_db.add(sync_record)
        test_db.commit()
        
        # Get history
        history = sync_service.get_sync_history(test_db, limit=10)
        
        assert len(history) == 3
        # Should be ordered by most recent first
        assert history[0].changes_summary == "Sync 2"

    def test_get_specific_sync_record(self, sync_service, test_db):
        """Test getting a specific sync record."""
        # Create a sync record
        sync_record = SyncRecord(
            status="success",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            changes_summary="Test sync"
        )
        test_db.add(sync_record)
        test_db.commit()
        test_db.refresh(sync_record)
        
        # Get the record
        retrieved = sync_service.get_sync_record(test_db, sync_record.id)
        
        assert retrieved is not None
        assert retrieved.id == sync_record.id
        assert retrieved.status == "success"
        assert retrieved.changes_summary == "Test sync"

    def test_build_changes_summary(self, sync_service):
        """Test building changes summary."""
        gptload_result = {
            "standard_groups": [{"id": 1}, {"id": 2}],
            "aggregate_groups": [{"id": 3}],
            "errors": []
        }
        yaml_content = "providers:\n  - provider: test1\n  - provider: test2\n"
        
        summary = sync_service._build_changes_summary(gptload_result, yaml_content)
        
        assert "2 standard groups" in summary
        assert "1 aggregate groups" in summary
        assert "2 provider entries" in summary

    def test_build_changes_summary_with_errors(self, sync_service):
        """Test building changes summary with errors."""
        gptload_result = {
            "standard_groups": [{"id": 1}],
            "aggregate_groups": [],
            "errors": ["Error 1", "Error 2"]
        }
        yaml_content = "providers:\n  - provider: test\n"
        
        summary = sync_service._build_changes_summary(gptload_result, yaml_content)
        
        assert "1 standard groups" in summary
        assert "2 errors" in summary
        assert "1 provider entries" in summary

