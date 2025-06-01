"""
Event handler for bot events - message processing, joins, parts, etc.
"""

import asyncio
import logging
from typing import TYPE_CHECKING
from twitchio import Message, Channel, User

if TYPE_CHECKING:
    from .core import ANSVBot


class EventHandler:
    """Handles TwitchIO events and coordinates with appropriate processors."""
    
    def __init__(self, bot: 'ANSVBot'):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        
    async def on_ready(self) -> None:
        """Called when bot is ready and connected to Twitch."""
        try:
            self.logger.info(f"Bot {self.bot.nick} connected to Twitch")
            
            # Update channel states to connected
            for channel_name in self.bot.config.channels:
                await self.bot.state_manager.set_channel_connected(channel_name, True)
                
            self.logger.info(f"Bot ready in channels: {', '.join(self.bot.config.channels)}")
            
        except Exception as e:
            self.logger.error(f"Error in on_ready event: {e}")
    
    async def on_message(self, message: Message) -> None:
        """Handle incoming chat messages."""
        try:
            # Skip if message is from the bot itself
            if message.author.name.lower() == self.bot.nick.lower():
                return
                
            # Check if it's a command
            if message.content.startswith('!'):
                await self.bot.process_command(message)
            else:
                # Regular message processing
                await self.bot.process_message(message)
                
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
    
    async def on_join(self, channel: Channel, user: User) -> None:
        """Called when a user joins a channel."""
        try:
            channel_name = channel.name.lower()
            username = user.name.lower()
            
            # Log the join event
            self.logger.debug(f"{username} joined {channel_name}")
            
            # If it's the bot joining, update state
            if username == self.bot.nick.lower():
                await self.bot.state_manager.set_channel_connected(channel_name, True)
                self.logger.info(f"Bot successfully joined {channel_name}")
                
        except Exception as e:
            self.logger.error(f"Error handling join event: {e}")
    
    async def on_part(self, user: User) -> None:
        """Called when a user leaves a channel."""
        try:
            username = user.name.lower()
            
            # Log the part event
            self.logger.debug(f"{username} left a channel")
            
            # If it's the bot leaving, we'd need channel context to update state
            # This is a limitation of the current TwitchIO event structure
            
        except Exception as e:
            self.logger.error(f"Error handling part event: {e}")
    
    async def on_error(self, error: Exception, data: str = None) -> None:
        """Handle bot errors."""
        self.logger.error(f"Bot error occurred: {error}")
        if data:
            self.logger.error(f"Error data: {data}")
    
    async def on_command_error(self, context, error: Exception) -> None:
        """Handle command errors."""
        self.logger.error(f"Command error in {context.channel.name}: {error}")
        
        # Send error message to channel if appropriate
        try:
            await context.send("An error occurred while processing that command.")
        except Exception:
            # If we can't send the error message, just log it
            pass