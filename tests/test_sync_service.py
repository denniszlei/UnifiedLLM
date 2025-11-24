"""Tests for sync service."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from sqlalchemy.orm import Session

from app.services.sync_service import SyncService
from app.services.config_generator import ConfigurationGenerator
from app.services.model_service import ModelService
from app.services.provider_service import ProviderService
from app.models.sync_record import SyncRecord


# Helper to create a mock sync record with proper attributes
def create_mock_sync_record(id=1, status="in_progress", started_at=None, completed_at=None, error_message=None, changes_summary=None):
    """Create a mock sync record with proper attribute access."""
    mock = MagicMock(spec=SyncRecord)
    type(mock).id = PropertyMock(return_value=id)
    type(mock).status = PropertyMock(return_value=status)
    type(mock).started_at = PropertyMock(return_value=started_at or datetime.utcnow())
    type(mock).completed_at = PropertyMock(return_value=completed_at)
    type(mock).error_message = PropertyMock(return_value=error_message)
    type(mock).changes_summary = PropertyMock(return_value=changes_summary)
    return mock


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock(spec=Session)
    return db


@pytest.fixture
def mock_config_generator():
    """Create a mock configuration generator."""
    generator = MagicMock(spec=ConfigurationGenerator)
    return generator


@pytest.fixture
def mock_model_service():
    """Create a mock model service."""
    service = MagicMock(spec=ModelService)
    return service


@pytest.fixture
def mock_provider_service():
    """Create a mock provider service."""
    service = MagicMock(spec=ProviderService)
    return service


@pytest.fixture
def sync_service(mock_config_generator, mock_model_service, mock_provider_service):
    """Create a sync service instance with mocked dependencies."""
    return SyncService(
        config_generator=mock_config_generator,
        model_service=mock_model_service,
        provider_service=mock_provider_service
    )


class TestSyncConfiguration:
    """Tests for sync_configuration method."""

    @pytest.mark.asyncio
    async def test_concurrent_sync_prevention(self, sync_service):
        """Test that concurrent syncs are prevented."""
        # Acquire the lock manually
        await sync_service._sync_lock.acquire()
        
        try:
            # Try to start sync - should raise RuntimeError
            with pytest.raises(RuntimeError, match="already in progress"):
                await sync_service.sync_configuration(MagicMock())
        finally:
            # Release the lock
            sync_service._sync_lock.release()


class TestSyncStatus:
    """Tests for sync status methods."""

    def test_get_sync_status_no_sync(self, sync_service, mock_db):
        """Test getting status when no sync is in progress."""
        result = sync_service.get_sync_status(mock_db)
        assert result is None

    def test_get_sync_status_with_sync(self, sync_service, mock_db):
        """Test getting status when sync is in progress."""
        # Set current sync ID
        sync_service._current_sync_id = 1
        
        # Mock sync record
        mock_sync_record = create_mock_sync_record(id=1, status="in_progress")
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_sync_record
        
        # Get status
        result = sync_service.get_sync_status(mock_db)
        
        # Verify result
        assert result is not None
        assert result["sync_id"] == 1
        assert result["status"] == "in_progress"
        assert "started_at" in result
        assert "duration_seconds" in result

    def test_is_sync_in_progress(self, sync_service):
        """Test checking if sync is in progress."""
        # Initially no sync
        assert not sync_service.is_sync_in_progress()


class TestSyncHistory:
    """Tests for sync history methods."""

    def test_get_sync_history(self, sync_service, mock_db):
        """Test getting sync history."""
        # Mock sync records
        mock_records = [
            create_mock_sync_record(id=3, status="success"),
            create_mock_sync_record(id=2, status="failed"),
            create_mock_sync_record(id=1, status="success")
        ]
        
        mock_db.query.return_value.order_by.return_value.limit.return_value.offset.return_value.all.return_value = mock_records
        
        # Get history
        result = sync_service.get_sync_history(mock_db, limit=10, offset=0)
        
        # Verify result
        assert len(result) == 3
        assert result[0].id == 3  # Most recent first

    def test_get_sync_record(self, sync_service, mock_db):
        """Test getting a specific sync record."""
        # Mock sync record
        mock_record = create_mock_sync_record(id=1, status="success")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_record
        
        # Get record
        result = sync_service.get_sync_record(mock_db, 1)
        
        # Verify result
        assert result is not None
        assert result.id == 1
        assert result.status == "success"

    def test_get_sync_record_not_found(self, sync_service, mock_db):
        """Test getting a non-existent sync record."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Get record
        result = sync_service.get_sync_record(mock_db, 999)
        
        # Verify result
        assert result is None


class TestRetrySync:
    """Tests for retry functionality."""

    @pytest.mark.asyncio
    async def test_retry_non_failed_sync_raises_error(self, sync_service, mock_db):
        """Test that retrying a non-failed sync raises an error."""
        # Mock successful sync record
        success_sync = create_mock_sync_record(id=1, status="success")
        
        mock_db.query.return_value.filter.return_value.first.return_value = success_sync
        
        # Try to retry - should raise ValueError
        with pytest.raises(ValueError, match="not in failed status"):
            await sync_service.retry_failed_sync(mock_db, 1)

    @pytest.mark.asyncio
    async def test_retry_nonexistent_sync_raises_error(self, sync_service, mock_db):
        """Test that retrying a non-existent sync raises an error."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Try to retry - should raise ValueError
        with pytest.raises(ValueError, match="not found"):
            await sync_service.retry_failed_sync(mock_db, 999)


class TestBuildChangesSummary:
    """Tests for _build_changes_summary method."""

    def test_build_changes_summary_success(self, sync_service):
        """Test building changes summary for successful sync."""
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

