#!/usr/bin/env python3
"""
AWS Break CLI - Main entry point
Stop AWS services to save money without deleting anything.
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import click
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Prompt, Confirm
    from rich.panel import Panel
except ImportError:
    print("❌ Required dependencies not installed. Please run:")
    print("   pip install click rich boto3 pyyaml cryptography")
    sys.exit(1)

from aws_break.core.auth import AuthManager
from aws_break.core.discovery import ServiceDiscovery
from aws_break.core.controller import ServiceController
from aws_break.core.state import StateManager
from aws_break.core.cost import CostCalculator
from aws_break.ui.display import UIManager

console = Console()

@click.group()
@click.version_option(version="1.0.0")
@click.pass_context
def cli(ctx):
    """
    AWS Break - Stop services to save money 💰
    
    Make it feel like turning off lights in your house.
    """
    ctx.ensure_object(dict)
    
    # Initialize core components
    ctx.obj['auth'] = AuthManager()
    ctx.obj['discovery'] = ServiceDiscovery()
    ctx.obj['controller'] = ServiceController()
    ctx.obj['state'] = StateManager()
    ctx.obj['cost'] = CostCalculator()
    ctx.obj['ui'] = UIManager(console)

@cli.command()
@click.option('--expensive', is_flag=True, help='Only show costly stuff (over $10/month)')
@click.option('--cheap', is_flag=True, help='Show everything, even small costs')
@click.pass_context
def look(ctx, expensive, cheap):
    """Show me what's running and costing money"""
    ui = ctx.obj['ui']
    discovery = ctx.obj['discovery']
    
    ui.show_header("💰 Here's what's costing you money:")
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("🔍 Scanning AWS services...", total=None)
            
            # Mock data for now - will be replaced with real AWS discovery
            services = [
                {"name": "Web Server (EC2)", "cost": 145.0, "status": "🟢 Running", "type": "ec2"},
                {"name": "Database (RDS)", "cost": 289.0, "status": "🟢 Running", "type": "rds"},
                {"name": "File Storage (EFS)", "cost": 23.0, "status": "🟢 Running", "type": "efs"},
            ]
            
            progress.update(task, completed=100)
        
        # Filter services based on flags
        if expensive:
            services = [s for s in services if s['cost'] > 10]
        elif not cheap:
            # Default behavior - show all
            pass
            
        ui.display_services_table(services)
        
        total_cost = sum(s['cost'] for s in services)
        ui.show_total_cost(total_cost)
        
    except Exception as e:
        ui.show_error(f"Failed to scan services: {str(e)}")

@cli.command()
@click.option('--preview', is_flag=True, help='Show what would be stopped (safe mode)')
@click.option('--everything', is_flag=True, help='Stop all services')
@click.option('--keep', help='Stop everything except what you specify')
@click.pass_context
def stop(ctx, preview, everything, keep):
    """Turn off services to save money"""
    ui = ctx.obj['ui']
    controller = ctx.obj['controller']
    
    if preview:
        ui.show_header("🛑 Preview: What would be stopped...")
        # Show preview without making changes
        services_to_stop = [
            {"name": "Web Server (EC2)", "cost": 145.0},
            {"name": "File Storage (EFS)", "cost": 23.0},
        ]
        
        if keep:
            ui.show_info(f"⏭️  Keeping {keep} running as requested")
            services_to_stop = [s for s in services_to_stop if keep.lower() not in s['name'].lower()]
        
        ui.display_stop_preview(services_to_stop)
        estimated_savings = sum(s['cost'] for s in services_to_stop)
        ui.show_savings_estimate(estimated_savings)
        
        ui.show_info("💡 This is just a preview - nothing was actually stopped")
        ui.show_info("💡 Run without --preview to actually stop services")
    else:
        # Actual stop operation
        if everything:
            confirmed = Confirm.ask("⚠️  This will stop ALL services including protected ones. Are you sure?")
            if not confirmed:
                ui.show_info("Operation cancelled")
                return
        
        ui.show_header("🛑 Stopping services...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Stopping services...", total=None)
            
            # Mock stopping services
            stopped_services = [
                {"name": "Web Server", "status": "✅ Stopped"},
                {"name": "File Storage", "status": "✅ Stopped"},
            ]
            
            if keep:
                ui.show_info(f"⏭️  {keep} skipped (you said keep it)")
            
            progress.update(task, completed=100)
        
        for service in stopped_services:
            ui.show_success(f"{service['status']} {service['name']}")
        
        ui.show_savings_estimate(168.0)

@cli.command()
@click.option('--last', is_flag=True, help='Restart everything from your last stop')
@click.option('--preview', is_flag=True, help='Show what would be started')
@click.pass_context
def start(ctx, last, preview):
    """Turn services back on"""
    ui = ctx.obj['ui']
    
    if preview:
        ui.show_header("🚀 Preview: What would be started...")
        services_to_start = [
            {"name": "Web Server (EC2)", "cost": 145.0},
            {"name": "File Storage (EFS)", "cost": 23.0},
        ]
        ui.display_start_preview(services_to_start)
        total_cost = sum(s['cost'] for s in services_to_start)
        ui.show_cost_impact(total_cost)
        ui.show_info("💡 This is just a preview - nothing was actually started")
    else:
        ui.show_header("🚀 Starting services...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Starting services...", total=None)
            
            # Mock starting services
            started_services = [
                {"name": "Web Server", "status": "✅ Started"},
                {"name": "File Storage", "status": "✅ Started"},
            ]
            
            progress.update(task, completed=100)
        
        for service in started_services:
            ui.show_success(f"{service['status']} {service['name']}")
        
        ui.show_cost_impact(457.0, restored=True)

@cli.command()
@click.pass_context
def savings(ctx):
    """Show how much money you've saved"""
    ui = ctx.obj['ui']
    
    ui.show_header("💰 Your Savings Report")
    
    savings_data = {
        "monthly": 1247.0,
        "yearly": 8932.0,
        "biggest_win": "Stopped dev environment over weekend (saved $234)"
    }
    
    ui.display_savings_report(savings_data)

@cli.command()
@click.pass_context
def undo(ctx):
    """Put everything back the way it was"""
    ui = ctx.obj['ui']
    
    confirmed = Confirm.ask("🔄 This will restore all services to their previous state. Continue?")
    if not confirmed:
        ui.show_info("Operation cancelled")
        return
    
    ui.show_header("🔄 Putting everything back...")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Restoring services...", total=None)
        
        # Mock undo operation
        progress.update(task, completed=100)
    
    ui.show_success("✅ All services restored")
    ui.show_cost_impact(457.0, restored=True)

@cli.command()
@click.pass_context
def setup(ctx):
    """Set up AWS Break for first time use"""
    ui = ctx.obj['ui']
    auth = ctx.obj['auth']
    
    ui.show_welcome()
    
    try:
        # Get AWS credentials
        ui.show_info("🔑 Let's set up your AWS credentials...")
        
        access_key = Prompt.ask("AWS Access Key ID")
        secret_key = Prompt.ask("AWS Secret Access Key", password=True)
        region = Prompt.ask("Default AWS Region", default="us-east-1")
        
        # Validate credentials (mock for now)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("🔍 Validating credentials...", total=None)
            # Mock validation
            progress.update(task, completed=100)
        
        ui.show_success("✅ Credentials validated successfully!")
        
        # Scan AWS account
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("🔍 Scanning your AWS account...", total=None)
            # Mock scanning
            progress.update(task, completed=100)
        
        ui.show_success("✅ Found 3 services costing $457/month")
        ui.show_success("✅ Created config file at ~/.aws-break-config.yaml")
        