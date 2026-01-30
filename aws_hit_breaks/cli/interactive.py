"""Interactive CLI flow for AWS Hit Breaks."""

import sys
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from aws_hit_breaks.core.config import Config, ConfigManager
from aws_hit_breaks.auth.iam_auth import IAMRoleAuthenticator, create_cloudformation_template
from aws_hit_breaks.core.exceptions import AWSBreakError, ConfigurationError, AuthenticationError, UserCancelled
from aws_hit_breaks.cli.keyboard import (
    prompt_with_escape,
    confirm_with_escape,
    show_escape_hint,
    escape_listener,
    is_cancelled,
    reset_cancel,
    poll_escape,
)


class InteractiveFlow:
    """Handles interactive CLI flows for AWS Hit Breaks."""

    def __init__(self, console: Console, config_manager: ConfigManager, iam_manager: IAMRoleAuthenticator):
        """Initialize interactive flow.

        Args:
            console: Rich console for output
            config_manager: Configuration manager instance
            iam_manager: IAM role authenticator instance
        """
        self.console = console
        self.config_manager = config_manager
        self.iam_manager = iam_manager

    def _handle_cancellation(self, message: str = "Cancel and quit?") -> bool:
        """Handle ESC key press with confirmation.

        Args:
            message: Confirmation message to display

        Returns:
            True if user confirmed cancellation, False to continue

        Raises:
            UserCancelled: If user confirms they want to quit
        """
        # Poll for ESC key press
        poll_escape()

        if is_cancelled():
            self.console.print()
            self.console.print("[yellow]ESC pressed - cancelling...[/yellow]")
            try:
                if confirm_with_escape(message, self.console, default=False):
                    raise UserCancelled("User cancelled operation")
                else:
                    # User wants to continue, reset the flag
                    reset_cancel()
                    self.console.print("[green]Continuing...[/green]")
                    return False
            except UserCancelled:
                # User pressed ESC again during confirmation - treat as quit
                raise
        return False
    
    def setup_iam_role(self) -> None:
        """Guide user through IAM role setup process."""
        self.console.print("I'll create an IAM role with minimal required permissions.")
        self.console.print("This ensures your AWS account stays secure.")
        self.console.print()
        show_escape_hint(self.console)

        # Ask user for setup method
        self.console.print("Choose setup method:")
        self.console.print("1. 📋 Copy CloudFormation template (recommended)")
        self.console.print("2. 🔧 Manual IAM role creation")
        self.console.print()

        choice = prompt_with_escape("Select option", self.console, choices=["1", "2"], default="1")
        
        if choice == "1":
            self._setup_with_cloudformation()
        else:
            self._setup_manual()
    
    def _setup_with_cloudformation(self) -> None:
        """Setup using CloudFormation template."""
        self.console.print()
        self.console.print("📋 [bold]CloudFormation Template Setup[/bold]")
        self.console.print("━" * 40)
        
        # Generate and display CloudFormation template
        template = create_cloudformation_template()
        
        self.console.print("1. Copy the CloudFormation template below:")
        self.console.print()
        
        # Display template in a panel
        template_panel = Panel(
            template,
            title="CloudFormation Template",
            border_style="blue",
            expand=False
        )
        self.console.print(template_panel)
        
        self.console.print()
        self.console.print("2. Deploy this template in your AWS account:")
        self.console.print("   • Go to AWS CloudFormation console")
        self.console.print("   • Create new stack")
        self.console.print("   • Paste the template above")
        self.console.print("   • Deploy with default parameters")
        self.console.print()
        
        # Wait for user to deploy
        confirm_with_escape("Have you deployed the CloudFormation template?", self.console, default=False)
        
        # Get role ARN from user
        self._get_role_arn_from_user()
    
    def _setup_manual(self) -> None:
        """Setup with manual IAM role creation."""
        self.console.print()
        self.console.print("🔧 [bold]Manual IAM Role Setup[/bold]")
        self.console.print("━" * 30)
        
        self.console.print("1. Go to AWS IAM console")
        self.console.print("2. Create a new IAM role")
        self.console.print("3. Choose 'AWS account' as trusted entity")
        self.console.print("4. Add the following permissions:")
        
        permissions = [
            "ec2:DescribeInstances", "ec2:StopInstances", "ec2:StartInstances",
            "rds:DescribeDBInstances", "rds:StopDBInstance", "rds:StartDBInstance",
            "ecs:DescribeServices", "ecs:UpdateService",
            "autoscaling:DescribeAutoScalingGroups", "autoscaling:SuspendProcesses",
            "pricing:GetProducts"
        ]
        
        for permission in permissions:
            self.console.print(f"   • {permission}")
        
        self.console.print()
        self.console.print("5. Name the role 'AWSHitBreaksRole'")
        self.console.print("6. Copy the role ARN")
        self.console.print()
        
        # Get role ARN from user
        self._get_role_arn_from_user()
    
    def _get_role_arn_from_user(self) -> None:
        """Get and validate role ARN from user input."""
        while True:
            role_arn = prompt_with_escape("Enter the IAM role ARN", self.console)
            
            if not role_arn:
                self.console.print("❌ [red]Role ARN cannot be empty[/red]")
                continue
            
            # Validate role ARN format
            try:
                config = Config(iam_role_arn=role_arn)
            except ValueError as e:
                self.console.print(f"❌ [red]{e}[/red]")
                continue
            
            # Test role access
            self.console.print("🔍 Testing role access...")
            
            if self.iam_manager.validate_role_access(role_arn):
                # Save configuration
                self.config_manager.save_config(config)
                self.console.print("✅ [green]IAM role configured successfully![/green]")
                self.console.print()
                self.console.print("You can now run 'aws-hit-breaks' to start using the tool.")
                break
            else:
                self.console.print("❌ [red]Unable to assume the specified role.[/red]")
                self.console.print("Please check:")
                self.console.print("• The role ARN is correct")
                self.console.print("• The role exists in your account")
                self.console.print("• Your AWS credentials have permission to assume the role")
                self.console.print()
                
                if not confirm_with_escape("Try a different role ARN?", self.console, default=True):
                    sys.exit(1)
    
    def discover_and_pause(self, region: Optional[str], dry_run: bool) -> None:
        """Main discover and pause flow."""
        self.console.print("🚨 [bold red]AWS Hit Breaks - Emergency Cost Control[/bold red]")
        self.console.print("━" * 50)
        self.console.print()
        show_escape_hint(self.console)

        with escape_listener(self.console):
            # Check for cancellation periodically
            self._handle_cancellation()

            # TODO: Implement service discovery and pause logic
            # This will be implemented in later tasks
            self.console.print("🔍 [yellow]Service discovery not yet implemented[/yellow]")
            self.console.print("This will be available in the next implementation phase.")

            # Check for cancellation after operations
            self._handle_cancellation()
    
    def resume_services(self, region: Optional[str], dry_run: bool) -> None:
        """Resume previously paused services."""
        self.console.print("🚨 [bold red]AWS Hit Breaks - Resume Services[/bold red]")
        self.console.print("━" * 40)
        self.console.print()
        show_escape_hint(self.console)

        with escape_listener(self.console):
            # Check for cancellation periodically
            self._handle_cancellation()

            # TODO: Implement resume logic
            # This will be implemented in later tasks
            self.console.print("🔄 [yellow]Service resume not yet implemented[/yellow]")
            self.console.print("This will be available in the next implementation phase.")

            # Check for cancellation after operations
            self._handle_cancellation()
    
    def show_status(self, region: Optional[str]) -> None:
        """Show current status of services and snapshots."""
        self.console.print("🚨 [bold red]AWS Hit Breaks - Status[/bold red]")
        self.console.print("━" * 30)
        self.console.print()
        show_escape_hint(self.console)

        with escape_listener(self.console):
            # Check for cancellation periodically
            self._handle_cancellation()

            # TODO: Implement status display
            # This will be implemented in later tasks
            self.console.print("📊 [yellow]Status display not yet implemented[/yellow]")
            self.console.print("This will be available in the next implementation phase.")

            # Check for cancellation after operations
            self._handle_cancellation()