"""
RDS service manager for discovering and managing RDS instances and clusters.
"""
from typing import List, Dict, Any
from datetime import datetime

from .base import BaseServiceManager
from .models import Resource, OperationResult
from ..core.exceptions import ServiceError


class RDSServiceManager(BaseServiceManager):
    """Service manager for RDS instances and Aurora clusters."""
    
    @property
    def service_name(self) -> str:
        return 'rds'
    
    def discover_resources(self) -> List[Resource]:
        """Discover all RDS instances and Aurora clusters in the region.
        
        Returns:
            List of RDS resources as Resource objects
            
        Raises:
            ServiceError: If discovery fails
        """
        try:
            resources = []
            
            # Discover RDS instances
            db_instances = self.client.describe_db_instances()
            for instance in db_instances['DBInstances']:
                # Skip instances that are being deleted
                if instance['DBInstanceStatus'] == 'deleting':
                    continue
                
                # Extract tags
                tags = {}
                try:
                    tag_response = self.client.list_tags_for_resource(
                        ResourceName=instance['DBInstanceArn']
                    )
                    for tag in tag_response['TagList']:
                        tags[tag['Key']] = tag['Value']
                except Exception:
                    # Tags might not be accessible, continue without them
                    pass
                
                resource = Resource(
                    service_type='rds',
                    resource_id=instance['DBInstanceIdentifier'],
                    region=self.region,
                    current_state=instance['DBInstanceStatus'],
                    tags=tags,
                    metadata={
                        'engine': instance['Engine'],
                        'engine_version': instance['EngineVersion'],
                        'instance_class': instance['DBInstanceClass'],
                        'allocated_storage': instance.get('AllocatedStorage'),
                        'storage_type': instance.get('StorageType'),
                        'multi_az': instance.get('MultiAZ', False),
                        'availability_zone': instance.get('AvailabilityZone'),
                        'vpc_security_groups': [sg['VpcSecurityGroupId'] for sg in instance.get('VpcSecurityGroups', [])],
                        'db_subnet_group': instance.get('DBSubnetGroup', {}).get('DBSubnetGroupName'),
                        'resource_type': 'db_instance'
                    }
                )
                resources.append(resource)
            
            # Discover Aurora clusters
            db_clusters = self.client.describe_db_clusters()
            for cluster in db_clusters['DBClusters']:
                # Skip clusters that are being deleted
                if cluster['Status'] == 'deleting':
                    continue
                
                # Extract tags
                tags = {}
                try:
                    tag_response = self.client.list_tags_for_resource(
                        ResourceName=cluster['DBClusterArn']
                    )
                    for tag in tag_response['TagList']:
                        tags[tag['Key']] = tag['Value']
                except Exception:
                    # Tags might not be accessible, continue without them
                    pass
                
                resource = Resource(
                    service_type='rds',
                    resource_id=cluster['DBClusterIdentifier'],
                    region=self.region,
                    current_state=cluster['Status'],
                    tags=tags,
                    metadata={
                        'engine': cluster['Engine'],
                        'engine_version': cluster['EngineVersion'],
                        'cluster_members': [member['DBInstanceIdentifier'] for member in cluster.get('DBClusterMembers', [])],
                        'multi_az': cluster.get('MultiAZ', False),
                        'availability_zones': cluster.get('AvailabilityZones', []),
                        'vpc_security_groups': [sg['VpcSecurityGroupId'] for sg in cluster.get('VpcSecurityGroups', [])],
                        'db_subnet_group': cluster.get('DBSubnetGroup'),
                        'resource_type': 'db_cluster'
                    }
                )
                resources.append(resource)
            
            return resources
            
        except Exception as e:
            self._handle_aws_error(e, 'discovery')
    
    def pause_resource(self, resource: Resource) -> OperationResult:
        """Stop an RDS instance or cluster.
        
        Args:
            resource: RDS resource to stop
            
        Returns:
            Result of the stop operation
        """
        start_time = datetime.now()
        
        try:
            resource_type = resource.metadata.get('resource_type')
            
            if resource_type == 'db_instance':
                return self._pause_db_instance(resource, start_time)
            elif resource_type == 'db_cluster':
                return self._pause_db_cluster(resource, start_time)
            else:
                return self._create_operation_result(
                    resource=resource,
                    operation='pause',
                    success=False,
                    message=f"Unknown RDS resource type: {resource_type}",
                    start_time=start_time,
                    duration=0.0
                )
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return self._create_operation_result(
                resource=resource,
                operation='pause',
                success=False,
                message=f"Failed to stop RDS resource {resource.resource_id}: {str(e)}",
                start_time=start_time,
                duration=duration
            )
    
    def resume_resource(self, resource: Resource) -> OperationResult:
        """Start an RDS instance or cluster.
        
        Args:
            resource: RDS resource to start
            
        Returns:
            Result of the start operation
        """
        start_time = datetime.now()
        
        try:
            resource_type = resource.metadata.get('resource_type')
            
            if resource_type == 'db_instance':
                return self._resume_db_instance(resource, start_time)
            elif resource_type == 'db_cluster':
                return self._resume_db_cluster(resource, start_time)
            else:
                return self._create_operation_result(
                    resource=resource,
                    operation='resume',
                    success=False,
                    message=f"Unknown RDS resource type: {resource_type}",
                    start_time=start_time,
                    duration=0.0
                )
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return self._create_operation_result(
                resource=resource,
                operation='resume',
                success=False,
                message=f"Failed to start RDS resource {resource.resource_id}: {str(e)}",
                start_time=start_time,
                duration=duration
            )
    
    def _pause_db_instance(self, resource: Resource, start_time: datetime) -> OperationResult:
        """Stop a DB instance."""
        # Check if instance can be stopped
        if resource.current_state not in ['available']:
            return self._create_operation_result(
                resource=resource,
                operation='pause',
                success=False,
                message=f"DB instance {resource.resource_id} cannot be stopped (current state: {resource.current_state})",
                start_time=start_time,
                duration=0.0
            )
        
        # Stop the instance
        self.client.stop_db_instance(DBInstanceIdentifier=resource.resource_id)
        
        # Wait for instance to stop
        waiter = self.client.get_waiter('db_instance_stopped')
        waiter.wait(
            DBInstanceIdentifier=resource.resource_id,
            WaiterConfig={'Delay': 30, 'MaxAttempts': 60}  # Wait up to 30 minutes
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return self._create_operation_result(
            resource=resource,
            operation='pause',
            success=True,
            message=f"Successfully stopped RDS instance {resource.resource_id}",
            start_time=start_time,
            duration=duration
        )
    
    def _resume_db_instance(self, resource: Resource, start_time: datetime) -> OperationResult:
        """Start a DB instance."""
        # Check if instance can be started
        if resource.current_state not in ['stopped']:
            return self._create_operation_result(
                resource=resource,
                operation='resume',
                success=False,
                message=f"DB instance {resource.resource_id} cannot be started (current state: {resource.current_state})",
                start_time=start_time,
                duration=0.0
            )
        
        # Start the instance
        self.client.start_db_instance(DBInstanceIdentifier=resource.resource_id)
        
        # Wait for instance to be available
        waiter = self.client.get_waiter('db_instance_available')
        waiter.wait(
            DBInstanceIdentifier=resource.resource_id,
            WaiterConfig={'Delay': 30, 'MaxAttempts': 60}  # Wait up to 30 minutes
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return self._create_operation_result(
            resource=resource,
            operation='resume',
            success=True,
            message=f"Successfully started RDS instance {resource.resource_id}",
            start_time=start_time,
            duration=duration
        )
    
    def _pause_db_cluster(self, resource: Resource, start_time: datetime) -> OperationResult:
        """Stop a DB cluster."""
        # Check if cluster can be stopped
        if resource.current_state not in ['available']:
            return self._create_operation_result(
                resource=resource,
                operation='pause',
                success=False,
                message=f"DB cluster {resource.resource_id} cannot be stopped (current state: {resource.current_state})",
                start_time=start_time,
                duration=0.0
            )
        
        # Stop the cluster
        self.client.stop_db_cluster(DBClusterIdentifier=resource.resource_id)
        
        # Wait for cluster to stop
        waiter = self.client.get_waiter('db_cluster_stopped')
        waiter.wait(
            DBClusterIdentifier=resource.resource_id,
            WaiterConfig={'Delay': 30, 'MaxAttempts': 60}  # Wait up to 30 minutes
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return self._create_operation_result(
            resource=resource,
            operation='pause',
            success=True,
            message=f"Successfully stopped RDS cluster {resource.resource_id}",
            start_time=start_time,
            duration=duration
        )
    
    def _resume_db_cluster(self, resource: Resource, start_time: datetime) -> OperationResult:
        """Start a DB cluster."""
        # Check if cluster can be started
        if resource.current_state not in ['stopped']:
            return self._create_operation_result(
                resource=resource,
                operation='resume',
                success=False,
                message=f"DB cluster {resource.resource_id} cannot be started (current state: {resource.current_state})",
                start_time=start_time,
                duration=0.0
            )
        
        # Start the cluster
        self.client.start_db_cluster(DBClusterIdentifier=resource.resource_id)
        
        # Wait for cluster to be available
        waiter = self.client.get_waiter('db_cluster_available')
        waiter.wait(
            DBClusterIdentifier=resource.resource_id,
            WaiterConfig={'Delay': 30, 'MaxAttempts': 60}  # Wait up to 30 minutes
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return self._create_operation_result(
            resource=resource,
            operation='resume',
            success=True,
            message=f"Successfully started RDS cluster {resource.resource_id}",
            start_time=start_time,
            duration=duration
        )