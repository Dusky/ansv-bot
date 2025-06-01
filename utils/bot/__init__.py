"""
Bot core module - Main bot class and factory functions.
"""

from .factory import setup_bot
from .core import Bot

__all__ = ['setup_bot', 'Bot']