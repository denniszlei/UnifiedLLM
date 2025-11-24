"""Tests for GPT-Load client."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.gptload_client import GPTLoadClient


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx client."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


@pytest.fixture
async def gptload_client():
    """Create a GPT-Load client instance."""
    client = GPTLoadClient(base_url="http://test-gptload:3001", auth_key="test-auth-key")
    async with client:
        yield client


class TestGPTLoadClient:
    """Test GPT-Load client functionality."""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initialization with custom settings."""
        client = GPTLoadClient(base_url="http://custom:3001", auth_key="custom-key")
        assert client.base_url == "http://custom:3001"
        assert client.auth_key == "custom-key"

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test client can be used as async context manager."""
        client = GPTLoadClient(base_url="http://test:3001", auth_key="test-key")
        
        async with client:
            assert client._client is not None
        
        assert client._client is None

    @pytest.mark.asyncio
    async def test_health_check_success(self, gptload_client, mock_httpx_client):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "message": "OK", "data": {"status": "healthy"}}
        mock_httpx_client.request.return_value = mock_response
        
        gptload_client._client = mock_httpx_client
        
        result = await gptload_client.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, gptload_client, mock_httpx_client):
        """Test health check failure."""
        mock_httpx_client.request.side_effect = httpx.RequestError("Connection failed")
        gptload_client._client = mock_httpx_client
        
        result = await gptload_client.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_create_group_success(self, gptload_client, mock_httpx_client):
        """Test successful group creation."""
        group_config = {
            "name": "test-group",
            "group_type": "standard",
            "channel_type": "openai"
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "message": "Success",
            "data": {"id": 1, **group_config}
        }
        mock_httpx_client.request.return_value = mock_response
        
        gptload_client._client = mock_httpx_client
        
        result = await gptload_client.create_group(group_config)
        assert result["id"] == 1
        assert result["name"] == "test-group"

    @pytest.mark.asyncio
    async def test_list_groups(self, gptload_client, mock_httpx_client):
        """Test listing groups."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "message": "Success",
            "data": [
                {"id": 1, "name": "group1"},
                {"id": 2, "name": "group2"}
            ]
        }
        mock_httpx_client.request.return_value = mock_response
        
        gptload_client._client = mock_httpx_client
        
        result = await gptload_client.list_groups()
        assert len(result) == 2
        assert result[0]["name"] == "group1"

    @pytest.mark.asyncio
    async def test_add_keys_to_group(self, gptload_client, mock_httpx_client):
        """Test adding keys to a group."""
        keys = ["sk-key1", "sk-key2", "sk-key3"]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "message": "Success",
            "data": {"added": 3}
        }
        mock_httpx_client.request.return_value = mock_response
        
        gptload_client._client = mock_httpx_client
        
        result = await gptload_client.add_keys_to_group(1, keys)
        assert result["added"] == 3

    @pytest.mark.asyncio
    async def test_add_sub_groups(self, gptload_client, mock_httpx_client):
        """Test adding sub-groups to aggregate group."""
        sub_groups = [
            {"group_id": 2, "weight": 10},
            {"group_id": 3, "weight": 20}
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "message": "Success", "data": {}}
        mock_httpx_client.request.return_value = mock_response
        
        gptload_client._client = mock_httpx_client
        
        await gptload_client.add_sub_groups(1, sub_groups)
        
        # Verify the request was made with correct data
        mock_httpx_client.request.assert_called_once()
        call_args = mock_httpx_client.request.call_args
        assert call_args[1]["json"]["sub_groups"] == sub_groups

    @pytest.mark.asyncio
    async def test_delete_group(self, gptload_client, mock_httpx_client):
        """Test deleting a group."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "message": "Success", "data": {}}
        mock_httpx_client.request.return_value = mock_response
        
        gptload_client._client = mock_httpx_client
        
        await gptload_client.delete_group(1)
        
        # Verify DELETE request was made
        mock_httpx_client.request.assert_called_once()
        call_args = mock_httpx_client.request.call_args
        assert call_args[1]["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_error_response_handling(self, gptload_client, mock_httpx_client):
        """Test handling of error responses from GPT-Load."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": "VALIDATION_ERROR",
            "message": "Invalid group configuration"
        }
        mock_httpx_client.request.return_value = mock_response
        
        gptload_client._client = mock_httpx_client
        
        with pytest.raises(ValueError, match="Invalid group configuration"):
            await gptload_client.create_group({"name": "test"})


    @pytest.mark.asyncio
    async def test_create_standard_group(self, gptload_client, mock_httpx_client):
        """Test creating a standard group with model redirect rules."""
        model_redirect_rules = {
            "gpt-4": "gpt-4-turbo-preview",
            "gpt-3.5": "gpt-3.5-turbo"
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "message": "Success",
            "data": {
                "id": 1,
                "name": "provider-a-standard",
                "display_name": "Provider A Standard",
                "group_type": "standard",
                "model_redirect_strict": True,
                "model_redirect_rules": model_redirect_rules
            }
        }
        mock_httpx_client.request.return_value = mock_response
        
        gptload_client._client = mock_httpx_client
        
        result = await gptload_client.create_standard_group(
            name="provider-a-standard",
            display_name="Provider A Standard",
            channel_type="openai",
            upstream_url="https://api.provider-a.com",
            model_redirect_rules=model_redirect_rules,
            test_model="gpt-4"
        )
        
        assert result["id"] == 1
        assert result["model_redirect_strict"] is True
        assert result["model_redirect_rules"] == model_redirect_rules
        
        # Verify the request was made with correct configuration
        call_args = mock_httpx_client.request.call_args
        json_data = call_args[1]["json"]
        assert json_data["model_redirect_strict"] is True
        assert json_data["upstreams"][0]["url"] == "https://api.provider-a.com"

    @pytest.mark.asyncio
    async def test_create_standard_group_sanitizes_name(self, gptload_client, mock_httpx_client):
        """Test that group names with dots are sanitized to dashes."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "message": "Success",
            "data": {"id": 1, "name": "provider-a-0-deepseek-v3-1"}
        }
        mock_httpx_client.request.return_value = mock_response
        
        gptload_client._client = mock_httpx_client
        
        await gptload_client.create_standard_group(
            name="provider.a.0.deepseek.v3.1",
            display_name="Provider A - deepseek v3.1",
            channel_type="openai",
            upstream_url="https://api.provider-a.com",
            model_redirect_rules={"deepseek-v3.1": "deepseek-v3.1-preview"}
        )
        
        # Verify the name was sanitized
        call_args = mock_httpx_client.request.call_args
        json_data = call_args[1]["json"]
        assert json_data["name"] == "provider-a-0-deepseek-v3-1"


    @pytest.mark.asyncio
    async def test_add_keys_to_group_error_handling(self, gptload_client, mock_httpx_client):
        """Test error handling when adding keys to a group."""
        keys = ["sk-key1", "sk-key2"]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": "VALIDATION_ERROR",
            "message": "Invalid group ID"
        }
        mock_httpx_client.request.return_value = mock_response
        
        gptload_client._client = mock_httpx_client
        
        with pytest.raises(ValueError, match="Invalid group ID"):
            await gptload_client.add_keys_to_group(999, keys)

    @pytest.mark.asyncio
    async def test_add_keys_formats_correctly(self, gptload_client, mock_httpx_client):
        """Test that keys are formatted correctly as newline-separated text."""
        keys = ["sk-key1", "sk-key2", "sk-key3"]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "message": "Success",
            "data": {"added": 3}
        }
        mock_httpx_client.request.return_value = mock_response
        
        gptload_client._client = mock_httpx_client
        
        await gptload_client.add_keys_to_group(1, keys)
        
        # Verify keys are formatted as newline-separated text
        call_args = mock_httpx_client.request.call_args
        json_data = call_args[1]["json"]
        assert json_data["keys_text"] == "sk-key1\nsk-key2\nsk-key3"
        assert json_data["group_id"] == 1


    @pytest.mark.asyncio
    async def test_create_aggregate_group(self, gptload_client, mock_httpx_client):
        """Test creating an aggregate group."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "message": "Success",
            "data": {
                "id": 10,
                "name": "gpt-4-aggregate",
                "display_name": "GPT-4 Aggregate",
                "group_type": "aggregate",
                "test_model": "-"
            }
        }
        mock_httpx_client.request.return_value = mock_response
        
        gptload_client._client = mock_httpx_client
        
        result = await gptload_client.create_aggregate_group(
            name="gpt-4-aggregate",
            display_name="GPT-4 Aggregate",
            channel_type="openai",
            description="Aggregate group for GPT-4 models"
        )
        
        assert result["id"] == 10
        assert result["group_type"] == "aggregate"
        assert result["test_model"] == "-"
        
        # Verify the request configuration
        call_args = mock_httpx_client.request.call_args
        json_data = call_args[1]["json"]
        assert json_data["group_type"] == "aggregate"
        assert json_data["test_model"] == "-"

    @pytest.mark.asyncio
    async def test_add_sub_groups_with_equal_weights(self, gptload_client, mock_httpx_client):
        """Test adding sub-groups with equal weights."""
        standard_group_ids = [2, 3, 4]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "message": "Success", "data": {}}
        mock_httpx_client.request.return_value = mock_response
        
        gptload_client._client = mock_httpx_client
        
        await gptload_client.add_sub_groups_with_equal_weights(1, standard_group_ids, weight=15)
        
        # Verify all groups were added with equal weights
        call_args = mock_httpx_client.request.call_args
        json_data = call_args[1]["json"]
        sub_groups = json_data["sub_groups"]
        
        assert len(sub_groups) == 3
        assert all(sg["weight"] == 15 for sg in sub_groups)
        assert [sg["group_id"] for sg in sub_groups] == [2, 3, 4]

    @pytest.mark.asyncio
    async def test_cleanup_empty_aggregate_group_deletes(self, gptload_client, mock_httpx_client):
        """Test that empty aggregate groups are deleted."""
        # Mock get_sub_groups to return empty list
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"code": 0, "message": "Success", "data": []}
        
        # Mock delete_group
        mock_delete_response = MagicMock()
        mock_delete_response.status_code = 200
        mock_delete_response.json.return_value = {"code": 0, "message": "Success", "data": {}}
        
        mock_httpx_client.request.side_effect = [mock_get_response, mock_delete_response]
        gptload_client._client = mock_httpx_client
        
        result = await gptload_client.cleanup_empty_aggregate_group(1)
        
        assert result is True
        assert mock_httpx_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_cleanup_aggregate_group_with_subgroups_keeps(self, gptload_client, mock_httpx_client):
        """Test that aggregate groups with sub-groups are not deleted."""
        # Mock get_sub_groups to return non-empty list
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": 0,
            "message": "Success",
            "data": [
                {"group": {"id": 2}, "weight": 10},
                {"group": {"id": 3}, "weight": 10}
            ]
        }
        mock_httpx_client.request.return_value = mock_response
        
        gptload_client._client = mock_httpx_client
        
        result = await gptload_client.cleanup_empty_aggregate_group(1)
        
        assert result is False
        # Only get_sub_groups should be called, not delete
        assert mock_httpx_client.request.call_count == 1


    @pytest.mark.asyncio
    async def test_delete_standard_group_with_cascade(self, gptload_client, mock_httpx_client):
        """Test cascade deletion of standard group updates aggregate groups."""
        # Mock sequence of responses:
        # 1. get_parent_aggregate_groups
        # 2. delete_sub_group
        # 3. get_sub_groups (for cleanup check)
        # 4. delete_group (aggregate is empty)
        # 5. delete_group (standard group)
        
        mock_responses = [
            # get_parent_aggregate_groups
            MagicMock(
                status_code=200,
                json=lambda: {
                    "code": 0,
                    "data": [{"group_id": 10, "name": "aggregate-1"}]
                }
            ),
            # delete_sub_group
            MagicMock(
                status_code=200,
                json=lambda: {"code": 0, "data": {}}
            ),
            # get_sub_groups (empty)
            MagicMock(
                status_code=200,
                json=lambda: {"code": 0, "data": []}
            ),
            # delete_group (aggregate)
            MagicMock(
                status_code=200,
                json=lambda: {"code": 0, "data": {}}
            ),
            # delete_group (standard)
            MagicMock(
                status_code=200,
                json=lambda: {"code": 0, "data": {}}
            )
        ]
        
        mock_httpx_client.request.side_effect = mock_responses
        gptload_client._client = mock_httpx_client
        
        result = await gptload_client.delete_standard_group_with_cascade(2)
        
        assert result["deleted_group_id"] == 2
        assert result["deleted_aggregates"] == [10]
        assert result["updated_aggregates"] == []

    @pytest.mark.asyncio
    async def test_delete_standard_group_updates_but_keeps_aggregate(self, gptload_client, mock_httpx_client):
        """Test cascade deletion keeps aggregate groups that still have sub-groups."""
        # Mock sequence where aggregate still has other sub-groups
        mock_responses = [
            # get_parent_aggregate_groups
            MagicMock(
                status_code=200,
                json=lambda: {
                    "code": 0,
                    "data": [{"group_id": 10, "name": "aggregate-1"}]
                }
            ),
            # delete_sub_group
            MagicMock(
                status_code=200,
                json=lambda: {"code": 0, "data": {}}
            ),
            # get_sub_groups (still has other groups)
            MagicMock(
                status_code=200,
                json=lambda: {
                    "code": 0,
                    "data": [{"group": {"id": 3}, "weight": 10}]
                }
            ),
            # delete_group (standard)
            MagicMock(
                status_code=200,
                json=lambda: {"code": 0, "data": {}}
            )
        ]
        
        mock_httpx_client.request.side_effect = mock_responses
        gptload_client._client = mock_httpx_client
        
        result = await gptload_client.delete_standard_group_with_cascade(2)
        
        assert result["deleted_group_id"] == 2
        assert result["updated_aggregates"] == [10]
        assert result["deleted_aggregates"] == []

    @pytest.mark.asyncio
    async def test_delete_aggregate_group_with_cascade(self, gptload_client, mock_httpx_client):
        """Test deletion of aggregate group."""
        mock_responses = [
            # get_sub_groups
            MagicMock(
                status_code=200,
                json=lambda: {
                    "code": 0,
                    "data": [
                        {"group": {"id": 2}, "weight": 10},
                        {"group": {"id": 3}, "weight": 10}
                    ]
                }
            ),
            # delete_group
            MagicMock(
                status_code=200,
                json=lambda: {"code": 0, "data": {}}
            )
        ]
        
        mock_httpx_client.request.side_effect = mock_responses
        gptload_client._client = mock_httpx_client
        
        result = await gptload_client.delete_aggregate_group_with_cascade(10)
        
        assert result["deleted_group_id"] == 10
        assert result["sub_group_count"] == 2
