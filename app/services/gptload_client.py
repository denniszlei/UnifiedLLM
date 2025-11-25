"""GPT-Load API client for managing groups and keys."""

import logging
from typing import List, Dict, Optional, Any, Tuple
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


    # ========================================================================
    # Two-Step Sync Methods (Ported from Reference Implementation)
    # ========================================================================

    async def sync_config_step1(
        self,
        split_groups: List[Any]  # List of SplitGroup from provider_splitter
    ) -> Dict[str, Any]:
        """Step 1: Create all standard groups and return ID mappings.
        
        This is the first step of the two-step sync process. It creates all
        standard groups and returns mappings needed for step 2.
        
        Args:
            split_groups: List of SplitGroup configurations (standard groups only).
            
        Returns:
            Dictionary with:
                - group_name_to_id: Mapping of group names to GPT-Load IDs
                - group_name_to_apikey: Mapping of group names to API keys
                - success: Boolean indicating if all groups were created
                - message: Summary message
                - errors: List of error messages (if any)
        """
        group_name_to_id = {}
        group_name_to_apikey = {}
        errors = []
        
        # Filter to only standard groups
        standard_groups = [g for g in split_groups if g.group_type == 'standard']
        
        logger.info(f"Step 1: Creating {len(standard_groups)} standard groups")
        
        for split_group in standard_groups:
            try:
                # Determine test model (use first model from redirect rules)
                test_model = None
                if split_group.model_redirect_rules:
                    # Use the original model name (value) as test_model
                    test_model = list(split_group.model_redirect_rules.values())[0]
                
                # Create the standard group
                created_group = await self.create_standard_group(
                    name=split_group.group_name,
                    display_name=f"{split_group.provider_name} - {split_group.group_name}",
                    channel_type=split_group.channel_type,
                    upstream_url=split_group.base_url,
                    model_redirect_rules=split_group.model_redirect_rules,
                    test_model=test_model,
                    description=f"Auto-generated group for {split_group.provider_name}"
                )
                
                group_id = created_group.get("id")
                if not group_id:
                    raise ValueError(f"No group ID returned for '{split_group.group_name}'")
                
                # Store mappings
                group_name_to_id[split_group.group_name] = group_id
                group_name_to_apikey[split_group.group_name] = split_group.api_key
                
                logger.info(f"Created standard group: {split_group.group_name} (ID: {group_id})")
                
            except Exception as e:
                error_msg = f"{split_group.group_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Failed to create standard group: {error_msg}")
        
        success = len(errors) == 0
        message = f"Created {len(group_name_to_id)}/{len(standard_groups)} standard groups"
        if errors:
            message += f" ({len(errors)} errors)"
        
        return {
            "group_name_to_id": group_name_to_id,
            "group_name_to_apikey": group_name_to_apikey,
            "success": success,
            "message": message,
            "errors": errors
        }

    async def sync_config_step2(
        self,
        aggregations: Dict[str, List[str]],  # {model_name: [group_names]}
        group_name_to_id: Dict[str, int],
        group_name_to_apikey: Dict[str, str],
        refresh_api_keys: bool = True
    ) -> Dict[str, Any]:
        """Step 2: Add API keys to standard groups and create aggregate groups.
        
        This is the second step of the two-step sync process. It adds API keys
        to the standard groups created in step 1 and creates aggregate groups.
        
        Args:
            aggregations: Mapping of model names to list of group names to aggregate.
            group_name_to_id: Mapping from step 1 (group names to IDs).
            group_name_to_apikey: Mapping from step 1 (group names to API keys).
            refresh_api_keys: Whether to add/refresh API keys (default: True).
            
        Returns:
            Dictionary with:
                - success: Boolean indicating if all operations succeeded
                - message: Summary message
                - errors: List of error messages (if any)
                - keys_added: Number of groups that received API keys
                - aggregates_created: Number of aggregate groups created
        """
        errors = []
        keys_added = 0
        aggregates_created = 0
        
        logger.info(f"Step 2: Adding API keys and creating {len(aggregations)} aggregate groups")
        
        # Add API keys to standard groups
        if refresh_api_keys:
            for group_name, group_id in group_name_to_id.items():
                api_key = group_name_to_apikey.get(group_name, '')
                if not api_key:
                    logger.debug(f"No API key for group {group_name}, skipping")
                    continue
                
                try:
                    await self.add_keys_to_group(group_id, [api_key])
                    keys_added += 1
                    logger.info(f"Added API key to group {group_name} (ID: {group_id})")
                except Exception as e:
                    error_msg = f"Add API key to {group_name}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"Failed to add API key: {error_msg}")
        
        # Create aggregate groups
        for model_name, sub_group_names in aggregations.items():
            try:
                # Sanitize aggregate group name
                from app.services.provider_splitter import ProviderSplitter
                sanitized_model = ProviderSplitter.sanitize_name(model_name)
                aggregate_name = f"aggregate-{sanitized_model}"
                
                # Determine channel type (use first sub-group's channel type)
                # For now, default to openai
                channel_type = "openai"
                
                # Create aggregate group
                created_aggregate = await self.create_aggregate_group(
                    name=aggregate_name,
                    display_name=f"{model_name} (Load Balanced)",
                    channel_type=channel_type,
                    description=f"Aggregate group for {model_name} across {len(sub_group_names)} providers"
                )
                
                aggregate_id = created_aggregate.get("id")
                if not aggregate_id:
                    raise ValueError(f"No group ID returned for aggregate '{aggregate_name}'")
                
                logger.info(f"Created aggregate group: {aggregate_name} (ID: {aggregate_id})")
                
                # Add sub-groups
                sub_group_ids = []
                for sub_name in sub_group_names:
                    if sub_name in group_name_to_id:
                        sub_group_ids.append(group_name_to_id[sub_name])
                    else:
                        logger.warning(f"Sub-group {sub_name} not found in ID mapping, skipping")
                
                if sub_group_ids:
                    await self.add_sub_groups_with_equal_weights(
                        aggregate_id,
                        sub_group_ids,
                        weight=10
                    )
                    logger.info(f"Added {len(sub_group_ids)} sub-groups to aggregate {aggregate_name}")
                
                aggregates_created += 1
                
            except Exception as e:
                error_msg = f"Create aggregate for {model_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Failed to create aggregate: {error_msg}")
        
        success = len(errors) == 0
        message = f"Added keys to {keys_added} groups, created {aggregates_created} aggregates"
        if errors:
            message += f" ({len(errors)} errors)"
        
        return {
            "success": success,
            "message": message,
            "errors": errors,
            "keys_added": keys_added,
            "aggregates_created": aggregates_created
        }

    # ========================================================================
    # Incremental Sync Methods (Ported from Reference Implementation)
    # ========================================================================

    async def get_existing_config(self) -> Dict[str, Any]:
        """Get existing GPT-Load configuration with full details.
        
        Fetches all groups and their sub-groups from GPT-Load API.
        
        Returns:
            Dictionary with:
                - groups: List of all groups with full configuration
                - standard_groups: List of standard groups only
                - aggregate_groups: List of aggregate groups only
                - group_by_name: Dictionary mapping group names to group configs
        """
        logger.info("Fetching existing GPT-Load configuration")
        
        # Get all groups
        groups = await self.list_groups()
        
        # Separate by type
        standard_groups = []
        aggregate_groups = []
        group_by_name = {}
        
        for group in groups:
            group_name = group.get("name")
            group_type = group.get("group_type", "standard")
            
            if group_name:
                group_by_name[group_name] = group
            
            # Fetch sub-groups for aggregate groups
            if group_type == "aggregate":
                group_id = group.get("id")
                if group_id:
                    try:
                        sub_groups = await self.get_sub_groups(group_id)
                        group["sub_groups"] = sub_groups
                    except Exception as e:
                        logger.warning(f"Failed to fetch sub-groups for aggregate {group_name}: {e}")
                        group["sub_groups"] = []
                
                aggregate_groups.append(group)
            else:
                standard_groups.append(group)
        
        logger.info(
            f"Fetched {len(groups)} groups: "
            f"{len(standard_groups)} standard, {len(aggregate_groups)} aggregate"
        )
        
        return {
            "groups": groups,
            "standard_groups": standard_groups,
            "aggregate_groups": aggregate_groups,
            "group_by_name": group_by_name
        }

    def diff_configs(
        self,
        existing_config: Dict[str, Any],
        desired_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare existing and desired configurations with detailed change detection.
        
        This method identifies:
        - Groups to CREATE (new groups not in existing)
        - Groups to UPDATE (existing groups with changed configuration)
        - Groups to DELETE (existing groups not in desired)
        - Orphaned aggregates (aggregates with only 1 sub-group remaining)
        
        Args:
            existing_config: Current configuration from GPT-Load.
            desired_config: Desired configuration to apply.
            
        Returns:
            Dictionary with:
                - to_create_standard: List of standard groups to create
                - to_create_aggregate: List of aggregate groups to create
                - to_update_standard: List of standard groups to update with change details
                - to_update_aggregate: List of aggregate groups to update with change details
                - to_delete_standard: List of standard group names to delete
                - to_delete_aggregate: List of aggregate group names to delete
                - orphaned_aggregates: List of aggregate names with only 1 sub-group
                - summary: Summary statistics
        """
        # Extract groups from configs
        existing_groups = existing_config.get('groups', [])
        existing_by_name = existing_config.get('group_by_name', {})
        
        # If group_by_name not provided, build it
        if not existing_by_name:
            existing_by_name = {g['name']: g for g in existing_groups if g.get('name')}
        
        desired_by_name = desired_config.get('group_by_name', {})
        
        # Separate by type
        existing_standard = {
            name: group for name, group in existing_by_name.items()
            if group.get('group_type', 'standard') == 'standard'
        }
        existing_aggregate = {
            name: group for name, group in existing_by_name.items()
            if group.get('group_type', 'standard') == 'aggregate'
        }
        
        desired_standard = {
            name: group for name, group in desired_by_name.items()
            if group.get('group_type', 'standard') == 'standard'
        }
        desired_aggregate = {
            name: group for name, group in desired_by_name.items()
            if group.get('group_type', 'standard') == 'aggregate'
        }
        
        # Identify standard groups to create
        to_create_standard = [
            group for name, group in desired_standard.items()
            if name not in existing_standard
        ]
        
        # Identify standard groups to delete
        to_delete_standard = [
            name for name in existing_standard.keys()
            if name not in desired_standard
        ]
        
        # Identify standard groups to update
        to_update_standard = []
        for name in desired_standard.keys() & existing_standard.keys():
            existing_group = existing_standard[name]
            desired_group = desired_standard[name]
            
            changes = self._detect_standard_group_changes(existing_group, desired_group)
            if changes:
                to_update_standard.append({
                    'name': name,
                    'group_id': existing_group.get('id'),
                    'existing': existing_group,
                    'desired': desired_group,
                    'changes': changes
                })
        
        # Identify aggregate groups to create
        to_create_aggregate = [
            group for name, group in desired_aggregate.items()
            if name not in existing_aggregate
        ]
        
        # Identify aggregate groups to delete
        to_delete_aggregate = [
            name for name in existing_aggregate.keys()
            if name not in desired_aggregate
        ]
        
        # Identify aggregate groups to update (sub-group membership changes)
        to_update_aggregate = []
        for name in desired_aggregate.keys() & existing_aggregate.keys():
            existing_group = existing_aggregate[name]
            desired_group = desired_aggregate[name]
            
            changes = self._detect_aggregate_group_changes(existing_group, desired_group)
            if changes:
                to_update_aggregate.append({
                    'name': name,
                    'group_id': existing_group.get('id'),
                    'existing': existing_group,
                    'desired': desired_group,
                    'changes': changes
                })
        
        # Identify orphaned aggregates (only 1 sub-group remaining)
        orphaned_aggregates = []
        for name, group in existing_aggregate.items():
            if name in desired_aggregate:
                # Check if desired has only 1 sub-group
                desired_group = desired_aggregate[name]
                sub_group_names = desired_group.get('sub_group_names', [])
                if len(sub_group_names) == 1:
                    orphaned_aggregates.append({
                        'name': name,
                        'group_id': group.get('id'),
                        'remaining_sub_group': sub_group_names[0]
                    })
        
        # Build summary
        summary = {
            'existing_total': len(existing_groups),
            'existing_standard': len(existing_standard),
            'existing_aggregate': len(existing_aggregate),
            'desired_total': len(desired_by_name),
            'desired_standard': len(desired_standard),
            'desired_aggregate': len(desired_aggregate),
            'create_standard': len(to_create_standard),
            'create_aggregate': len(to_create_aggregate),
            'update_standard': len(to_update_standard),
            'update_aggregate': len(to_update_aggregate),
            'delete_standard': len(to_delete_standard),
            'delete_aggregate': len(to_delete_aggregate),
            'orphaned_aggregates': len(orphaned_aggregates),
            'unchanged': (
                len(existing_standard) - len(to_delete_standard) - len(to_update_standard) +
                len(existing_aggregate) - len(to_delete_aggregate) - len(to_update_aggregate)
            )
        }
        
        logger.info(f"Config diff summary: {summary}")
        
        return {
            'to_create_standard': to_create_standard,
            'to_create_aggregate': to_create_aggregate,
            'to_update_standard': to_update_standard,
            'to_update_aggregate': to_update_aggregate,
            'to_delete_standard': to_delete_standard,
            'to_delete_aggregate': to_delete_aggregate,
            'orphaned_aggregates': orphaned_aggregates,
            'summary': summary
        }

    def _detect_standard_group_changes(
        self,
        existing_group: Dict[str, Any],
        desired_group: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Detect changes in a standard group's configuration.
        
        Args:
            existing_group: Existing group configuration.
            desired_group: Desired group configuration.
            
        Returns:
            Dictionary with change details, or None if no changes.
        """
        changes = {}
        
        # Check model_redirect_rules changes
        existing_rules = existing_group.get('model_redirect_rules', {})
        desired_rules = desired_group.get('model_redirect_rules', {})
        
        if existing_rules != desired_rules:
            # Identify added, removed, and changed models
            existing_models = set(existing_rules.keys())
            desired_models = set(desired_rules.keys())
            
            added_models = desired_models - existing_models
            removed_models = existing_models - desired_models
            
            changed_models = []
            for model in existing_models & desired_models:
                if existing_rules[model] != desired_rules[model]:
                    changed_models.append({
                        'model': model,
                        'old_mapping': existing_rules[model],
                        'new_mapping': desired_rules[model]
                    })
            
            changes['model_redirect_rules'] = {
                'added': list(added_models),
                'removed': list(removed_models),
                'changed': changed_models
            }
        
        # Check other fields
        if existing_group.get('channel_type') != desired_group.get('channel_type'):
            changes['channel_type'] = {
                'old': existing_group.get('channel_type'),
                'new': desired_group.get('channel_type')
            }
        
        if existing_group.get('model_redirect_strict') != desired_group.get('model_redirect_strict'):
            changes['model_redirect_strict'] = {
                'old': existing_group.get('model_redirect_strict'),
                'new': desired_group.get('model_redirect_strict')
            }
        
        # Check upstreams
        existing_upstreams = self._normalize_upstreams(existing_group.get('upstreams', []))
        desired_upstreams = self._normalize_upstreams(desired_group.get('upstreams', []))
        
        if existing_upstreams != desired_upstreams:
            changes['upstreams'] = {
                'old': existing_upstreams,
                'new': desired_upstreams
            }
        
        return changes if changes else None

    def _detect_aggregate_group_changes(
        self,
        existing_group: Dict[str, Any],
        desired_group: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Detect changes in an aggregate group's sub-group membership.
        
        Args:
            existing_group: Existing group configuration.
            desired_group: Desired group configuration.
            
        Returns:
            Dictionary with change details, or None if no changes.
        """
        changes = {}
        
        # Extract sub-group names
        existing_subs = set(self._extract_sub_group_names(existing_group))
        desired_subs = set(desired_group.get('sub_group_names', []))
        
        if existing_subs != desired_subs:
            added_subs = desired_subs - existing_subs
            removed_subs = existing_subs - desired_subs
            
            changes['sub_groups'] = {
                'added': list(added_subs),
                'removed': list(removed_subs),
                'existing_count': len(existing_subs),
                'desired_count': len(desired_subs)
            }
        
        return changes if changes else None

    def _need_update(
        self,
        existing_group: Dict[str, Any],
        desired_group: Dict[str, Any]
    ) -> bool:
        """Check if a group needs to be updated.
        
        Args:
            existing_group: Existing group configuration.
            desired_group: Desired group configuration.
            
        Returns:
            True if update is needed, False otherwise.
        """
        # Compare group types
        existing_type = existing_group.get('group_type', 'standard')
        desired_type = desired_group.get('group_type', 'standard')
        
        if existing_type != desired_type:
            return True
        
        # For aggregate groups, compare sub-groups
        if existing_type == 'aggregate':
            existing_subs = sorted(self._extract_sub_group_names(existing_group))
            desired_subs = sorted(self._extract_sub_group_names(desired_group))
            return existing_subs != desired_subs
        
        # For standard groups, compare key fields
        fields_to_compare = [
            'channel_type',
            'model_redirect_rules',
            'model_redirect_strict'
        ]
        
        for field in fields_to_compare:
            if existing_group.get(field) != desired_group.get(field):
                return True
        
        # Compare upstreams (normalize first)
        existing_upstreams = self._normalize_upstreams(
            existing_group.get('upstreams', [])
        )
        desired_upstreams = self._normalize_upstreams(
            desired_group.get('upstreams', [])
        )
        
        return existing_upstreams != desired_upstreams

    def _extract_sub_group_names(self, group: Dict[str, Any]) -> List[str]:
        """Extract sub-group names from a group configuration."""
        sub_groups = group.get('sub_groups', [])
        names = []
        
        for item in sub_groups:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                if 'name' in item:
                    names.append(item['name'])
                elif 'group' in item and isinstance(item['group'], dict):
                    name = item['group'].get('name')
                    if name:
                        names.append(name)
        
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for name in names:
            if name not in seen:
                deduped.append(name)
                seen.add(name)
        
        return deduped

    def _normalize_upstreams(
        self,
        upstreams: List[Dict[str, Any]]
    ) -> List[Tuple[str, int]]:
        """Normalize upstream list for comparison."""
        normalized = []
        for up in upstreams:
            url = up.get('url')
            weight = up.get('weight', 10)
            if url:
                normalized.append((url.rstrip('/'), weight))
        return sorted(normalized)

    async def update_standard_group_models(
        self,
        group_id: int,
        group_name: str,
        new_model_redirect_rules: Dict[str, str],
        channel_type: Optional[str] = None,
        upstream_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update a standard group's model_redirect_rules.
        
        This handles Scenarios A, B, and C:
        - Scenario A: Adding models to model_redirect_rules
        - Scenario B: Removing models from model_redirect_rules
        - Scenario C: Changing normalized names in model_redirect_rules
        
        Args:
            group_id: Group ID to update.
            group_name: Group name (for logging).
            new_model_redirect_rules: New model redirect rules to apply.
            channel_type: Optional channel type to update.
            upstream_url: Optional upstream URL to update.
            
        Returns:
            Updated group dictionary.
            
        Raises:
            httpx.HTTPError: If request fails.
        """
        logger.info(
            f"Updating standard group {group_name} (ID: {group_id}) "
            f"with {len(new_model_redirect_rules)} model mappings"
        )
        
        # Build update payload
        update_payload = {
            "model_redirect_rules": new_model_redirect_rules,
            "model_redirect_strict": True
        }
        
        if channel_type:
            update_payload["channel_type"] = channel_type
        
        if upstream_url:
            update_payload["upstreams"] = [
                {
                    "url": upstream_url.rstrip('/'),
                    "weight": 10
                }
            ]
        
        # Determine test model (use first model from redirect rules)
        if new_model_redirect_rules:
            # Use the original model name (value) as test_model
            update_payload["test_model"] = list(new_model_redirect_rules.values())[0]
        
        # Update the group
        result = await self.update_group(group_id, update_payload)
        
        logger.info(f"Successfully updated standard group {group_name}")
        
        return result

    async def apply_standard_group_updates(
        self,
        updates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Apply updates to multiple standard groups.
        
        Args:
            updates: List of update dictionaries from diff_configs.
                    Each should have: name, group_id, desired, changes
            
        Returns:
            Dictionary with:
                - success: Boolean indicating if all updates succeeded
                - updated_count: Number of groups updated
                - errors: List of error messages
        """
        logger.info(f"Applying updates to {len(updates)} standard groups")
        
        updated_count = 0
        errors = []
        
        for update_info in updates:
            group_name = update_info['name']
            group_id = update_info['group_id']
            desired = update_info['desired']
            
            try:
                # Extract configuration from desired state
                new_rules = desired.get('model_redirect_rules', {})
                channel_type = desired.get('channel_type')
                upstream_url = desired.get('base_url')
                
                # Update the group
                await self.update_standard_group_models(
                    group_id,
                    group_name,
                    new_rules,
                    channel_type,
                    upstream_url
                )
                
                updated_count += 1
                
            except Exception as e:
                error_msg = f"Update {group_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Failed to update standard group: {error_msg}")
        
        success = len(errors) == 0
        
        return {
            "success": success,
            "updated_count": updated_count,
            "errors": errors
        }

    async def remove_standard_group_from_aggregates(
        self,
        standard_group_id: int,
        standard_group_name: str,
        aggregate_group_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Remove a standard group from its parent aggregate groups.
        
        This handles removing a provider from aggregates when:
        - Models are deleted (Scenario B)
        - Normalization changes (Scenario C)
        
        Args:
            standard_group_id: Standard group ID to remove.
            standard_group_name: Standard group name (for logging).
            aggregate_group_ids: Optional list of specific aggregate IDs to remove from.
                                If None, removes from all parent aggregates.
            
        Returns:
            Dictionary with:
                - removed_from: List of aggregate group IDs removed from
                - deleted_aggregates: List of aggregate group IDs that were deleted (orphaned)
                - errors: List of error messages
        """
        logger.info(f"Removing standard group {standard_group_name} from aggregates")
        
        removed_from = []
        deleted_aggregates = []
        errors = []
        
        # Get parent aggregates if not specified
        if aggregate_group_ids is None:
            try:
                parent_aggregates = await self.get_parent_aggregate_groups(standard_group_id)
                aggregate_group_ids = [agg.get('group_id') for agg in parent_aggregates if agg.get('group_id')]
            except Exception as e:
                logger.warning(f"Could not get parent aggregates for {standard_group_name}: {e}")
                aggregate_group_ids = []
        
        # Remove from each aggregate
        for aggregate_id in aggregate_group_ids:
            try:
                # Remove the sub-group
                await self.delete_sub_group(aggregate_id, standard_group_id)
                removed_from.append(aggregate_id)
                logger.info(f"Removed {standard_group_name} from aggregate {aggregate_id}")
                
                # Check if aggregate is now orphaned (only 1 sub-group remaining)
                try:
                    sub_groups = await self.get_sub_groups(aggregate_id)
                    if len(sub_groups) <= 1:
                        logger.info(f"Aggregate {aggregate_id} is orphaned, deleting")
                        await self.delete_group(aggregate_id)
                        deleted_aggregates.append(aggregate_id)
                except Exception as e:
                    logger.error(f"Error checking/deleting orphaned aggregate {aggregate_id}: {e}")
                    errors.append(f"Check orphaned aggregate {aggregate_id}: {str(e)}")
                
            except Exception as e:
                error_msg = f"Remove from aggregate {aggregate_id}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Failed to remove from aggregate: {error_msg}")
        
        return {
            "removed_from": removed_from,
            "deleted_aggregates": deleted_aggregates,
            "errors": errors
        }

    async def cleanup_orphaned_aggregates(
        self,
        orphaned_aggregates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Delete aggregate groups that have only 1 sub-group remaining.
        
        Args:
            orphaned_aggregates: List of orphaned aggregate info from diff_configs.
                                Each should have: name, group_id
            
        Returns:
            Dictionary with:
                - deleted_count: Number of aggregates deleted
                - errors: List of error messages
        """
        logger.info(f"Cleaning up {len(orphaned_aggregates)} orphaned aggregates")
        
        deleted_count = 0
        errors = []
        
        for orphan_info in orphaned_aggregates:
            aggregate_name = orphan_info['name']
            aggregate_id = orphan_info['group_id']
            
            try:
                logger.info(f"Deleting orphaned aggregate {aggregate_name} (ID: {aggregate_id})")
                await self.delete_group(aggregate_id)
                deleted_count += 1
                
            except Exception as e:
                error_msg = f"Delete orphaned aggregate {aggregate_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Failed to delete orphaned aggregate: {error_msg}")
        
        return {
            "deleted_count": deleted_count,
            "errors": errors
        }

    async def recreate_aggregate_group(
        self,
        aggregate_name: str,
        model_name: str,
        sub_group_names: List[str],
        group_name_to_id: Dict[str, int],
        channel_type: str = "openai"
    ) -> Optional[int]:
        """Recreate an aggregate group with new sub-group membership.
        
        Due to GPT-Load API limitations, aggregate groups must be deleted and
        recreated when sub-group membership changes.
        
        Args:
            aggregate_name: Aggregate group name.
            model_name: Model name this aggregate represents.
            sub_group_names: List of sub-group names to include.
            group_name_to_id: Mapping of group names to IDs.
            channel_type: Channel type (default: openai).
            
        Returns:
            Created aggregate group ID, or None if creation failed.
        """
        logger.info(f"Recreating aggregate {aggregate_name} with {len(sub_group_names)} sub-groups")
        
        try:
            # Create the aggregate group
            created_aggregate = await self.create_aggregate_group(
                name=aggregate_name,
                display_name=f"{model_name} (Load Balanced)",
                channel_type=channel_type,
                description=f"Aggregate group for {model_name} across {len(sub_group_names)} providers"
            )
            
            aggregate_id = created_aggregate.get("id")
            if not aggregate_id:
                raise ValueError(f"No group ID returned for aggregate '{aggregate_name}'")
            
            logger.info(f"Created aggregate group: {aggregate_name} (ID: {aggregate_id})")
            
            # Add sub-groups
            sub_group_ids = []
            for sub_name in sub_group_names:
                if sub_name in group_name_to_id:
                    sub_group_ids.append(group_name_to_id[sub_name])
                else:
                    logger.warning(f"Sub-group {sub_name} not found in ID mapping, skipping")
            
            if sub_group_ids:
                await self.add_sub_groups_with_equal_weights(
                    aggregate_id,
                    sub_group_ids,
                    weight=10
                )
                logger.info(f"Added {len(sub_group_ids)} sub-groups to aggregate {aggregate_name}")
            
            return aggregate_id
            
        except Exception as e:
            logger.error(f"Failed to recreate aggregate {aggregate_name}: {e}")
            return None

    async def create_new_provider_groups(
        self,
        new_standard_groups: List[Dict[str, Any]],
        existing_aggregates: Dict[str, int]
    ) -> Dict[str, Any]:
        """Create standard groups for a new provider and add to existing aggregates.
        
        This handles Scenario D: New provider with models that match existing
        normalized names.
        
        Args:
            new_standard_groups: List of standard group configurations to create.
                                Each should have: name, channel_type, base_url,
                                api_key, model_redirect_rules
            existing_aggregates: Mapping of aggregate names to their IDs.
            
        Returns:
            Dictionary with:
                - created_groups: List of created group info (name, id)
                - updated_aggregates: List of aggregate IDs that were updated
                - errors: List of error messages
        """
        logger.info(f"Creating {len(new_standard_groups)} new standard groups (Scenario D)")
        
        created_groups = []
        updated_aggregates = []
        errors = []
        
        # Create standard groups
        for group_config in new_standard_groups:
            group_name = group_config.get('name')
            
            try:
                # Determine test model
                test_model = None
                model_redirect_rules = group_config.get('model_redirect_rules', {})
                if model_redirect_rules:
                    test_model = list(model_redirect_rules.values())[0]
                
                # Create the standard group
                created_group = await self.create_standard_group(
                    name=group_name,
                    display_name=group_config.get('display_name', group_name),
                    channel_type=group_config.get('channel_type', 'openai'),
                    upstream_url=group_config.get('base_url', ''),
                    model_redirect_rules=model_redirect_rules,
                    test_model=test_model,
                    description=group_config.get('description')
                )
                
                group_id = created_group.get("id")
                if not group_id:
                    raise ValueError(f"No group ID returned for '{group_name}'")
                
                created_groups.append({
                    'name': group_name,
                    'id': group_id
                })
                
                logger.info(f"Created new standard group: {group_name} (ID: {group_id})")
                
                # Add API key if provided
                api_key = group_config.get('api_key')
                if api_key:
                    try:
                        await self.add_keys_to_group(group_id, [api_key])
                        logger.info(f"Added API key to group {group_name}")
                    except Exception as e:
                        logger.error(f"Failed to add API key to {group_name}: {e}")
                        errors.append(f"Add API key to {group_name}: {str(e)}")
                
            except Exception as e:
                error_msg = f"Create standard group {group_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Failed to create standard group: {error_msg}")
        
        # Build group name to ID mapping for new groups
        new_group_name_to_id = {g['name']: g['id'] for g in created_groups}
        
        # Add new groups to existing aggregates if they have matching models
        for group_info in created_groups:
            group_name = group_info['name']
            group_id = group_info['id']
            
            # Check if this group should be added to any existing aggregates
            # This is determined by checking if the group's normalized model
            # matches any existing aggregate
            for aggregate_name, aggregate_id in existing_aggregates.items():
                # Extract model name from aggregate name (format: aggregate-{model})
                if aggregate_name.startswith('aggregate-'):
                    try:
                        # Add this standard group as a sub-group to the aggregate
                        await self.add_sub_groups_with_equal_weights(
                            aggregate_id,
                            [group_id],
                            weight=10
                        )
                        
                        if aggregate_id not in updated_aggregates:
                            updated_aggregates.append(aggregate_id)
                        
                        logger.info(f"Added {group_name} to existing aggregate {aggregate_name}")
                        
                    except Exception as e:
                        error_msg = f"Add {group_name} to aggregate {aggregate_name}: {str(e)}"
                        errors.append(error_msg)
                        logger.error(f"Failed to add to aggregate: {error_msg}")
        
        return {
            "created_groups": created_groups,
            "updated_aggregates": updated_aggregates,
            "errors": errors
        }
