"""Property-based tests for IAM role authentication."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import boto3
import pytest
from botocore.exceptions import ClientError, NoCredentialsError
from hypothesis import given, strategies as st
from moto import mock_aws

from aws_hit_breaks.auth.iam_auth import IAMRoleAuthenticator, create_cloudformation_template
from aws_hit_breaks.core.config import Config, ConfigManager
from aws_hit_breaks.core.exceptions import AuthenticationError, ConfigurationError


# Hypothesis strategies for generating test data
@st.composite
def valid_iam_role_arn(draw):
    """Generate valid IAM role ARNs."""
    account_id = draw(st.integers(min_value=100000000000, max_value=999999999999))
    # Generate role names with only valid characters for IAM role names
    role_name = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+=,.@_-',
        min_size=1,
        max_size=64
    ).filter(lambda x: x and not x.startswith('-') and not x.endswith('-') and x.replace('-', '').replace('_', '').replace('.', '').replace('+', '').replace('=', '').replace(',', '').replace('@', '')))
    return f"arn:aws:iam::{account_id}:role/{role_name}"


@st.composite
def valid_aws_region(draw):
    """Generate valid AWS region names."""
    region_prefix = draw(st.sampled_from(['us', 'eu', 'ap', 'ca', 'sa']))
    region_middle = draw(st.sampled_from(['east', 'west', 'north', 'south', 'central', 'southeast', 'northeast']))
    region_suffix = draw(st.integers(min_value=1, max_value=9))
    return f"{region_prefix}-{region_middle}-{region_suffix}"


@st.composite
def valid_config_with_role(draw):
    """Generate valid Config objects with IAM roles."""
    return Config(
        iam_role_arn=draw(valid_iam_role_arn()),
        default_region=draw(valid_aws_region()),
        created_at=datetime.utcnow(),
        version="1.0.0"
    )


class TestIAMRoleAuthentication:
    """Property-based tests for IAM role authentication."""
    
    @mock_aws
    @given(config=valid_config_with_role())
    def test_iam_role_authentication_with_valid_config(self, config):
        """
        Feature: aws-break-cli, Property 13: IAM Role Authentication
        
        For any valid IAM role configuration, the authenticator should use 
        STS assume role for all AWS API operations and provide clear setup 
        guidance when the role is missing or invalid.
        
        **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            config_manager.save_config(config)
            
            authenticator = IAMRoleAuthenticator(config_manager)
            
            # Mock successful STS assume role response
            mock_credentials = {
                'AccessKeyId': 'AKIAIOSFODNN7EXAMPLE',
                'SecretAccessKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                'SessionToken': 'session-token-example',
                'Expiration': datetime.utcnow() + timedelta(hours=1)
            }
            
            with patch('boto3.client') as mock_boto_client:
                mock_sts = Mock()
                mock_sts.assume_role.return_value = {'Credentials': mock_credentials}
                mock_boto_client.return_value = mock_sts
                
                # Test getting AWS session
                session = authenticator.get_aws_session()
                
                # Verify session was created with assumed role credentials
                assert session is not None
                assert isinstance(session, boto3.Session)
                
                # Verify STS assume role was called with correct parameters
                mock_sts.assume_role.assert_called_once()
                call_args = mock_sts.assume_role.call_args
                assert call_args[1]['RoleArn'] == config.iam_role_arn
                assert 'aws-hit-breaks-session' in call_args[1]['RoleSessionName']
    
    @mock_aws
    @given(config=valid_config_with_role(), service_name=st.sampled_from(['ec2', 'rds', 'ecs', 'autoscaling']))
    def test_aws_client_creation_with_different_services(self, config, service_name):
        """
        Test that AWS clients can be created for different services using assumed role.
        
        **Validates: Requirements 8.1, 8.4**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            config_manager.save_config(config)
            
            authenticator = IAMRoleAuthenticator(config_manager)
            
            # Mock successful STS assume role response
            mock_credentials = {
                'AccessKeyId': 'AKIAIOSFODNN7EXAMPLE',
                'SecretAccessKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                'SessionToken': 'session-token-example',
                'Expiration': datetime.utcnow() + timedelta(hours=1)
            }
            
            with patch('boto3.client') as mock_boto_client, \
                 patch('boto3.Session') as mock_session_class:
                
                # Mock STS client for assume role
                mock_sts = Mock()
                mock_sts.assume_role.return_value = {'Credentials': mock_credentials}
                
                # Mock session and its client method
                mock_session = Mock()
                mock_service_client = Mock()
                mock_session.client.return_value = mock_service_client
                mock_session_class.return_value = mock_session
                
                # Configure boto3.client to return STS client when called directly
                mock_boto_client.return_value = mock_sts
                
                # Test getting AWS client for the service
                client = authenticator.get_aws_client(service_name, region=config.default_region)
                
                # Verify client was created
                assert client is not None
                
                # Verify session was created with correct credentials
                mock_session_class.assert_called_once_with(
                    aws_access_key_id=mock_credentials['AccessKeyId'],
                    aws_secret_access_key=mock_credentials['SecretAccessKey'],
                    aws_session_token=mock_credentials['SessionToken'],
                    region_name=config.default_region
                )
                
                # Verify client was created for the correct service
                mock_session.client.assert_called_once_with(service_name)
    
    def test_missing_configuration_error(self):
        """
        Test that appropriate error is raised when no configuration exists.
        
        **Validates: Requirements 8.2, 8.5**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            authenticator = IAMRoleAuthenticator(config_manager)
            
            # Should raise ConfigurationError when no config exists
            with pytest.raises(ConfigurationError, match="No configuration found"):
                authenticator.get_aws_session()
    
    @given(role_arn=valid_iam_role_arn())
    def test_role_validation_with_access_denied(self, role_arn):
        """
        Test role validation handles access denied errors gracefully.
        
        **Validates: Requirements 8.4, 8.5**
        """
        authenticator = IAMRoleAuthenticator()
        
        # Mock ClientError for access denied
        error_response = {
            'Error': {
                'Code': 'AccessDenied',
                'Message': 'User is not authorized to perform: sts:AssumeRole'
            }
        }
        
        with patch('boto3.client') as mock_boto_client:
            mock_sts = Mock()
            mock_sts.assume_role.side_effect = ClientError(error_response, 'AssumeRole')
            mock_boto_client.return_value = mock_sts
            
            # Should return False for invalid role
            result = authenticator.validate_role_access(role_arn)
            assert result is False
    
    @given(role_arn=valid_iam_role_arn())
    def test_role_validation_with_success(self, role_arn):
        """
        Test role validation returns True for valid roles.
        
        **Validates: Requirements 8.1, 8.3**
        """
        authenticator = IAMRoleAuthenticator()
        
        # Mock successful assume role response
        mock_response = {
            'Credentials': {
                'AccessKeyId': 'AKIAIOSFODNN7EXAMPLE',
                'SecretAccessKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                'SessionToken': 'session-token-example',
                'Expiration': datetime.utcnow() + timedelta(hours=1)
            }
        }
        
        with patch('boto3.client') as mock_boto_client:
            mock_sts = Mock()
            mock_sts.assume_role.return_value = mock_response
            mock_boto_client.return_value = mock_sts
            
            # Should return True for valid role
            result = authenticator.validate_role_access(role_arn)
            assert result is True
    
    def test_credentials_caching_behavior(self):
        """
        Test that credentials are cached and reused when still valid.
        
        **Validates: Requirements 8.1, 8.4**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(
                iam_role_arn="arn:aws:iam::123456789012:role/TestRole",
                default_region="us-east-1"
            )
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            config_manager.save_config(config)
            
            authenticator = IAMRoleAuthenticator(config_manager)
            
            # Mock successful STS assume role response
            mock_credentials = {
                'AccessKeyId': 'AKIAIOSFODNN7EXAMPLE',
                'SecretAccessKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
                'SessionToken': 'session-token-example',
                'Expiration': datetime.utcnow() + timedelta(hours=1)
            }
            
            with patch('boto3.client') as mock_boto_client:
                mock_sts = Mock()
                mock_sts.assume_role.return_value = {'Credentials': mock_credentials}
                mock_boto_client.return_value = mock_sts
                
                # First call should assume role
                session1 = authenticator.get_aws_session()
                assert mock_sts.assume_role.call_count == 1
                
                # Second call should use cached credentials
                session2 = authenticator.get_aws_session()
                assert mock_sts.assume_role.call_count == 1  # Should not increase
                
                # Clear cache and call again
                authenticator.clear_cached_credentials()
                session3 = authenticator.get_aws_session()
                assert mock_sts.assume_role.call_count == 2  # Should increase


class TestCloudFormationTemplate:
    """Unit tests for CloudFormation template generation."""
    
    def test_cloudformation_template_generation(self):
        """
        Test that CloudFormation template is generated correctly.
        
        **Validates: Requirements 8.2**
        """
        template = create_cloudformation_template()
        
        # Verify template contains required elements
        assert 'AWSTemplateFormatVersion' in template
        assert 'AWSHitBreaksRole' in template
        assert 'AssumeRolePolicyDocument' in template
        assert 'AWSHitBreaksPolicy' in template
        
        # Verify required permissions are included
        required_permissions = [
            'ec2:DescribeInstances',
            'ec2:StopInstances',
            'ec2:StartInstances',
            'rds:DescribeDBInstances',
            'rds:StopDBInstance',
            'rds:StartDBInstance',
            'ecs:DescribeServices',
            'ecs:UpdateService',
            'autoscaling:DescribeAutoScalingGroups',
            'lambda:ListFunctions',
            'pricing:GetProducts'
        ]
        
        for permission in required_permissions:
            assert permission in template
        
        # Verify outputs section exists
        assert 'Outputs' in template
        assert 'RoleArn' in template
        assert 'SetupInstructions' in template


class TestAuthenticationErrorHandling:
    """Unit tests for authentication error handling."""
    
    def test_no_credentials_error_handling(self):
        """
        Test handling of NoCredentialsError.
        
        **Validates: Requirements 8.5**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(
                iam_role_arn="arn:aws:iam::123456789012:role/TestRole",
                default_region="us-east-1"
            )
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            config_manager.save_config(config)
            
            authenticator = IAMRoleAuthenticator(config_manager)
            
            with patch('boto3.client') as mock_boto_client:
                mock_boto_client.side_effect = NoCredentialsError()
                
                with pytest.raises(AuthenticationError, match="No AWS credentials found"):
                    authenticator.get_aws_session()
    
    def test_invalid_role_error_handling(self):
        """
        Test handling of invalid role ARN errors.
        
        **Validates: Requirements 8.4, 8.5**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(
                iam_role_arn="arn:aws:iam::123456789012:role/NonExistentRole",
                default_region="us-east-1"
            )
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            config_manager.save_config(config)
            
            authenticator = IAMRoleAuthenticator(config_manager)
            
            # Mock ClientError for role not found
            error_response = {
                'Error': {
                    'Code': 'InvalidUserID.NotFound',
                    'Message': 'The role does not exist'
                }
            }
            
            with patch('boto3.client') as mock_boto_client:
                mock_sts = Mock()
                mock_sts.assume_role.side_effect = ClientError(error_response, 'AssumeRole')
                mock_boto_client.return_value = mock_sts
                
                with pytest.raises(AuthenticationError, match="IAM role not found"):
                    authenticator.get_aws_session()