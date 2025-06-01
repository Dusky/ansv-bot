"""
TTS (Text-to-Speech) coordination and management.
This module coordinates TTS operations without handling the actual TTS processing.
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from .database import DatabaseManager
from ..tts import process_text, start_tts_processing


class TTSController:
    """Coordinates TTS operations and manages TTS-related functionality."""
    
    def __init__(self, database_manager: DatabaseManager):
        self.db = database_manager
        self._last_tts_times = {}  # Channel -> last TTS time
        self.logger = logging.getLogger(__name__)
    
    async def handle_speak_command(self, channel_name: str, text: str, 
                                  voice_preset_override: Optional[str] = None) -> bool:
        """Handle TTS speak command with rate limiting and validation."""
        try:
            # Check if TTS is enabled for the channel
            if not await self.is_tts_enabled(channel_name):
                logging.info(f"TTS not enabled for channel {channel_name}")
                return False
            
            # Check rate limiting
            if not await self._check_tts_rate_limit(channel_name):
                logging.info(f"TTS rate limited for channel {channel_name}")
                return False
            
            # Get voice preset
            voice_preset = voice_preset_override or await self.get_voice_preset(channel_name)
            
            # Start TTS processing asynchronously
            success, output_file = await process_text(
                channel=channel_name,
                text=text,
                model_type="bark",
                voice_preset_override=voice_preset
            )
            
            if success and output_file:
                # Log successful TTS generation
                await self.db.log_tts_generation(
                    channel_name=channel_name,
                    text=text,
                    file_path=output_file,
                    voice_preset=voice_preset
                )
                
                # Update last TTS time
                self._last_tts_times[channel_name] = datetime.now()
                
                logging.info(f"TTS generated successfully for {channel_name}: {output_file}")
                return True
            else:
                logging.error(f"TTS generation failed for {channel_name}")
                return False
                
        except Exception as e:
            logging.error(f"Error in TTS speak command for {channel_name}: {e}")
            return False
    
    async def generate_tts_for_message(self, channel_name: str, text: str, 
                                     message_id: Optional[str] = None,
                                     timestamp_str: Optional[str] = None) -> bool:
        """Generate TTS for a bot message (non-command)."""
        try:
            # Check if TTS is enabled
            if not await self.is_tts_enabled(channel_name):
                return False
            
            # Check TTS delay if enabled
            if await self.is_tts_delay_enabled(channel_name):
                if not await self._check_tts_delay(channel_name):
                    return False
            
            # Get voice preset
            voice_preset = await self.get_voice_preset(channel_name)
            
            # Use the threaded TTS processing for bot messages
            start_tts_processing(
                input_text=text,
                channel_name=channel_name,
                message_id=message_id,
                timestamp_str=timestamp_str,
                voice_preset_override=voice_preset
            )
            
            logging.info(f"TTS processing started for bot message in {channel_name}")
            return True
            
        except Exception as e:
            logging.error(f"Error generating TTS for message in {channel_name}: {e}")
            return False
    
    async def is_tts_enabled(self, channel_name: str) -> bool:
        """Check if TTS is enabled for a channel."""
        try:
            config = await self.db.get_channel_config(channel_name)
            return config.tts_enabled if config else False
        except Exception as e:
            logging.error(f"Error checking TTS status for {channel_name}: {e}")
            return False
    
    async def is_tts_delay_enabled(self, channel_name: str) -> bool:
        """Check if TTS delay is enabled for a channel."""
        try:
            # This would need to be added to the database schema
            # For now, return False as default
            return False
        except Exception as e:
            logging.error(f"Error checking TTS delay status for {channel_name}: {e}")
            return False
    
    async def get_voice_preset(self, channel_name: str) -> str:
        """Get voice preset for a channel."""
        try:
            config = await self.db.get_channel_config(channel_name)
            return config.voice_preset if config and config.voice_preset else "v2/en_speaker_0"
        except Exception as e:
            logging.error(f"Error getting voice preset for {channel_name}: {e}")
            return "v2/en_speaker_0"
    
    async def set_voice_preset(self, channel_name: str, voice_preset: str) -> bool:
        """Set voice preset for a channel."""
        try:
            config = await self.db.get_channel_config(channel_name)
            if config:
                config.voice_preset = voice_preset
                await self.db.save_channel_config(config)
                return True
            return False
        except Exception as e:
            logging.error(f"Error setting voice preset for {channel_name}: {e}")
            return False
    
    async def toggle_tts(self, channel_name: str) -> bool:
        """Toggle TTS enabled/disabled for a channel."""
        try:
            config = await self.db.get_channel_config(channel_name)
            if config:
                config.tts_enabled = not config.tts_enabled
                await self.db.save_channel_config(config)
                logging.info(f"TTS {'enabled' if config.tts_enabled else 'disabled'} for {channel_name}")
                return config.tts_enabled
            return False
        except Exception as e:
            logging.error(f"Error toggling TTS for {channel_name}: {e}")
            return False
    
    async def get_tts_history(self, channel_name: str, limit: int = 50) -> list:
        """Get TTS history for a channel."""
        try:
            return await self.db.get_tts_history(channel_name, limit)
        except Exception as e:
            logging.error(f"Error getting TTS history for {channel_name}: {e}")
            return []
    
    async def _check_tts_rate_limit(self, channel_name: str) -> bool:
        """Check if TTS rate limit allows generation."""
        last_tts = self._last_tts_times.get(channel_name)
        if last_tts:
            # Allow TTS every 3 seconds (configurable)
            min_interval = timedelta(seconds=3)
            if datetime.now() - last_tts < min_interval:
                return False
        return True
    
    async def _check_tts_delay(self, channel_name: str) -> bool:
        """Check TTS delay settings for bot messages."""
        try:
            config = await self.db.get_channel_config(channel_name)
            if not config:
                return True
            
            # Check time between messages setting
            if config.time_between_messages > 0:
                last_tts = self._last_tts_times.get(channel_name)
                if last_tts:
                    min_interval = timedelta(seconds=config.time_between_messages)
                    if datetime.now() - last_tts < min_interval:
                        return False
            
            return True
        except Exception as e:
            logging.error(f"Error checking TTS delay for {channel_name}: {e}")
            return True
    
    async def get_tts_status(self, channel_name: str) -> Dict[str, Any]:
        """Get comprehensive TTS status for a channel."""
        try:
            config = await self.db.get_channel_config(channel_name)
            if not config:
                return {
                    "enabled": False,
                    "voice_preset": "v2/en_speaker_0",
                    "last_generation": None,
                    "rate_limited": False
                }
            
            last_tts = self._last_tts_times.get(channel_name)
            rate_limited = not await self._check_tts_rate_limit(channel_name)
            
            return {
                "enabled": config.tts_enabled,
                "voice_preset": config.voice_preset or "v2/en_speaker_0",
                "last_generation": last_tts.isoformat() if last_tts else None,
                "rate_limited": rate_limited,
                "time_between_messages": config.time_between_messages
            }
        except Exception as e:
            logging.error(f"Error getting TTS status for {channel_name}: {e}")
            return {"enabled": False, "error": str(e)}
    
    async def initialize(self) -> None:
        """Initialize the TTS controller."""
        self.logger.info("TTS controller initialized")
    
    async def shutdown(self) -> None:
        """Shutdown TTS controller resources."""
        self._last_tts_times.clear()
        self.logger.info("TTS controller shutdown completed")
    
    def cleanup(self) -> None:
        """Cleanup TTS controller resources."""
        self._last_tts_times.clear()
        logging.info("TTS controller cleanup completed")