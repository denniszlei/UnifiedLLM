"""Model service for managing LLM models."""

import logging
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.model import Model
from app.models.provider import Provider

logger = logging.getLogger(__name__)


class ProviderSplit:
    """Represents a split provider configuration."""
    
    def __init__(
        self,
        group_name: str,
        models: List[Model],
        normalized_name: Optional[str] = None,
        is_duplicate_group: bool = False
    ):
        """Initialize provider split.
        
        Args:
            group_name: Name for the split group.
            models: List of models in this split.
            normalized_name: The normalized name for duplicate groups.
            is_duplicate_group: Whether this is a duplicate group.
        """
        self.group_name = group_name
        self.models = models
        self.normalized_name = normalized_name
        self.is_duplicate_group = is_duplicate_group
    
    def get_model_redirect_rules(self) -> Dict[str, str]:
        """Get model redirect rules for this split.
        
        Returns:
            Dictionary mapping normalized names to original names.
        """
        rules = {}
        for model in self.models:
            normalized = model.normalized_name if model.normalized_name else model.original_name
            rules[normalized] = model.original_name
        return rules


class ModelService:
    """Service for managing LLM models."""

    def __init__(self):
        """Initialize model service."""
        pass

    def normalize_model(
        self,
        db: Session,
        model_id: int,
        normalized_name: str,
        allow_duplicates: bool = True
    ) -> Model:
        """Normalize a model name.
        
        Updates the model mapping with a new normalized name while preserving
        the original provider model name for API calls.
        
        Args:
            db: Database session.
            model_id: Model ID to normalize.
            normalized_name: New normalized name for the model.
            allow_duplicates: Whether to allow duplicate normalized names within provider.
                             When True, duplicates trigger provider splitting.
                             When False, duplicates raise an error (for UI validation).
            
        Returns:
            Updated Model instance.
            
        Raises:
            ValueError: If model not found or (if allow_duplicates=False) duplicate 
                       normalized name within provider.
        """
        # Get the model
        model = db.query(Model).filter(Model.id == model_id).first()
        if not model:
            raise ValueError(f"Model {model_id} not found")
        
        # Check for duplicate normalized name within the same provider
        duplicate = db.query(Model).filter(
            Model.provider_id == model.provider_id,
            Model.normalized_name == normalized_name,
            Model.id != model_id,
            Model.is_active == True
        ).first()
        
        if duplicate:
            if not allow_duplicates:
                raise ValueError(
                    f"Duplicate normalized name '{normalized_name}' already exists "
                    f"for provider {model.provider_id} (model ID: {duplicate.id})"
                )
            else:
                logger.warning(
                    f"Creating duplicate normalized name '{normalized_name}' for provider "
                    f"{model.provider_id}. This will trigger provider splitting."
                )
        
        # Update the normalized name
        model.normalized_name = normalized_name
        model.updated_at = datetime.utcnow()
        
        try:
            db.commit()
            db.refresh(model)
            logger.info(
                f"Model {model_id} normalized: '{model.original_name}' -> '{normalized_name}'"
            )
            return model
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to normalize model {model_id}: {e}")
            raise

    def reset_model_name(self, db: Session, model_id: int) -> Model:
        """Reset a model name to its original provider name.
        
        Args:
            db: Database session.
            model_id: Model ID to reset.
            
        Returns:
            Updated Model instance.
            
        Raises:
            ValueError: If model not found.
        """
        model = db.query(Model).filter(Model.id == model_id).first()
        if not model:
            raise ValueError(f"Model {model_id} not found")
        
        # Reset normalized name to None (will use original_name)
        model.normalized_name = None
        model.updated_at = datetime.utcnow()
        
        try:
            db.commit()
            db.refresh(model)
            logger.info(f"Model {model_id} name reset to original: '{model.original_name}'")
            return model
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to reset model {model_id}: {e}")
            raise

    def detect_duplicates(self, db: Session, provider_id: int) -> Dict[str, List[Model]]:
        """Detect duplicate normalized names within a provider.
        
        Args:
            db: Database session.
            provider_id: Provider ID to check for duplicates.
            
        Returns:
            Dictionary mapping normalized names to lists of models with that name.
            Only includes names that appear more than once.
        """
        # Get all active models for the provider
        models = db.query(Model).filter(
            Model.provider_id == provider_id,
            Model.is_active == True
        ).all()
        
        # Group by effective name (normalized_name if set, otherwise original_name)
        name_groups: Dict[str, List[Model]] = {}
        for model in models:
            effective_name = model.normalized_name if model.normalized_name else model.original_name
            if effective_name not in name_groups:
                name_groups[effective_name] = []
            name_groups[effective_name].append(model)
        
        # Filter to only duplicates (names with more than one model)
        duplicates = {
            name: models_list
            for name, models_list in name_groups.items()
            if len(models_list) > 1
        }
        
        if duplicates:
            logger.info(
                f"Found {len(duplicates)} duplicate normalized names for provider {provider_id}"
            )
        
        return duplicates

    def get_models_by_provider(
        self,
        db: Session,
        provider_id: int,
        include_inactive: bool = False
    ) -> List[Model]:
        """Get all models for a provider.
        
        Args:
            db: Database session.
            provider_id: Provider ID.
            include_inactive: Whether to include inactive (deleted) models.
            
        Returns:
            List of Model instances.
        """
        query = db.query(Model).filter(Model.provider_id == provider_id)
        
        if not include_inactive:
            query = query.filter(Model.is_active == True)
        
        return query.all()

    def get_model(self, db: Session, model_id: int) -> Optional[Model]:
        """Get a model by ID.
        
        Args:
            db: Database session.
            model_id: Model ID.
            
        Returns:
            Model instance or None if not found.
        """
        return db.query(Model).filter(Model.id == model_id).first()

    def delete_model(self, db: Session, model_id: int) -> bool:
        """Delete a model by marking it as inactive.
        
        Args:
            db: Database session.
            model_id: Model ID to delete.
            
        Returns:
            True if deleted, False if model not found.
        """
        model = self.get_model(db, model_id)
        if not model:
            return False
        
        model.is_active = False
        model.updated_at = datetime.utcnow()
        
        try:
            db.commit()
            logger.info(f"Model {model_id} marked as inactive")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete model {model_id}: {e}")
            raise

    def bulk_delete_models(
        self,
        db: Session,
        model_ids: List[int],
        provider_id: Optional[int] = None
    ) -> Dict[str, any]:
        """Bulk delete models with atomicity.
        
        All models are deleted in a single transaction. If any error occurs,
        all changes are rolled back.
        
        Args:
            db: Database session.
            model_ids: List of model IDs to delete.
            provider_id: Optional provider ID to verify all models belong to same provider.
            
        Returns:
            Dictionary with deletion results:
                - deleted_count: Number of models deleted
                - warning: Optional warning message
                
        Raises:
            ValueError: If models don't all belong to the specified provider.
        """
        if not model_ids:
            return {"deleted_count": 0}
        
        try:
            # Get all models
            models = db.query(Model).filter(Model.id.in_(model_ids)).all()
            
            if not models:
                return {"deleted_count": 0}
            
            # Verify all models belong to the same provider if specified
            if provider_id:
                for model in models:
                    if model.provider_id != provider_id:
                        raise ValueError(
                            f"Model {model.id} does not belong to provider {provider_id}"
                        )
            
            # Check if we're deleting all models from a provider
            warning = None
            if provider_id:
                total_active = db.query(Model).filter(
                    Model.provider_id == provider_id,
                    Model.is_active == True
                ).count()
                
                if len(models) >= total_active:
                    warning = f"Deleting all {total_active} active models from provider {provider_id}"
                    logger.warning(warning)
            
            # Mark all models as inactive
            for model in models:
                model.is_active = False
                model.updated_at = datetime.utcnow()
            
            db.commit()
            
            result = {
                "deleted_count": len(models)
            }
            if warning:
                result["warning"] = warning
            
            logger.info(f"Bulk deleted {len(models)} models")
            return result
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to bulk delete models: {e}")
            raise

    def split_provider_by_duplicates(
        self,
        db: Session,
        provider_id: int
    ) -> List[ProviderSplit]:
        """Split a provider into separate logical groups based on duplicate normalized names.
        
        This algorithm handles the case where multiple models within a provider are
        normalized to the same name. Each duplicate normalized name gets its own group,
        and non-duplicate models are grouped together.
        
        Args:
            db: Database session.
            provider_id: Provider ID to split.
            
        Returns:
            List of ProviderSplit objects representing the split configuration.
        """
        # Get provider
        provider = db.query(Provider).filter(Provider.id == provider_id).first()
        if not provider:
            raise ValueError(f"Provider {provider_id} not found")
        
        # Get all active models for the provider
        models = self.get_models_by_provider(db, provider_id, include_inactive=False)
        
        if not models:
            logger.info(f"No models found for provider {provider_id}")
            return []
        
        # Step 1: Group models by normalized name
        normalized_groups: Dict[str, List[Model]] = {}
        for model in models:
            effective_name = model.normalized_name if model.normalized_name else model.original_name
            if effective_name not in normalized_groups:
                normalized_groups[effective_name] = []
            normalized_groups[effective_name].append(model)
        
        # Step 2: Identify duplicates and non-duplicates
        duplicates: Dict[str, List[Model]] = {}
        non_duplicates: List[Model] = []
        
        for name, model_list in normalized_groups.items():
            if len(model_list) > 1:
                duplicates[name] = model_list
            else:
                non_duplicates.append(model_list[0])
        
        # Step 3: Create split configurations
        splits: List[ProviderSplit] = []
        
        # Create a separate split for EACH model with a duplicate normalized name
        split_index = 0
        for normalized_name, model_list in sorted(duplicates.items()):
            for model in model_list:
                # Sanitize group name: convert dots to dashes
                sanitized_name = normalized_name.replace('.', '-')
                group_name = f"{provider.name}-{split_index}-{sanitized_name}"
                
                split = ProviderSplit(
                    group_name=group_name,
                    models=[model],  # Each split contains a single model
                    normalized_name=normalized_name,
                    is_duplicate_group=True
                )
                splits.append(split)
                split_index += 1
                
                logger.debug(
                    f"Created duplicate split '{group_name}' for model '{model.original_name}' "
                    f"with normalized name '{normalized_name}'"
                )
        
        # Create a split for non-duplicate models if any exist
        if non_duplicates:
            group_name = f"{provider.name}-no-aggregate_models"
            split = ProviderSplit(
                group_name=group_name,
                models=non_duplicates,
                normalized_name=None,
                is_duplicate_group=False
            )
            splits.append(split)
            
            logger.debug(
                f"Created non-duplicate split '{group_name}' with {len(non_duplicates)} models"
            )
        
        logger.info(
            f"Split provider {provider_id} into {len(splits)} groups "
            f"({len(duplicates)} duplicate groups, "
            f"{'1' if non_duplicates else '0'} non-duplicate group)"
        )
        
        return splits

    def get_all_normalized_names(
        self,
        db: Session,
        provider_ids: Optional[List[int]] = None
    ) -> Dict[str, List[Tuple[int, Model]]]:
        """Get all normalized names across providers.
        
        This is useful for identifying which models appear across multiple providers
        and need aggregate groups.
        
        Args:
            db: Database session.
            provider_ids: Optional list of provider IDs to limit the search.
            
        Returns:
            Dictionary mapping normalized names to lists of (provider_id, model) tuples.
        """
        query = db.query(Model).filter(Model.is_active == True)
        
        if provider_ids:
            query = query.filter(Model.provider_id.in_(provider_ids))
        
        models = query.all()
        
        # Group by effective normalized name
        name_groups: Dict[str, List[Tuple[int, Model]]] = {}
        for model in models:
            effective_name = model.normalized_name if model.normalized_name else model.original_name
            if effective_name not in name_groups:
                name_groups[effective_name] = []
            name_groups[effective_name].append((model.provider_id, model))
        
        return name_groups

    def get_cross_provider_duplicates(
        self,
        db: Session,
        provider_ids: Optional[List[int]] = None
    ) -> Dict[str, List[Tuple[int, Model]]]:
        """Get normalized names that appear across multiple providers.
        
        These are candidates for aggregate groups.
        
        Args:
            db: Database session.
            provider_ids: Optional list of provider IDs to limit the search.
            
        Returns:
            Dictionary mapping normalized names to lists of (provider_id, model) tuples.
            Only includes names that appear in multiple providers.
        """
        all_names = self.get_all_normalized_names(db, provider_ids)
        
        # Filter to only names that appear in multiple providers
        cross_provider = {}
        for name, provider_model_list in all_names.items():
            # Get unique provider IDs
            unique_providers = set(provider_id for provider_id, _ in provider_model_list)
            if len(unique_providers) > 1:
                cross_provider[name] = provider_model_list
        
        if cross_provider:
            logger.info(
                f"Found {len(cross_provider)} normalized names appearing across multiple providers"
            )
        
        return cross_provider

    def batch_normalize_models(
        self,
        db: Session,
        updates: List[dict]
    ) -> Dict[str, any]:
        """Batch normalize model names.
        
        Updates multiple model names in a single transaction. All updates are
        applied atomically - if any error occurs, all changes are rolled back.
        
        Args:
            db: Database session.
            updates: List of dictionaries with 'model_id' and 'normalized_name' keys.
            
        Returns:
            Dictionary with update results:
                - updated_count: Number of models updated
                
        Raises:
            ValueError: If any model is not found or validation fails.
        """
        if not updates:
            return {"updated_count": 0}
        
        try:
            updated_count = 0
            
            for update in updates:
                model_id = update.get('model_id')
                normalized_name = update.get('normalized_name')
                
                if not model_id or not normalized_name:
                    raise ValueError("Each update must have 'model_id' and 'normalized_name'")
                
                # Get the model
                model = db.query(Model).filter(Model.id == model_id).first()
                if not model:
                    raise ValueError(f"Model {model_id} not found")
                
                # Update the normalized name (allow duplicates for provider splitting)
                model.normalized_name = normalized_name
                model.updated_at = datetime.utcnow()
                updated_count += 1
                
                logger.debug(
                    f"Batch update: Model {model_id} normalized to '{normalized_name}'"
                )
            
            db.commit()
            
            logger.info(f"Batch normalized {updated_count} models")
            return {"updated_count": updated_count}
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to batch normalize models: {e}")
            raise
