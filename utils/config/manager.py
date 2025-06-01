"""
Configuration management for bot settings and channels.
"""

import configparser
import logging
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class BotConfig:
    """Bot configuration data class."""
    token: str
    client_id: str
    nickname: str
    owner: str
    channels: List[str]
    verbose_logs: bool = False
    lines_between_messages: int = 100
    time_between_messages: int = 0


class ConfigManager:
    """Manages bot configuration loading and validation."""
    
    def __init__(self, config_file: str = "settings.conf"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file."""
        try:
            self.config.read(self.config_file)
        except Exception as e:
            logging.error(f"Failed to load config from {self.config_file}: {e}")
            raise
    
    def get_bot_config(self) -> BotConfig:
        """Get validated bot configuration."""
        try:
            # Extract channels with error handling
            channels_str = self.config.get("channels", "channels", fallback="")
            channels = [ch.strip() for ch in channels_str.split(",") if ch.strip()]
            
            return BotConfig(
                token=self.config.get("auth", "tmi_token"),
                client_id=self.config.get("auth", "client_id"),
                nickname=self.config.get("auth", "nickname"),
                owner=self.config.get("auth", "owner"),
                channels=channels,
                verbose_logs=self.config.getboolean("settings", "verbose_logs", fallback=False),
                lines_between_messages=self.config.getint("settings", "lines_between_messages", fallback=100),
                time_between_messages=self.config.getint("settings", "time_between_messages", fallback=0)
            )
        except Exception as e:
            logging.error(f"Error parsing configuration: {e}")
            raise ValueError(f"Invalid configuration: {e}")
    
    def get_channels(self) -> List[str]:
        """Get list of channels from configuration."""
        return self.get_bot_config().channels
    
    def get_setting(self, section: str, key: str, fallback: Optional[str] = None) -> Optional[str]:
        """Get a specific setting value."""
        return self.config.get(section, key, fallback=fallback)
    
    def get_boolean_setting(self, section: str, key: str, fallback: bool = False) -> bool:
        """Get a boolean setting value."""
        return self.config.getboolean(section, key, fallback=fallback)
    
    def get_int_setting(self, section: str, key: str, fallback: int = 0) -> int:
        """Get an integer setting value."""
        return self.config.getint(section, key, fallback=fallback)