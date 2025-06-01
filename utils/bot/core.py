"""
Core bot implementation - Lightweight TwitchIO bot with modular architecture.
"""

import asyncio
import logging
import time
from typing import Optional, List, Dict, Any
from twitchio.ext import commands
from twitchio import Message, Channel

from ..config.manager import BotConfig
from ..coordination.state_manager import StateManager
from ..integrations.database import DatabaseManager
from ..integrations.tts_controller import TTSController
from ..channels.manager import ChannelManager
from ..messaging.processor import MessageProcessor
from ..messaging.commands import CommandRouter, CommandContext
from .events import EventHandler


class ANSVBot(commands.Bot):
    """Lightweight ANSV bot with modular architecture and dependency injection."""
    
    def __init__(self, config: BotConfig):
        super().__init__(
            token=config.token,
            client_id=config.client_id,
            nick=config.nickname,
            prefix='!',
            initial_channels=config.channels
        )
        
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize managers and controllers
        self.state_manager = StateManager()
        self.database_manager = DatabaseManager(config.database_path)
        self.tts_controller = TTSController(self.database_manager)
        self.channel_manager = ChannelManager(self, self.database_manager, self.state_manager)
        self.message_processor = MessageProcessor(self.database_manager, self.state_manager)
        self.command_router = CommandRouter(self.database_manager, self.state_manager, self.tts_controller)
        self.event_handler = EventHandler(self)
        
        # Track initialization
        self._initialized = False
        
    async def setup_hook(self) -> None:
        """Setup hook called when bot starts."""
        try:
            self.logger.info("Starting ANSV bot initialization...")
            
            # Initialize database connection
            await self.database_manager.initialize()
            
            # Initialize state manager
            await self.state_manager.initialize()
            
            # Initialize channel states
            for channel_name in self.config.channels:
                await self.state_manager.add_channel(channel_name)
            
            # Initialize TTS if enabled
            if self.config.enable_tts:
                await self.tts_controller.initialize()
            
            self._initialized = True
            self.logger.info("ANSV bot initialization complete")
            
        except Exception as e:
            self.logger.error(f"Error during bot initialization: {e}")
            raise
    
    async def event_ready(self) -> None:
        """Called when bot is ready and connected."""
        self.logger.info(f'Bot {self.nick} is ready!')
        await self.event_handler.on_ready()
    
    async def event_message(self, message: Message) -> None:
        """Handle incoming chat messages."""
        if not self._initialized:
            return
            
        # Ignore messages from self
        if message.echo:
            return
            
        await self.event_handler.on_message(message)
    
    async def event_join(self, channel: Channel, user) -> None:
        """Called when someone joins a channel."""
        await self.event_handler.on_join(channel, user)
    
    async def event_part(self, user) -> None:
        """Called when someone leaves a channel."""
        await self.event_handler.on_part(user)
    
    async def process_message(self, message: Message) -> None:
        """Process incoming message through message processor."""
        try:
            channel_name = message.channel.name.lower()
            author = message.author.name.lower()
            content = message.content
            
            # Process the message
            await self.message_processor.process_message(channel_name, author, content)
            
            # Check if we should generate a markov response
            if await self.message_processor.should_generate_response(channel_name):
                response = await self.message_processor.generate_markov_response(channel_name)
                if response:
                    await message.channel.send(response)
            
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    async def process_command(self, message: Message) -> None:
        """Process bot commands."""
        try:
            content = message.content.strip()
            if not content.startswith('!'):
                return
                
            # Parse command and arguments
            parts = content[1:].split()
            if not parts:
                return
                
            command = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            # Create command context
            ctx = CommandContext(
                channel_name=message.channel.name.lower(),
                author=message.author.name.lower(),
                message_content=content,
                is_mod=message.author.is_mod,
                is_owner=(message.author.name.lower() == self.config.owner.lower())
            )
            
            # Process command
            response = await self.command_router.process_command(ctx, command, args)
            if response:
                await message.channel.send(response)
                
        except Exception as e:
            self.logger.error(f"Error processing command: {e}")
    
    async def join_channel(self, channel_name: str) -> bool:
        """Join a channel through channel manager."""
        return await self.channel_manager.join_channel(channel_name)
    
    async def leave_channel(self, channel_name: str) -> bool:
        """Leave a channel through channel manager."""
        return await self.channel_manager.leave_channel(channel_name)
    
    async def get_channel_status(self, channel_name: str) -> Optional[Dict[str, Any]]:
        """Get channel status information."""
        try:
            state = await self.state_manager.get_channel_state(channel_name)
            config = await self.database_manager.get_channel_config(channel_name)
            
            if not state:
                return None
                
            return {
                'name': channel_name,
                'connected': state.connected,
                'message_count': state.chat_line_count,
                'tts_enabled': config.tts_enabled if config else False,
                'markov_enabled': config.markov_enabled if config else False
            }
            
        except Exception as e:
            self.logger.error(f"Error getting channel status: {e}")
            return None
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the bot."""
        try:
            self.logger.info("Shutting down ANSV bot...")
            
            # Shutdown TTS controller
            if hasattr(self.tts_controller, 'shutdown'):
                await self.tts_controller.shutdown()
            
            # Close database connections
            await self.database_manager.close()
            
            # Close the bot connection
            await self.close()
            
            self.logger.info("ANSV bot shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")