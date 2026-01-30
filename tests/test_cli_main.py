"""Comprehensive end-to-end tests for CLI main entry point with mock data."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

import pytest
import boto3
from moto import mock_aws
from click.testing import CliRunner
from rich.console import Console

from aws_hit_breaks.cli.main import main, EXIT_SUCCESS, EXIT_CONFIG_ERROR, EXIT_AUTH_ERROR, EXIT_SERVICE_ERROR, EXIT_USER_CANCELLED
from aws_hit_breaks.core.config import Config, ConfigManager
from aws_hit_breaks.core.exceptions import ConfigurationError, AuthenticationError, ServiceError, AWSBreakError

# Import version from package metadata
try:
    from importlib.metadata import version as get_version
    CLI_VERSION = get_version('aws-hit-breaks')
except Exception:
    CLI_VERSION = "1.0.0"  # Fallback version


class TestCLIMainEntryPoint:
    """Test the main CLI entry point with various options and scenarios."""
    
    def test_main_first_time_setup_flow(self):
        """Test CLI when no configuration exists - should guide through IAM setup."""
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            
            # Configure mock to indicate no config exists
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = False
            MockConfigManager.return_value = mock_config_manager
            
            mock_interactive_flow = Mock()
            MockInteractiveFlow.return_value = mock_interactive_flow
            
            # Run CLI
            result = runner.invoke(main, [])
            
            # Verify setup flow was triggered
            assert result.exit_code == EXIT_SUCCESS
            mock_interactive_flow.setup_iam_role.assert_called_once()
            
            # Verify appropriate messages were shown
            assert "AWS Hit Breaks" in result.output
            assert "Emergency Cost Control" in result.output
    
    def test_main_with_configured_iam_default_pause(self):
        """Test CLI with configured IAM role - default discover and pause flow."""
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            
            # Configure mock to indicate config exists
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            
            mock_interactive_flow = Mock()
            MockInteractiveFlow.return_value = mock_interactive_flow
            
            # Run CLI without any flags (default pause)
            result = runner.invoke(main, [])
            
            # Verify discover and pause flow was called
            assert result.exit_code == EXIT_SUCCESS
            mock_interactive_flow.discover_and_pause.assert_called_once_with(None, False)
    
    def test_main_with_resume_flag(self):
        """Test CLI with --resume flag to resume paused services."""
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            
            # Configure mock
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            
            mock_interactive_flow = Mock()
            MockInteractiveFlow.return_value = mock_interactive_flow
            
            # Run CLI with --resume
            result = runner.invoke(main, ['--resume'])
            
            # Verify resume flow was called
            assert result.exit_code == EXIT_SUCCESS
            mock_interactive_flow.resume_services.assert_called_once_with(None, False)
            mock_interactive_flow.discover_and_pause.assert_not_called()
    
    def test_main_with_dry_run_flag(self):
        """Test CLI with --dry-run flag to preview changes without execution."""
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            
            # Configure mock
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            
            mock_interactive_flow = Mock()
            MockInteractiveFlow.return_value = mock_interactive_flow
            
            # Run CLI with --dry-run
            result = runner.invoke(main, ['--dry-run'])
            
            # Verify dry-run was passed to discover_and_pause
            assert result.exit_code == EXIT_SUCCESS
            mock_interactive_flow.discover_and_pause.assert_called_once_with(None, True)
    
    def test_main_with_status_flag(self):
        """Test CLI with --status flag to show current status."""
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            
            # Configure mock
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            
            mock_interactive_flow = Mock()
            MockInteractiveFlow.return_value = mock_interactive_flow
            
            # Run CLI with --status
            result = runner.invoke(main, ['--status'])
            
            # Verify status flow was called
            assert result.exit_code == EXIT_SUCCESS
            mock_interactive_flow.show_status.assert_called_once_with(None)
            mock_interactive_flow.discover_and_pause.assert_not_called()
    
    def test_main_with_region_flag(self):
        """Test CLI with --region flag to specify AWS region."""
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            
            # Configure mock
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            
            mock_interactive_flow = Mock()
            MockInteractiveFlow.return_value = mock_interactive_flow
            
            # Run CLI with --region
            result = runner.invoke(main, ['--region', 'us-west-2'])
            
            # Verify region was passed to discover_and_pause
            assert result.exit_code == EXIT_SUCCESS
            mock_interactive_flow.discover_and_pause.assert_called_once_with('us-west-2', False)
    
    def test_main_with_resume_and_dry_run(self):
        """Test CLI with both --resume and --dry-run flags."""
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            
            # Configure mock
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            
            mock_interactive_flow = Mock()
            MockInteractiveFlow.return_value = mock_interactive_flow
            
            # Run CLI with --resume --dry-run
            result = runner.invoke(main, ['--resume', '--dry-run'])
            
            # Verify both flags were respected
            assert result.exit_code == EXIT_SUCCESS
            mock_interactive_flow.resume_services.assert_called_once_with(None, True)
    
    def test_main_configuration_error_handling(self):
        """Test CLI handles ConfigurationError appropriately."""
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager:
            # Configure mock to raise ConfigurationError
            MockConfigManager.side_effect = ConfigurationError("Invalid configuration file")
            
            # Run CLI
            result = runner.invoke(main, [])
            
            # Verify correct exit code and error message
            assert result.exit_code == EXIT_CONFIG_ERROR
            assert "Configuration error" in result.output
            assert "Invalid configuration file" in result.output
    
    def test_main_authentication_error_handling(self):
        """Test CLI handles AuthenticationError appropriately."""
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.IAMRoleAuthenticator') as MockIAMAuth:
            
            # Configure mock to raise AuthenticationError
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            
            MockIAMAuth.side_effect = AuthenticationError("Unable to assume IAM role")
            
            # Run CLI
            result = runner.invoke(main, [])
            
            # Verify correct exit code and error message
            assert result.exit_code == EXIT_AUTH_ERROR
            assert "Authentication error" in result.output
            assert "Unable to assume IAM role" in result.output
    
    def test_main_service_error_handling(self):
        """Test CLI handles ServiceError appropriately."""
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            
            # Configure mock
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            
            mock_interactive_flow = Mock()
            mock_interactive_flow.discover_and_pause.side_effect = ServiceError("EC2 service unavailable")
            MockInteractiveFlow.return_value = mock_interactive_flow
            
            # Run CLI
            result = runner.invoke(main, [])
            
            # Verify correct exit code and error message
            assert result.exit_code == EXIT_SERVICE_ERROR
            assert "Service error" in result.output
            assert "EC2 service unavailable" in result.output
    
    def test_main_keyboard_interrupt_handling(self):
        """Test CLI handles user cancellation (KeyboardInterrupt) gracefully."""
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            
            # Configure mock
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            
            mock_interactive_flow = Mock()
            mock_interactive_flow.discover_and_pause.side_effect = KeyboardInterrupt()
            MockInteractiveFlow.return_value = mock_interactive_flow
            
            # Run CLI
            result = runner.invoke(main, [])
            
            # Verify correct exit code and message
            assert result.exit_code == EXIT_USER_CANCELLED
            assert "cancelled" in result.output.lower()
    
    def test_main_generic_aws_break_error_handling(self):
        """Test CLI handles generic AWSBreakError appropriately."""
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            
            # Configure mock
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            
            mock_interactive_flow = Mock()
            mock_interactive_flow.discover_and_pause.side_effect = AWSBreakError("Generic error occurred")
            MockInteractiveFlow.return_value = mock_interactive_flow
            
            # Run CLI
            result = runner.invoke(main, [])
            
            # Verify correct exit code and error message
            assert result.exit_code != EXIT_SUCCESS
            assert "Generic error occurred" in result.output
    
    def test_main_unexpected_exception_handling(self):
        """Test CLI handles unexpected exceptions gracefully."""
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            
            # Configure mock
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            
            mock_interactive_flow = Mock()
            mock_interactive_flow.discover_and_pause.side_effect = RuntimeError("Unexpected error")
            MockInteractiveFlow.return_value = mock_interactive_flow
            
            # Run CLI
            result = runner.invoke(main, [])
            
            # Verify error is caught and reported
            assert result.exit_code != EXIT_SUCCESS
            assert "Unexpected error" in result.output


class TestCLIWithMockAWSServices:
    """Test CLI with mock AWS services to verify end-to-end integration."""
    
    @mock_aws
    def test_cli_discover_and_pause_with_ec2_instances(self):
        """Test CLI discover and pause flow with mock EC2 instances."""
        # Create mock EC2 instances
        ec2 = boto3.client('ec2', region_name='us-east-1')
        response = ec2.run_instances(
            ImageId='ami-12345678',
            MinCount=2,
            MaxCount=2,
            InstanceType='t3.micro'
        )
        instance_ids = [inst['InstanceId'] for inst in response['Instances']]
        
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            
            # Configure mock
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            
            mock_interactive_flow = Mock()
            MockInteractiveFlow.return_value = mock_interactive_flow
            
            # Run CLI
            result = runner.invoke(main, [])
            
            # Verify flow was called
            assert result.exit_code == EXIT_SUCCESS
            mock_interactive_flow.discover_and_pause.assert_called_once()
    
    @mock_aws
    def test_cli_resume_with_mock_resources(self):
        """Test CLI resume flow with mock resources."""
        # Create mock RDS instance
        rds = boto3.client('rds', region_name='us-east-1')
        rds.create_db_instance(
            DBInstanceIdentifier='test-db',
            DBInstanceClass='db.t3.micro',
            Engine='mysql',
            MasterUsername='admin',
            MasterUserPassword='password123',
            AllocatedStorage=20
        )
        
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            
            # Configure mock
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            
            mock_interactive_flow = Mock()
            MockInteractiveFlow.return_value = mock_interactive_flow
            
            # Run CLI with --resume
            result = runner.invoke(main, ['--resume'])
            
            # Verify flow was called
            assert result.exit_code == EXIT_SUCCESS
            mock_interactive_flow.resume_services.assert_called_once()
    
    @mock_aws
    def test_cli_status_with_mock_resources(self):
        """Test CLI status flow with mock resources."""
        # Create mock ECS cluster and service
        ecs = boto3.client('ecs', region_name='us-east-1')
        ecs.create_cluster(clusterName='test-cluster')
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
        ecs.create_service(
            cluster='test-cluster',
            serviceName='test-service',
            taskDefinition='test-task',
            desiredCount=2
        )
        
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            
            # Configure mock
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            
            mock_interactive_flow = Mock()
            MockInteractiveFlow.return_value = mock_interactive_flow
            
            # Run CLI with --status
            result = runner.invoke(main, ['--status'])
            
            # Verify flow was called
            assert result.exit_code == EXIT_SUCCESS
            mock_interactive_flow.show_status.assert_called_once()
    
    @mock_aws
    def test_cli_dry_run_with_multiple_services(self):
        """Test CLI dry-run mode with multiple mock AWS services."""
        # Create multiple mock resources
        ec2 = boto3.client('ec2', region_name='us-east-1')
        ec2.run_instances(ImageId='ami-12345678', MinCount=1, MaxCount=1, InstanceType='t3.small')
        
        rds = boto3.client('rds', region_name='us-east-1')
        rds.create_db_instance(
            DBInstanceIdentifier='test-db',
            DBInstanceClass='db.t3.micro',
            Engine='postgres',
            MasterUsername='admin',
            MasterUserPassword='password123',
            AllocatedStorage=20
        )
        
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            
            # Configure mock
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            
            mock_interactive_flow = Mock()
            MockInteractiveFlow.return_value = mock_interactive_flow
            
            # Run CLI with --dry-run
            result = runner.invoke(main, ['--dry-run'])
            
            # Verify dry-run was called with correct flag
            assert result.exit_code == EXIT_SUCCESS
            mock_interactive_flow.discover_and_pause.assert_called_once_with(None, True)


class TestCLIVersionAndHelp:
    """Test CLI version and help commands."""
    
    def test_cli_version_flag(self):
        """Test CLI --version flag displays version."""
        runner = CliRunner()
        result = runner.invoke(main, ['--version'])
        
        # Verify version is displayed
        assert result.exit_code == EXIT_SUCCESS
        assert CLI_VERSION in result.output
    
    def test_cli_help_flag(self):
        """Test CLI --help flag displays help message."""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        
        # Verify help message is displayed
        assert result.exit_code == EXIT_SUCCESS
        assert "AWS Hit Breaks" in result.output
        assert "Emergency Cost Control" in result.output
        assert "--resume" in result.output
        assert "--dry-run" in result.output
        assert "--region" in result.output
        assert "--status" in result.output


class TestCLIComplexScenarios:
    """Test complex CLI scenarios with multiple conditions."""
    
    @mock_aws
    def test_cli_multiple_regions_with_resources(self):
        """Test CLI with resources in multiple regions."""
        # Create resources in multiple regions
        for region in ['us-east-1', 'us-west-2']:
            ec2 = boto3.client('ec2', region_name=region)
            ec2.run_instances(ImageId='ami-12345678', MinCount=1, MaxCount=1, InstanceType='t3.micro')
        
        runner = CliRunner()
        
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            
            # Configure mock
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            
            mock_interactive_flow = Mock()
            MockInteractiveFlow.return_value = mock_interactive_flow
            
            # Run CLI with specific region
            result = runner.invoke(main, ['--region', 'us-west-2'])
            
            # Verify correct region was used
            assert result.exit_code == EXIT_SUCCESS
            mock_interactive_flow.discover_and_pause.assert_called_once_with('us-west-2', False)
    
    def test_cli_exit_codes_comprehensive(self):
        """Test all exit codes are used correctly."""
        runner = CliRunner()
        
        # Test EXIT_CONFIG_ERROR
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager:
            MockConfigManager.side_effect = ConfigurationError("Config error")
            result = runner.invoke(main, [])
            assert result.exit_code == EXIT_CONFIG_ERROR
        
        # Test EXIT_AUTH_ERROR
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.IAMRoleAuthenticator') as MockIAMAuth:
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            MockIAMAuth.side_effect = AuthenticationError("Auth error")
            result = runner.invoke(main, [])
            assert result.exit_code == EXIT_AUTH_ERROR
        
        # Test EXIT_SERVICE_ERROR
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            mock_interactive_flow = Mock()
            mock_interactive_flow.discover_and_pause.side_effect = ServiceError("Service error")
            MockInteractiveFlow.return_value = mock_interactive_flow
            result = runner.invoke(main, [])
            assert result.exit_code == EXIT_SERVICE_ERROR
        
        # Test EXIT_USER_CANCELLED
        with patch('aws_hit_breaks.cli.main.ConfigManager') as MockConfigManager, \
             patch('aws_hit_breaks.cli.main.InteractiveFlow') as MockInteractiveFlow:
            mock_config_manager = Mock()
            mock_config_manager.config_exists.return_value = True
            MockConfigManager.return_value = mock_config_manager
            mock_interactive_flow = Mock()
            mock_interactive_flow.discover_and_pause.side_effect = KeyboardInterrupt()
            MockInteractiveFlow.return_value = mock_interactive_flow
            result = runner.invoke(main, [])
            assert result.exit_code == EXIT_USER_CANCELLED
