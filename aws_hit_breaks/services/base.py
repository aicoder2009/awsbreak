"""
Base service manager interface for AWS services.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import boto3
from datetime import datetime

from .models import Resource, OperationResult
from ..core.exceptions import ServiceError


class BaseServiceManager(ABC):
    """Abstract base class for all AWS service managers."""
    
    def __init__(self, session: boto3.Session, region: str):
        """Initialize the service manager with AWS session and region.
        
        Args:
            session: Authenticated boto3 session
            region: AWS region to operate in
        """
        self.session = session
        self.region = region
        self._client = None
    
    @property
    def client(self):
        """Lazy-loaded AWS service client."""
        if self._client is None:
            self._client = self.session.client(self.service_name, region_name=self.region)
        return self._client
    
    @property
    @abstractmethod
    def service_name(self) -> str:
        """AWS service name (e.g., 'ec2', 'rds', 'ecs')."""
        pass
    
    @abstractmethod
    def discover_resources(self) -> List[Resource]:
        """Discover all resources of this service type in the region.
        
        Returns:
            List of discovered resources
            
        Raises:
            ServiceError: If discovery fails
        """
        pass
    
    @abstractmethod
    def pause_resource(self, resource: Resource) -> OperationResult:
        """Pause/stop a specific resource.
        
        Args:
            resource: Resource to pause
            
        Returns:
            Result of the pause operation
            
        Raises:
            ServiceError: If pause operation fails
        """
        pass
    
    @abstractmethod
    def resume_resource(self, resource: Resource) -> OperationResult:
        """Resume/start a specific resource.
        
        Args:
            resource: Resource to resume
            
        Returns:
            Result of the resume operation
            
        Raises:
            ServiceError: If resume operation fails
        """
        pass
    
    def get_resource_cost(self, resource: Resource) -> Optional[float]:
        """Get estimated hourly cost for a resource.
        
        Args:
            resource: Resource to calculate cost for
            
        Returns:
            Estimated hourly cost in USD, or None if unavailable
        """
        # Default implementation returns None
        # Subclasses can override to provide cost estimation
        return None
    
    def _create_operation_result(
        self, 
        resource: Resource, 
        operation: str, 
        success: bool, 
        message: str,
        start_time: datetime,
        duration: Optional[float] = None
    ) -> OperationResult:
        """Helper method to create operation results.
        
        Args:
            resource: Resource that was operated on
            operation: Type of operation ('pause', 'resume', 'discover')
            success: Whether the operation succeeded
            message: Success or error message
            start_time: When the operation started
            duration: How long the operation took in seconds
            
        Returns:
            OperationResult instance
        """
        return OperationResult(
            success=success,
            resource=resource,
            operation=operation,
            message=message,
            timestamp=start_time,
            duration=duration
        )
    
    def _handle_aws_error(self, error: Exception, operation: str, resource_id: str = None) -> None:
        """Handle AWS API errors and convert to ServiceError.
        
        Args:
            error: The original AWS error
            operation: Operation that failed
            resource_id: ID of resource being operated on (if applicable)
            
        Raises:
            ServiceError: Wrapped error with context
        """
        resource_context = f" for resource {resource_id}" if resource_id else ""
        error_message = f"AWS {self.service_name} {operation} failed{resource_context}: {str(error)}"
        raise ServiceError(error_message, details=str(error))