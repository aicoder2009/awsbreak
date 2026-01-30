"""
Operation orchestrator for coordinating multi-service pause/resume operations.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from .base import BaseServiceManager
from .models import Resource, OperationResult, AccountSnapshot
from .ec2 import EC2ServiceManager
from .rds import RDSServiceManager
from .ecs import ECSServiceManager
from .autoscaling import AutoScalingServiceManager
from ..core.exceptions import ServiceError
from ..cli.keyboard import is_cancelled, poll_escape


logger = logging.getLogger(__name__)


class OperationOrchestrator:
    """Orchestrates pause/resume operations across multiple AWS services."""
    
    def __init__(self, session: boto3.Session, regions: Optional[List[str]] = None):
        """Initialize the orchestrator with AWS session and regions.
        
        Args:
            session: Authenticated boto3 session
            regions: List of AWS regions to operate in. If None, uses current region.
        """
        self.session = session
        self.regions = regions or [session.region_name or 'us-east-1']
        
        # Service manager classes
        self.service_managers = {
            'ec2': EC2ServiceManager,
            'rds': RDSServiceManager,
            'ecs': ECSServiceManager,
            'autoscaling': AutoScalingServiceManager
        }
        
        # Cache for service manager instances
        self._manager_cache: Dict[Tuple[str, str], BaseServiceManager] = {}
    
    def get_service_manager(self, service_type: str, region: str) -> BaseServiceManager:
        """Get or create a service manager instance.
        
        Args:
            service_type: Type of service ('ec2', 'rds', 'ecs', 'autoscaling')
            region: AWS region
            
        Returns:
            Service manager instance
            
        Raises:
            ServiceError: If service type is not supported
        """
        cache_key = (service_type, region)
        
        if cache_key not in self._manager_cache:
            if service_type not in self.service_managers:
                raise ServiceError(f"Unsupported service type: {service_type}")
            
            manager_class = self.service_managers[service_type]
            self._manager_cache[cache_key] = manager_class(self.session, region)
        
        return self._manager_cache[cache_key]
    
    def discover_all_resources(self, service_types: Optional[List[str]] = None) -> List[Resource]:
        """Discover all resources across all configured regions and services.
        
        Args:
            service_types: List of service types to discover. If None, discovers all.
            
        Returns:
            List of all discovered resources
            
        Raises:
            ServiceError: If discovery fails for all services
        """
        if service_types is None:
            service_types = list(self.service_managers.keys())
        
        all_resources = []
        discovery_errors = []
        
        # Use thread pool for parallel discovery across regions and services
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit discovery tasks
            future_to_context = {}
            
            for region in self.regions:
                for service_type in service_types:
                    # Poll for ESC key and check cancellation
                    poll_escape()
                    if is_cancelled():
                        logger.info("Discovery cancelled by user")
                        break
                    try:
                        manager = self.get_service_manager(service_type, region)
                        future = executor.submit(manager.discover_resources)
                        future_to_context[future] = (service_type, region)
                    except Exception as e:
                        discovery_errors.append(f"Failed to create {service_type} manager for {region}: {str(e)}")

                # Check for cancellation after inner loop
                if is_cancelled():
                    break

            # Collect results
            for future in as_completed(future_to_context):
                # Poll for ESC key and check cancellation
                poll_escape()
                if is_cancelled():
                    logger.info("Discovery cancelled - stopping result collection")
                    # Cancel pending futures
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                service_type, region = future_to_context[future]
                try:
                    resources = future.result()
                    all_resources.extend(resources)
                    logger.info(f"Discovered {len(resources)} {service_type} resources in {region}")
                except Exception as e:
                    error_msg = f"Discovery failed for {service_type} in {region}: {str(e)}"
                    discovery_errors.append(error_msg)
                    logger.error(error_msg)
        
        # Log summary
        logger.info(f"Discovery complete: {len(all_resources)} total resources found")
        if discovery_errors:
            logger.warning(f"Discovery errors: {len(discovery_errors)} services failed")
            for error in discovery_errors:
                logger.warning(f"  - {error}")
        
        return all_resources
    
    def pause_resources(self, resources: List[Resource], max_workers: int = 5) -> Tuple[List[OperationResult], AccountSnapshot]:
        """Pause multiple resources with error aggregation.
        
        Args:
            resources: List of resources to pause
            max_workers: Maximum number of concurrent operations
            
        Returns:
            Tuple of (operation_results, account_snapshot)
        """
        start_time = datetime.now()
        snapshot_id = f"pause-{start_time.strftime('%Y%m%d-%H%M%S')}"
        
        # Create snapshot with original states before any operations
        original_states = {}
        for resource in resources:
            original_states[f"{resource.service_type}:{resource.region}:{resource.resource_id}"] = {
                'current_state': resource.current_state,
                'metadata': resource.metadata.copy()
            }
        
        operation_results = []
        
        # Use thread pool for parallel pause operations
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit pause tasks
            future_to_resource = {}
            
            for resource in resources:
                # Poll for ESC key and check cancellation
                poll_escape()
                if is_cancelled():
                    logger.info("Pause operation cancelled by user")
                    break
                try:
                    manager = self.get_service_manager(resource.service_type, resource.region)
                    future = executor.submit(manager.pause_resource, resource)
                    future_to_resource[future] = resource
                except Exception as e:
                    # Create failed operation result for resources we can't even attempt
                    result = OperationResult(
                        success=False,
                        resource=resource,
                        operation='pause',
                        message=f"Failed to get service manager: {str(e)}",
                        timestamp=datetime.now(),
                        duration=0.0
                    )
                    operation_results.append(result)

            # Collect results
            for future in as_completed(future_to_resource):
                # Poll for ESC key and check cancellation
                poll_escape()
                if is_cancelled():
                    logger.info("Pause operation cancelled - stopping result collection")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                resource = future_to_resource[future]
                try:
                    result = future.result()
                    operation_results.append(result)

                    if result.success:
                        logger.info(f"Successfully paused {resource.service_type} {resource.resource_id}")
                    else:
                        logger.error(f"Failed to pause {resource.service_type} {resource.resource_id}: {result.message}")

                except Exception as e:
                    # Create failed operation result for unexpected errors
                    result = OperationResult(
                        success=False,
                        resource=resource,
                        operation='pause',
                        message=f"Unexpected error during pause: {str(e)}",
                        timestamp=datetime.now(),
                        duration=0.0
                    )
                    operation_results.append(result)
                    logger.error(f"Unexpected error pausing {resource.service_type} {resource.resource_id}: {str(e)}")
        
        # Calculate total estimated savings
        total_estimated_savings = 0.0
        for resource in resources:
            if resource.cost_per_hour:
                total_estimated_savings += resource.cost_per_hour * 24 * 30  # Monthly savings
        
        # Create account snapshot
        snapshot = AccountSnapshot(
            snapshot_id=snapshot_id,
            timestamp=start_time,
            resources=resources,
            original_states=original_states,
            operation_results=operation_results,
            total_estimated_savings=total_estimated_savings
        )
        
        # Log summary
        successful_operations = [r for r in operation_results if r.success]
        failed_operations = [r for r in operation_results if not r.success]
        
        logger.info(f"Pause operation complete: {len(successful_operations)} succeeded, {len(failed_operations)} failed")
        
        return operation_results, snapshot
    
    def resume_resources(self, snapshot: AccountSnapshot, max_workers: int = 5) -> List[OperationResult]:
        """Resume resources from an account snapshot.
        
        Args:
            snapshot: Account snapshot containing resources to resume
            max_workers: Maximum number of concurrent operations
            
        Returns:
            List of operation results
        """
        operation_results = []
        
        # Use thread pool for parallel resume operations
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit resume tasks
            future_to_resource = {}
            
            for resource in snapshot.resources:
                # Poll for ESC key and check cancellation
                poll_escape()
                if is_cancelled():
                    logger.info("Resume operation cancelled by user")
                    break
                try:
                    manager = self.get_service_manager(resource.service_type, resource.region)
                    future = executor.submit(manager.resume_resource, resource)
                    future_to_resource[future] = resource
                except Exception as e:
                    # Create failed operation result for resources we can't even attempt
                    result = OperationResult(
                        success=False,
                        resource=resource,
                        operation='resume',
                        message=f"Failed to get service manager: {str(e)}",
                        timestamp=datetime.now(),
                        duration=0.0
                    )
                    operation_results.append(result)

            # Collect results
            for future in as_completed(future_to_resource):
                # Poll for ESC key and check cancellation
                poll_escape()
                if is_cancelled():
                    logger.info("Resume operation cancelled - stopping result collection")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                resource = future_to_resource[future]
                try:
                    result = future.result()
                    operation_results.append(result)

                    if result.success:
                        logger.info(f"Successfully resumed {resource.service_type} {resource.resource_id}")
                    else:
                        logger.error(f"Failed to resume {resource.service_type} {resource.resource_id}: {result.message}")

                except Exception as e:
                    # Create failed operation result for unexpected errors
                    result = OperationResult(
                        success=False,
                        resource=resource,
                        operation='resume',
                        message=f"Unexpected error during resume: {str(e)}",
                        timestamp=datetime.now(),
                        duration=0.0
                    )
                    operation_results.append(result)
                    logger.error(f"Unexpected error resuming {resource.service_type} {resource.resource_id}: {str(e)}")
        
        # Log summary
        successful_operations = [r for r in operation_results if r.success]
        failed_operations = [r for r in operation_results if not r.success]
        
        logger.info(f"Resume operation complete: {len(successful_operations)} succeeded, {len(failed_operations)} failed")
        
        return operation_results
    
    def get_operation_summary(self, operation_results: List[OperationResult]) -> Dict[str, Any]:
        """Generate a summary of operation results.
        
        Args:
            operation_results: List of operation results to summarize
            
        Returns:
            Dictionary containing operation summary
        """
        successful_operations = [r for r in operation_results if r.success]
        failed_operations = [r for r in operation_results if not r.success]
        
        # Group by service type
        by_service = {}
        for result in operation_results:
            service_type = result.resource.service_type
            if service_type not in by_service:
                by_service[service_type] = {'success': 0, 'failed': 0, 'total': 0}
            
            by_service[service_type]['total'] += 1
            if result.success:
                by_service[service_type]['success'] += 1
            else:
                by_service[service_type]['failed'] += 1
        
        # Calculate total duration
        total_duration = sum(r.duration or 0 for r in operation_results)
        
        return {
            'total_operations': len(operation_results),
            'successful_operations': len(successful_operations),
            'failed_operations': len(failed_operations),
            'success_rate': len(successful_operations) / len(operation_results) if operation_results else 0,
            'total_duration_seconds': total_duration,
            'by_service_type': by_service,
            'failed_resources': [
                {
                    'service_type': r.resource.service_type,
                    'resource_id': r.resource.resource_id,
                    'region': r.resource.region,
                    'error_message': r.message
                }
                for r in failed_operations
            ]
        }