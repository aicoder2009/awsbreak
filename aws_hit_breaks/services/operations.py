"""
High-level pause and resume operations for AWS resources.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

from .orchestrator import OperationOrchestrator
from .models import Resource, OperationResult, AccountSnapshot
from ..core.exceptions import ServiceError


logger = logging.getLogger(__name__)


class PauseResumeOperations:
    """High-level operations for pausing and resuming AWS resources."""
    
    def __init__(self, orchestrator: OperationOrchestrator):
        """Initialize with an operation orchestrator.
        
        Args:
            orchestrator: OperationOrchestrator instance
        """
        self.orchestrator = orchestrator
    
    def comprehensive_pause(
        self,
        service_types: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
        resource_filters: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ) -> Tuple[List[OperationResult], Optional[AccountSnapshot]]:
        """Perform comprehensive pause of all AWS resources.
        
        This method:
        1. Discovers all resources across specified services and regions
        2. Filters resources based on provided criteria
        3. Creates an account snapshot with original states
        4. Pauses all resources (EC2 instances, RDS databases, ECS services, ASGs)
        
        Args:
            service_types: List of service types to pause. If None, pauses all supported services.
            regions: List of regions to operate in. If None, uses orchestrator's regions.
            resource_filters: Optional filters to apply to resources
            dry_run: If True, shows what would be paused without making changes
            
        Returns:
            Tuple of (operation_results, account_snapshot)
            For dry_run, account_snapshot will be None
            
        Raises:
            ServiceError: If discovery or pause operations fail completely
        """
        logger.info("Starting comprehensive pause operation")
        
        # Use orchestrator's regions if none specified
        if regions:
            # Temporarily override orchestrator regions
            original_regions = self.orchestrator.regions
            self.orchestrator.regions = regions
        
        try:
            # Step 1: Discover all resources
            logger.info("Discovering resources...")
            all_resources = self.orchestrator.discover_all_resources(service_types)
            
            if not all_resources:
                logger.warning("No resources found to pause")
                return [], None
            
            # Step 2: Apply filters if provided
            filtered_resources = self._apply_resource_filters(all_resources, resource_filters)
            
            logger.info(f"Found {len(filtered_resources)} resources to pause after filtering")
            
            # Step 3: Separate resources by pausability
            pausable_resources = self._filter_pausable_resources(filtered_resources)
            
            if not pausable_resources:
                logger.warning("No pausable resources found")
                return [], None
            
            logger.info(f"Identified {len(pausable_resources)} pausable resources")
            
            # Step 4: Handle dry run
            if dry_run:
                return self._generate_dry_run_results(pausable_resources), None
            
            # Step 5: Perform actual pause operations
            logger.info("Executing pause operations...")
            operation_results, snapshot = self.orchestrator.pause_resources(pausable_resources)
            
            # Step 6: Log summary
            summary = self.orchestrator.get_operation_summary(operation_results)
            logger.info(f"Pause operation summary: {summary['successful_operations']}/{summary['total_operations']} succeeded")
            
            if summary['failed_operations'] > 0:
                logger.warning(f"{summary['failed_operations']} operations failed:")
                for failed_resource in summary['failed_resources']:
                    logger.warning(f"  - {failed_resource['service_type']} {failed_resource['resource_id']}: {failed_resource['error_message']}")
            
            return operation_results, snapshot
            
        finally:
            # Restore original regions if they were overridden
            if regions:
                self.orchestrator.regions = original_regions
    
    def comprehensive_resume(
        self,
        snapshot: AccountSnapshot,
        dry_run: bool = False
    ) -> List[OperationResult]:
        """Perform comprehensive resume of resources from a snapshot.
        
        This method:
        1. Validates the snapshot
        2. Resumes all resources to their original states
        3. Verifies successful restoration
        
        Args:
            snapshot: Account snapshot containing resources to resume
            dry_run: If True, shows what would be resumed without making changes
            
        Returns:
            List of operation results
            
        Raises:
            ServiceError: If snapshot is invalid or resume operations fail completely
        """
        logger.info(f"Starting comprehensive resume operation from snapshot {snapshot.snapshot_id}")
        
        # Step 1: Validate snapshot
        self._validate_snapshot(snapshot)
        
        # Step 2: Handle dry run
        if dry_run:
            return self._generate_resume_dry_run_results(snapshot.resources)
        
        # Step 3: Perform actual resume operations
        logger.info("Executing resume operations...")
        operation_results = self.orchestrator.resume_resources(snapshot)
        
        # Step 4: Log summary
        summary = self.orchestrator.get_operation_summary(operation_results)
        logger.info(f"Resume operation summary: {summary['successful_operations']}/{summary['total_operations']} succeeded")
        
        if summary['failed_operations'] > 0:
            logger.warning(f"{summary['failed_operations']} operations failed:")
            for failed_resource in summary['failed_resources']:
                logger.warning(f"  - {failed_resource['service_type']} {failed_resource['resource_id']}: {failed_resource['error_message']}")
        
        return operation_results
    
    def _apply_resource_filters(
        self,
        resources: List[Resource],
        filters: Optional[Dict[str, Any]]
    ) -> List[Resource]:
        """Apply filters to resource list.
        
        Args:
            resources: List of resources to filter
            filters: Dictionary of filters to apply
            
        Returns:
            Filtered list of resources
        """
        if not filters:
            return resources
        
        filtered_resources = resources
        
        # Filter by service types
        if 'service_types' in filters:
            service_types = filters['service_types']
            filtered_resources = [r for r in filtered_resources if r.service_type in service_types]
        
        # Filter by regions
        if 'regions' in filters:
            regions = filters['regions']
            filtered_resources = [r for r in filtered_resources if r.region in regions]
        
        # Filter by tags
        if 'tags' in filters:
            tag_filters = filters['tags']
            for key, value in tag_filters.items():
                filtered_resources = [
                    r for r in filtered_resources
                    if key in r.tags and r.tags[key] == value
                ]
        
        # Filter by exclusions
        if 'exclude_tags' in filters:
            exclude_tags = filters['exclude_tags']
            for key, value in exclude_tags.items():
                filtered_resources = [
                    r for r in filtered_resources
                    if key not in r.tags or r.tags[key] != value
                ]
        
        # Filter by resource IDs
        if 'resource_ids' in filters:
            resource_ids = filters['resource_ids']
            filtered_resources = [r for r in filtered_resources if r.resource_id in resource_ids]
        
        # Filter by exclusion resource IDs
        if 'exclude_resource_ids' in filters:
            exclude_ids = filters['exclude_resource_ids']
            filtered_resources = [r for r in filtered_resources if r.resource_id not in exclude_ids]
        
        return filtered_resources
    
    def _filter_pausable_resources(self, resources: List[Resource]) -> List[Resource]:
        """Filter resources to only include those that can be paused.
        
        Args:
            resources: List of resources to filter
            
        Returns:
            List of pausable resources
        """
        pausable_resources = []
        
        for resource in resources:
            if self._is_resource_pausable(resource):
                pausable_resources.append(resource)
            else:
                logger.debug(f"Skipping non-pausable resource: {resource.service_type} {resource.resource_id} (state: {resource.current_state})")
        
        return pausable_resources
    
    def _is_resource_pausable(self, resource: Resource) -> bool:
        """Check if a resource can be paused.
        
        Args:
            resource: Resource to check
            
        Returns:
            True if resource can be paused, False otherwise
        """
        if resource.service_type == 'ec2':
            return resource.current_state == 'running'
        elif resource.service_type == 'rds':
            return resource.current_state == 'available'
        elif resource.service_type == 'ecs':
            return resource.current_state in ['running', 'scaling_up', 'scaling_down']
        elif resource.service_type == 'autoscaling':
            return resource.current_state in ['running', 'suspended']
        else:
            return False
    
    def _generate_dry_run_results(self, resources: List[Resource]) -> List[OperationResult]:
        """Generate dry run results for pause operations.
        
        Args:
            resources: List of resources that would be paused
            
        Returns:
            List of simulated operation results
        """
        results = []
        current_time = datetime.now()
        
        for resource in resources:
            result = OperationResult(
                success=True,
                resource=resource,
                operation='pause',
                message=f"[DRY RUN] Would pause {resource.service_type} {resource.resource_id}",
                timestamp=current_time,
                duration=0.0
            )
            results.append(result)
        
        return results
    
    def _generate_resume_dry_run_results(self, resources: List[Resource]) -> List[OperationResult]:
        """Generate dry run results for resume operations.
        
        Args:
            resources: List of resources that would be resumed
            
        Returns:
            List of simulated operation results
        """
        results = []
        current_time = datetime.now()
        
        for resource in resources:
            result = OperationResult(
                success=True,
                resource=resource,
                operation='resume',
                message=f"[DRY RUN] Would resume {resource.service_type} {resource.resource_id}",
                timestamp=current_time,
                duration=0.0
            )
            results.append(result)
        
        return results
    
    def _validate_snapshot(self, snapshot: AccountSnapshot) -> None:
        """Validate that a snapshot is valid for resume operations.
        
        Args:
            snapshot: Snapshot to validate
            
        Raises:
            ServiceError: If snapshot is invalid
        """
        if not snapshot.resources:
            raise ServiceError("Snapshot contains no resources to resume")
        
        if not snapshot.original_states:
            raise ServiceError("Snapshot missing original states - cannot resume safely")
        
        # Check that all resources have corresponding original states
        for resource in snapshot.resources:
            state_key = f"{resource.service_type}:{resource.region}:{resource.resource_id}"
            if state_key not in snapshot.original_states:
                raise ServiceError(f"Missing original state for resource {state_key}")
        
        logger.info(f"Snapshot validation passed: {len(snapshot.resources)} resources ready for resume")