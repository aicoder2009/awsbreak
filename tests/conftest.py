"""
Pytest configuration and shared fixtures for AWS Hit Breaks tests.
"""

import pytest
from moto import mock_aws
from unittest.mock import Mock, patch
import tempfile
import os
from pathlib import Path

from aws_hit_breaks.core.config import ConfigManager


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for config files during tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock the config directory to use temp directory
        with patch.object(ConfigManager, '_get_config_dir', return_value=Path(temp_dir)):
            yield Path(temp_dir)


@pytest.fixture
def mock_aws_services():
    """Mock all AWS services used by the application."""
    with mock_aws():
        yield


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "iam_role_arn": "arn:aws:iam::123456789012:role/AWSHitBreaksRole",
        "default_region": "us-east-1",
        "created_at": "2024-01-05T14:30:22Z",
        "version": "1.0.0"
    }


@pytest.fixture
def mock_console():
    """Mock Rich console for CLI testing."""
    return Mock()


@pytest.fixture
def sample_resources():
    """Sample AWS resources for testing."""
    return [
        {
            "type": "ec2",
            "id": "i-1234567890abcdef0",
            "region": "us-east-1",
            "state": "running",
            "cost_per_hour": 0.0416,
            "metadata": {
                "instance_type": "t3.medium",
                "availability_zone": "us-east-1a"
            }
        },
        {
            "type": "rds",
            "id": "my-database",
            "region": "us-east-1", 
            "state": "available",
            "cost_per_hour": 0.017,
            "metadata": {
                "db_instance_class": "db.t3.micro",
                "engine": "mysql"
            }
        }
    ]