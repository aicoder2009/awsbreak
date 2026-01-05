"""
Auto Scaling Groups service manager for discovering and managing ASGs.
"""
from typing import List, Dict, Any
from datetime import datetime
import time

from .base import BaseServiceManager
from .models import Resource, OperationResult
from ..core.exceptions import ServiceError


class AutoScalingServiceManager(BaseServiceManager):
    """Service manager for Auto Scaling Groups."""
    
    @property
    def service_name(self) -> str:
        return 'autoscaling'
    
    def discover_resources(self) -> List[Resource]:
        """Discover all Auto Scaling Groups in the region.
        
        Returns:
            List of ASGs as Resource objects
            
        Raises:
            ServiceError: If discovery fails
        """
        try:
            resources = []
            
            # Get all Auto Scaling Groups
            paginator = self.client.get_paginator('describe_auto_scaling_groups')
            
            for page in paginator.paginate():
                for asg in page['AutoScalingGroups']:
                    # Extract tags
                    tags = {}
                    for tag in asg.get('Tags', []):
                        tags[tag['Key']] = tag['Value']
                    
                    # Determine current state
                    desired_capacity = asg['DesiredCapacity']
                    min_size = asg['MinSize']
                    max_size = asg['MaxSize']
                    
                    # Check if processes are suspended
                    suspended_processes = [p['ProcessName'] for p in asg.get('SuspendedProcesses', [])]
                    is_suspended = len(suspended_processes) > 0
                    
                    if is_suspended and desired_capacity == 0:
                        current_state = 'paused'
                    elif is_suspended:
                        current_state = 'suspended'
                    elif desired_capacity == 0:
                        current_state = 'stopped'
                    elif desired_capacity > 0:
                        current_state = 'running'
                    else:
                        current_state = 'unknown'
                    
                    resource = Resource(
                        service_type='autoscaling',
                        resource_id=asg['AutoScalingGroupName'],
                        region=self.region,
                        current_state=current_state,
                        tags=tags,
                        metadata={
                            'desired_capacity': desired_capacity,
                            'min_size': min_size,
                            'max_size': max_size,
                            'availability_zones': asg['AvailabilityZones'],
                            'vpc_zone_identifier': asg.get('VPCZoneIdentifier'),
                            'launch_configuration_name': asg.get('LaunchConfigurationName'),
                            'launch_template': asg.get('LaunchTemplate'),
                            'mixed_instances_policy': asg.get('MixedInstancesPolicy'),
                            'suspended_processes': suspended_processes,
                            'instances': [
                                {
                                    'instance_id': instance['InstanceId'],
                                    'lifecycle_state': instance['LifecycleState'],
                                    'health_status': instance['HealthStatus']
                                }
                                for instance in asg.get('Instances', [])
                            ],
                            'target_group_arns': asg.get('TargetGroupARNs', []),
                            'load_balancer_names': asg.get('LoadBalancerNames', [])
                        }
                    )
                    resources.append(resource)
            
            return resources
            
        except Exception as e:
            self._handle_aws_error(e, 'discovery')
    
    def pause_resource(self, resource: Resource) -> OperationResult:
        """Suspend Auto Scaling Group processes and set capacity to zero.
        
        Args:
            resource: ASG resource to pause
            
        Returns:
            Result of the pause operation
        """
        start_time = datetime.now()
        
        try:
            asg_name = resource.resource_id
            
            # Check if already paused
            if resource.current_state == 'paused':
                return self._create_operation_result(
                    resource=resource,
                    operation='pause',
                    success=False,
                    message=f"Auto Scaling Group {asg_name} is already paused",
                    start_time=start_time,
                    duration=0.0
                )
            
            # Suspend all scaling processes
            processes_to_suspend = [
                'Launch', 'Terminate', 'HealthCheck', 'ReplaceUnhealthy',
                'AZRebalance', 'AlarmNotification', 'ScheduledActions', 'AddToLoadBalancer'
            ]
            
            self.client.suspend_processes(
                AutoScalingGroupName=asg_name,
                ScalingProcesses=processes_to_suspend
            )
            
            # Set desired capacity to 0
            self.client.set_desired_capacity(
                AutoScalingGroupName=asg_name,
                DesiredCapacity=0,
                HonorCooldown=False
            )
            
            # Wait for instances to terminate
            self._wait_for_capacity_change(asg_name, target_capacity=0)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return self._create_operation_result(
                resource=resource,
                operation='pause',
                success=True,
                message=f"Successfully paused Auto Scaling Group {asg_name}",
                start_time=start_time,
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return self._create_operation_result(
                resource=resource,
                operation='pause',
                success=False,
                message=f"Failed to pause Auto Scaling Group {resource.resource_id}: {str(e)}",
                start_time=start_time,
                duration=duration
            )
    
    def resume_resource(self, resource: Resource) -> OperationResult:
        """Resume Auto Scaling Group processes and restore original capacity.
        
        Args:
            resource: ASG resource to resume
            
        Returns:
            Result of the resume operation
        """
        start_time = datetime.now()
        
        try:
            asg_name = resource.resource_id
            
            # Check if already running
            if resource.current_state == 'running':
                return self._create_operation_result(
                    resource=resource,
                    operation='resume',
                    success=False,
                    message=f"Auto Scaling Group {asg_name} is already running",
                    start_time=start_time,
                    duration=0.0
                )
            
            # Get original desired capacity from metadata
            original_desired_capacity = resource.metadata.get('desired_capacity', 1)
            
            # Resume all scaling processes
            processes_to_resume = [
                'Launch', 'Terminate', 'HealthCheck', 'ReplaceUnhealthy',
                'AZRebalance', 'AlarmNotification', 'ScheduledActions', 'AddToLoadBalancer'
            ]
            
            self.client.resume_processes(
                AutoScalingGroupName=asg_name,
                ScalingProcesses=processes_to_resume
            )
            
            # Restore original desired capacity
            self.client.set_desired_capacity(
                AutoScalingGroupName=asg_name,
                DesiredCapacity=original_desired_capacity,
                HonorCooldown=False
            )
            
            # Wait for instances to launch
            self._wait_for_capacity_change(asg_name, target_capacity=original_desired_capacity)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return self._create_operation_result(
                resource=resource,
                operation='resume',
                success=True,
                message=f"Successfully resumed Auto Scaling Group {asg_name} with {original_desired_capacity} instances",
                start_time=start_time,
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return self._create_operation_result(
                resource=resource,
                operation='resume',
                success=False,
                message=f"Failed to resume Auto Scaling Group {resource.resource_id}: {str(e)}",
                start_time=start_time,
                duration=duration
            )
    
    def _wait_for_capacity_change(self, asg_name: str, target_capacity: int, max_wait_time: int = 600):
        """Wait for Auto Scaling Group to reach target capacity.
        
        Args:
            asg_name: Name of the Auto Scaling Group
            target_capacity: Target desired capacity
            max_wait_time: Maximum time to wait in seconds (default 10 minutes)
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            try:
                response = self.client.describe_auto_scaling_groups(
                    AutoScalingGroupNames=[asg_name]
                )
                
                if not response['AutoScalingGroups']:
                    raise ServiceError(f"Auto Scaling Group {asg_name} not found")
                
                asg = response['AutoScalingGroups'][0]
                current_capacity = len([
                    instance for instance in asg.get('Instances', [])
                    if instance['LifecycleState'] == 'InService'
                ])
                
                if current_capacity == target_capacity:
                    return
                
                time.sleep(30)  # Wait 30 seconds before checking again
                
            except Exception as e:
                # If we can't check status, continue waiting
                time.sleep(30)
        
        # If we reach here, we've timed out
        raise ServiceError(f"Timeout waiting for Auto Scaling Group {asg_name} to reach capacity {target_capacity}")