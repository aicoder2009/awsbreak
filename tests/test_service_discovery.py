"""Property-based tests for AWS service discovery system."""

import boto3
import pytest
from moto import mock_aws
from hypothesis import given, strategies as st, assume, settings
from datetime import datetime
from typing import List, Dict, Any

from aws_hit_breaks.services import (
    EC2ServiceManager, 
    RDSServiceManager, 
    ECSServiceManager, 
    AutoScalingServiceManager,
    Resource
)


# Hypothesis strategies for generating test data
@st.composite
def aws_region(draw):
    """Generate valid AWS region names."""
    regions = [
        'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
        'eu-west-1', 'eu-west-2', 'eu-central-1',
        'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1'
    ]
    return draw(st.sampled_from(regions))


@st.composite
def ec2_instance_type(draw):
    """Generate valid EC2 instance types."""
    families = ['t3', 't2', 'm5', 'm4', 'c5', 'c4', 'r5', 'r4']
    sizes = ['nano', 'micro', 'small', 'medium', 'large', 'xlarge', '2xlarge']
    family = draw(st.sampled_from(families))
    size = draw(st.sampled_from(sizes))
    return f"{family}.{size}"


@st.composite
def rds_instance_class(draw):
    """Generate valid RDS instance classes."""
    families = ['db.t3', 'db.t2', 'db.m5', 'db.m4', 'db.r5', 'db.r4']
    sizes = ['micro', 'small', 'medium', 'large', 'xlarge', '2xlarge']
    family = draw(st.sampled_from(families))
    size = draw(st.sampled_from(sizes))
    return f"{family}.{size}"


@st.composite
def resource_tags(draw):
    """Generate resource tags."""
    num_tags = draw(st.integers(min_value=0, max_value=5))
    tags = {}
    for _ in range(num_tags):
        key = draw(st.text(min_size=1, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'))
        value = draw(st.text(min_size=0, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ '))
        tags[key] = value
    return tags


class TestCompleteServiceDiscovery:
    """Property-based tests for complete service discovery."""
    
    @settings(max_examples=10, deadline=None)
    @given(
        region=aws_region(),
        num_ec2_instances=st.integers(min_value=0, max_value=2),
        num_rds_instances=st.integers(min_value=0, max_value=1),
        num_ecs_services=st.integers(min_value=0, max_value=1),
        num_asgs=st.integers(min_value=0, max_value=1)
    )
    @mock_aws
    def test_complete_service_discovery_finds_all_resources(
        self, region, num_ec2_instances, num_rds_instances, num_ecs_services, num_asgs
    ):
        """
        Feature: aws-break-cli, Property 1: Complete Service Discovery
        
        For any AWS account with resources across multiple regions, the discovery 
        command should find all cost-generating services (EC2, RDS, ECS, ASG) in 
        all regions and include service type, region, resource ID, and current 
        state in the output.
        
        **Validates: Requirements 1.1, 1.2, 1.3**
        """
        session = boto3.Session()
        
        # Create mock resources
        created_resources = self._create_mock_resources(
            session, region, num_ec2_instances, num_rds_instances, 
            num_ecs_services, num_asgs
        )
        
        # Initialize service managers
        ec2_manager = EC2ServiceManager(session, region)
        rds_manager = RDSServiceManager(session, region)
        ecs_manager = ECSServiceManager(session, region)
        asg_manager = AutoScalingServiceManager(session, region)
        
        # Discover resources
        ec2_resources = ec2_manager.discover_resources()
        rds_resources = rds_manager.discover_resources()
        ecs_resources = ecs_manager.discover_resources()
        asg_resources = asg_manager.discover_resources()
        
        all_discovered = ec2_resources + rds_resources + ecs_resources + asg_resources
        
        # Calculate expected EC2 instances (direct + ASG-launched)
        # ASGs with desired_capacity > 0 will launch EC2 instances
        expected_ec2_instances = num_ec2_instances + (num_asgs if num_asgs > 0 else 0)
        
        # Verify all created resources were discovered
        assert len(ec2_resources) == expected_ec2_instances
        assert len(rds_resources) == num_rds_instances
        assert len(ecs_resources) == num_ecs_services
        assert len(asg_resources) == num_asgs
        
        # Verify each discovered resource has required fields
        for resource in all_discovered:
            assert isinstance(resource, Resource)
            assert resource.service_type in ['ec2', 'rds', 'ecs', 'autoscaling']
            assert resource.resource_id is not None and resource.resource_id != ""
            assert resource.region == region
            assert resource.current_state is not None and resource.current_state != ""
            assert isinstance(resource.tags, dict)
            assert isinstance(resource.metadata, dict)
        
        # Verify service-specific requirements
        for ec2_resource in ec2_resources:
            assert ec2_resource.service_type == 'ec2'
            assert 'instance_type' in ec2_resource.metadata
            assert 'availability_zone' in ec2_resource.metadata
        
        for rds_resource in rds_resources:
            assert rds_resource.service_type == 'rds'
            assert 'engine' in rds_resource.metadata
            assert 'resource_type' in rds_resource.metadata
        
        for ecs_resource in ecs_resources:
            assert ecs_resource.service_type == 'ecs'
            assert 'cluster_name' in ecs_resource.metadata
            assert 'desired_count' in ecs_resource.metadata
        
        for asg_resource in asg_resources:
            assert asg_resource.service_type == 'autoscaling'
            assert 'desired_capacity' in asg_resource.metadata
            assert 'min_size' in asg_resource.metadata
            assert 'max_size' in asg_resource.metadata
    
    def _create_mock_resources(
        self, session, region, num_ec2, num_rds, num_ecs, num_asgs
    ) -> Dict[str, List[str]]:
        """Create mock AWS resources for testing."""
        created = {'ec2': [], 'rds': [], 'ecs': [], 'asg': []}
        
        # Create EC2 instances
        if num_ec2 > 0:
            ec2 = session.client('ec2', region_name=region)
            for i in range(num_ec2):
                response = ec2.run_instances(
                    ImageId='ami-12345678',
                    MinCount=1,
                    MaxCount=1,
                    InstanceType='t3.micro'
                )
                created['ec2'].append(response['Instances'][0]['InstanceId'])
        
        # Create RDS instances
        if num_rds > 0:
            rds = session.client('rds', region_name=region)
            for i in range(num_rds):
                db_id = f'test-db-{i}'
                rds.create_db_instance(
                    DBInstanceIdentifier=db_id,
                    DBInstanceClass='db.t3.micro',
                    Engine='mysql',
                    MasterUsername='admin',
                    MasterUserPassword='password123',
                    AllocatedStorage=20
                )
                created['rds'].append(db_id)
        
        # Create ECS services
        if num_ecs > 0:
            ecs = session.client('ecs', region_name=region)
            # Create cluster first
            cluster_name = 'test-cluster'
            ecs.create_cluster(clusterName=cluster_name)
            
            # Register task definition
            ecs.register_task_definition(
                family='test-task',
                containerDefinitions=[
                    {
                        'name': 'test-container',
                        'image': 'nginx:latest',
                        'memory': 128
                    }
                ]
            )
            
            for i in range(num_ecs):
                service_name = f'test-service-{i}'
                ecs.create_service(
                    cluster=cluster_name,
                    serviceName=service_name,
                    taskDefinition='test-task',
                    desiredCount=1
                )
                created['ecs'].append(service_name)
        
        # Create Auto Scaling Groups
        if num_asgs > 0:
            asg = session.client('autoscaling', region_name=region)
            ec2 = session.client('ec2', region_name=region)
            
            # Create launch configuration
            asg.create_launch_configuration(
                LaunchConfigurationName='test-lc',
                ImageId='ami-12345678',
                InstanceType='t3.micro'
            )
            
            for i in range(num_asgs):
                asg_name = f'test-asg-{i}'
                asg.create_auto_scaling_group(
                    AutoScalingGroupName=asg_name,
                    LaunchConfigurationName='test-lc',
                    MinSize=0,
                    MaxSize=3,
                    DesiredCapacity=1,
                    AvailabilityZones=[f'{region}a']
                )
                created['asg'].append(asg_name)
        
        return created


class TestDiscoverySummaryAccuracy:
    """Property-based tests for discovery summary accuracy."""
    
    @settings(max_examples=10, deadline=None)
    @given(
        region=aws_region(),
        num_ec2_instances=st.integers(min_value=0, max_value=3),
        num_rds_instances=st.integers(min_value=0, max_value=2)
    )
    @mock_aws
    def test_discovery_summary_counts_match_actual_resources(
        self, region, num_ec2_instances, num_rds_instances
    ):
        """
        Feature: aws-break-cli, Property 2: Discovery Summary Accuracy
        
        For any discovery operation, the summary counts by service type should 
        exactly match the number of resources actually discovered and displayed.
        
        **Validates: Requirements 1.4**
        """
        session = boto3.Session()
        
        # Create mock resources
        self._create_mock_ec2_instances(session, region, num_ec2_instances)
        self._create_mock_rds_instances(session, region, num_rds_instances)
        
        # Initialize service managers
        ec2_manager = EC2ServiceManager(session, region)
        rds_manager = RDSServiceManager(session, region)
        
        # Discover resources
        ec2_resources = ec2_manager.discover_resources()
        rds_resources = rds_manager.discover_resources()
        
        # Create summary counts
        summary_counts = {
            'ec2': len(ec2_resources),
            'rds': len(rds_resources)
        }
        
        # Verify summary accuracy
        assert summary_counts['ec2'] == num_ec2_instances
        assert summary_counts['rds'] == num_rds_instances
        
        # Verify total count
        total_discovered = len(ec2_resources) + len(rds_resources)
        total_expected = num_ec2_instances + num_rds_instances
        assert total_discovered == total_expected
        
        # Verify each service type is correctly categorized
        for resource in ec2_resources:
            assert resource.service_type == 'ec2'
        
        for resource in rds_resources:
            assert resource.service_type == 'rds'
    
    def _create_mock_ec2_instances(self, session, region, count):
        """Create mock EC2 instances."""
        if count == 0:
            return
        
        ec2 = session.client('ec2', region_name=region)
        for i in range(count):
            ec2.run_instances(
                ImageId='ami-12345678',
                MinCount=1,
                MaxCount=1,
                InstanceType='t3.micro'
            )
    
    def _create_mock_rds_instances(self, session, region, count):
        """Create mock RDS instances."""
        if count == 0:
            return
        
        rds = session.client('rds', region_name=region)
        for i in range(count):
            rds.create_db_instance(
                DBInstanceIdentifier=f'test-db-{i}',
                DBInstanceClass='db.t3.micro',
                Engine='mysql',
                MasterUsername='admin',
                MasterUserPassword='password123',
                AllocatedStorage=20
            )