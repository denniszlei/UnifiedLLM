"""GPT-Load API client for managing groups and keys."""

import logging
from typing import List, Dict, Optional, Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings

logger = logging.getLogger(__name__)


class GPTLoadClient:
    """Client for interacting with GPT-Load REST API."""

    def __init__(self, base_url: Optional[str] = None, auth_key: Optional[str] = None):
        """Initialize GPT-Load client.
        
        Args:
            base_url: GPT-Load base URL (defaults to settings.gptload_url).
            auth_key: GPT-Load authentication key (defaults to settings.gptload_auth_key).
        """
        self.base_url = (base_url or settings.gptload_url).rstrip('/')
        self.auth_key = auth_key or settings.gptload_auth_key
        
        if not self.auth_key:
            logger.warning("GPT-Load auth key not configured")
        else:
            logger.info(f"GPT-Load client initialized with auth key: {self.auth_key[:8]}...")
        
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        headers = {"Content-Type": "application/json"}
        
        # Add authentication header if auth key is configured
        if self.auth_key:
            headers["X-Api-Key"] = self.auth_key
            logger.info(f"Setting X-Api-Key header: {self.auth_key[:8]}...")
        else:
            logger.warning("No auth key available when creating client")
        
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
            headers=headers
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client.
        
        Returns:
            HTTP client instance.
            
        Raises:
            RuntimeError: If client is not initialized (use async context manager).
        """
        if self._client is None:
            raise RuntimeError("GPTLoadClient must be used as async context manager")
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to GPT-Load API with retry logic.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: API endpoint path.
            json_data: JSON request body (optional).
            params: Query parameters (optional).
            
        Returns:
            Response JSON data.
            
        Raises:
            httpx.HTTPError: If request fails after retries.
            ValueError: If response format is invalid.
        """
        client = self._get_client()
        
        try:
            response = await client.request(
                method=method,
                url=endpoint,
                json=json_data,
                params=params
            )
            
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            
            # GPT-Load returns {code: 0, message: "...", data: {...}}
            # or error format {code: "ERROR_CODE", message: "..."}
            if isinstance(data, dict):
                if data.get("code") == 0:
                    # Success response
                    return data.get("data", {})
                elif "code" in data and data["code"] != 0:
                    # Error response
                    error_msg = data.get("message", "Unknown error")
                    logger.error(f"GPT-Load API error: {error_msg}")
                    raise ValueError(f"GPT-Load API error: {error_msg}")
            
            # If response doesn't match expected format, return as-is
            return data
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {method} {endpoint}: {e.response.text}")
            raise
        except httpx.TimeoutException:
            logger.error(f"Timeout for {method} {endpoint}")
            raise
        except httpx.NetworkError as e:
            logger.error(f"Network error for {method} {endpoint}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error for {method} {endpoint}: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if GPT-Load service is healthy.
        
        Returns:
            True if service is healthy, False otherwise.
        """
        try:
            await self._make_request("GET", "/health")
            return True
        except Exception as e:
            logger.error(f"GPT-Load health check failed: {e}")
            return False

    async def list_groups(self) -> List[Dict[str, Any]]:
        """List all groups.
        
        Returns:
            List of group dictionaries.
            
        Raises:
            httpx.HTTPError: If request fails.
        """
        return await self._make_request("GET", "/api/groups")

    async def get_group(self, group_id: int) -> Dict[str, Any]:
        """Get a specific group by ID.
        
        Args:
            group_id: Group ID.
            
        Returns:
            Group dictionary.
            
        Raises:
            httpx.HTTPError: If request fails.
        """
        groups = await self.list_groups()
        for group in groups:
            if group.get("id") == group_id:
                return group
        raise ValueError(f"Group {group_id} not found")


    async def create_group(self, group_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new group (standard or aggregate).
        
        Args:
            group_config: Group configuration dictionary.
            
        Returns:
            Created group dictionary with ID.
            
        Raises:
            httpx.HTTPError: If request fails.
            ValueError: If group creation fails.
        """
        logger.info(f"Creating group: {group_config.get('name')}")
        result = await self._make_request("POST", "/api/groups", json_data=group_config)
        logger.info(f"Group created successfully: {result.get('id')}")
        return result

    async def update_group(self, group_id: int, group_config: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing group.
        
        Args:
            group_id: Group ID to update.
            group_config: Updated group configuration.
            
        Returns:
            Updated group dictionary.
            
        Raises:
            httpx.HTTPError: If request fails.
        """
        logger.info(f"Updating group {group_id}")
        result = await self._make_request("PUT", f"/api/groups/{group_id}", json_data=group_config)
        logger.info(f"Group {group_id} updated successfully")
        return result

    async def delete_group(self, group_id: int) -> None:
        """Delete a group and all its keys.
        
        Args:
            group_id: Group ID to delete.
            
        Raises:
            httpx.HTTPError: If request fails.
        """
        logger.info(f"Deleting group {group_id}")
        await self._make_request("DELETE", f"/api/groups/{group_id}")
        logger.info(f"Group {group_id} deleted successfully")

    async def get_sub_groups(self, aggregate_group_id: int) -> List[Dict[str, Any]]:
        """Get sub-groups of an aggregate group.
        
        Args:
            aggregate_group_id: Aggregate group ID.
            
        Returns:
            List of sub-group dictionaries.
            
        Raises:
            httpx.HTTPError: If request fails.
        """
        return await self._make_request("GET", f"/api/groups/{aggregate_group_id}/sub-groups")

    async def add_sub_groups(
        self,
        aggregate_group_id: int,
        sub_groups: List[Dict[str, Any]]
    ) -> None:
        """Add sub-groups to an aggregate group.
        
        Args:
            aggregate_group_id: Aggregate group ID.
            sub_groups: List of sub-group configurations with group_id and weight.
                Example: [{"group_id": 2, "weight": 10}, {"group_id": 3, "weight": 20}]
            
        Raises:
            httpx.HTTPError: If request fails.
        """
        logger.info(f"Adding {len(sub_groups)} sub-groups to aggregate group {aggregate_group_id}")
        await self._make_request(
            "POST",
            f"/api/groups/{aggregate_group_id}/sub-groups",
            json_data={"sub_groups": sub_groups}
        )
        logger.info(f"Sub-groups added successfully to aggregate group {aggregate_group_id}")

    async def delete_sub_group(self, aggregate_group_id: int, sub_group_id: int) -> None:
        """Remove a sub-group from an aggregate group.
        
        Args:
            aggregate_group_id: Aggregate group ID.
            sub_group_id: Sub-group ID to remove.
            
        Raises:
            httpx.HTTPError: If request fails.
        """
        logger.info(f"Removing sub-group {sub_group_id} from aggregate group {aggregate_group_id}")
        await self._make_request(
            "DELETE",
            f"/api/groups/{aggregate_group_id}/sub-groups/{sub_group_id}"
        )
        logger.info(f"Sub-group {sub_group_id} removed from aggregate group {aggregate_group_id}")

    async def add_keys_to_group(self, group_id: int, keys: List[str]) -> Dict[str, Any]:
        """Add multiple API keys to a group.
        
        Args:
            group_id: Group ID.
            keys: List of API key strings.
            
        Returns:
            Result dictionary with added count.
            
        Raises:
            httpx.HTTPError: If request fails.
        """
        keys_text = "\n".join(keys)
        logger.info(f"Adding {len(keys)} keys to group {group_id}")
        result = await self._make_request(
            "POST",
            "/api/keys/add-multiple",
            json_data={"group_id": group_id, "keys_text": keys_text}
        )
        logger.info(f"Keys added successfully to group {group_id}")
        return result

    async def list_keys(
        self,
        group_id: int,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """List keys in a group.
        
        Args:
            group_id: Group ID.
            status: Optional status filter ("active", "invalid").
            
        Returns:
            Dictionary with keys list and pagination info.
            
        Raises:
            httpx.HTTPError: If request fails.
        """
        params = {"group_id": group_id}
        if status:
            params["status"] = status
        
        return await self._make_request("GET", "/api/keys", params=params)

    async def delete_keys_from_group(self, group_id: int, keys: List[str]) -> Dict[str, Any]:
        """Delete multiple API keys from a group.
        
        Args:
            group_id: Group ID.
            keys: List of API key strings to delete.
            
        Returns:
            Result dictionary with deleted count.
            
        Raises:
            httpx.HTTPError: If request fails.
        """
        keys_text = "\n".join(keys)
        logger.info(f"Deleting {len(keys)} keys from group {group_id}")
        result = await self._make_request(
            "POST",
            "/api/keys/delete-multiple",
            json_data={"group_id": group_id, "keys_text": keys_text}
        )
        logger.info(f"Keys deleted successfully from group {group_id}")
        return result

    async def get_parent_aggregate_groups(self, group_id: int) -> List[Dict[str, Any]]:
        """Get aggregate groups that include this group as a sub-group.
        
        Args:
            group_id: Standard group ID.
            
        Returns:
            List of parent aggregate group dictionaries.
            
        Raises:
            httpx.HTTPError: If request fails.
        """
        return await self._make_request("GET", f"/api/groups/{group_id}/parent-aggregate-groups")


    async def create_standard_group(
        self,
        name: str,
        display_name: str,
        channel_type: str,
        upstream_url: str,
        model_redirect_rules: Dict[str, str],
        test_model: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a standard group with model redirect rules.
        
        Args:
            name: Group name (must be unique, alphanumeric with dashes/underscores).
            display_name: Human-readable display name.
            channel_type: Channel type (openai, anthropic, gemini, etc.).
            upstream_url: Provider base URL (without path suffix).
            model_redirect_rules: Dictionary mapping normalized names to original provider names.
                Example: {"gpt-4": "gpt-4-turbo-preview"}
            test_model: Model to use for validation (optional).
            description: Group description (optional).
            
        Returns:
            Created group dictionary with ID.
            
        Raises:
            httpx.HTTPError: If request fails.
            ValueError: If group creation fails.
        """
        # Sanitize group name - convert dots to dashes
        sanitized_name = name.replace(".", "-")
        
        # Build group configuration
        group_config = {
            "name": sanitized_name,
            "display_name": display_name,
            "group_type": "standard",
            "channel_type": channel_type,
            "upstreams": [
                {
                    "url": upstream_url.rstrip('/'),  # Remove trailing slash
                    "weight": 10
                }
            ],
            "model_redirect_rules": model_redirect_rules,
            "model_redirect_strict": True,  # Only allow models in redirect rules
            "validation_endpoint": "/v1/chat/completions"
        }
        
        if test_model:
            group_config["test_model"] = test_model
        
        if description:
            group_config["description"] = description
        
        logger.info(f"Creating standard group '{sanitized_name}' with {len(model_redirect_rules)} model mappings")
        return await self.create_group(group_config)


    async def create_aggregate_group(
        self,
        name: str,
        display_name: str,
        channel_type: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an aggregate group for load balancing across multiple standard groups.
        
        Args:
            name: Group name (must be unique, alphanumeric with dashes/underscores).
            display_name: Human-readable display name.
            channel_type: Channel type (openai, anthropic, gemini, etc.).
            description: Group description (optional).
            
        Returns:
            Created aggregate group dictionary with ID.
            
        Raises:
            httpx.HTTPError: If request fails.
            ValueError: If group creation fails.
        """
        # Sanitize group name - convert dots to dashes
        sanitized_name = name.replace(".", "-")
        
        # Build aggregate group configuration
        group_config = {
            "name": sanitized_name,
            "display_name": display_name,
            "group_type": "aggregate",
            "channel_type": channel_type,
            "test_model": "-"  # Always "-" for aggregate groups
        }
        
        if description:
            group_config["description"] = description
        
        logger.info(f"Creating aggregate group '{sanitized_name}'")
        return await self.create_group(group_config)

    async def add_sub_groups_with_equal_weights(
        self,
        aggregate_group_id: int,
        standard_group_ids: List[int],
        weight: int = 10
    ) -> None:
        """Add multiple standard groups to an aggregate group with equal weights.
        
        Args:
            aggregate_group_id: Aggregate group ID.
            standard_group_ids: List of standard group IDs to add as sub-groups.
            weight: Weight for each sub-group (default: 10).
            
        Raises:
            httpx.HTTPError: If request fails.
        """
        sub_groups = [
            {"group_id": group_id, "weight": weight}
            for group_id in standard_group_ids
        ]
        
        await self.add_sub_groups(aggregate_group_id, sub_groups)

    async def cleanup_empty_aggregate_group(self, aggregate_group_id: int) -> bool:
        """Delete an aggregate group if it has no sub-groups.
        
        Args:
            aggregate_group_id: Aggregate group ID to check and potentially delete.
            
        Returns:
            True if group was deleted, False if it has sub-groups.
            
        Raises:
            httpx.HTTPError: If request fails.
        """
        try:
            sub_groups = await self.get_sub_groups(aggregate_group_id)
            
            if not sub_groups or len(sub_groups) == 0:
                logger.info(f"Aggregate group {aggregate_group_id} is empty, deleting")
                await self.delete_group(aggregate_group_id)
                return True
            else:
                logger.info(f"Aggregate group {aggregate_group_id} has {len(sub_groups)} sub-groups, keeping")
                return False
                
        except Exception as e:
            logger.error(f"Error checking/cleaning up aggregate group {aggregate_group_id}: {e}")
            raise


    async def delete_standard_group_with_cascade(self, standard_group_id: int) -> Dict[str, Any]:
        """Delete a standard group and update affected aggregate groups.
        
        This method:
        1. Finds all aggregate groups that include this standard group
        2. Removes the standard group from those aggregates
        3. Deletes empty aggregate groups
        4. Deletes the standard group itself
        
        Args:
            standard_group_id: Standard group ID to delete.
            
        Returns:
            Dictionary with deletion summary:
                - deleted_group_id: The deleted standard group ID
                - updated_aggregates: List of aggregate group IDs that were updated
                - deleted_aggregates: List of aggregate group IDs that were deleted
            
        Raises:
            httpx.HTTPError: If request fails.
        """
        logger.info(f"Starting cascade deletion for standard group {standard_group_id}")
        
        # Find parent aggregate groups
        try:
            parent_aggregates = await self.get_parent_aggregate_groups(standard_group_id)
        except Exception as e:
            logger.warning(f"Could not get parent aggregates for group {standard_group_id}: {e}")
            parent_aggregates = []
        
        updated_aggregates = []
        deleted_aggregates = []
        
        # Remove from each parent aggregate
        for parent in parent_aggregates:
            aggregate_id = parent.get("group_id")
            if aggregate_id:
                try:
                    logger.info(f"Removing standard group {standard_group_id} from aggregate {aggregate_id}")
                    await self.delete_sub_group(aggregate_id, standard_group_id)
                    updated_aggregates.append(aggregate_id)
                    
                    # Check if aggregate is now empty and delete if so
                    was_deleted = await self.cleanup_empty_aggregate_group(aggregate_id)
                    if was_deleted:
                        deleted_aggregates.append(aggregate_id)
                        updated_aggregates.remove(aggregate_id)  # Move from updated to deleted
                        
                except Exception as e:
                    logger.error(f"Error updating aggregate group {aggregate_id}: {e}")
                    # Continue with other aggregates
        
        # Delete the standard group itself
        logger.info(f"Deleting standard group {standard_group_id}")
        await self.delete_group(standard_group_id)
        
        result = {
            "deleted_group_id": standard_group_id,
            "updated_aggregates": updated_aggregates,
            "deleted_aggregates": deleted_aggregates
        }
        
        logger.info(f"Cascade deletion complete: {result}")
        return result

    async def delete_aggregate_group_with_cascade(self, aggregate_group_id: int) -> Dict[str, Any]:
        """Delete an aggregate group (does not delete sub-groups).
        
        Args:
            aggregate_group_id: Aggregate group ID to delete.
            
        Returns:
            Dictionary with deletion summary:
                - deleted_group_id: The deleted aggregate group ID
                - sub_group_count: Number of sub-groups that were in the aggregate
            
        Raises:
            httpx.HTTPError: If request fails.
        """
        logger.info(f"Deleting aggregate group {aggregate_group_id}")
        
        # Get sub-groups for logging
        try:
            sub_groups = await self.get_sub_groups(aggregate_group_id)
            sub_group_count = len(sub_groups) if sub_groups else 0
        except Exception as e:
            logger.warning(f"Could not get sub-groups for aggregate {aggregate_group_id}: {e}")
            sub_group_count = 0
        
        # Delete the aggregate group
        await self.delete_group(aggregate_group_id)
        
        result = {
            "deleted_group_id": aggregate_group_id,
            "sub_group_count": sub_group_count
        }
        
        logger.info(f"Aggregate group deletion complete: {result}")
        return result
