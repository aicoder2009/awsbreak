"""IAM role authentication and STS assume role functionality."""

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
from typing import Dict, Optional, Any
import logging
from datetime import datetime, timedelta

from aws_hit_breaks.core.config import Config, ConfigManager
from aws_hit_breaks.core.exceptions import AuthenticationError, ConfigurationError


logger = logging.getLogger(__name__)


class IAMRoleAuthenticator:
    """Handles IAM role authentication using STS assume role."""
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize the IAM role authenticator.
        
        Args:
            config_manager: Optional configuration manager instance.
                           If None, creates a new one with default settings.
        """
        self.config_manager = config_manager or ConfigManager()
        self._cached_credentials: Optional[Dict[str, Any]] = None
        self._credentials_expiry: Optional[datetime] = None
    
    def get_aws_session(self, region: Optional[str] = None) -> boto3.Session:
        """Get an authenticated AWS session using the configured IAM role.
        
        Args:
            region: Optional AWS region. If None, uses default from config.
            
        Returns:
            Authenticated boto3 Session object.
            
        Raises:
            ConfigurationError: If no IAM role is configured.
            AuthenticationError: If role assumption fails.
        """
        config = self._load_config()
        
        # Use provided region or fall back to config default
        session_region = region or config.default_region
        
        # Get credentials (cached or fresh)
        credentials = self._get_credentials(config.iam_role_arn)
        
        # Create session with assumed role credentials
        session = boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken'],
            region_name=session_region
        )
        
        return session
    
    def get_aws_client(self, service_name: str, region: Optional[str] = None) -> Any:
        """Get an authenticated AWS service client.
        
        Args:
            service_name: AWS service name (e.g., 'ec2', 'rds', 'ecs').
            region: Optional AWS region. If None, uses default from config.
            
        Returns:
            Authenticated boto3 client for the specified service.
            
        Raises:
            ConfigurationError: If no IAM role is configured.
            AuthenticationError: If role assumption fails.
        """
        session = self.get_aws_session(region)
        return session.client(service_name)
    
    def validate_role_access(self, role_arn: str) -> bool:
        """Validate that the IAM role can be assumed successfully.
        
        Args:
            role_arn: IAM role ARN to validate.
            
        Returns:
            True if role can be assumed, False otherwise.
        """
        try:
            # Try to assume the role
            sts_client = boto3.client('sts')
            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName='aws-hit-breaks-validation',
                DurationSeconds=900  # 15 minutes minimum
            )
            
            # If we get here, the role assumption worked
            logger.info(f"Successfully validated IAM role: {role_arn}")
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.warning(f"Failed to validate IAM role {role_arn}: {error_code} - {e}")
            return False
        except (NoCredentialsError, BotoCoreError) as e:
            logger.warning(f"AWS credentials or configuration error: {e}")
            return False
    
    def get_caller_identity(self) -> Dict[str, Any]:
        """Get the current caller identity information.
        
        Returns:
            Dictionary containing caller identity information.
            
        Raises:
            AuthenticationError: If unable to get caller identity.
        """
        try:
            session = self.get_aws_session()
            sts_client = session.client('sts')
            return sts_client.get_caller_identity()
        except Exception as e:
            raise AuthenticationError(f"Failed to get caller identity: {e}")
    
    def _load_config(self) -> Config:
        """Load configuration and validate IAM role is configured.
        
        Returns:
            Configuration object.
            
        Raises:
            ConfigurationError: If no configuration exists or IAM role not configured.
        """
        config = self.config_manager.load_config()
        
        if config is None:
            raise ConfigurationError(
                "No configuration found. Please run the setup process to configure your IAM role."
            )
        
        if not config.iam_role_arn:
            raise ConfigurationError(
                "No IAM role configured. Please run the setup process to configure your IAM role."
            )
        
        return config
    
    def _get_credentials(self, role_arn: str) -> Dict[str, Any]:
        """Get AWS credentials by assuming the specified IAM role.
        
        Args:
            role_arn: IAM role ARN to assume.
            
        Returns:
            Dictionary containing AWS credentials.
            
        Raises:
            AuthenticationError: If role assumption fails.
        """
        # Check if we have cached credentials that are still valid
        if self._cached_credentials and self._credentials_expiry:
            # Add 5 minute buffer before expiry
            if datetime.utcnow() < (self._credentials_expiry - timedelta(minutes=5)):
                logger.debug("Using cached AWS credentials")
                return self._cached_credentials
        
        try:
            logger.info(f"Assuming IAM role: {role_arn}")
            
            # Create STS client with current credentials
            sts_client = boto3.client('sts')
            
            # Assume the role
            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName='aws-hit-breaks-session',
                DurationSeconds=3600  # 1 hour
            )
            
            # Extract credentials
            credentials = response['Credentials']
            
            # Cache credentials and expiry time
            self._cached_credentials = credentials
            self._credentials_expiry = credentials['Expiration'].replace(tzinfo=None)
            
            logger.info("Successfully assumed IAM role")
            return credentials
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            if error_code == 'AccessDenied':
                raise AuthenticationError(
                    f"Access denied when assuming role {role_arn}. "
                    "Please check that:\n"
                    "1. The role exists and is correctly configured\n"
                    "2. Your current AWS credentials have permission to assume this role\n"
                    "3. The role's trust policy allows your account/user to assume it"
                )
            elif error_code == 'InvalidUserID.NotFound':
                raise AuthenticationError(
                    f"IAM role not found: {role_arn}. "
                    "Please check that the role ARN is correct and the role exists."
                )
            else:
                raise AuthenticationError(
                    f"Failed to assume IAM role {role_arn}: {error_code} - {error_message}"
                )
                
        except NoCredentialsError:
            raise AuthenticationError(
                "No AWS credentials found. Please configure your AWS credentials using:\n"
                "1. AWS CLI: aws configure\n"
                "2. Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY\n"
                "3. IAM instance profile (if running on EC2)\n"
                "4. AWS SSO: aws sso login"
            )
            
        except BotoCoreError as e:
            raise AuthenticationError(f"AWS configuration error: {e}")
        
        except Exception as e:
            raise AuthenticationError(f"Unexpected error assuming IAM role: {e}")
    
    def clear_cached_credentials(self) -> None:
        """Clear any cached credentials to force fresh authentication."""
        self._cached_credentials = None
        self._credentials_expiry = None
        logger.debug("Cleared cached AWS credentials")


def create_cloudformation_template() -> str:
    """Generate CloudFormation template for creating the required IAM role.
    
    Returns:
        CloudFormation template as a YAML string.
    """
    template = """AWSTemplateFormatVersion: '2010-09-09'
Description: 'IAM role for AWS Hit Breaks CLI with minimal required permissions'

Parameters:
  TrustedAccountId:
    Type: String
    Description: 'AWS Account ID that can assume this role (your account ID)'
    Default: !Ref 'AWS::AccountId'

Resources:
  AWSHitBreaksRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: AWSHitBreaksRole
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              AWS: !Sub 'arn:aws:iam::${TrustedAccountId}:root'
            Action: sts:AssumeRole
            Condition:
              StringEquals:
                'sts:ExternalId': 'aws-hit-breaks-cli'
      Policies:
        - PolicyName: AWSHitBreaksPolicy
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  # EC2 permissions
                  - ec2:DescribeInstances
                  - ec2:DescribeInstanceStatus
                  - ec2:StopInstances
                  - ec2:StartInstances
                  # RDS permissions
                  - rds:DescribeDBInstances
                  - rds:DescribeDBClusters
                  - rds:StopDBInstance
                  - rds:StartDBInstance
                  - rds:StopDBCluster
                  - rds:StartDBCluster
                  # ECS permissions
                  - ecs:DescribeServices
                  - ecs:DescribeClusters
                  - ecs:ListServices
                  - ecs:UpdateService
                  # Auto Scaling permissions
                  - autoscaling:DescribeAutoScalingGroups
                  - autoscaling:SuspendProcesses
                  - autoscaling:ResumeProcesses
                  - autoscaling:SetDesiredCapacity
                  # Lambda permissions
                  - lambda:ListFunctions
                  - lambda:GetProvisionedConcurrencyConfig
                  - lambda:PutProvisionedConcurrencyConfig
                  - lambda:DeleteProvisionedConcurrencyConfig
                  # Pricing API permissions
                  - pricing:GetProducts
                Resource: '*'

Outputs:
  RoleArn:
    Description: 'ARN of the created IAM role'
    Value: !GetAtt AWSHitBreaksRole.Arn
    Export:
      Name: !Sub '${AWS::StackName}-RoleArn'
  
  SetupInstructions:
    Description: 'Instructions for configuring AWS Hit Breaks CLI'
    Value: !Sub |
      1. Copy this role ARN: ${AWSHitBreaksRole.Arn}
      2. Run: aws-hit-breaks configure
      3. Paste the role ARN when prompted
"""
    
    return template