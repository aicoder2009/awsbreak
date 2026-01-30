"""
Core exception classes for AWS Hit Breaks.
"""


class AWSBreakError(Exception):
    """Base exception for all AWS Break CLI errors."""
    
    def __init__(self, message: str, details: str = None):
        super().__init__(message)
        self.message = message
        self.details = details


class AuthenticationError(AWSBreakError):
    """Raised when AWS authentication fails."""
    pass


class ConfigurationError(AWSBreakError):
    """Raised when configuration is invalid or missing."""
    pass


class ServiceError(AWSBreakError):
    """Raised when AWS service operations fail."""
    pass


class StateError(AWSBreakError):
    """Raised when state management operations fail."""
    pass


class ValidationError(AWSBreakError):
    """Raised when input validation fails."""
    pass


class UserCancelled(AWSBreakError):
    """Raised when user cancels operation (ESC key or Ctrl+C)."""

    def __init__(self, message: str = "Operation cancelled by user"):
        super().__init__(message)