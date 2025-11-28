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
from app.services.provider_splitter import ProviderSplitter, ProviderConfig
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
        """Generate GPT-Load configuration using improved two-step sync.
        
        This method uses the ported algorithm from the reference implementation:
        1. Gather all provider data and model normalizations
        2. Use ProviderSplitter to compute split configuration
        3. Step 1: Create all standard groups via GPT-Load API
        4. Step 2: Add API keys and create aggregate groups
        5. Store results in database
        
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
        logger.info("Starting GPT-Load configuration generation (two-step sync)")
        
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
        
        # Prepare provider configurations for splitting
        provider_configs = []
        rename_mapping = {}
        
        for provider in providers:
            # Get decrypted API key
            provider_data = self.provider_service.get_provider_with_decrypted_key(db, provider.id)
            if not provider_data:
                logger.error(f"Failed to get decrypted API key for provider {provider.id}")
                continue
            
            # Get active models for this provider
            models = db.query(Model).filter(
                Model.provider_id == provider.id,
                Model.is_active == True
            ).all()
            
            if not models:
                logger.warning(f"No active models for provider {provider.id}")
                continue
            
            # Build model list and rename mapping
            model_names = []
            provider_renames = {}
            
            for model in models:
                model_names.append(model.original_name)
                if model.normalized_name and model.normalized_name != model.original_name:
                    provider_renames[model.original_name] = model.normalized_name
            
            # Create ProviderConfig
            provider_config = ProviderConfig(
                name=provider.name,
                base_url=provider.base_url,
                api_key=provider_data["api_key"],
                channel_type=provider.channel_type,
                models=model_names
            )
            
            provider_configs.append(provider_config)
            if provider_renames:
                rename_mapping[provider.name] = provider_renames
        
        if not provider_configs:
            logger.warning("No valid provider configurations")
            return {
                "standard_groups": [],
                "aggregate_groups": [],
                "errors": ["No valid provider configurations"]
            }
        
        # Use ProviderSplitter to compute split configuration
        logger.info("Computing provider split configuration")
        split_groups, aggregations = ProviderSplitter.split_providers(
            provider_configs,
            rename_mapping
        )
        
        logger.info(
            f"Split complete: {len(split_groups)} standard groups, "
            f"{len(aggregations)} models need aggregation"
        )
        
        # Execute two-step sync
        standard_groups_info = []
        aggregate_groups_info = []
        all_errors = []
        
        async with GPTLoadClient() as gptload_client:
            # Step 1: Create standard groups
            logger.info("Step 1: Creating standard groups")
            step1_result = await gptload_client.sync_config_step1(split_groups)
            
            if step1_result["errors"]:
                all_errors.extend(step1_result["errors"])
            
            group_name_to_id = step1_result["group_name_to_id"]
            group_name_to_apikey = step1_result["group_name_to_apikey"]
            
            # Store standard groups in database
            for group_name, group_id in group_name_to_id.items():
                # Find the corresponding split_group
                split_group = next((g for g in split_groups if g.group_name == group_name), None)
                if not split_group:
                    continue
                
                # Find provider ID
                provider = next((p for p in providers if p.name == split_group.provider_name), None)
                if not provider:
                    continue
                
                # Determine if this is a duplicate group
                is_duplicate = any(
                    group_name in group_list
                    for group_list in aggregations.values()
                )
                
                # Determine normalized model (for duplicate groups)
                normalized_model = None
                if is_duplicate:
                    for model_name, group_list in aggregations.items():
                        if group_name in group_list:
                            normalized_model = model_name
                            break
                
                # Store in database
                gptload_group = GPTLoadGroup(
                    gptload_group_id=group_id,
                    name=group_name,
                    group_type="standard",
                    provider_id=provider.id,
                    normalized_model=normalized_model
                )
                db.add(gptload_group)
                
                standard_groups_info.append({
                    "id": group_id,
                    "name": group_name,
                    "provider_id": provider.id,
                    "provider_name": provider.name,
                    "normalized_model": normalized_model,
                    "is_duplicate_group": is_duplicate,
                    "model_count": len(split_group.model_redirect_rules)
                })
            
            db.commit()
            
            # Step 2: Add API keys and create aggregate groups
            logger.info("Step 2: Adding API keys and creating aggregate groups")
            step2_result = await gptload_client.sync_config_step2(
                aggregations,
                group_name_to_id,
                group_name_to_apikey,
                refresh_api_keys=True
            )
            
            if step2_result["errors"]:
                all_errors.extend(step2_result["errors"])
            
            # Store aggregate groups in database
            for model_name, sub_group_names in aggregations.items():
                sanitized_model = ProviderSplitter.sanitize_name(model_name)
                aggregate_name = f"aggregate-{sanitized_model}"
                
                # Try to find the aggregate group ID from GPT-Load
                try:
                    groups = await gptload_client.list_groups()
                    aggregate_group = next((g for g in groups if g.get("name") == aggregate_name), None)
                    
                    if aggregate_group:
                        aggregate_id = aggregate_group.get("id")
                        
                        # Store in database
                        gptload_group = GPTLoadGroup(
                            gptload_group_id=aggregate_id,
                            name=aggregate_name,
                            group_type="aggregate",
                            provider_id=None,
                            normalized_model=model_name
                        )
                        db.add(gptload_group)
                        
                        aggregate_groups_info.append({
                            "id": aggregate_id,
                            "name": aggregate_name,
                            "normalized_model": model_name,
                            "sub_group_count": len(sub_group_names)
                        })
                except Exception as e:
                    logger.error(f"Failed to store aggregate group {aggregate_name}: {e}")
                    all_errors.append(f"Store aggregate {aggregate_name}: {str(e)}")
            
            db.commit()
        
        result = {
            "standard_groups": standard_groups_info,
            "aggregate_groups": aggregate_groups_info,
            "errors": all_errors
        }
        
        logger.info(
            f"GPT-Load configuration complete: "
            f"{len(standard_groups_info)} standard groups, "
            f"{len(aggregate_groups_info)} aggregate groups, "
            f"{len(all_errors)} errors"
        )
        
        return result

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

    async def generate_gptload_configuration_incremental(
        self,
        db: Session,
        provider_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Generate GPT-Load configuration using incremental sync approach.
        
        This method implements smart diff-based updates:
        1. Fetch existing GPT-Load configuration
        2. Build desired configuration from local database
        3. Compute diff to identify changes
        4. Apply changes in correct sequence:
           - Delete orphaned aggregates
           - Update existing standard groups
           - Create new standard groups
           - Delete obsolete standard groups
           - Recreate aggregate groups with updated membership
        
        Args:
            db: Database session.
            provider_ids: Optional list of provider IDs to configure.
                         If None, configures all providers.
            
        Returns:
            Dictionary with configuration results:
                - standard_groups_created: List of created standard groups
                - standard_groups_updated: List of updated standard groups
                - standard_groups_deleted: List of deleted standard groups
                - aggregate_groups_created: List of created aggregate groups
                - aggregate_groups_deleted: List of deleted aggregate groups
                - errors: List of any errors encountered
                - summary: Human-readable summary
            
        Raises:
            Exception: If critical errors occur during configuration.
        """
        logger.info("Starting incremental GPT-Load configuration sync")
        
        result = {
            "standard_groups_created": [],
            "standard_groups_updated": [],
            "standard_groups_deleted": [],
            "aggregate_groups_created": [],
            "aggregate_groups_deleted": [],
            "errors": []
        }
        
        async with GPTLoadClient() as gptload_client:
            try:
                # Step 1: Fetch existing configuration
                logger.info("Step 1: Fetching existing GPT-Load configuration")
                existing_config = await gptload_client.get_existing_config()
                
                # Step 2: Build desired configuration
                logger.info("Step 2: Building desired configuration from database")
                desired_config = await self.build_desired_config(db, provider_ids)
                
                # Step 3: Compute diff
                logger.info("Step 3: Computing configuration diff")
                diff = gptload_client.diff_configs(existing_config, desired_config)
                
                logger.info(f"Diff summary: {diff['summary']}")
                
                # Step 4: Delete orphaned aggregates (only 1 sub-group remaining)
                if diff['orphaned_aggregates']:
                    logger.info(f"Step 4: Deleting {len(diff['orphaned_aggregates'])} orphaned aggregates")
                    cleanup_result = await gptload_client.cleanup_orphaned_aggregates(
                        diff['orphaned_aggregates']
                    )
                    result['aggregate_groups_deleted'].extend([
                        {'name': agg['name'], 'reason': 'orphaned'}
                        for agg in diff['orphaned_aggregates']
                    ])
                    if cleanup_result['errors']:
                        result['errors'].extend(cleanup_result['errors'])
                
                # Step 5: Delete aggregates that need recreation
                if diff['to_delete_aggregate']:
                    logger.info(f"Step 5: Deleting {len(diff['to_delete_aggregate'])} aggregates for recreation")
                    for agg_name in diff['to_delete_aggregate']:
                        try:
                            # Find the aggregate ID
                            agg_group = existing_config['group_by_name'].get(agg_name)
                            if agg_group:
                                agg_id = agg_group.get('id')
                                if agg_id:
                                    await gptload_client.delete_group(agg_id)
                                    result['aggregate_groups_deleted'].append({
                                        'name': agg_name,
                                        'reason': 'recreation'
                                    })
                                    logger.info(f"Deleted aggregate {agg_name} for recreation")
                        except Exception as e:
                            error_msg = f"Delete aggregate {agg_name}: {str(e)}"
                            result['errors'].append(error_msg)
                            logger.error(error_msg)
                
                # Step 6: Update existing standard groups
                if diff['to_update_standard']:
                    logger.info(f"Step 6: Updating {len(diff['to_update_standard'])} standard groups")
                    update_result = await gptload_client.apply_standard_group_updates(
                        diff['to_update_standard']
                    )
                    result['standard_groups_updated'] = [
                        {'name': upd['name'], 'changes': upd['changes']}
                        for upd in diff['to_update_standard']
                    ]
                    if update_result['errors']:
                        result['errors'].extend(update_result['errors'])
                
                # Step 6.5: Update existing aggregate groups' sub-group membership
                if diff.get('to_update_aggregate'):
                    logger.info(f"Step 6.5: Updating {len(diff['to_update_aggregate'])} aggregate groups' sub-group membership")
                    for agg_update in diff['to_update_aggregate']:
                        agg_name = agg_update['name']
                        agg_id = agg_update['group_id']
                        changes = agg_update.get('changes', {})
                        
                        try:
                            # Handle sub-group membership changes
                            if 'sub_groups' in changes:
                                removed_subs = changes['sub_groups'].get('removed', [])
                                added_subs = changes['sub_groups'].get('added', [])
                                
                                # Remove sub-groups that should no longer be in this aggregate
                                for sub_name in removed_subs:
                                    sub_group = existing_config['group_by_name'].get(sub_name)
                                    if sub_group:
                                        sub_id = sub_group.get('id')
                                        if sub_id:
                                            try:
                                                await gptload_client.delete_sub_group(agg_id, sub_id)
                                                logger.info(f"Removed {sub_name} from aggregate {agg_name}")
                                            except Exception as e:
                                                logger.warning(f"Failed to remove {sub_name} from {agg_name}: {e}")
                                
                                # Add new sub-groups to this aggregate
                                for sub_name in added_subs:
                                    sub_group = existing_config['group_by_name'].get(sub_name)
                                    if sub_group:
                                        sub_id = sub_group.get('id')
                                        if sub_id:
                                            try:
                                                await gptload_client.add_sub_groups_with_equal_weights(agg_id, [sub_id])
                                                logger.info(f"Added {sub_name} to aggregate {agg_name}")
                                            except Exception as e:
                                                logger.warning(f"Failed to add {sub_name} to {agg_name}: {e}")
                                
                                logger.info(f"Updated aggregate {agg_name}: removed {len(removed_subs)}, added {len(added_subs)} sub-groups")
                        except Exception as e:
                            error_msg = f"Update aggregate {agg_name}: {str(e)}"
                            result['errors'].append(error_msg)
                            logger.error(error_msg)
                
                # Step 7: Create new standard groups
                if diff['to_create_standard']:
                    logger.info(f"Step 7: Creating {len(diff['to_create_standard'])} new standard groups")
                    
                    # Build group name to ID mapping from existing groups
                    existing_group_name_to_id = {
                        name: group.get('id')
                        for name, group in existing_config['group_by_name'].items()
                        if group.get('id')
                    }
                    
                    # Build existing aggregates mapping
                    existing_aggregates = {
                        name: group.get('id')
                        for name, group in existing_config['group_by_name'].items()
                        if group.get('group_type') == 'aggregate' and group.get('id')
                    }
                    
                    create_result = await gptload_client.create_new_provider_groups(
                        diff['to_create_standard'],
                        existing_aggregates
                    )
                    
                    result['standard_groups_created'] = create_result['created_groups']
                    if create_result['errors']:
                        result['errors'].extend(create_result['errors'])
                    
                    # Update group name to ID mapping with newly created groups
                    for group_info in create_result['created_groups']:
                        existing_group_name_to_id[group_info['name']] = group_info['id']
                
                # Step 8: Delete obsolete standard groups
                if diff['to_delete_standard']:
                    logger.info(f"Step 8: Deleting {len(diff['to_delete_standard'])} obsolete standard groups")
                    for std_name in diff['to_delete_standard']:
                        try:
                            # Find the standard group ID
                            std_group = existing_config['group_by_name'].get(std_name)
                            if std_group:
                                std_id = std_group.get('id')
                                if std_id:
                                    # Use cascade deletion to handle aggregate cleanup
                                    cascade_result = await gptload_client.delete_standard_group_with_cascade(std_id)
                                    result['standard_groups_deleted'].append({
                                        'name': std_name,
                                        'id': std_id
                                    })
                                    logger.info(f"Deleted standard group {std_name}")
                                    
                                    # Track deleted aggregates from cascade
                                    if cascade_result.get('deleted_aggregates'):
                                        for agg_id in cascade_result['deleted_aggregates']:
                                            result['aggregate_groups_deleted'].append({
                                                'id': agg_id,
                                                'reason': 'cascade'
                                            })
                        except Exception as e:
                            error_msg = f"Delete standard group {std_name}: {str(e)}"
                            result['errors'].append(error_msg)
                            logger.error(error_msg)
                
                # Step 9: Create/recreate aggregate groups
                if diff['to_create_aggregate']:
                    logger.info(f"Step 9: Creating {len(diff['to_create_aggregate'])} aggregate groups")
                    
                    # Build complete group name to ID mapping
                    all_groups = await gptload_client.list_groups()
                    group_name_to_id = {
                        g.get('name'): g.get('id')
                        for g in all_groups
                        if g.get('name') and g.get('id')
                    }
                    
                    for agg_config in diff['to_create_aggregate']:
                        agg_name = agg_config.get('name')
                        model_name = agg_config.get('model_name', agg_name)
                        sub_group_names = agg_config.get('sub_group_names', [])
                        channel_type = agg_config.get('channel_type', 'openai')
                        
                        try:
                            agg_id = await gptload_client.recreate_aggregate_group(
                                agg_name,
                                model_name,
                                sub_group_names,
                                group_name_to_id,
                                channel_type
                            )
                            
                            if agg_id:
                                result['aggregate_groups_created'].append({
                                    'name': agg_name,
                                    'id': agg_id,
                                    'sub_group_count': len(sub_group_names)
                                })
                                logger.info(f"Created aggregate {agg_name}")
                            else:
                                error_msg = f"Failed to create aggregate {agg_name}"
                                result['errors'].append(error_msg)
                                
                        except Exception as e:
                            error_msg = f"Create aggregate {agg_name}: {str(e)}"
                            result['errors'].append(error_msg)
                            logger.error(error_msg)
                
                # Update database tracking
                logger.info("Updating database with sync results")
                await self._update_database_tracking(db, result, desired_config)
                
            except Exception as e:
                error_msg = f"Incremental sync failed: {str(e)}"
                result['errors'].append(error_msg)
                logger.error(error_msg)
                raise
        
        # Build summary
        summary_parts = []
        if result['standard_groups_created']:
            summary_parts.append(f"{len(result['standard_groups_created'])} standard groups created")
        if result['standard_groups_updated']:
            summary_parts.append(f"{len(result['standard_groups_updated'])} standard groups updated")
        if result['standard_groups_deleted']:
            summary_parts.append(f"{len(result['standard_groups_deleted'])} standard groups deleted")
        if result['aggregate_groups_created']:
            summary_parts.append(f"{len(result['aggregate_groups_created'])} aggregate groups created")
        if result['aggregate_groups_deleted']:
            summary_parts.append(f"{len(result['aggregate_groups_deleted'])} aggregate groups deleted")
        if result['errors']:
            summary_parts.append(f"{len(result['errors'])} errors")
        
        result['summary'] = "; ".join(summary_parts) if summary_parts else "No changes"
        
        logger.info(f"Incremental sync complete: {result['summary']}")
        
        return result

    async def _update_database_tracking(
        self,
        db: Session,
        sync_result: Dict[str, Any],
        desired_config: Dict[str, Any]
    ) -> None:
        """Update database with sync results.
        
        Args:
            db: Database session.
            sync_result: Result from incremental sync.
            desired_config: Desired configuration that was applied.
        """
        import hashlib
        import json
        from datetime import datetime
        
        # Clear existing GPTLoadGroup entries
        db.query(GPTLoadGroup).delete()
        
        # Get all current groups from GPT-Load
        async with GPTLoadClient() as gptload_client:
            all_groups = await gptload_client.list_groups()
        
        # Get providers for mapping
        providers = db.query(Provider).all()
        provider_by_name = {p.name: p for p in providers}
        
        # Current timestamp for sync tracking
        sync_timestamp = datetime.utcnow()
        
        # Store all groups in database
        for group in all_groups:
            group_name = group.get('name')
            group_id = group.get('id')
            group_type = group.get('group_type', 'standard')
            
            if not group_name or not group_id:
                continue
            
            # Determine provider_id and normalized_model
            provider_id = None
            normalized_model = None
            
            if group_type == 'standard':
                # Find provider from desired config
                desired_group = desired_config['group_by_name'].get(group_name)
                if desired_group:
                    provider_name = desired_group.get('provider_name')
                    if provider_name and provider_name in provider_by_name:
                        provider_id = provider_by_name[provider_name].id
            
            elif group_type == 'aggregate':
                # Extract model name from aggregate name
                if group_name.startswith('aggregate-'):
                    # Find in desired config
                    desired_group = desired_config['group_by_name'].get(group_name)
                    if desired_group:
                        normalized_model = desired_group.get('model_name')
            
            # Compute config hash for change detection
            config_hash = None
            desired_group = desired_config['group_by_name'].get(group_name)
            if desired_group:
                # Create a stable hash of the configuration
                config_str = json.dumps(desired_group, sort_keys=True)
                config_hash = hashlib.md5(config_str.encode()).hexdigest()
            
            # Create database entry
            gptload_group = GPTLoadGroup(
                gptload_group_id=group_id,
                name=group_name,
                group_type=group_type,
                provider_id=provider_id,
                normalized_model=normalized_model,
                last_sync_timestamp=sync_timestamp,
                config_hash=config_hash
            )
            db.add(gptload_group)
        
        db.commit()
        logger.info("Database tracking updated with sync timestamps and config hashes")

    async def build_desired_config(
        self,
        db: Session,
        provider_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Build desired GPT-Load configuration from local database.
        
        This method computes what the GPT-Load configuration should look like
        based on the current state of providers and models in the local database.
        
        Args:
            db: Database session.
            provider_ids: Optional list of provider IDs to include.
                         If None, includes all providers.
        
        Returns:
            Dictionary with:
                - split_groups: List of SplitGroup objects (standard groups)
                - aggregations: Dict mapping model names to list of group names
                - provider_configs: List of ProviderConfig objects used
                - group_by_name: Dict mapping group names to their configurations
        """
        logger.info("Building desired GPT-Load configuration from database")
        
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
                "split_groups": [],
                "aggregations": {},
                "provider_configs": [],
                "group_by_name": {}
            }
        
        # Prepare provider configurations for splitting
        provider_configs = []
        rename_mapping = {}
        
        for provider in providers:
            # Get decrypted API key
            provider_data = self.provider_service.get_provider_with_decrypted_key(db, provider.id)
            if not provider_data:
                logger.error(f"Failed to get decrypted API key for provider {provider.id}")
                continue
            
            # Get active models for this provider
            models = db.query(Model).filter(
                Model.provider_id == provider.id,
                Model.is_active == True
            ).all()
            
            if not models:
                logger.warning(f"No active models for provider {provider.id}")
                continue
            
            # Build model list and rename mapping
            model_names = []
            provider_renames = {}
            
            for model in models:
                model_names.append(model.original_name)
                if model.normalized_name and model.normalized_name != model.original_name:
                    provider_renames[model.original_name] = model.normalized_name
            
            # Create ProviderConfig
            provider_config = ProviderConfig(
                name=provider.name,
                base_url=provider.base_url,
                api_key=provider_data["api_key"],
                channel_type=provider.channel_type,
                models=model_names
            )
            
            provider_configs.append(provider_config)
            if provider_renames:
                rename_mapping[provider.name] = provider_renames
        
        if not provider_configs:
            logger.warning("No valid provider configurations")
            return {
                "split_groups": [],
                "aggregations": {},
                "provider_configs": [],
                "group_by_name": {}
            }
        
        # Use ProviderSplitter to compute split configuration
        logger.info("Computing provider split configuration")
        split_groups, aggregations = ProviderSplitter.split_providers(
            provider_configs,
            rename_mapping
        )
        
        logger.info(
            f"Desired config: {len(split_groups)} standard groups, "
            f"{len(aggregations)} models need aggregation"
        )
        
        # Build group_by_name mapping for easy lookup
        group_by_name = {}
        for split_group in split_groups:
            group_by_name[split_group.group_name] = {
                "name": split_group.group_name,
                "group_type": "standard",
                "channel_type": split_group.channel_type,
                "provider_name": split_group.provider_name,
                "base_url": split_group.base_url,
                "api_key": split_group.api_key,
                "model_redirect_rules": split_group.model_redirect_rules,
                "model_redirect_strict": True
            }
        
        # Add aggregate groups to mapping
        for model_name, sub_group_names in aggregations.items():
            sanitized_model = ProviderSplitter.sanitize_name(model_name)
            aggregate_name = f"aggregate-{sanitized_model}"
            
            group_by_name[aggregate_name] = {
                "name": aggregate_name,
                "group_type": "aggregate",
                "channel_type": "openai",  # Default
                "model_name": model_name,
                "sub_group_names": sub_group_names
            }
        
        return {
            "split_groups": split_groups,
            "aggregations": aggregations,
            "provider_configs": provider_configs,
            "group_by_name": group_by_name
        }


    def build_base_url(
        self,
        db: Session,
        group: GPTLoadGroup,
        gptload_base_url: str
    ) -> str:
        """Build base_url with correct path based on channel type.
        
        Args:
            db: Database session.
            group: GPTLoadGroup instance.
            gptload_base_url: GPT-Load base URL.
            
        Returns:
            Complete base_url with appropriate path suffix.
        """
        # Normalize base URL
        gptload_base_url = gptload_base_url.rstrip('/')
        group_name = group.name
        
        # Determine channel type
        channel_type = "openai"  # Default
        
        if group.group_type == "standard" and group.provider_id:
            # Query provider to get channel_type
            provider = db.query(Provider).filter(Provider.id == group.provider_id).first()
            if provider and provider.channel_type:
                channel_type = provider.channel_type
        elif group.group_type == "aggregate":
            # For aggregate groups, try to determine channel type from sub-groups
            # For now, we'll use the default (openai) since aggregates typically
            # combine groups of the same channel type
            channel_type = "openai"
        
        # Build path based on channel type
        if channel_type == "anthropic":
            path = "/v1/messages"
        elif channel_type == "gemini":
            path = "/v1beta"
        else:  # openai and others
            path = "/v1/chat/completions"
        
        return f"{gptload_base_url}/proxy/{group_name}{path}"

    def generate_uniapi_yaml(
        self,
        db: Session,
        gptload_base_url: Optional[str] = None,
        gptload_auth_key: Optional[str] = None,
        existing_yaml_path: Optional[str] = None
    ) -> str:
        """Generate uni-api configuration YAML with intelligent merging.
        
        Creates a uni-api configuration that points to GPT-Load proxy endpoints.
        If an existing YAML file exists, it will:
        1. Read and parse the existing file
        2. Remove dummy provider entries (provider_name)
        3. Preserve existing api_keys and preferences sections
        4. Merge generated providers with existing configuration
        
        Args:
            db: Database session.
            gptload_base_url: GPT-Load base URL (defaults to settings.gptload_url).
            gptload_auth_key: GPT-Load auth key (defaults to settings.gptload_auth_key).
            existing_yaml_path: Path to existing api.yaml file (defaults to /app/uni-api-config/api.yaml).
            
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
        
        # Step 1: Read existing YAML file if it exists (Subtask 26.1)
        existing_config = self._read_existing_yaml(existing_yaml_path)
        
        # Step 2: Remove dummy provider entries (Subtask 26.2)
        if existing_config:
            existing_config = self._remove_dummy_providers(existing_config)
        
        # Step 3: Extract api_keys and preferences sections (Subtask 26.3)
        api_keys_section = self._extract_api_keys_section(existing_config)
        preferences_section = self._extract_preferences_section(existing_config)
        
        # Get all GPT-Load groups
        all_groups = self.get_gptload_groups(db)
        
        if not all_groups:
            logger.warning("No GPT-Load groups found for uni-api configuration")
        
        # Build provider entries
        providers = []
        
        # Add aggregate groups first (for duplicate models)
        aggregate_groups = [g for g in all_groups if g.group_type == "aggregate"]
        for group in aggregate_groups:
            base_url = self.build_base_url(db, group, gptload_base_url)
            provider_entry = {
                "provider": group.name,
                "base_url": base_url,
                "api": gptload_auth_key,
                "model": []  # Empty for auto-discovery
            }
            providers.append(provider_entry)
            logger.debug(f"Added aggregate group '{group.name}' to uni-api config")
        
        # Add standard groups with non-duplicate models
        # Only include groups ending with '-no-aggregate-models'
        # These groups contain models that are NOT part of any aggregate group
        # This prevents bypassing load balancing by accessing sub-groups directly
        standard_groups = [g for g in all_groups if g.group_type == "standard"]
        
        for group in standard_groups:
            # Only include groups that end with '-no-aggregate-models'
            # These are the groups created by ProviderSplitter for non-duplicate models
            if group.name.endswith('-no-aggregate-models'):
                base_url = self.build_base_url(db, group, gptload_base_url)
                provider_entry = {
                    "provider": group.name,
                    "base_url": base_url,
                    "api": gptload_auth_key,
                    "model": []  # Empty for auto-discovery
                }
                providers.append(provider_entry)
                logger.debug(f"Added standard group '{group.name}' to uni-api config")
        
        # Step 4: Merge configuration (Subtask 26.4)
        config = self._merge_configuration(
            providers,
            api_keys_section,
            preferences_section
        )
        
        # Validate configuration
        self._validate_uniapi_config(config)
        
        # Convert to YAML
        yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Generated uni-api YAML with {len(providers)} provider entries")
        
        return yaml_str

    def _read_existing_yaml(
        self,
        yaml_path: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Read and parse existing api.yaml file if it exists.
        
        Implements Subtask 26.1: Implement existing file reading and parsing.
        
        Args:
            yaml_path: Path to existing api.yaml file.
                      Defaults to /app/uni-api-config/api.yaml.
            
        Returns:
            Parsed YAML configuration as dictionary, or None if file doesn't exist.
        """
        import os
        
        # Use default path if not provided
        if not yaml_path:
            yaml_path = "/app/uni-api-config/api.yaml"
        
        # Check if file exists
        if not os.path.exists(yaml_path):
            logger.info(f"No existing YAML file found at {yaml_path}")
            return None
        
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                existing_config = yaml.safe_load(f)
            
            if existing_config is None:
                logger.warning(f"Existing YAML file at {yaml_path} is empty")
                return None
            
            logger.info(f"Successfully read existing YAML file from {yaml_path}")
            return existing_config
            
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse existing YAML file at {yaml_path}: {e}")
            logger.warning("Will create new configuration file")
            return None
        except Exception as e:
            logger.error(f"Error reading existing YAML file at {yaml_path}: {e}")
            return None

    def _remove_dummy_providers(
        self,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Remove dummy provider entries from configuration.
        
        Implements Subtask 26.2: Implement dummy provider removal.
        
        Args:
            config: Existing configuration dictionary.
            
        Returns:
            Configuration with dummy providers removed.
        """
        if not config or "providers" not in config:
            return config
        
        if not isinstance(config["providers"], list):
            return config
        
        # Filter out providers with name "provider_name"
        original_count = len(config["providers"])
        config["providers"] = [
            p for p in config["providers"]
            if not (isinstance(p, dict) and p.get("provider") == "provider_name")
        ]
        
        removed_count = original_count - len(config["providers"])
        if removed_count > 0:
            logger.info(f"Removed {removed_count} dummy provider(s) named 'provider_name'")
        
        return config

    def _extract_api_keys_section(
        self,
        existing_config: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract api_keys section from existing configuration.
        
        Implements Subtask 26.3: Implement configuration section preservation.
        
        Args:
            existing_config: Existing configuration dictionary.
            
        Returns:
            api_keys section from existing config, or default if not found.
        """
        # Default api_keys section
        default_api_keys = [
            {
                "api": "sk-user-key",
                "role": "user",
                "model": ["all"]
            }
        ]
        
        if not existing_config:
            logger.debug("No existing config, using default api_keys section")
            return default_api_keys
        
        if "api_keys" in existing_config and isinstance(existing_config["api_keys"], list):
            logger.info("Preserving existing api_keys section")
            return existing_config["api_keys"]
        
        logger.debug("No api_keys section in existing config, using default")
        return default_api_keys

    def _extract_preferences_section(
        self,
        existing_config: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract preferences section from existing configuration.
        
        Implements Subtask 26.3: Implement configuration section preservation.
        
        Args:
            existing_config: Existing configuration dictionary.
            
        Returns:
            preferences section from existing config, or default if not found.
        """
        # Default preferences section
        default_preferences = {
            "rate_limit": "999999/min"
        }
        
        if not existing_config:
            logger.debug("No existing config, using default preferences section")
            return default_preferences
        
        if "preferences" in existing_config and isinstance(existing_config["preferences"], dict):
            logger.info("Preserving existing preferences section")
            return existing_config["preferences"]
        
        logger.debug("No preferences section in existing config, using default")
        return default_preferences

    def _merge_configuration(
        self,
        generated_providers: List[Dict[str, Any]],
        api_keys_section: List[Dict[str, Any]],
        preferences_section: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge generated providers with preserved configuration sections.
        
        Implements Subtask 26.4: Implement configuration merging logic.
        
        Args:
            generated_providers: List of provider entries generated from GPT-Load groups.
            api_keys_section: Preserved or default api_keys section.
            preferences_section: Preserved or default preferences section.
            
        Returns:
            Complete merged configuration dictionary.
        """
        config = {
            "providers": generated_providers,
            "api_keys": api_keys_section,
            "preferences": preferences_section
        }
        
        logger.info(
            f"Merged configuration: {len(generated_providers)} providers, "
            f"{len(api_keys_section)} api_keys, "
            f"{len(preferences_section)} preferences"
        )
        
        return config

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
        
        # Generate YAML (will read existing file at file_path for merging)
        yaml_content = self.generate_uniapi_yaml(
            db,
            gptload_base_url,
            gptload_auth_key,
            existing_yaml_path=file_path
        )
        
        # Write to file with proper error handling
        try:
            # Create directory if it doesn't exist
            import os
            directory = os.path.dirname(file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
                logger.info(f"Ensured directory exists: {directory}")
            
            # Write the file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(yaml_content)
            
            # Set file permissions (readable by all, writable by owner)
            # This ensures the uni-api container can read the file
            os.chmod(file_path, 0o644)
            logger.info(f"Set file permissions to 0o644 for {file_path}")
            
            logger.info(f"uni-api YAML exported successfully to {file_path}")
            return file_path
            
        except (IOError, OSError) as e:
            # Log detailed error but don't fail the entire sync
            error_msg = f"Failed to write uni-api YAML to {file_path}: {type(e).__name__}: {e}"
            logger.error(error_msg)
            raise IOError(error_msg)
