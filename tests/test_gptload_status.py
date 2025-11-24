"""Tests for GPT-Load status endpoint."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.database import Base, get_db
from app.services.gptload_client import GPTLoadClient


@pytest.fixture
def test_db():
    """Create a test database."""
    from sqlalchemy import event
    
    engine = create_engine("sqlite:///:memory:")
    
    # Enable foreign key constraints for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture
def client(test_db):
    """Create test client with test database."""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gptload_status_connected(client):
    """Test GPT-Load status endpoint when connected."""
    # Mock GPTLoadClient
    with patch('app.api.gptload.GPTLoadClient') as mock_client_class:
        # Create mock instance
        mock_client = AsyncMock()
        mock_client.health_check = AsyncMock(return_value=True)
        mock_client.list_groups = AsyncMock(return_value=[
            {"id": 1, "name": "group1"},
            {"id": 2, "name": "group2"},
            {"id": 3, "name": "group3"}
        ])
        
        # Setup context manager
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client
        
        # Make request
        response = client.get("/api/gptload/status")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["group_count"] == 3
        assert data["error_message"] is None
        assert "url" in data


@pytest.mark.asyncio
async def test_gptload_status_disconnected(client):
    """Test GPT-Load status endpoint when disconnected."""
    # Mock GPTLoadClient to raise exception
    with patch('app.api.gptload.GPTLoadClient') as mock_client_class:
        # Create mock instance that raises exception
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client_class.return_value = mock_client
        
        # Make request
        response = client.get("/api/gptload/status")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["group_count"] == 0
        assert data["error_message"] is not None
        assert "url" in data


@pytest.mark.asyncio
async def test_gptload_status_unhealthy(client):
    """Test GPT-Load status endpoint when service is unhealthy."""
    # Mock GPTLoadClient
    with patch('app.api.gptload.GPTLoadClient') as mock_client_class:
        # Create mock instance
        mock_client = AsyncMock()
        mock_client.health_check = AsyncMock(return_value=False)
        
        # Setup context manager
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = mock_client
        
        # Make request
        response = client.get("/api/gptload/status")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["group_count"] == 0
        assert data["error_message"] == "GPT-Load service is not responding"
