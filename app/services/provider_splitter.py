"""Provider splitting algorithm - ported from reference implementation.

This module provides a pure, stateless algorithm for splitting providers
based on duplicate model names. It takes provider data as input and returns
complete split configurations ready for GPT-Load API calls.
"""

import re
import logging
from typing import Dict, List, Tuple, Any
from collections import defaultdict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """Provider configuration for splitting."""
    name: str
    base_url: str
    api_key: str
    channel_type: str
    models: List[str]  # List of original model names


@dataclass
class SplitGroup:
    """A split group configuration ready for GPT-Load."""
    group_name: str
    group_type: str  # 'standard' or 'aggregate'
    provider_name: str
    base_url: str
    api_key: str
    channel_type: str
    model_redirect_rules: Dict[str, str]  # {normalized_name: original_name}
    sub_group_names: List[str] = None  # For aggregate groups


class ProviderSplitter:
    """Provider splitting algorithm.
    
    This class provides a pure, stateless algorithm for splitting providers
    based on duplicate model names. The algorithm:
    
    1. Collects all models with their normalized names
    2. Identifies duplicates across all providers
    3. Splits each provider into separate groups for duplicates
    4. Creates aggregate group configurations for cross-provider duplicates
    
    The algorithm is designed to be database-independent and returns
    complete configurations ready for API calls.
    """
    
    @staticmethod
    def sanitize_name(name: str) -> str:
        """Sanitize name to meet GPT-Load requirements.
        
        GPT-Load group names must:
        - Contain only lowercase letters, numbers, hyphens, or underscores
        - Be 1-100 characters long
        
        Args:
            name: Original name to sanitize.
            
        Returns:
            Sanitized name meeting GPT-Load requirements.
        """
        # Convert to lowercase
        name = name.lower()
        
        # Replace disallowed characters with hyphens
        name = re.sub(r'[^a-z0-9\-_]', '-', name)
        
        # Remove consecutive hyphens
        name = re.sub(r'-+', '-', name)
        
        # Remove leading/trailing hyphens
        name = name.strip('-')
        
        # Limit length
        if len(name) > 100:
            name = name[:100].rstrip('-')
        
        # Ensure at least 1 character
        if not name:
            name = 'model'
        
        return name
    
    @staticmethod
    def split_providers(
        providers: List[ProviderConfig],
        rename_mapping: Dict[str, Dict[str, str]]
    ) -> Tuple[List[SplitGroup], Dict[str, List[str]]]:
        """Split providers based on duplicate model names.
        
        This is the core algorithm ported from the reference implementation.
        It handles both within-provider duplicates and cross-provider duplicates.
        
        Args:
            providers: List of provider configurations with their models.
            rename_mapping: Mapping of {provider_name: {original_name: normalized_name}}.
            
        Returns:
            Tuple of (split_groups, aggregations):
                - split_groups: List of standard group configurations
                - aggregations: Dict of {normalized_model: [group_names]} for aggregates
        """
        split_groups: List[SplitGroup] = []
        model_to_providers = defaultdict(list)  # {normalized_model: [(provider_name, original_name)]}
        
        # Step 1: Collect all models with their normalized names and sources
        for provider in providers:
            provider_name = provider.name
            models = provider.models
            renames = rename_mapping.get(provider_name, {})
            
            for original_model in models:
                # Get normalized name (or use original if not renamed)
                normalized_model = renames.get(original_model, original_model)
                model_to_providers[normalized_model].append((provider_name, original_model))
        
        # Step 2: Identify duplicate models (appear in multiple places)
        duplicate_models = {
            model: sources
            for model, sources in model_to_providers.items()
            if len(sources) > 1
        }
        
        logger.info(f"Found {len(duplicate_models)} duplicate models across all providers")
        
        # Step 3: Split each provider into groups
        for provider in providers:
            provider_name = provider.name
            base_url = provider.base_url
            api_key = provider.api_key
            channel_type = provider.channel_type
            models = provider.models
            renames = rename_mapping.get(provider_name, {})
            
            # Categorize models: duplicates vs non-duplicates
            duplicate_in_provider = defaultdict(list)  # {normalized_model: [original_names]}
            non_duplicate_models = {}  # {normalized_model: original_model}
            
            for original_model in models:
                normalized_model = renames.get(original_model, original_model)
                
                if normalized_model in duplicate_models:
                    # This model appears in multiple places (within or across providers)
                    duplicate_in_provider[normalized_model].append(original_model)
                else:
                    # This model is unique
                    non_duplicate_models[normalized_model] = original_model
            
            # Create group for non-duplicate models
            if non_duplicate_models:
                sanitized_provider = ProviderSplitter.sanitize_name(provider_name)
                group_name = f"{sanitized_provider}-0-no-aggregate-models"
                
                split_group = SplitGroup(
                    group_name=group_name,
                    group_type='standard',
                    provider_name=provider_name,
                    base_url=base_url,
                    api_key=api_key,
                    channel_type=channel_type,
                    model_redirect_rules={
                        normalized: original
                        for normalized, original in non_duplicate_models.items()
                    }
                )
                split_groups.append(split_group)
                logger.debug(f"Created non-duplicate group: {group_name} with {len(non_duplicate_models)} models")
            
            # Create separate group for each duplicate model instance
            for normalized_model, original_names in duplicate_in_provider.items():
                for idx, original_name in enumerate(original_names):
                    sanitized_provider = ProviderSplitter.sanitize_name(provider_name)
                    sanitized_model = ProviderSplitter.sanitize_name(normalized_model)
                    group_name = f"{sanitized_provider}-{idx + 1}-{sanitized_model}"
                    
                    split_group = SplitGroup(
                        group_name=group_name,
                        group_type='standard',
                        provider_name=provider_name,
                        base_url=base_url,
                        api_key=api_key,
                        channel_type=channel_type,
                        model_redirect_rules={
                            normalized_model: original_name
                        }
                    )
                    split_groups.append(split_group)
                    logger.debug(f"Created duplicate group: {group_name} for model {normalized_model}")
        
        # Step 4: Generate aggregation mappings
        aggregations = {}
        for model, sources in duplicate_models.items():
            provider_groups = []
            seen_groups = set()  # Prevent duplicates
            
            # Find all groups that offer this model
            for provider_name, original_name in sources:
                # Find the corresponding group name
                for split_group in split_groups:
                    if (split_group.provider_name == provider_name and
                        model in split_group.model_redirect_rules and
                        split_group.model_redirect_rules[model] == original_name and
                        split_group.group_name not in seen_groups):
                        provider_groups.append(split_group.group_name)
                        seen_groups.add(split_group.group_name)
                        break  # Found the matching group
            
            aggregations[model] = provider_groups
        
        logger.info(
            f"Split complete: {len(split_groups)} standard groups, "
            f"{len(aggregations)} models need aggregation"
        )
        
        return split_groups, aggregations
    
    @staticmethod
    def generate_aggregate_group_config(
        model_name: str,
        sub_group_names: List[str],
        channel_type: str = "openai"
    ) -> SplitGroup:
        """Generate configuration for an aggregate group.
        
        Args:
            model_name: Normalized model name.
            sub_group_names: List of standard group names to aggregate.
            channel_type: Channel type for the aggregate group.
            
        Returns:
            SplitGroup configuration for the aggregate group.
        """
        sanitized_model = ProviderSplitter.sanitize_name(model_name)
        aggregate_name = f"aggregate-{sanitized_model}"
        
        return SplitGroup(
            group_name=aggregate_name,
            group_type='aggregate',
            provider_name='',  # Aggregate groups don't belong to a single provider
            base_url='',  # Aggregate groups don't have upstream URLs
            api_key='',  # Aggregate groups don't have API keys
            channel_type=channel_type,
            model_redirect_rules={model_name: model_name},
            sub_group_names=sub_group_names
        )
