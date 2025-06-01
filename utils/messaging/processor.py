"""
Message processor for handling chat messages and coordinating responses.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import time

from ..coordination.state_manager import StateManager
from ..integrations.database import DatabaseManager
from .markov import MarkovProcessor


class MessageProcessor:
    """Handles incoming chat messages and coordinates response generation."""
    
    def __init__(self, database_manager: DatabaseManager, state_manager: StateManager):
        self.database_manager = database_manager
        self.state_manager = state_manager
        self.markov_processor = MarkovProcessor(database_manager)
        self.logger = logging.getLogger(__name__)
        
    async def process_message(self, channel_name: str, author: str, content: str) -> None:
        """Process an incoming chat message."""
        try:
            # Update channel state
            await self.state_manager.update_channel_message_count(channel_name)
            
            # Store message in database
            await self.database_manager.store_message(
                channel_name=channel_name,
                author=author,
                content=content,
                timestamp=datetime.now()
            )
            
            # Update markov training data
            await self.markov_processor.add_message_to_training(channel_name, content)
            
            self.logger.info(f"Processed message from {author} in {channel_name}")
            
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    async def should_generate_response(self, channel_name: str) -> bool:
        """Determine if bot should generate a markov response."""
        try:
            channel_config = await self.database_manager.get_channel_config(channel_name)
            if not channel_config or not channel_config.markov_enabled:
                return False
                
            channel_state = await self.state_manager.get_channel_state(channel_name)
            if not channel_state:
                return False
                
            # Check if enough messages have accumulated
            threshold = channel_config.markov_response_threshold or 50
            return channel_state.chat_line_count >= threshold
            
        except Exception as e:
            self.logger.error(f"Error checking response condition: {e}")
            return False
    
    async def generate_markov_response(self, channel_name: str) -> Optional[str]:
        """Generate a markov chain response for the channel."""
        try:
            response = await self.markov_processor.generate_response(channel_name)
            if response:
                # Reset message count after generating response
                await self.state_manager.reset_channel_message_count(channel_name)
            return response
            
        except Exception as e:
            self.logger.error(f"Error generating markov response: {e}")
            return None