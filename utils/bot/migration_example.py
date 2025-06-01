"""
Example migration script showing how to transition from old bot.py to new modular architecture.

This demonstrates the new API and how to create and run the bot with the modular system.
"""

import asyncio
import logging
from pathlib import Path

# Import the new modular components
from .factory import create_bot, load_config_from_file
from .core import ANSVBot


async def run_new_modular_bot():
    """Example of running the new modular bot."""
    try:
        # Create bot using the factory
        bot = await create_bot("settings.conf")
        
        # The bot is now fully configured with all modules
        print(f"Bot created successfully: {bot.nick}")
        print(f"Configured for channels: {', '.join(bot.config.channels)}")
        
        # Start the bot (this would run indefinitely)
        # await bot.start()
        
        # For demonstration, just show the configuration
        return bot
        
    except Exception as e:
        logging.error(f"Failed to create bot: {e}")
        raise


async def demonstrate_new_architecture():
    """Demonstrate the new modular architecture features."""
    print("=== ANSV Bot Modular Architecture Demo ===")
    
    # Load configuration
    try:
        config = load_config_from_file("settings.conf")
        print(f"Loaded config for bot: {config.nickname}")
        print(f"Channels: {', '.join(config.channels)}")
        print(f"TTS enabled: {config.enable_tts}")
        print(f"Log level: {config.log_level}")
        
    except Exception as e:
        print(f"Config loading failed: {e}")
        return
    
    # Create bot instance
    bot = ANSVBot(config)
    
    # Show modular components
    print("\n=== Modular Components ===")
    print(f"State Manager: {bot.state_manager.__class__.__name__}")
    print(f"Database Manager: {bot.database_manager.__class__.__name__}")
    print(f"TTS Controller: {bot.tts_controller.__class__.__name__}")
    print(f"Channel Manager: {bot.channel_manager.__class__.__name__}")
    print(f"Message Processor: {bot.message_processor.__class__.__name__}")
    print(f"Command Router: {bot.command_router.__class__.__name__}")
    
    # Initialize bot components (without starting)
    try:
        await bot.setup_hook()
        print("\n=== Bot Components Initialized ===")
        
        # Test database connection
        db_healthy = await bot.database_manager.health_check()
        print(f"Database health: {'OK' if db_healthy else 'FAILED'}")
        
        # Get state summary
        state_summary = await bot.state_manager.get_state_summary()
        print(f"State summary: {state_summary}")
        
        # Test channel status
        for channel in config.channels[:2]:  # Test first 2 channels
            status = await bot.get_channel_status(channel)
            print(f"Channel {channel} status: {status}")
        
        print("\n=== Architecture Demo Complete ===")
        
    except Exception as e:
        print(f"Initialization failed: {e}")
        raise
    
    finally:
        # Cleanup
        await bot.shutdown()


def compare_architectures():
    """Compare old vs new architecture."""
    print("\n=== Architecture Comparison ===")
    print("OLD (Monolithic bot.py - 1,963 lines):")
    print("  ❌ Single massive file with all functionality")
    print("  ❌ Tightly coupled database operations")
    print("  ❌ Mixed concerns (TTS, markov, channels, commands)")
    print("  ❌ Difficult to test individual components")
    print("  ❌ Hard to extend or modify specific features")
    
    print("\nNEW (Modular Architecture):")
    print("  ✅ Focused, single-responsibility modules")
    print("  ✅ Centralized async database operations")
    print("  ✅ Separated concerns with dependency injection")
    print("  ✅ Individually testable components")
    print("  ✅ Easy to extend and modify specific features")
    print("  ✅ Clean configuration management")
    print("  ✅ Async/await throughout")
    
    print("\nModule Breakdown:")
    modules = [
        ("config/", "Configuration management"),
        ("coordination/", "State management and async coordination"),
        ("integrations/", "Database and TTS coordination"),
        ("channels/", "Channel joining, leaving, and management"),
        ("messaging/", "Message processing, markov, and commands"),
        ("bot/", "Core bot implementation and factory")
    ]
    
    for module, description in modules:
        print(f"  📁 utils/{module:<20} - {description}")


if __name__ == "__main__":
    # Run the demonstration
    compare_architectures()
    
    # Only run the async demo if the config file exists
    if Path("settings.conf").exists():
        asyncio.run(demonstrate_new_architecture())
    else:
        print("\nSkipping bot demo - settings.conf not found")