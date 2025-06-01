"""
Integrations module - External service coordination.
"""

from .tts_controller import TTSController
from .database import DatabaseManager

__all__ = ['TTSController', 'DatabaseManager']