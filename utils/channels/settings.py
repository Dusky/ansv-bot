"""
Channel settings management and configuration.
"""

import logging
from typing import Dict, Any, Optional, List

from ..integrations.database import DatabaseManager, ChannelConfig


class ChannelSettings:
    """Manages per-channel configuration and settings."""
    
    def __init__(self, database_manager: DatabaseManager):
        self.db = database_manager
        self._settings_cache = {}
    
    async def load_channel_settings(self, channel_name: str) -> Optional[ChannelConfig]:
        """Load settings for a specific channel."""
        try:
            clean_channel = channel_name.lstrip('#').lower()
            
            # Check cache first
            if clean_channel in self._settings_cache:
                return self._settings_cache[clean_channel]
            
            # Load from database
            config = await self.db.get_channel_config(clean_channel)
            
            if config:
                # Cache the result
                self._settings_cache[clean_channel] = config
                return config
            else:
                # Create default configuration if none exists
                default_config = ChannelConfig(channel_name=clean_channel)
                await self.db.save_channel_config(default_config)
                self._settings_cache[clean_channel] = default_config
                logging.info(f"Created default settings for channel: {clean_channel}")
                return default_config
                
        except Exception as e:
            logging.error(f"Error loading settings for channel {channel_name}: {e}")
            return None
    
    async def save_channel_settings(self, config: ChannelConfig) -> bool:
        """Save channel settings to database and update cache."""
        try:
            await self.db.save_channel_config(config)
            
            # Update cache
            self._settings_cache[config.channel_name] = config
            
            logging.info(f"Saved settings for channel: {config.channel_name}")
            return True
            
        except Exception as e:
            logging.error(f"Error saving settings for channel {config.channel_name}: {e}")
            return False
    
    async def update_channel_setting(self, channel_name: str, setting: str, value: Any) -> bool:
        """Update a specific setting for a channel."""
        try:
            clean_channel = channel_name.lstrip('#').lower()
            config = await self.load_channel_settings(clean_channel)
            
            if not config:
                return False
            
            # Update the specific setting
            if hasattr(config, setting):
                setattr(config, setting, value)
                return await self.save_channel_settings(config)
            else:
                logging.error(f"Unknown setting: {setting}")
                return False
                
        except Exception as e:
            logging.error(f"Error updating setting {setting} for channel {channel_name}: {e}")
            return False
    
    async def get_channel_setting(self, channel_name: str, setting: str, default: Any = None) -> Any:
        """Get a specific setting value for a channel."""
        try:
            clean_channel = channel_name.lstrip('#').lower()
            config = await self.load_channel_settings(clean_channel)
            
            if config and hasattr(config, setting):
                return getattr(config, setting)
            else:
                return default
                
        except Exception as e:
            logging.error(f"Error getting setting {setting} for channel {channel_name}: {e}")
            return default
    
    async def toggle_channel_setting(self, channel_name: str, setting: str) -> Optional[bool]:
        """Toggle a boolean setting for a channel."""
        try:
            clean_channel = channel_name.lstrip('#').lower()
            config = await self.load_channel_settings(clean_channel)
            
            if not config:
                return None
            
            if hasattr(config, setting):
                current_value = getattr(config, setting)
                if isinstance(current_value, bool):
                    new_value = not current_value
                    setattr(config, setting, new_value)
                    await self.save_channel_settings(config)
                    logging.info(f"Toggled {setting} for {clean_channel}: {new_value}")
                    return new_value
                else:
                    logging.error(f"Setting {setting} is not boolean")
                    return None
            else:
                logging.error(f"Unknown setting: {setting}")
                return None
                
        except Exception as e:
            logging.error(f"Error toggling setting {setting} for channel {channel_name}: {e}")
            return None
    
    async def get_all_channel_settings(self) -> Dict[str, ChannelConfig]:
        """Get settings for all configured channels."""
        try:
            channels = await self.db.get_channels_to_join()
            settings = {}
            
            for channel in channels:
                clean_channel = channel.lstrip('#').lower()
                config = await self.load_channel_settings(clean_channel)
                if config:
                    settings[clean_channel] = config
            
            return settings
            
        except Exception as e:
            logging.error(f"Error getting all channel settings: {e}")
            return {}
    
    async def ensure_channel_configs(self, channels: List[str]) -> None:
        """Ensure all channels have configuration entries."""
        try:
            for channel in channels:
                clean_channel = channel.lstrip('#').lower()
                await self.load_channel_settings(clean_channel)  # This creates if missing
            
            logging.info(f"Ensured configurations for {len(channels)} channels")
            
        except Exception as e:
            logging.error(f"Error ensuring channel configurations: {e}")
    
    async def reset_channel_settings(self, channel_name: str) -> bool:
        """Reset channel settings to defaults."""
        try:
            clean_channel = channel_name.lstrip('#').lower()
            default_config = ChannelConfig(channel_name=clean_channel)
            
            success = await self.save_channel_settings(default_config)
            if success:
                logging.info(f"Reset settings for channel: {clean_channel}")
            
            return success
            
        except Exception as e:
            logging.error(f"Error resetting settings for channel {channel_name}: {e}")
            return False
    
    async def export_channel_settings(self, channel_name: str) -> Optional[Dict[str, Any]]:
        """Export channel settings as a dictionary."""
        try:
            clean_channel = channel_name.lstrip('#').lower()
            config = await self.load_channel_settings(clean_channel)
            
            if config:
                return {
                    "channel_name": config.channel_name,
                    "join_channel": config.join_channel,
                    "tts_enabled": config.tts_enabled,
                    "voice_enabled": config.voice_enabled,
                    "voice_preset": config.voice_preset,
                    "bark_model": config.bark_model,
                    "lines_between_messages": config.lines_between_messages,
                    "time_between_messages": config.time_between_messages,
                    "use_general_model": config.use_general_model,
                    "currently_connected": config.currently_connected
                }
            return None
            
        except Exception as e:
            logging.error(f"Error exporting settings for channel {channel_name}: {e}")
            return None
    
    async def import_channel_settings(self, channel_name: str, settings: Dict[str, Any]) -> bool:
        """Import channel settings from a dictionary."""
        try:
            clean_channel = channel_name.lstrip('#').lower()
            
            # Create config from settings
            config = ChannelConfig(
                channel_name=clean_channel,
                join_channel=settings.get("join_channel", True),
                tts_enabled=settings.get("tts_enabled", False),
                voice_enabled=settings.get("voice_enabled", False),
                voice_preset=settings.get("voice_preset"),
                bark_model=settings.get("bark_model"),
                lines_between_messages=settings.get("lines_between_messages", 100),
                time_between_messages=settings.get("time_between_messages", 0),
                use_general_model=settings.get("use_general_model", False),
                currently_connected=settings.get("currently_connected", False)
            )
            
            success = await self.save_channel_settings(config)
            if success:
                logging.info(f"Imported settings for channel: {clean_channel}")
            
            return success
            
        except Exception as e:
            logging.error(f"Error importing settings for channel {channel_name}: {e}")
            return False
    
    def invalidate_cache(self, channel_name: Optional[str] = None) -> None:
        """Invalidate settings cache for a channel or all channels."""
        if channel_name:
            clean_channel = channel_name.lstrip('#').lower()
            self._settings_cache.pop(clean_channel, None)
            logging.debug(f"Invalidated cache for channel: {clean_channel}")
        else:
            self._settings_cache.clear()
            logging.debug("Invalidated all channel settings cache")
    
    def get_cache_size(self) -> int:
        """Get the current size of the settings cache."""
        return len(self._settings_cache)
    
    def cleanup(self) -> None:
        """Cleanup channel settings resources."""
        self._settings_cache.clear()
        logging.info("Channel settings cleanup completed")