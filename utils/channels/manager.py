"""
Channel management - joining, leaving, and status tracking.
"""

import logging
import asyncio
from typing import List, Set, Optional
from datetime import datetime

from ..integrations.database import DatabaseManager, ChannelConfig
from ..coordination.state_manager import StateManager


class ChannelManager:
    """Handles channel operations and status management."""
    
    def __init__(self, bot_instance, database_manager: DatabaseManager, 
                 state_manager: StateManager):
        self.bot = bot_instance
        self.db = database_manager
        self.state = state_manager
        self._join_lock = asyncio.Lock()
    
    async def join_channel(self, channel_name: str) -> bool:
        """Join a specific channel with error handling and state tracking."""
        async with self._join_lock:
            try:
                # Clean channel name
                clean_channel = channel_name.lstrip('#').lower()
                
                # Check if already connected
                connected_channels = await self.state.get_connected_channels()
                if clean_channel in connected_channels:
                    logging.info(f"Already connected to channel: {clean_channel}")
                    return True
                
                # Attempt to join the channel
                logging.info(f"Attempting to join channel: {clean_channel}")
                await self.bot.join_channels([clean_channel])
                
                # Update state
                await self.state.add_connected_channel(clean_channel)
                await self.db.update_channel_connection_status(clean_channel, True)
                
                # Ensure channel configuration exists
                await self._ensure_channel_config(clean_channel)
                
                logging.info(f"Successfully joined channel: {clean_channel}")
                return True
                
            except Exception as e:
                logging.error(f"Failed to join channel {channel_name}: {e}")
                return False
    
    async def leave_channel(self, channel_name: str) -> bool:
        """Leave a specific channel with state cleanup."""
        async with self._join_lock:
            try:
                # Clean channel name
                clean_channel = channel_name.lstrip('#').lower()
                
                # Check if currently connected
                connected_channels = await self.state.get_connected_channels()
                if clean_channel not in connected_channels:
                    logging.info(f"Not connected to channel: {clean_channel}")
                    return True
                
                # Attempt to leave the channel
                logging.info(f"Attempting to leave channel: {clean_channel}")
                await self.bot.part_channels([clean_channel])
                
                # Update state
                await self.state.remove_connected_channel(clean_channel)
                await self.db.update_channel_connection_status(clean_channel, False)
                
                logging.info(f"Successfully left channel: {clean_channel}")
                return True
                
            except Exception as e:
                logging.error(f"Failed to leave channel {channel_name}: {e}")
                return False
    
    async def check_and_join_channels(self) -> None:
        """Check and join all configured channels."""
        try:
            # Get channels that should be joined from database
            channels_to_join = await self.db.get_channels_to_join()
            
            if not channels_to_join:
                logging.warning("No channels configured to join")
                return
            
            logging.info(f"Checking {len(channels_to_join)} channels to join: {channels_to_join}")
            
            # Get currently connected channels
            connected_channels = await self.state.get_connected_channels()
            
            # Join channels that aren't already connected
            join_tasks = []
            for channel in channels_to_join:
                clean_channel = channel.lstrip('#').lower()
                if clean_channel not in connected_channels:
                    task = asyncio.create_task(self.join_channel(clean_channel))
                    join_tasks.append(task)
                else:
                    logging.info(f"Already connected to {clean_channel}")
            
            # Wait for all join operations to complete
            if join_tasks:
                results = await asyncio.gather(*join_tasks, return_exceptions=True)
                
                # Log results
                successful_joins = sum(1 for result in results if result is True)
                total_attempts = len(join_tasks)
                logging.info(f"Channel join results: {successful_joins}/{total_attempts} successful")
                
                # Log any exceptions
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logging.error(f"Join task {i} failed: {result}")
            
            # Update final connected channels count
            final_connected = await self.state.get_connected_channels()
            logging.info(f"Total connected channels: {len(final_connected)}")
            
        except Exception as e:
            logging.error(f"Error in check_and_join_channels: {e}")
    
    async def get_connected_channels(self) -> Set[str]:
        """Get set of currently connected channels."""
        return await self.state.get_connected_channels()
    
    async def get_channel_list(self) -> List[str]:
        """Get list of all configured channels."""
        try:
            return await self.db.get_channels_to_join()
        except Exception as e:
            logging.error(f"Error getting channel list: {e}")
            return []
    
    async def is_channel_connected(self, channel_name: str) -> bool:
        """Check if a specific channel is connected."""
        clean_channel = channel_name.lstrip('#').lower()
        connected_channels = await self.state.get_connected_channels()
        return clean_channel in connected_channels
    
    async def update_channel_status(self, channel_name: str, connected: bool) -> None:
        """Update the connection status of a channel."""
        clean_channel = channel_name.lstrip('#').lower()
        
        if connected:
            await self.state.add_connected_channel(clean_channel)
        else:
            await self.state.remove_connected_channel(clean_channel)
        
        await self.db.update_channel_connection_status(clean_channel, connected)
        logging.info(f"Updated {clean_channel} status: {'connected' if connected else 'disconnected'}")
    
    async def _ensure_channel_config(self, channel_name: str) -> None:
        """Ensure a channel has a configuration entry."""
        config = await self.db.get_channel_config(channel_name)
        if not config:
            # Create default configuration
            default_config = ChannelConfig(channel_name=channel_name)
            await self.db.save_channel_config(default_config)
            logging.info(f"Created default configuration for channel: {channel_name}")
    
    async def add_channel_to_join_list(self, channel_name: str) -> bool:
        """Add a channel to the join list and attempt to join it."""
        try:
            clean_channel = channel_name.lstrip('#').lower()
            
            # Get or create channel config
            config = await self.db.get_channel_config(clean_channel)
            if not config:
                config = ChannelConfig(channel_name=clean_channel, join_channel=True)
            else:
                config.join_channel = True
            
            # Save configuration
            await self.db.save_channel_config(config)
            
            # Attempt to join the channel
            success = await self.join_channel(clean_channel)
            if success:
                logging.info(f"Added and joined channel: {clean_channel}")
            else:
                logging.warning(f"Added channel {clean_channel} to join list but failed to join")
            
            return success
            
        except Exception as e:
            logging.error(f"Error adding channel {channel_name} to join list: {e}")
            return False
    
    async def remove_channel_from_join_list(self, channel_name: str) -> bool:
        """Remove a channel from the join list and leave it."""
        try:
            clean_channel = channel_name.lstrip('#').lower()
            
            # Update channel config to not join
            config = await self.db.get_channel_config(clean_channel)
            if config:
                config.join_channel = False
                await self.db.save_channel_config(config)
            
            # Leave the channel
            success = await self.leave_channel(clean_channel)
            if success:
                logging.info(f"Removed and left channel: {clean_channel}")
            else:
                logging.warning(f"Removed channel {clean_channel} from join list but failed to leave")
            
            return success
            
        except Exception as e:
            logging.error(f"Error removing channel {channel_name} from join list: {e}")
            return False
    
    async def get_channel_status_summary(self) -> dict:
        """Get a summary of all channel statuses."""
        try:
            all_channels = await self.db.get_channels_to_join()
            connected_channels = await self.state.get_connected_channels()
            
            status_summary = {
                "total_configured": len(all_channels),
                "total_connected": len(connected_channels),
                "channels": {}
            }
            
            for channel in all_channels:
                clean_channel = channel.lstrip('#').lower()
                config = await self.db.get_channel_config(clean_channel)
                
                status_summary["channels"][clean_channel] = {
                    "connected": clean_channel in connected_channels,
                    "should_join": config.join_channel if config else False,
                    "tts_enabled": config.tts_enabled if config else False,
                    "voice_enabled": config.voice_enabled if config else False
                }
            
            return status_summary
            
        except Exception as e:
            logging.error(f"Error getting channel status summary: {e}")
            return {"error": str(e)}
    
    async def reconnect_all_channels(self) -> None:
        """Reconnect to all configured channels."""
        try:
            logging.info("Starting reconnection to all channels")
            
            # Get currently connected channels and disconnect
            connected_channels = await self.state.get_connected_channels()
            for channel in connected_channels.copy():
                await self.leave_channel(channel)
            
            # Wait a moment for disconnections to complete
            await asyncio.sleep(1)
            
            # Rejoin all configured channels
            await self.check_and_join_channels()
            
            logging.info("Channel reconnection completed")
            
        except Exception as e:
            logging.error(f"Error during channel reconnection: {e}")
    
    def cleanup(self) -> None:
        """Cleanup channel manager resources."""
        logging.info("Channel manager cleanup completed")