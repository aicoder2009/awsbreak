"""
Data models for AWS service management.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any


@dataclass
class Resource:
    """Represents an AWS resource that can be paused/resumed."""
    service_type: str           # 'ec2', 'rds', 'ecs', etc.
    resource_id: str           # Instance ID, DB identifier, etc.
    region: str                # AWS region
    current_state: str         # Current operational state
    tags: Dict[str, str]       # Resource tags
    metadata: Dict[str, Any]   # Service-specific metadata
    cost_per_hour: Optional[float] = None  # Estimated hourly cost


@dataclass
class OperationResult:
    """Result of a service operation (pause, resume, discover)."""
    success: bool
    resource: Resource
    operation: str             # 'pause', 'resume', 'discover'
    message: str              # Success/error message
    timestamp: datetime
    duration: Optional[float] = None  # Operation duration in seconds


@dataclass
class AccountSnapshot:
    """Snapshot of account state before operations."""
    snapshot_id: str          # Unique identifier
    timestamp: datetime       # When snapshot was created
    resources: List[Resource] # All discovered resources
    original_states: Dict[str, Dict]  # Original configurations
    operation_results: List[OperationResult]  # Operation history
    total_estimated_savings: float  # Estimated cost savings