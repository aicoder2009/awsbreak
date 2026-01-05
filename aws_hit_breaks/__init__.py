"""
AWS Hit Breaks - Emergency cost control for AWS accounts.

A CLI tool that acts like a car's brakes for AWS accounts, allowing users to pause
all running processes and services to stop incurring costs without permanent deletion.
"""

__version__ = "1.0.0"
__author__ = "AWS Break CLI Team"
__email__ = "support@aws-hit-breaks.com"

from aws_hit_breaks.core.exceptions import AWSBreakError

__all__ = ["AWSBreakError"]