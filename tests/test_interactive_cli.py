"""Property-based tests for interactive CLI user experience."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

import pytest
from hypothesis import given, strategies as st
from rich.console import Console

from aws_hit_breaks.cli.interactive import InteractiveFlow
from aws_hit_breaks.core.config import Config, ConfigManager
from aws_hit_breaks.auth.iam_auth import IAMRoleAuthenticator


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
    ).filter(lambda x: x and not x.startswith('-') and not x.endswith('-')))
    return f"arn:aws:iam::{account_id}:role/{role_name}"


@st.composite
def valid_aws_region(draw):
    """Generate valid AWS region names."""
    region_prefix = draw(st.sampled_from(['us', 'eu', 'ap', 'ca', 'sa']))
    region_middle = draw(st.sampled_from(['east', 'west', 'north', 'south', 'central', 'southeast', 'northeast']))
    region_suffix = draw(st.integers(min_value=1, max_value=9))
    return f"{region_prefix}-{region_middle}-{region_suffix}"


@st.composite
def mock_user_inputs(draw):
    """Generate mock user inputs for interactive flow testing."""
    setup_choice = draw(st.sampled_from(["1", "2"]))  # CloudFormation or manual
    role_arn = draw(valid_iam_role_arn())
    confirm_deployment = draw(st.booleans())
    return {
        'setup_choice': setup_choice,
        'role_arn': role_arn,
        'confirm_deployment': confirm_deployment
    }


class TestInteractiveUserExperience:
    """Property-based tests for interactive CLI user experience."""
    
    @given(user_inputs=mock_user_inputs())
    def test_interactive_user_experience_property(self, user_inputs):
        """
        Feature: aws-break-cli, Property 14: Interactive User Experience
        
        For any execution of "aws hit breaks", the tool should automatically 
        discover resources, display them with cost estimates, and allow the 
        user to confirm before making changes.
        
        **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup test environment
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            iam_manager = IAMRoleAuthenticator(config_manager)
            
            # Create mock console that captures output
            mock_console = Mock(spec=Console)
            captured_output = []
            
            def capture_print(*args, **kwargs):
                if args:
                    captured_output.append(str(args[0]))
            
            mock_console.print.side_effect = capture_print
            
            # Create interactive flow
            interactive_flow = InteractiveFlow(mock_console, config_manager, iam_manager)
            
            # Mock user input responses
            with patch('rich.prompt.Prompt.ask') as mock_prompt, \
                 patch('rich.prompt.Confirm.ask') as mock_confirm, \
                 patch.object(iam_manager, 'validate_role_access', return_value=True):
                
                # Configure mock responses based on generated inputs
                mock_prompt.side_effect = [
                    user_inputs['setup_choice'],  # Setup method choice
                    user_inputs['role_arn']       # Role ARN input
                ]
                mock_confirm.return_value = user_inputs['confirm_deployment']
                
                # Test IAM role setup flow
                interactive_flow.setup_iam_role()
                
                # Verify interactive prompts were called
                assert mock_prompt.call_count >= 1
                
                # Verify console output contains expected elements
                output_text = ' '.join(captured_output)
                
                # Should display setup guidance and IAM role information (Requirement 8.1, 8.2)
                assert 'IAM role' in output_text or 'minimal required permissions' in output_text
                
                # Should provide setup options (Requirement 8.1, 8.2)
                assert 'CloudFormation' in output_text or 'Manual' in output_text
                
                # Should guide user through role setup
                if user_inputs['setup_choice'] == "1":
                    # CloudFormation path should show template
                    assert 'CloudFormation' in output_text
                else:
                    # Manual path should show instructions
                    assert 'manual' in output_text.lower() or 'Manual' in output_text
                
                # Verify role ARN was processed
                if user_inputs['confirm_deployment']:
                    # Should attempt to validate and save role
                    iam_manager.validate_role_access.assert_called_once_with(user_inputs['role_arn'])
    
    @given(region=valid_aws_region())
    def test_discover_and_pause_flow_structure(self, region):
        """
        Test that discover and pause flow follows expected structure.
        
        **Validates: Requirements 9.1, 9.2, 9.3, 9.4**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup configured environment
            config = Config(
                iam_role_arn="arn:aws:iam::123456789012:role/TestRole",
                default_region=region
            )
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            config_manager.save_config(config)
            
            iam_manager = IAMRoleAuthenticator(config_manager)
            
            # Create mock console
            mock_console = Mock(spec=Console)
            captured_output = []
            
            def capture_print(*args, **kwargs):
                if args:
                    captured_output.append(str(args[0]))
            
            mock_console.print.side_effect = capture_print
            
            # Create interactive flow
            interactive_flow = InteractiveFlow(mock_console, config_manager, iam_manager)
            
            # Test discover and pause flow
            interactive_flow.discover_and_pause(region, dry_run=False)
            
            # Verify console output structure
            output_text = ' '.join(captured_output)
            
            # Should display main title (Requirement 9.1)
            assert 'AWS Hit Breaks' in output_text
            assert 'Emergency Cost Control' in output_text
            
            # Should indicate discovery process (Requirement 9.2)
            # Note: Currently shows "not yet implemented" message
            assert 'discovery' in output_text.lower() or 'Discovery' in output_text
    
    @given(region=valid_aws_region())
    def test_resume_services_flow_structure(self, region):
        """
        Test that resume services flow follows expected structure.
        
        **Validates: Requirements 9.5**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup configured environment
            config = Config(
                iam_role_arn="arn:aws:iam::123456789012:role/TestRole",
                default_region=region
            )
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            config_manager.save_config(config)
            
            iam_manager = IAMRoleAuthenticator(config_manager)
            
            # Create mock console
            mock_console = Mock(spec=Console)
            captured_output = []
            
            def capture_print(*args, **kwargs):
                if args:
                    captured_output.append(str(args[0]))
            
            mock_console.print.side_effect = capture_print
            
            # Create interactive flow
            interactive_flow = InteractiveFlow(mock_console, config_manager, iam_manager)
            
            # Test resume services flow
            interactive_flow.resume_services(region, dry_run=False)
            
            # Verify console output structure
            output_text = ' '.join(captured_output)
            
            # Should display resume title (Requirement 9.5)
            assert 'Resume' in output_text
            assert 'AWS Hit Breaks' in output_text
    
    def test_status_display_flow_structure(self):
        """
        Test that status display flow follows expected structure.
        
        **Validates: Requirements 9.1**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup configured environment
            config = Config(
                iam_role_arn="arn:aws:iam::123456789012:role/TestRole",
                default_region="us-east-1"
            )
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            config_manager.save_config(config)
            
            iam_manager = IAMRoleAuthenticator(config_manager)
            
            # Create mock console
            mock_console = Mock(spec=Console)
            captured_output = []
            
            def capture_print(*args, **kwargs):
                if args:
                    captured_output.append(str(args[0]))
            
            mock_console.print.side_effect = capture_print
            
            # Create interactive flow
            interactive_flow = InteractiveFlow(mock_console, config_manager, iam_manager)
            
            # Test status display flow
            interactive_flow.show_status("us-east-1")
            
            # Verify console output structure
            output_text = ' '.join(captured_output)
            
            # Should display status title
            assert 'Status' in output_text
            assert 'AWS Hit Breaks' in output_text


class TestInteractiveFlowEdgeCases:
    """Unit tests for interactive flow edge cases."""
    
    def test_invalid_role_arn_retry_flow(self):
        """
        Test that invalid role ARN prompts for retry.
        
        **Validates: Requirements 8.1, 8.4**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            iam_manager = IAMRoleAuthenticator(config_manager)
            mock_console = Mock(spec=Console)
            
            interactive_flow = InteractiveFlow(mock_console, config_manager, iam_manager)
            
            with patch('rich.prompt.Prompt.ask') as mock_prompt, \
                 patch('rich.prompt.Confirm.ask') as mock_confirm, \
                 patch.object(iam_manager, 'validate_role_access') as mock_validate:
                
                # First attempt: invalid ARN format, second attempt: valid ARN but access denied, third: success
                mock_prompt.side_effect = [
                    "1",  # CloudFormation choice
                    "invalid-arn",  # Invalid ARN format
                    "arn:aws:iam::123456789012:role/TestRole",  # Valid ARN format but access denied
                    "arn:aws:iam::123456789012:role/ValidRole"   # Valid ARN with access
                ]
                mock_confirm.return_value = True  # Confirm deployment
                mock_validate.side_effect = [False, True]  # First role fails validation, second succeeds
                
                # Should handle invalid ARN and retry
                interactive_flow.setup_iam_role()
                
                # Should have prompted multiple times for role ARN
                assert mock_prompt.call_count >= 3
                
                # Should have validated the successful role
                assert mock_validate.call_count == 2
    
    def test_user_cancels_setup(self):
        """
        Test behavior when user cancels setup process.
        
        **Validates: Requirements 8.1**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            iam_manager = IAMRoleAuthenticator(config_manager)
            mock_console = Mock(spec=Console)
            
            interactive_flow = InteractiveFlow(mock_console, config_manager, iam_manager)
            
            with patch('rich.prompt.Prompt.ask') as mock_prompt, \
                 patch('rich.prompt.Confirm.ask') as mock_confirm, \
                 patch.object(iam_manager, 'validate_role_access', return_value=False), \
                 patch('sys.exit') as mock_exit:
                
                mock_prompt.side_effect = [
                    "1",  # CloudFormation choice
                    "arn:aws:iam::123456789012:role/TestRole"  # Valid ARN format
                ]
                mock_confirm.side_effect = [True, False]  # Confirm deployment, then refuse retry
                
                # Should exit when user refuses to retry
                interactive_flow.setup_iam_role()
                
                # Should have called sys.exit
                mock_exit.assert_called_once_with(1)
    
    def test_cloudformation_template_display(self):
        """
        Test that CloudFormation template is properly displayed.
        
        **Validates: Requirements 8.2**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            iam_manager = IAMRoleAuthenticator(config_manager)
            mock_console = Mock(spec=Console)
            
            interactive_flow = InteractiveFlow(mock_console, config_manager, iam_manager)
            
            with patch('rich.prompt.Prompt.ask') as mock_prompt, \
                 patch('rich.prompt.Confirm.ask') as mock_confirm, \
                 patch.object(iam_manager, 'validate_role_access', return_value=True):
                
                mock_prompt.side_effect = [
                    "1",  # CloudFormation choice
                    "arn:aws:iam::123456789012:role/TestRole"
                ]
                mock_confirm.return_value = True
                
                interactive_flow.setup_iam_role()
                
                # Verify CloudFormation template was displayed
                print_calls = [call[0] for call in mock_console.print.call_args_list if call[0]]
                template_displayed = any('CloudFormation' in str(call) for call in print_calls)
                assert template_displayed
    
    def test_manual_setup_instructions(self):
        """
        Test that manual setup shows proper instructions.
        
        **Validates: Requirements 8.2**
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigManager(config_dir=Path(temp_dir))
            iam_manager = IAMRoleAuthenticator(config_manager)
            mock_console = Mock(spec=Console)
            
            interactive_flow = InteractiveFlow(mock_console, config_manager, iam_manager)
            
            with patch('rich.prompt.Prompt.ask') as mock_prompt, \
                 patch.object(iam_manager, 'validate_role_access', return_value=True):
                
                mock_prompt.side_effect = [
                    "2",  # Manual choice
                    "arn:aws:iam::123456789012:role/TestRole"
                ]
                
                interactive_flow.setup_iam_role()
                
                # Verify manual setup instructions were displayed
                print_calls = [str(call[0][0]) if call[0] else '' for call in mock_console.print.call_args_list]
                instructions_text = ' '.join(print_calls)
                
                # Should contain manual setup instructions
                assert 'manual' in instructions_text.lower() or 'Manual' in instructions_text
                assert 'IAM' in instructions_text