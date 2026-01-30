"""
Main CLI entry point for AWS Hit Breaks.

Provides the simple "aws hit breaks" command interface.
"""

import sys
from typing import Optional

import click
from rich.console import Console

from aws_hit_breaks.core.config import ConfigManager
from aws_hit_breaks.auth.iam_auth import IAMRoleAuthenticator
from aws_hit_breaks.cli.interactive import InteractiveFlow
from aws_hit_breaks.core.exceptions import (
    AWSBreakError, AuthenticationError, ConfigurationError, ServiceError, UserCancelled
)


console = Console()

# Exit codes for different error types
EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_AUTH_ERROR = 3
EXIT_SERVICE_ERROR = 4
EXIT_USER_CANCELLED = 130


@click.command()
@click.option(
    "--resume",
    is_flag=True,
    help="Resume previously paused services",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be changed without making actual changes",
)
@click.option(
    "--region",
    help="AWS region to operate in (defaults to configured region)",
)
@click.option(
    "--status",
    is_flag=True,
    help="Show current status of services and snapshots",
)
@click.version_option(version="1.0.0")
def main(
    resume: bool = False,
    dry_run: bool = False,
    region: Optional[str] = None,
    status: bool = False,
) -> None:
    """
    🚨 AWS Hit Breaks - Emergency Cost Control
    
    Stop AWS services to save money without deleting anything.
    Like hitting the brakes on your cloud spending.
    """
    try:
        # Initialize core components
        config_manager = ConfigManager()
        iam_manager = IAMRoleAuthenticator(config_manager)
        interactive_flow = InteractiveFlow(console, config_manager, iam_manager)
        
        # Check if IAM role is configured
        if not config_manager.config_exists():
            console.print("🚨 [bold red]AWS Hit Breaks - Emergency Cost Control[/bold red]")
            console.print("━" * 50)
            console.print()
            console.print("⚠️  [yellow]No IAM role configured. Let's set this up securely.[/yellow]")
            console.print()
            
            # Guide user through setup
            interactive_flow.setup_iam_role()
            return
        
        # Handle different command modes
        if status:
            interactive_flow.show_status(region)
        elif resume:
            interactive_flow.resume_services(region, dry_run)
        else:
            # Default: discover and pause flow
            interactive_flow.discover_and_pause(region, dry_run)
            
    except (KeyboardInterrupt, UserCancelled):
        console.print("\n⚠️  [yellow]Operation cancelled by user[/yellow]")
        sys.exit(EXIT_USER_CANCELLED)
    except ConfigurationError as e:
        console.print(f"❌ [red]Configuration error: {e}[/red]")
        sys.exit(EXIT_CONFIG_ERROR)
    except AuthenticationError as e:
        console.print(f"❌ [red]Authentication error: {e}[/red]")
        sys.exit(EXIT_AUTH_ERROR)
    except ServiceError as e:
        console.print(f"❌ [red]Service error: {e}[/red]")
        sys.exit(EXIT_SERVICE_ERROR)
    except AWSBreakError as e:
        console.print(f"❌ [red]{e}[/red]")
        sys.exit(EXIT_GENERAL_ERROR)
    except Exception as e:
        console.print(f"💥 [red]Unexpected error: {e}[/red]")
        console.print("[dim]Please report this issue with the full error message.[/dim]")
        sys.exit(EXIT_GENERAL_ERROR)


if __name__ == "__main__":
    main()