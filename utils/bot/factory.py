"""
Bot factory for creating and configuring the ANSV bot instance.
"""

import asyncio
import logging
import configparser
from typing import Optional, List
from pathlib import Path

from ..config.manager import BotConfig
from .core import ANSVBot


def load_config_from_file(config_path: str = "settings.conf") -> BotConfig:
    """Load bot configuration from config file."""
    config = configparser.ConfigParser()
    config.read(config_path)
    
    try:
        # Extract required settings - try both auth and settings sections for compatibility
        try:
            token = config["auth"]["tmi_token"]
            client_id = config["auth"]["client_id"]
            nickname = config["auth"]["nickname"]
            owner = config["auth"]["owner"]
        except KeyError:
            # Fallback to settings section
            token = config["settings"]["token"]
            client_id = config["settings"]["client_id"]
            nickname = config["settings"]["nickname"]
            owner = config["settings"]["owner"]
        
        # Parse channels - try both sections
        try:
            channels_str = config["settings"]["channels"]
        except KeyError:
            try:
                channels_str = config["channels"]["channels"]
            except KeyError:
                channels_str = config["auth"]["channels"]
        channels = [ch.strip().lower() for ch in channels_str.split(",") if ch.strip()]
        
        # Optional settings
        database_path = config.get("settings", "database_path", fallback="messages.db")
        enable_tts = config.getboolean("settings", "enable_tts", fallback=False)
        log_level = config.get("settings", "log_level", fallback="INFO")
        
        return BotConfig(
            token=token,
            client_id=client_id,
            nickname=nickname,
            owner=owner,
            channels=channels,
            database_path=database_path,
            enable_tts=enable_tts,
            log_level=log_level
        )
        
    except KeyError as e:
        raise ValueError(f"Missing required configuration key: {e}")
    except Exception as e:
        raise ValueError(f"Error loading configuration: {e}")


def setup_logging(log_level: str = "INFO") -> None:
    """Setup logging configuration for the bot."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("ansv_bot.log"),
            logging.StreamHandler()
        ]
    )
    
    # Set specific logger levels
    logging.getLogger("twitchio").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)


async def create_bot(config_path: str = "settings.conf", rebuild_cache: bool = False, enable_tts: bool = False) -> ANSVBot:
    """Create and configure an ANSV bot instance."""
    try:
        # Load configuration
        config = load_config_from_file(config_path)
        
        # Override TTS setting from command line if provided
        if enable_tts:
            config.enable_tts = enable_tts
        
        # Setup logging
        setup_logging(config.log_level)
        
        # Create bot instance
        bot = ANSVBot(config)
        
        # Handle cache rebuild if requested
        if rebuild_cache:
            logging.info("Rebuild cache requested - will rebuild markov models")
        
        # Validate configuration
        await validate_bot_config(bot)
        
        return bot
        
    except Exception as e:
        logging.error(f"Failed to create bot: {e}")
        raise


async def validate_bot_config(bot: ANSVBot) -> None:
    """Validate bot configuration and dependencies."""
    config = bot.config
    
    # Check required fields
    if not config.token:
        raise ValueError("Bot token is required")
    if not config.client_id:
        raise ValueError("Client ID is required")
    if not config.nickname:
        raise ValueError("Bot nickname is required")
    if not config.channels:
        raise ValueError("At least one channel is required")
    
    # Check database path
    db_path = Path(config.database_path)
    if not db_path.parent.exists():
        raise ValueError(f"Database directory does not exist: {db_path.parent}")
    
    # Validate channels format
    for channel in config.channels:
        if not channel.replace('_', '').replace('-', '').isalnum():
            raise ValueError(f"Invalid channel name format: {channel}")
    
    logging.info(f"Bot configuration validated for {len(config.channels)} channels")


async def setup_bot(config_path: str = "settings.conf") -> ANSVBot:
    """Setup and return a configured bot instance (legacy function name)."""
    return await create_bot(config_path)


if __name__ == "__main__":
    # Example usage
    async def main():
        bot = await create_bot()
        await bot.start()
    
    asyncio.run(main())