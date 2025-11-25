"""Tests for ProviderSplitter algorithm."""

import pytest
from app.services.provider_splitter import ProviderSplitter, ProviderConfig


class TestProviderSplitter:
    """Test suite for ProviderSplitter."""

    def test_sanitize_name_basic(self):
        """Test basic name sanitization."""
        assert ProviderSplitter.sanitize_name("Provider-A") == "provider-a"
        assert ProviderSplitter.sanitize_name("Provider_B") == "provider_b"
        assert ProviderSplitter.sanitize_name("Provider123") == "provider123"

    def test_sanitize_name_special_chars(self):
        """Test sanitization of special characters."""
        assert ProviderSplitter.sanitize_name("Provider.A") == "provider-a"
        assert ProviderSplitter.sanitize_name("Provider@#$B") == "provider-b"
        assert ProviderSplitter.sanitize_name("Provider A B") == "provider-a-b"

    def test_sanitize_name_consecutive_hyphens(self):
        """Test removal of consecutive hyphens."""
        assert ProviderSplitter.sanitize_name("Provider---A") == "provider-a"
        assert ProviderSplitter.sanitize_name("Provider..A") == "provider-a"

    def test_sanitize_name_leading_trailing(self):
        """Test removal of leading/trailing hyphens."""
        assert ProviderSplitter.sanitize_name("-Provider-") == "provider"
        assert ProviderSplitter.sanitize_name("---Provider---") == "provider"

    def test_sanitize_name_length_limit(self):
        """Test length limiting."""
        long_name = "a" * 150
        result = ProviderSplitter.sanitize_name(long_name)
        assert len(result) <= 100
        assert not result.endswith("-")

    def test_sanitize_name_empty(self):
        """Test empty name handling."""
        assert ProviderSplitter.sanitize_name("") == "model"
        assert ProviderSplitter.sanitize_name("---") == "model"

    def test_split_providers_no_duplicates(self):
        """Test splitting with no duplicate models."""
        providers = [
            ProviderConfig(
                name="ProviderA",
                base_url="https://api.a.com",
                api_key="key-a",
                channel_type="openai",
                models=["gpt-4", "gpt-3.5"]
            ),
            ProviderConfig(
                name="ProviderB",
                base_url="https://api.b.com",
                api_key="key-b",
                channel_type="openai",
                models=["claude-3", "claude-2"]
            )
        ]
        
        split_groups, aggregations = ProviderSplitter.split_providers(providers, {})
        
        # Should create 2 standard groups (one per provider)
        assert len(split_groups) == 2
        
        # No aggregations needed
        assert len(aggregations) == 0
        
        # Check group names
        group_names = [g.group_name for g in split_groups]
        assert "providera-0-no-aggregate-models" in group_names
        assert "providerb-0-no-aggregate-models" in group_names

    def test_split_providers_within_provider_duplicates(self):
        """Test splitting with duplicates within same provider."""
        providers = [
            ProviderConfig(
                name="ProviderA",
                base_url="https://api.a.com",
                api_key="key-a",
                channel_type="openai",
                models=["deepseek-v3.1", "Deepseek-V3.1", "gpt-4"]
            )
        ]
        
        rename_mapping = {
            "ProviderA": {
                "deepseek-v3.1": "deepseek-v3",
                "Deepseek-V3.1": "deepseek-v3"
            }
        }
        
        split_groups, aggregations = ProviderSplitter.split_providers(providers, rename_mapping)
        
        # Should create 3 groups:
        # - 2 for the duplicate model (deepseek-v3)
        # - 1 for non-duplicate (gpt-4)
        assert len(split_groups) == 3
        
        # Should have 1 aggregation (deepseek-v3)
        assert len(aggregations) == 1
        assert "deepseek-v3" in aggregations
        assert len(aggregations["deepseek-v3"]) == 2

    def test_split_providers_cross_provider_duplicates(self):
        """Test splitting with duplicates across providers."""
        providers = [
            ProviderConfig(
                name="ProviderA",
                base_url="https://api.a.com",
                api_key="key-a",
                channel_type="openai",
                models=["gpt-4-turbo"]
            ),
            ProviderConfig(
                name="ProviderB",
                base_url="https://api.b.com",
                api_key="key-b",
                channel_type="openai",
                models=["gpt-4-turbo-preview"]
            )
        ]
        
        rename_mapping = {
            "ProviderA": {"gpt-4-turbo": "gpt-4"},
            "ProviderB": {"gpt-4-turbo-preview": "gpt-4"}
        }
        
        split_groups, aggregations = ProviderSplitter.split_providers(providers, rename_mapping)
        
        # Should create 2 groups (one per provider)
        assert len(split_groups) == 2
        
        # Should have 1 aggregation (gpt-4)
        assert len(aggregations) == 1
        assert "gpt-4" in aggregations
        assert len(aggregations["gpt-4"]) == 2

    def test_split_providers_mixed_scenario(self):
        """Test splitting with mix of duplicates and unique models."""
        providers = [
            ProviderConfig(
                name="ProviderA",
                base_url="https://api.a.com",
                api_key="key-a",
                channel_type="openai",
                models=["gpt-4", "claude-3", "deepseek-v3"]
            ),
            ProviderConfig(
                name="ProviderB",
                base_url="https://api.b.com",
                api_key="key-b",
                channel_type="openai",
                models=["gpt-4", "gemini-pro"]
            )
        ]
        
        rename_mapping = {}
        
        split_groups, aggregations = ProviderSplitter.split_providers(providers, rename_mapping)
        
        # ProviderA: 1 group for duplicates (gpt-4), 1 for non-duplicates (claude-3, deepseek-v3)
        # ProviderB: 1 group for duplicates (gpt-4), 1 for non-duplicates (gemini-pro)
        assert len(split_groups) == 4
        
        # Should have 1 aggregation (gpt-4)
        assert len(aggregations) == 1
        assert "gpt-4" in aggregations
        assert len(aggregations["gpt-4"]) == 2

    def test_split_providers_model_redirect_rules(self):
        """Test that model redirect rules are correctly set."""
        providers = [
            ProviderConfig(
                name="ProviderA",
                base_url="https://api.a.com",
                api_key="key-a",
                channel_type="openai",
                models=["gpt-4-turbo-preview"]
            )
        ]
        
        rename_mapping = {
            "ProviderA": {"gpt-4-turbo-preview": "gpt-4"}
        }
        
        split_groups, aggregations = ProviderSplitter.split_providers(providers, rename_mapping)
        
        assert len(split_groups) == 1
        group = split_groups[0]
        
        # Check redirect rules: normalized -> original
        assert group.model_redirect_rules == {"gpt-4": "gpt-4-turbo-preview"}

    def test_split_providers_preserves_provider_info(self):
        """Test that provider information is preserved in split groups."""
        providers = [
            ProviderConfig(
                name="ProviderA",
                base_url="https://api.a.com",
                api_key="key-a",
                channel_type="anthropic",
                models=["claude-3"]
            )
        ]
        
        split_groups, aggregations = ProviderSplitter.split_providers(providers, {})
        
        assert len(split_groups) == 1
        group = split_groups[0]
        
        assert group.provider_name == "ProviderA"
        assert group.base_url == "https://api.a.com"
        assert group.api_key == "key-a"
        assert group.channel_type == "anthropic"
        assert group.group_type == "standard"

    def test_generate_aggregate_group_config(self):
        """Test aggregate group configuration generation."""
        aggregate = ProviderSplitter.generate_aggregate_group_config(
            model_name="gpt-4",
            sub_group_names=["providera-1-gpt-4", "providerb-1-gpt-4"],
            channel_type="openai"
        )
        
        assert aggregate.group_name == "aggregate-gpt-4"
        assert aggregate.group_type == "aggregate"
        assert aggregate.channel_type == "openai"
        assert aggregate.sub_group_names == ["providera-1-gpt-4", "providerb-1-gpt-4"]
        assert aggregate.model_redirect_rules == {"gpt-4": "gpt-4"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
