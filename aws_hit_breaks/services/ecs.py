"""
ECS service manager for discovering and managing ECS services.
"""
from typing import List, Dict, Any
from datetime import datetime
import time

from .base import BaseServiceManager
from .models import Resource, OperationResult
from ..core.exceptions import ServiceError


class ECSServiceManager(BaseServiceManager):
    """Service manager for ECS services."""
    
    @property
    def service_name(self) -> str:
        return 'ecs'
    
    def discover_resources(self) -> List[Resource]:
        """Discover all ECS services in the region.
        
        Returns:
            List of ECS services as Resource objects
            
        Raises:
            ServiceError: If discovery fails
        """
        try:
            resources = []
            
            # Get all clusters
            clusters_response = self.client.list_clusters()
            cluster_arns = clusters_response['clusterArns']
            
            if not cluster_arns:
                return resources
            
            # Get cluster details
            clusters_detail = self.client.describe_clusters(clusters=cluster_arns)
            
            for cluster in clusters_detail['clusters']:
                # Skip inactive clusters
                if cluster['status'] != 'ACTIVE':
                    continue
                
                cluster_name = cluster['clusterName']
                cluster_arn = cluster['clusterArn']
                
                # Get services in this cluster
                services_response = self.client.list_services(cluster=cluster_arn)
                service_arns = services_response['serviceArns']
                
                if not service_arns:
                    continue
                
                # Get service details
                services_detail = self.client.describe_services(
                    cluster=cluster_arn,
                    services=service_arns
                )
                
                for service in services_detail['services']:
                    # Skip inactive services
                    if service['status'] != 'ACTIVE':
                        continue
                    
                    # Extract tags
                    tags = {}
                    try:
                        tag_response = self.client.list_tags_for_resource(
                            resourceArn=service['serviceArn']
                        )
                        for tag in tag_response['tags']:
                            tags[tag['key']] = tag['value']
                    except Exception:
                        # Tags might not be accessible, continue without them
                        pass
                    
                    # Determine current state based on desired vs running count
                    desired_count = service['desiredCount']
                    running_count = service['runningCount']
                    
                    if desired_count == 0:
                        current_state = 'stopped'
                    elif running_count == desired_count:
                        current_state = 'running'
                    elif running_count < desired_count:
                        current_state = 'scaling_up'
                    else:
                        current_state = 'scaling_down'
                    
                    resource = Resource(
                        service_type='ecs',
                        resource_id=service['serviceName'],
                        region=self.region,
                        current_state=current_state,
                        tags=tags,
                        metadata={
                            'cluster_name': cluster_name,
                            'cluster_arn': cluster_arn,
                            'service_arn': service['serviceArn'],
                            'task_definition': service['taskDefinition'],
                            'desired_count': desired_count,
                            'running_count': running_count,
                            'pending_count': service['pendingCount'],
                            'platform_version': service.get('platformVersion'),
                            'launch_type': service.get('launchType', 'EC2'),
                            'network_configuration': service.get('networkConfiguration'),
                            'load_balancers': service.get('loadBalancers', []),
                            'service_registries': service.get('serviceRegistries', [])
                        }
                    )
                    resources.append(resource)
            
            return resources
            
        except Exception as e:
            self._handle_aws_error(e, 'discovery')
    
    def pause_resource(self, resource: Resource) -> OperationResult:
        """Scale an ECS service to zero tasks.
        
        Args:
            resource: ECS service resource to pause
            
        Returns:
            Result of the pause operation
        """
        start_time = datetime.now()
        
        try:
            # Check if service is already stopped
            if resource.current_state == 'stopped':
                return self._create_operation_result(
                    resource=resource,
                    operation='pause',
                    success=False,
                    message=f"ECS service {resource.resource_id} is already stopped",
                    start_time=start_time,
                    duration=0.0
                )
            
            cluster_arn = resource.metadata['cluster_arn']
            
            # Scale service to 0
            self.client.update_service(
                cluster=cluster_arn,
                service=resource.resource_id,
                desiredCount=0
            )
            
            # Wait for service to scale down
            self._wait_for_service_stable(cluster_arn, resource.resource_id)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return self._create_operation_result(
                resource=resource,
                operation='pause',
                success=True,
                message=f"Successfully scaled ECS service {resource.resource_id} to 0 tasks",
                start_time=start_time,
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return self._create_operation_result(
                resource=resource,
                operation='pause',
                success=False,
                message=f"Failed to pause ECS service {resource.resource_id}: {str(e)}",
                start_time=start_time,
                duration=duration
            )
    
    def resume_resource(self, resource: Resource) -> OperationResult:
        """Restore an ECS service to its original task count.
        
        Args:
            resource: ECS service resource to resume
            
        Returns:
            Result of the resume operation
        """
        start_time = datetime.now()
        
        try:
            # Get the original desired count from metadata
            original_desired_count = resource.metadata.get('desired_count', 1)
            
            # Check if service is already running at desired count
            if resource.current_state == 'running' and resource.metadata.get('desired_count', 0) > 0:
                return self._create_operation_result(
                    resource=resource,
                    operation='resume',
                    success=False,
                    message=f"ECS service {resource.resource_id} is already running",
                    start_time=start_time,
                    duration=0.0
                )
            
            cluster_arn = resource.metadata['cluster_arn']
            
            # Scale service back to original count
            self.client.update_service(
                cluster=cluster_arn,
                service=resource.resource_id,
                desiredCount=original_desired_count
            )
            
            # Wait for service to scale up
            self._wait_for_service_stable(cluster_arn, resource.resource_id)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return self._create_operation_result(
                resource=resource,
                operation='resume',
                success=True,
                message=f"Successfully scaled ECS service {resource.resource_id} to {original_desired_count} tasks",
                start_time=start_time,
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return self._create_operation_result(
                resource=resource,
                operation='resume',
                success=False,
                message=f"Failed to resume ECS service {resource.resource_id}: {str(e)}",
                start_time=start_time,
                duration=duration
            )
    
    def _wait_for_service_stable(self, cluster_arn: str, service_name: str, max_wait_time: int = 600):
        """Wait for ECS service to reach stable state.
        
        Args:
            cluster_arn: ARN of the ECS cluster
            service_name: Name of the ECS service
            max_wait_time: Maximum time to wait in seconds (default 10 minutes)
        """
        waiter = self.client.get_waiter('services_stable')
        waiter.wait(
            cluster=cluster_arn,
            services=[service_name],
            WaiterConfig={
                'Delay': 15,
                'MaxAttempts': max_wait_time // 15
            }
        )