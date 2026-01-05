"""Property-based tests for configuration management."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from aws_hit_breaks.core.config import Config, ConfigManager


# Hypothesis strategies for generating test data
@st.composite
def valid_iam_role_arn(draw):
    """Generate valid IAM role ARNs."""
    account_id = draw(st.integers(min_value=100000000000, max_value=999999999999))
    # Generate role names with only valid characters for IAM role names
    role_name = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+=,.@_-',
        min_size=1,
        max_size=64
    ).filter(lambda x: x and not x.startswith('-') and not x.endswith('-') and x.replace('-', '').replace('_', '').replace('.', '').replace('+', '').replace('=', '').replace(',', '').replace('@', '')))
    return f"arn:aws:iam::{account_id}:role/{role_name}"


@st.composite
def valid_aws_region(draw):
    """Generate valid AWS region names."""
    region_prefix = draw(st.sampled_from(['us', 'eu', 'ap', 'ca', 'sa']))
    region_middle = draw(st.sampled_from(['east', 'west', 'north', 'south', 'central', 'southeast', 'northeast']))
    region_suffix = draw(st.integers(min_value=1, max_value=9))
    return f"{region_prefix}-{region_middle}-{region_suffix}"


@st.composite
def valid_config(draw):
    """Generate valid Config objects."""
    return Config(
        iam_role_arn=draw(valid_iam_role_arn()),
        default_region=draw(valid_aws_region()),
        created_at=draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31))).replace(tzinfo=None),
        version=draw(st.text(min_size=1, max_size=20).filter(lambda x: x.strip()))
    )


class TestConfigurationRoundTrip:
    """Property-based tests for configuration round trip operations."""
    
    @given(config=valid_config())
    def test_config_save_load_round_trip(self, config):
        """
        Feature: aws-break-cli, Property 3: State Persistence Round Trip
        
        For any valid configuration, saving then loading should produce 
        an equivalent configuration object.
        
        **Validates: Requirements 1.5, 6.1**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            
            # Save the configuration
            config_manager.save_config(config)
            
            # Load the configuration back
            loaded_config = config_manager.load_config()
            
            # Verify round trip consistency
            assert loaded_config is not None
            assert loaded_config.iam_role_arn == config.iam_role_arn
            assert loaded_config.default_region == config.default_region
            assert loaded_config.version == config.version
            
            # Handle datetime comparison with some tolerance for serialization
            time_diff = abs((loaded_config.created_at - config.created_at).total_seconds())
            assert time_diff < 1.0  # Allow up to 1 second difference for serialization
    
    @given(config=valid_config())
    def test_config_file_exists_after_save(self, config):
        """
        Verify that configuration file exists after saving.
        
        **Validates: Requirements 8.3**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            
            # Initially no config should exist
            assert not config_manager.config_exists()
            
            # Save configuration
            config_manager.save_config(config)
            
            # Config should now exist
            assert config_manager.config_exists()
            assert config_manager.get_config_path().exists()
    
    @given(config=valid_config())
    def test_config_delete_removes_file(self, config):
        """
        Verify that deleting configuration removes the file.
        
        **Validates: Requirements 8.3**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            
            # Save and verify config exists
            config_manager.save_config(config)
            assert config_manager.config_exists()
            
            # Delete config
            config_manager.delete_config()
            
            # Config should no longer exist
            assert not config_manager.config_exists()
            assert not config_manager.get_config_path().exists()


class TestConfigValidation:
    """Unit tests for configuration validation."""
    
    def test_invalid_iam_role_arn_format(self):
        """Test that invalid IAM role ARN formats are rejected."""
        invalid_arns = [
            "invalid-arn",
            "arn:aws:iam::123:role/test",  # Account ID too short
            "arn:aws:iam::12345678901234:role/test",  # Account ID too long
            "arn:aws:s3:::bucket/key",  # Wrong service
            "arn:aws:iam::123456789012:user/test",  # Wrong resource type
        ]
        
        for invalid_arn in invalid_arns:
            with pytest.raises(ValueError, match="Invalid IAM role ARN format"):
                Config(iam_role_arn=invalid_arn)
    
    def test_invalid_region_format(self):
        """Test that invalid AWS region formats are rejected."""
        invalid_regions = [
            "invalid-region",
            "us-east",  # Missing number
            "us-east-10",  # Number too high
            "usa-east-1",  # Country code too long
            "us_east_1",  # Wrong separator
        ]
        
        for invalid_region in invalid_regions:
            with pytest.raises(ValueError, match="Invalid AWS region format"):
                Config(
                    iam_role_arn="arn:aws:iam::123456789012:role/TestRole",
                    default_region=invalid_region
                )
    
    def test_valid_config_creation(self):
        """Test that valid configurations can be created."""
        config = Config(
            iam_role_arn="arn:aws:iam::123456789012:role/AWSHitBreaksRole",
            default_region="us-east-1"
        )
        
        assert config.iam_role_arn == "arn:aws:iam::123456789012:role/AWSHitBreaksRole"
        assert config.default_region == "us-east-1"
        assert config.version == "1.0.0"
        assert isinstance(config.created_at, datetime)


class TestConfigManagerEdgeCases:
    """Unit tests for configuration manager edge cases."""
    
    def test_load_nonexistent_config(self):
        """Test loading configuration when file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            
            config = config_manager.load_config()
            assert config is None
    
    def test_load_corrupted_config(self):
        """Test loading corrupted configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            
            # Write invalid JSON
            with open(config_manager.get_config_path(), 'w') as f:
                f.write("invalid json content")
            
            with pytest.raises(ValueError, match="Invalid configuration file"):
                config_manager.load_config()
    
    def test_config_directory_creation(self):
        """Test that configuration directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "nested" / "config" / "dir"
            config_manager = ConfigManager(config_dir=config_dir)
            
            # Directory should be created
            assert config_dir.exists()
            assert config_dir.is_dir()