"""
Shared state management for bot components.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ChannelState:
    """State information for a single channel."""
    name: str
    connected: bool = False
    chat_line_count: int = 0
    last_message_time: Optional[datetime] = None
    tts_enabled: bool = False
    voice_enabled: bool = False
    use_general_model: bool = False


@dataclass
class BotState:
    """Global bot state."""
    channels: Dict[str, ChannelState] = field(default_factory=dict)
    connected_channels: Set[str] = field(default_factory=set)
    models_loaded: bool = False
    tts_enabled: bool = False
    startup_complete: bool = False


class StateManager:
    """Manages shared state across bot components."""
    
    def __init__(self):
        self.state = BotState()
        self._lock = asyncio.Lock()
        self._observers = {}
    
    async def get_channel_state(self, channel_name: str) -> ChannelState:
        """Get state for a specific channel."""
        async with self._lock:
            if channel_name not in self.state.channels:
                self.state.channels[channel_name] = ChannelState(name=channel_name)
            return self.state.channels[channel_name]
    
    async def update_channel_state(self, channel_name: str, **kwargs) -> None:
        """Update channel state with new values."""
        async with self._lock:
            if channel_name not in self.state.channels:
                self.state.channels[channel_name] = ChannelState(name=channel_name)
            
            channel_state = self.state.channels[channel_name]
            for key, value in kwargs.items():
                if hasattr(channel_state, key):
                    setattr(channel_state, key, value)
                else:
                    logging.warning(f"Unknown channel state attribute: {key}")
            
            # Notify observers
            await self._notify_observers('channel_state_changed', channel_name, channel_state)
    
    async def add_connected_channel(self, channel_name: str) -> None:
        """Mark a channel as connected."""
        async with self._lock:
            self.state.connected_channels.add(channel_name)
            await self.update_channel_state(channel_name, connected=True)
    
    async def remove_connected_channel(self, channel_name: str) -> None:
        """Mark a channel as disconnected."""
        async with self._lock:
            self.state.connected_channels.discard(channel_name)
            await self.update_channel_state(channel_name, connected=False)
    
    async def get_connected_channels(self) -> Set[str]:
        """Get set of currently connected channels."""
        async with self._lock:
            return self.state.connected_channels.copy()
    
    async def update_bot_state(self, **kwargs) -> None:
        """Update global bot state."""
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.state, key):
                    setattr(self.state, key, value)
                else:
                    logging.warning(f"Unknown bot state attribute: {key}")
            
            # Notify observers
            await self._notify_observers('bot_state_changed', self.state)
    
    async def get_bot_state(self) -> BotState:
        """Get current bot state."""
        async with self._lock:
            return self.state
    
    def add_observer(self, event_type: str, callback) -> None:
        """Add an observer for state changes."""
        if event_type not in self._observers:
            self._observers[event_type] = []
        self._observers[event_type].append(callback)
    
    def remove_observer(self, event_type: str, callback) -> None:
        """Remove an observer for state changes."""
        if event_type in self._observers:
            try:
                self._observers[event_type].remove(callback)
            except ValueError:
                pass
    
    async def _notify_observers(self, event_type: str, *args) -> None:
        """Notify all observers of a state change."""
        if event_type in self._observers:
            for callback in self._observers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(*args)
                    else:
                        callback(*args)
                except Exception as e:
                    logging.error(f"Error in state observer {callback}: {e}")
    
    async def increment_channel_line_count(self, channel_name: str) -> int:
        """Increment and return the line count for a channel."""
        async with self._lock:
            if channel_name not in self.state.channels:
                self.state.channels[channel_name] = ChannelState(name=channel_name)
            channel_state = self.state.channels[channel_name]
            channel_state.chat_line_count += 1
            return channel_state.chat_line_count
    
    async def reset_channel_line_count(self, channel_name: str) -> None:
        """Reset the line count for a channel."""
        await self.update_channel_state(channel_name, chat_line_count=0)
    
    async def update_last_message_time(self, channel_name: str) -> None:
        """Update the last message time for a channel."""
        await self.update_channel_state(channel_name, last_message_time=datetime.now())
    
    async def update_channel_message_count(self, channel_name: str) -> None:
        """Increment message count for channel."""
        await self.increment_channel_line_count(channel_name)
    
    async def reset_channel_message_count(self, channel_name: str) -> None:
        """Reset message count for channel."""
        await self.reset_channel_line_count(channel_name)
    
    async def set_channel_connected(self, channel_name: str, connected: bool) -> None:
        """Set channel connection status."""
        if connected:
            await self.add_connected_channel(channel_name)
        else:
            await self.remove_connected_channel(channel_name)
    
    async def add_channel(self, channel_name: str) -> None:
        """Add a new channel to state tracking."""
        async with self._lock:
            if channel_name not in self.state.channels:
                self.state.channels[channel_name] = ChannelState(name=channel_name)
    
    async def initialize(self) -> None:
        """Initialize the state manager."""
        logging.info("State manager initialized")
    
    async def get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of current state."""
        async with self._lock:
            return {
                'total_channels': len(self.state.channels),
                'connected_channels': len(self.state.connected_channels),
                'models_loaded': self.state.models_loaded,
                'tts_enabled': self.state.tts_enabled,
                'startup_complete': self.state.startup_complete
            }