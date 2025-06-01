"""
Messaging module - Message processing and command routing.
"""

from .processor import MessageProcessor
from .commands import CommandRouter

__all__ = ['MessageProcessor', 'CommandRouter']