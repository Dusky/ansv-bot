"""
Markov chain text generation processor.
"""

import asyncio
import logging
import markovify
import os
import json
import time
from typing import Optional, Dict, Any
from datetime import datetime

from ..integrations.database import DatabaseManager
from ..config.cache import LRUCache


class MarkovProcessor:
    """Handles markov chain model building and text generation."""
    
    def __init__(self, database_manager: DatabaseManager):
        self.database_manager = database_manager
        self.logger = logging.getLogger(__name__)
        self.models_cache = LRUCache(maxsize=50)  # Cache for channel models
        self.cache_update_threshold = 3600 * 24  # 24 hours
        self.cache_build_times = {}
        self.model_lock = asyncio.Lock()
        
    async def load_last_cache_build_times(self) -> Dict[str, float]:
        """Load cache build times from database."""
        try:
            times = await self.database_manager.get_cache_build_times()
            return times or {}
        except Exception as e:
            self.logger.error(f"Error loading cache build times: {e}")
            return {}
    
    async def save_cache_build_time(self, channel_name: str, build_time: float) -> None:
        """Save cache build time to database."""
        try:
            await self.database_manager.save_cache_build_time(channel_name, build_time)
            self.cache_build_times[channel_name] = build_time
        except Exception as e:
            self.logger.error(f"Error saving cache build time: {e}")
    
    async def should_rebuild_model(self, channel_name: str) -> bool:
        """Check if model should be rebuilt based on cache age."""
        try:
            last_build = self.cache_build_times.get(channel_name, 0)
            current_time = time.time()
            return (current_time - last_build) > self.cache_update_threshold
        except Exception as e:
            self.logger.error(f"Error checking rebuild condition: {e}")
            return True
    
    async def build_channel_model(self, channel_name: str, force_rebuild: bool = False) -> Optional[markovify.Text]:
        """Build markov model for specific channel."""
        async with self.model_lock:
            try:
                # Check if rebuild is needed
                if not force_rebuild and not await self.should_rebuild_model(channel_name):
                    cached_model = self.models_cache.get(channel_name)
                    if cached_model:
                        return cached_model
                
                # Get messages from database
                messages = await self.database_manager.get_channel_messages(channel_name)
                if not messages or len(messages) < 10:
                    self.logger.warning(f"Insufficient messages for {channel_name} model")
                    return None
                
                # Combine messages into training text
                text_data = "\n".join([msg.content for msg in messages if msg.content])
                
                if not text_data.strip():
                    self.logger.warning(f"No valid text data for {channel_name}")
                    return None
                
                # Build markov model
                model = markovify.Text(text_data, state_size=2)
                
                # Cache the model
                self.models_cache[channel_name] = model
                
                # Save build time
                await self.save_cache_build_time(channel_name, time.time())
                
                self.logger.info(f"Built markov model for {channel_name}")
                return model
                
            except Exception as e:
                self.logger.error(f"Error building model for {channel_name}: {e}")
                return None
    
    async def generate_response(self, channel_name: str, max_length: int = 140) -> Optional[str]:
        """Generate markov response for channel."""
        try:
            # Get or build model
            model = await self.build_channel_model(channel_name)
            if not model:
                return None
            
            # Generate response
            for _ in range(10):  # Try up to 10 times
                try:
                    sentence = model.make_sentence(max_overlap_ratio=0.7, max_overlap_total=15)
                    if sentence and len(sentence) <= max_length:
                        return sentence
                except Exception:
                    continue
                    
            self.logger.warning(f"Could not generate response for {channel_name}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error generating response for {channel_name}: {e}")
            return None
    
    async def add_message_to_training(self, channel_name: str, content: str) -> None:
        """Add new message to training data (invalidates cache if needed)."""
        try:
            # Simple approach: if we have a model cached and enough new messages,
            # mark for rebuild on next generation
            if channel_name in self.models_cache:
                # Could implement incremental updates here in the future
                pass
                
        except Exception as e:
            self.logger.error(f"Error updating training data: {e}")
    
    async def rebuild_all_models(self) -> None:
        """Rebuild all channel models."""
        try:
            channels = await self.database_manager.get_all_channels()
            for channel in channels:
                await self.build_channel_model(channel.channel_name, force_rebuild=True)
                await asyncio.sleep(0.1)  # Small delay to prevent overwhelming
                
        except Exception as e:
            self.logger.error(f"Error rebuilding all models: {e}")