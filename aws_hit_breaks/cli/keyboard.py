"""
Keyboard handling utilities for AWS Hit Breaks CLI.

Provides ESC key detection and cancellation support.
"""

import os
import sys
import signal
import select
import threading
import atexit
from contextlib import contextmanager
from typing import Optional, Callable, Any, List, Generator

from rich.console import Console
from rich.prompt import Prompt, Confirm, InvalidResponse

from aws_hit_breaks.core.exceptions import UserCancelled

# ESC key code
ESC_KEY = '\x1b'

# Global flag to signal cancellation
_cancel_requested = threading.Event()

# Terminal settings storage
_original_term_settings = None
_listener_active = False


def _setup_terminal() -> bool:
    """Set up terminal for raw input. Returns True if successful."""
    global _original_term_settings

    if not sys.stdin.isatty():
        return False

    try:
        import termios
        import tty

        fd = sys.stdin.fileno()
        _original_term_settings = termios.tcgetattr(fd)
        # Use cbreak mode - allows character-by-character input but keeps Ctrl+C working
        tty.setcbreak(fd)
        return True
    except Exception:
        return False


def _restore_terminal() -> None:
    """Restore terminal to original settings."""
    global _original_term_settings

    if _original_term_settings is not None:
        try:
            import termios
            fd = sys.stdin.fileno()
            termios.tcsetattr(fd, termios.TCSADRAIN, _original_term_settings)
        except Exception:
            pass
        _original_term_settings = None


def check_for_escape() -> bool:
    """Check if ESC key was pressed (non-blocking).

    Returns:
        True if ESC was detected, False otherwise
    """
    if not sys.stdin.isatty():
        return False

    try:
        # Check if input is available without blocking
        if select.select([sys.stdin], [], [], 0)[0]:
            char = sys.stdin.read(1)
            if char == ESC_KEY:
                return True
    except Exception:
        pass

    return False


@contextmanager
def escape_listener(console: Optional[Console] = None) -> Generator[None, None, None]:
    """Context manager that enables ESC key detection.

    Sets up terminal for raw input to detect ESC key.
    Use check_for_escape() or poll_escape() within the context.

    Args:
        console: Optional Rich console for displaying messages

    Yields:
        None
    """
    global _listener_active

    terminal_setup = _setup_terminal()
    _listener_active = True

    # Register cleanup at exit in case of unexpected termination
    atexit.register(_restore_terminal)

    try:
        yield
    finally:
        _listener_active = False
        _restore_terminal()
        atexit.unregister(_restore_terminal)


def poll_escape() -> None:
    """Poll for ESC key and set cancellation flag if pressed.

    Call this periodically during long-running operations.
    """
    if _listener_active and check_for_escape():
        request_cancel()


def stop_escape_listener() -> None:
    """Stop escape listener and restore terminal."""
    global _listener_active
    _listener_active = False
    _restore_terminal()


def reset_cancel():
    """Reset the cancellation flag."""
    _cancel_requested.clear()


def is_cancelled() -> bool:
    """Check if cancellation was requested."""
    return _cancel_requested.is_set()


def request_cancel():
    """Request cancellation (called when ESC is detected)."""
    _cancel_requested.set()


def check_cancel():
    """Check if cancelled and raise UserCancelled if so."""
    if is_cancelled():
        raise UserCancelled()


class CancellablePrompt(Prompt):
    """A Rich Prompt that can be cancelled with ESC key."""

    def __call__(self, *args, **kwargs) -> str:
        """Override to check for ESC during input."""
        try:
            result = super().__call__(*args, **kwargs)
            check_cancel()
            return result
        except KeyboardInterrupt:
            raise UserCancelled()


class CancellableConfirm(Confirm):
    """A Rich Confirm that can be cancelled with ESC key."""

    def __call__(self, *args, **kwargs) -> bool:
        """Override to check for ESC during input."""
        try:
            result = super().__call__(*args, **kwargs)
            check_cancel()
            return result
        except KeyboardInterrupt:
            raise UserCancelled()


def prompt_with_escape(
    prompt_text: str,
    console: Console,
    choices: Optional[List[str]] = None,
    default: Optional[str] = None,
    password: bool = False,
) -> str:
    """
    Display a prompt that can be cancelled with ESC or Ctrl+C.

    Args:
        prompt_text: The prompt text to display
        console: Rich console instance
        choices: Optional list of valid choices
        default: Default value if user presses enter
        password: Whether to hide input (for passwords)

    Returns:
        User's input string

    Raises:
        UserCancelled: If user presses ESC or Ctrl+C
    """
    try:
        if choices:
            return Prompt.ask(
                prompt_text,
                console=console,
                choices=choices,
                default=default,
            )
        else:
            return Prompt.ask(
                prompt_text,
                console=console,
                default=default,
                password=password,
            )
    except KeyboardInterrupt:
        console.print()
        raise UserCancelled()


def confirm_with_escape(
    prompt_text: str,
    console: Console,
    default: bool = False,
) -> bool:
    """
    Display a confirmation prompt that can be cancelled with ESC or Ctrl+C.

    Args:
        prompt_text: The prompt text to display
        console: Rich console instance
        default: Default value if user presses enter

    Returns:
        True if user confirmed, False otherwise

    Raises:
        UserCancelled: If user presses ESC or Ctrl+C
    """
    try:
        return Confirm.ask(prompt_text, console=console, default=default)
    except KeyboardInterrupt:
        console.print()
        raise UserCancelled()


def show_escape_hint(console: Console) -> None:
    """Display a hint about ESC key to cancel."""
    console.print("[dim](Press ESC at any time to cancel)[/dim]")
    console.print()
