#!/usr/bin/env python3
"""Test script for ESC key detection."""

import time
from rich.console import Console

from aws_hit_breaks.cli.keyboard import (
    escape_listener,
    poll_escape,
    is_cancelled,
    reset_cancel,
)

console = Console()

def main():
    console.print("[bold]ESC Key Detection Test[/bold]")
    console.print("=" * 40)
    console.print()
    console.print("[dim]Press ESC to test cancellation...[/dim]")
    console.print("[dim]The test will run for 10 seconds.[/dim]")
    console.print()

    with escape_listener(console):
        for i in range(10):
            # Poll for ESC key
            poll_escape()

            if is_cancelled():
                console.print()
                console.print("[yellow]ESC detected! Cancellation requested.[/yellow]")
                console.print("[green]Test successful - ESC key is working![/green]")
                return

            console.print(f"Waiting... {10 - i} seconds remaining. Press ESC to cancel.")
            time.sleep(1)

    console.print()
    console.print("[red]ESC was not detected during the test.[/red]")
    console.print("Try pressing ESC more firmly or check terminal compatibility.")


if __name__ == "__main__":
    main()
