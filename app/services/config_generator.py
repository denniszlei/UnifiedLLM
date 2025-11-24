"""Configuration generator for GPT-Load and uni-api."""

import logging
from typing import List, Dict, Optional, Any, Tuple
from sqlalchemy.orm import Session
import yaml

from app.models.provider import Provider
from app.models.model import Model
from app.models.gptload_group import GPTLoadGroup
from app.services.model_service import ModelService, ProviderSplit
from app.services.provider_service import ProviderService
from app.services.gptload_client import GPTLoadClient
from app.config import settings

logger = logging.getLogger(__name__)


class ConfigurationGenerator:
    """Service for generating GPT-Load and uni-api configurations."""

    def __init__(
        self,
        model_service: ModelService,
        provider_service: ProviderService
    ):
        """Initialize configuration generator.
        
        Args:
            model_service: Service for model operations.
            provider_service: Service for provider operations.
        """
        self.model_service = model_service
        self.provider_service = provider_service

    async def generate_gptload_configuration(
        self,
        db: Session,
        provider_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Generate GPT-Load configuration by creating groups via API.
        
        This method orchestrates the complete GPT-Load configuration generation:
        1. Split providers by duplicate models
        2. Create standard groups for each split
        3. Add API keys to standard groups
        4. Identify cross-provider duplicates
        5. Create aggregate groups for duplicates
        6. Add sub-groups to aggregate groups
        
        Args:
            db: Database session.
            provider_ids: Optional list of provider IDs to configure.
                         If None, configures all providers.
            
        Returns:
            Dictionary with configuration results:
                - standard_groups: List of created standard group info
                - aggregate_groups: List of created aggregate group info
                - errors: List of any errors encountered
            
        Raises:
            Exception: If critical errors occur during configuration.
        """
        logger.info("Starting GPT-Load configuration generation")
        
        # Get providers to configure
        if provider_ids:
            providers = [
                self.provider_service.get_provider(db, pid)
                for pid in provider_ids
            ]
            providers = [p for p in providers if p is not None]
        else:
            providers = db.query(Provider).all()
        
        if not providers:
            logger.warning("No providers found for configuration")
            return {
                "standard_groups": [],
                "aggregate_groups": [],
                "errors": ["No providers found"]
            }
        
        logger.info(f"Configuring {len(providers)} providers")
        
        standard_groups_info = []
        errors = []
        
        # Map to track standard groups by (provider_id, normalized_model_name)
        standard_group_map: Dict[Tuple[int, str], Dict[str, Any]] = {}
        
        async with GPTLoadClient() as gptload_client:
            # Step 1 & 2: Split providers and create standard groups
            for provider in providers:
                try:
                    await self._create_standard_groups_for_provider(
                        db,
                        gptload_client,
                        provider,
                        standard_groups_info,
                        standard_group_map,
                        errors
                    )
                except Exception as e:
                    error_msg = f"Failed to configure provider {provider.id} ({provider.name}): {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Step 4 & 5: Identify cross-provider duplicates and create aggregate groups
            aggregate_groups_info = await self._create_aggregate_groups(
                db,
                gptload_client,
                standard_group_map,
                errors
            )
        
        result = {
            "standard_groups": standard_groups_info,
            "aggregate_groups": aggregate_groups_info,
            "errors": errors
        }
        
        logger.info(
            f"GPT-Load configuration complete: "
            f"{len(standard_groups_info)} standard groups, "
            f"{len(aggregate_groups_info)} aggregate groups, "
            f"{len(errors)} errors"
        )
        
        return result

    async def _create_standard_groups_for_provider(
        self,
        db: Session,
        gptload_client: GPTLoadClient,
        provider: Provider,
        standard_groups_info: List[Dict[str, Any]],
        standard_group_map: Dict[Tuple[int, str], Dict[str, Any]],
        errors: List[str]
    ) -> None:
        """Create standard groups for a single provider.
        
        Args:
            db: Database session.
            gptload_client: GPT-Load API client.
            provider: Provider to configure.
            standard_groups_info: List to append created group info to.
            standard_group_map: Map to track groups by (provider_id, normalized_name).
            errors: List to append errors to.
        """
        logger.info(f"Processing provider {provider.id} ({provider.name})")
        
        # Split provider by duplicates
        splits = self.model_service.split_provider_by_duplicates(db, provider.id)
        
        if not splits:
            logger.warning(f"No models found for provider {provider.id}")
            return
        
        logger.info(f"Provider {provider.id} split into {len(splits)} groups")
        
        # Get decrypted API key
        provider_data = self.provider_service.get_provider_with_decrypted_key(db, provider.id)
        if not provider_data:
            error_msg = f"Failed to get decrypted API key for provider {provider.id}"
            logger.error(error_msg)
            errors.append(error_msg)
            return
        
        api_key = provider_data["api_key"]
        
        # Create standard group for each split
        for split in splits:
            try:
                group_info = await self._create_standard_group_from_split(
                    db,
                    gptload_client,
                    provider,
                    split,
                    api_key
                )
                
                standard_groups_info.append(group_info)
                
                # Track in map for aggregate group creation
                # For duplicate groups, use the normalized name
                # For non-duplicate groups, track each model separately
                if split.is_duplicate_group and split.normalized_name:
                    key = (provider.id, split.normalized_name)
                    standard_group_map[key] = group_info
                else:
                    # Non-duplicate group - track each model
                    for model in split.models:
                        normalized = model.normalized_name if model.normalized_name else model.original_name
                        key = (provider.id, normalized)
                        standard_group_map[key] = group_info
                
            except Exception as e:
                error_msg = f"Failed to create standard group '{split.group_name}': {e}"
                logger.error(error_msg)
                errors.append(error_msg)

    async def _create_standard_group_from_split(
        self,
        db: Session,
        gptload_client: GPTLoadClient,
        provider: Provider,
        split: ProviderSplit,
        api_key: str
    ) -> Dict[str, Any]:
        """Create a single standard group from a provider split.
        
        Args:
            db: Database session.
            gptload_client: GPT-Load API client.
            provider: Provider instance.
            split: Provider split configuration.
            api_key: Decrypted provider API key.
            
        Returns:
            Dictionary with created group information.
        """
        # Get model redirect rules
        model_redirect_rules = split.get_model_redirect_rules()
        
        # Determine test model (use first normalized name)
        test_model = None
        if model_redirect_rules:
            test_model = list(model_redirect_rules.keys())[0]
        
        # Create standard group via GPT-Load API
        logger.info(f"Creating standard group '{split.group_name}'")
        
        created_group = await gptload_client.create_standard_group(
            name=split.group_name,
            display_name=f"{provider.name} - {split.group_name}",
            channel_type=provider.channel_type,
            upstream_url=provider.base_url,
            model_redirect_rules=model_redirect_rules,
            test_model=test_model
        )
        
        gptload_group_id = created_group.get("id")
        if not gptload_group_id:
            raise ValueError(f"No group ID returned from GPT-Load for '{split.group_name}'")
        
        logger.info(f"Standard group '{split.group_name}' created with ID {gptload_group_id}")
        
        # Add API keys to the group
        logger.info(f"Adding API key to group {gptload_group_id}")
        await gptload_client.add_keys_to_group(gptload_group_id, [api_key])
        
        # Store in database
        gptload_group = GPTLoadGroup(
            gptload_group_id=gptload_group_id,
            name=split.group_name,
            group_type="standard",
            provider_id=provider.id,
            normalized_model=split.normalized_name  # Only set for duplicate groups
        )
        db.add(gptload_group)
        db.commit()
        
        logger.info(f"Standard group '{split.group_name}' stored in database")
        
        return {
            "id": gptload_group_id,
            "name": split.group_name,
            "provider_id": provider.id,
            "provider_name": provider.name,
            "normalized_model": split.normalized_name,
            "is_duplicate_group": split.is_duplicate_group,
            "model_count": len(split.models),
            "model_redirect_rules": model_redirect_rules
        }

    async def _create_aggregate_groups(
        self,
        db: Session,
        gptload_client: GPTLoadClient,
        standard_group_map: Dict[Tuple[int, str], Dict[str, Any]],
        errors: List[str]
    ) -> List[Dict[str, Any]]:
        """Create aggregate groups for models that appear in multiple standard groups.
        
        Note: "Multiple providers" includes provider splits. If a provider is split
        due to duplicate models, each split is treated as a separate provider.
        For example, if providerA has duplicate "deepseek-v3" models and is split
        into providerA-0-deepseek-v3 and providerA-1-deepseek-v3, an aggregate
        group should be created for load balancing between these splits.
        
        Args:
            db: Database session.
            gptload_client: GPT-Load API client.
            standard_group_map: Map of (provider_id, normalized_name) to group info.
            errors: List to append errors to.
            
        Returns:
            List of created aggregate group information.
        """
        logger.info("Identifying duplicate models for aggregate groups")
        
        # Group standard groups by normalized model name
        model_to_groups: Dict[str, List[Dict[str, Any]]] = {}
        
        for (provider_id, normalized_name), group_info in standard_group_map.items():
            if normalized_name not in model_to_groups:
                model_to_groups[normalized_name] = []
            model_to_groups[normalized_name].append(group_info)
        
        # Filter to only models that appear in multiple standard groups
        # This includes both cross-provider duplicates AND within-provider splits
        duplicate_models = {
            model_name: groups
            for model_name, groups in model_to_groups.items()
            if len(groups) > 1  # Multiple standard groups offer this model
        }
        
        if not duplicate_models:
            logger.info("No duplicate models found for aggregate groups")
            return []
        
        logger.info(f"Found {len(duplicate_models)} models appearing in multiple standard groups")
        
        aggregate_groups_info = []
        
        # Create aggregate group for each duplicate model
        for model_name, groups in duplicate_models.items():
            try:
                aggregate_info = await self._create_aggregate_group_for_model(
                    db,
                    gptload_client,
                    model_name,
                    groups
                )
                aggregate_groups_info.append(aggregate_info)
                
            except Exception as e:
                error_msg = f"Failed to create aggregate group for '{model_name}': {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        return aggregate_groups_info

    async def _create_aggregate_group_for_model(
        self,
        db: Session,
        gptload_client: GPTLoadClient,
        model_name: str,
        standard_groups: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create an aggregate group for a specific model.
        
        Args:
            db: Database session.
            gptload_client: GPT-Load API client.
            model_name: Normalized model name.
            standard_groups: List of standard group info dicts that offer this model.
            
        Returns:
            Dictionary with created aggregate group information.
        """
        # Sanitize aggregate group name
        sanitized_name = model_name.replace(".", "-")
        aggregate_name = f"{sanitized_name}-aggregate"
        
        logger.info(f"Creating aggregate group '{aggregate_name}' with {len(standard_groups)} sub-groups")
        
        # Determine channel type (use first group's channel type)
        # In practice, all groups for the same model should have compatible channel types
        channel_type = "openai"  # Default
        if standard_groups:
            # Get provider to determine channel type
            first_provider_id = standard_groups[0]["provider_id"]
            provider = db.query(Provider).filter(Provider.id == first_provider_id).first()
            if provider:
                channel_type = provider.channel_type
        
        # Create aggregate group
        created_aggregate = await gptload_client.create_aggregate_group(
            name=aggregate_name,
            display_name=f"{model_name} (Load Balanced)",
            channel_type=channel_type,
            description=f"Aggregate group for {model_name} across {len(standard_groups)} providers"
        )
        
        aggregate_group_id = created_aggregate.get("id")
        if not aggregate_group_id:
            raise ValueError(f"No group ID returned from GPT-Load for aggregate '{aggregate_name}'")
        
        logger.info(f"Aggregate group '{aggregate_name}' created with ID {aggregate_group_id}")
        
        # Add sub-groups with equal weights
        standard_group_ids = [g["id"] for g in standard_groups]
        await gptload_client.add_sub_groups_with_equal_weights(
            aggregate_group_id,
            standard_group_ids,
            weight=10
        )
        
        logger.info(f"Added {len(standard_group_ids)} sub-groups to aggregate {aggregate_group_id}")
        
        # Store in database
        gptload_group = GPTLoadGroup(
            gptload_group_id=aggregate_group_id,
            name=aggregate_name,
            group_type="aggregate",
            provider_id=None,  # Aggregate groups don't belong to a single provider
            normalized_model=model_name
        )
        db.add(gptload_group)
        db.commit()
        
        logger.info(f"Aggregate group '{aggregate_name}' stored in database")
        
        return {
            "id": aggregate_group_id,
            "name": aggregate_name,
            "normalized_model": model_name,
            "sub_group_count": len(standard_groups),
            "sub_groups": [
                {
                    "id": g["id"],
                    "name": g["name"],
                    "provider_name": g["provider_name"]
                }
                for g in standard_groups
            ]
        }

    def get_gptload_groups(
        self,
        db: Session,
        group_type: Optional[str] = None
    ) -> List[GPTLoadGroup]:
        """Get GPT-Load groups from database.
        
        Args:
            db: Database session.
            group_type: Optional filter by group type ('standard' or 'aggregate').
            
        Returns:
            List of GPTLoadGroup instances.
        """
        query = db.query(GPTLoadGroup)
        
        if group_type:
            query = query.filter(GPTLoadGroup.group_type == group_type)
        
        return query.all()

    def get_gptload_group_by_id(
        self,
        db: Session,
        gptload_group_id: int
    ) -> Optional[GPTLoadGroup]:
        """Get a GPT-Load group by its GPT-Load ID.
        
        Args:
            db: Database session.
            gptload_group_id: GPT-Load group ID.
            
        Returns:
            GPTLoadGroup instance or None if not found.
        """
        return db.query(GPTLoadGroup).filter(
            GPTLoadGroup.gptload_group_id == gptload_group_id
        ).first()

    def delete_gptload_group(
        self,
        db: Session,
        gptload_group_id: int
    ) -> bool:
        """Delete a GPT-Load group from database.
        
        Args:
            db: Database session.
            gptload_group_id: GPT-Load group ID.
            
        Returns:
            True if deleted, False if not found.
        """
        group = self.get_gptload_group_by_id(db, gptload_group_id)
        if not group:
            return False
        
        db.delete(group)
        db.commit()
        logger.info(f"Deleted GPT-Load group {gptload_group_id} from database")
        return True


    def generate_uniapi_yaml(
        self,
        db: Session,
        gptload_base_url: Optional[str] = None,
        gptload_auth_key: Optional[str] = None
    ) -> str:
        """Generate uni-api configuration YAML.
        
        Creates a uni-api configuration that points to GPT-Load proxy endpoints.
        
        Args:
            db: Database session.
            gptload_base_url: GPT-Load base URL (defaults to settings.gptload_url).
            gptload_auth_key: GPT-Load auth key (defaults to settings.gptload_auth_key).
            
        Returns:
            YAML configuration string.
            
        Raises:
            ValueError: If configuration is invalid.
        """
        logger.info("Generating uni-api YAML configuration")
        
        # Use defaults from settings if not provided
        if not gptload_base_url:
            gptload_base_url = settings.gptload_url
        if not gptload_auth_key:
            gptload_auth_key = settings.gptload_auth_key
        
        if not gptload_auth_key:
            raise ValueError("GPT-Load auth key not configured")
        
        # Normalize base URL
        gptload_base_url = gptload_base_url.rstrip('/')
        
        # Get all GPT-Load groups
        all_groups = self.get_gptload_groups(db)
        
        if not all_groups:
            logger.warning("No GPT-Load groups found for uni-api configuration")
        
        # Build provider entries
        providers = []
        
        # Add aggregate groups first (for duplicate models)
        aggregate_groups = [g for g in all_groups if g.group_type == "aggregate"]
        for group in aggregate_groups:
            provider_entry = {
                "provider": group.name,
                "base_url": f"{gptload_base_url}/proxy/{group.name}",
                "api": gptload_auth_key,
                "model": []  # Empty for auto-discovery
            }
            providers.append(provider_entry)
            logger.debug(f"Added aggregate group '{group.name}' to uni-api config")
        
        # Add standard groups with non-duplicate models
        standard_groups = [g for g in all_groups if g.group_type == "standard"]
        
        # Filter standard groups: only include those that are NOT part of an aggregate
        # (i.e., groups with normalized_model=None or groups whose normalized_model
        # doesn't appear in any aggregate group)
        aggregate_models = set(g.normalized_model for g in aggregate_groups if g.normalized_model)
        
        for group in standard_groups:
            # Include if:
            # 1. It has no normalized_model (non-duplicate group), OR
            # 2. Its normalized_model is not in any aggregate group
            if not group.normalized_model or group.normalized_model not in aggregate_models:
                provider_entry = {
                    "provider": group.name,
                    "base_url": f"{gptload_base_url}/proxy/{group.name}",
                    "api": gptload_auth_key,
                    "model": []  # Empty for auto-discovery
                }
                providers.append(provider_entry)
                logger.debug(f"Added standard group '{group.name}' to uni-api config")
        
        # Build complete configuration
        config = {
            "providers": providers,
            "api_keys": [
                {
                    "api": "sk-user-key",
                    "role": "user",
                    "model": ["all"]
                }
            ],
            "preferences": {
                "rate_limit": "999999/min"
            }
        }
        
        # Validate configuration
        self._validate_uniapi_config(config)
        
        # Convert to YAML
        yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Generated uni-api YAML with {len(providers)} provider entries")
        
        return yaml_str

    def _validate_uniapi_config(self, config: Dict[str, Any]) -> None:
        """Validate uni-api configuration structure.
        
        Args:
            config: Configuration dictionary to validate.
            
        Raises:
            ValueError: If configuration is invalid.
        """
        # Check required top-level keys
        if "providers" not in config:
            raise ValueError("Configuration missing 'providers' key")
        
        if not isinstance(config["providers"], list):
            raise ValueError("'providers' must be a list")
        
        # Validate each provider entry
        for i, provider in enumerate(config["providers"]):
            if not isinstance(provider, dict):
                raise ValueError(f"Provider {i} is not a dictionary")
            
            required_keys = ["provider", "base_url", "api", "model"]
            for key in required_keys:
                if key not in provider:
                    raise ValueError(f"Provider {i} missing required key '{key}'")
            
            # Validate base_url format
            base_url = provider["base_url"]
            if not base_url.startswith("http://") and not base_url.startswith("https://"):
                raise ValueError(f"Provider {i} has invalid base_url: {base_url}")
            
            # Validate model is a list
            if not isinstance(provider["model"], list):
                raise ValueError(f"Provider {i} 'model' must be a list")
        
        logger.debug("uni-api configuration validation passed")

    def export_uniapi_yaml_to_file(
        self,
        db: Session,
        file_path: str,
        gptload_base_url: Optional[str] = None,
        gptload_auth_key: Optional[str] = None
    ) -> str:
        """Generate and export uni-api YAML to a file.
        
        Args:
            db: Database session.
            file_path: Path to write YAML file.
            gptload_base_url: GPT-Load base URL (defaults to settings.gptload_url).
            gptload_auth_key: GPT-Load auth key (defaults to settings.gptload_auth_key).
            
        Returns:
            Path to the written file.
            
        Raises:
            ValueError: If configuration is invalid.
            IOError: If file write fails.
        """
        logger.info(f"Exporting uni-api YAML to {file_path}")
        
        # Generate YAML
        yaml_content = self.generate_uniapi_yaml(
            db,
            gptload_base_url,
            gptload_auth_key
        )
        
        # Write to file
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(yaml_content)
            logger.info(f"uni-api YAML exported successfully to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to write uni-api YAML to {file_path}: {e}")
            raise IOError(f"Failed to write YAML file: {e}")
