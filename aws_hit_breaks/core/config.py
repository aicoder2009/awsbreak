"""Configuration management for AWS Hit Breaks CLI."""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator


class Config(BaseModel):
    """Configuration model for AWS Hit Breaks CLI."""
    
    iam_role_arn: str = Field(..., description="IAM role ARN for AWS operations")
    default_region: str = Field(default="us-east-1", description="Default AWS region")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Configuration creation timestamp")
    version: str = Field(default="1.0.0", description="Configuration version")
    
    @field_validator('iam_role_arn')
    @classmethod
    def validate_iam_role_arn(cls, v: str) -> str:
        """Validate IAM role ARN format."""
        arn_pattern = r'^arn:aws:iam::\d{12}:role/[a-zA-Z0-9+=,.@_-]+$'
        if not re.match(arn_pattern, v):
            raise ValueError(
                f"Invalid IAM role ARN format: {v}. "
                "Expected format: arn:aws:iam::123456789012:role/RoleName"
            )
        return v
    
    @field_validator('default_region')
    @classmethod
    def validate_region(cls, v: str) -> str:
        """Validate AWS region format."""
        # Updated pattern to support regions like ap-southeast-3, me-central-1, eu-south-2
        region_pattern = r'^[a-z]{2,3}-[a-z]+-\d+$'
        if not re.match(region_pattern, v):
            raise ValueError(
                f"Invalid AWS region format: {v}. "
                "Expected format: us-east-1, eu-west-1, ap-southeast-3, etc."
            )
        return v


class ConfigManager:
    """Manages local configuration file for AWS Hit Breaks CLI."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize configuration manager.
        
        Args:
            config_dir: Optional custom configuration directory path.
                       Defaults to ~/.aws-hit-breaks/
        """
        if config_dir is None:
            config_dir = Path.home() / ".aws-hit-breaks"
        
        self.config_dir = config_dir
        self.config_file = config_dir / "config.json"
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def load_config(self) -> Optional[Config]:
        """Load configuration from file.
        
        Returns:
            Config object if file exists and is valid, None otherwise.
            
        Raises:
            ValueError: If configuration file is corrupted or invalid.
        """
        if not self.config_file.exists():
            return None
        
        try:
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
            
            # Convert created_at string back to datetime if needed
            if isinstance(config_data.get('created_at'), str):
                # Parse ISO format and ensure it's timezone-naive
                dt_str = config_data['created_at'].replace('Z', '+00:00')
                dt_with_tz = datetime.fromisoformat(dt_str)
                config_data['created_at'] = dt_with_tz.replace(tzinfo=None)
            
            return Config(**config_data)
        
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Invalid configuration file: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load configuration: {e}")
    
    def save_config(self, config: Config) -> None:
        """Save configuration to file.
        
        Args:
            config: Configuration object to save.
            
        Raises:
            OSError: If unable to write configuration file.
        """
        try:
            # Convert to dict and handle datetime serialization
            config_dict = config.model_dump()
            config_dict['created_at'] = config.created_at.isoformat() + 'Z'
            
            # Write atomically by writing to temp file first
            temp_file = self.config_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(config_dict, f, indent=2)
            
            # Atomic move
            temp_file.replace(self.config_file)
            
        except Exception as e:
            # Clean up temp file if it exists
            temp_file = self.config_file.with_suffix('.tmp')
            if temp_file.exists():
                temp_file.unlink()
            raise OSError(f"Failed to save configuration: {e}")
    
    def config_exists(self) -> bool:
        """Check if configuration file exists.
        
        Returns:
            True if configuration file exists, False otherwise.
        """
        return self.config_file.exists()
    
    def get_config_path(self) -> Path:
        """Get the configuration file path.
        
        Returns:
            Path to the configuration file.
        """
        return self.config_file
    
    def delete_config(self) -> None:
        """Delete the configuration file.
        
        Raises:
            OSError: If unable to delete configuration file.
        """
        if self.config_file.exists():
            try:
                self.config_file.unlink()
            except Exception as e:
                raise OSError(f"Failed to delete configuration: {e}")