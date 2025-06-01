"""
Command router and processor for bot commands.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass

from ..integrations.database import DatabaseManager
from ..coordination.state_manager import StateManager
from ..integrations.tts_controller import TTSController


@dataclass
class CommandContext:
    """Context information for command execution."""
    channel_name: str
    author: str
    message_content: str
    is_mod: bool = False
    is_owner: bool = False


class CommandRouter:
    """Routes and processes bot commands."""
    
    def __init__(self, database_manager: DatabaseManager, state_manager: StateManager, tts_controller: TTSController):
        self.database_manager = database_manager
        self.state_manager = state_manager
        self.tts_controller = tts_controller
        self.logger = logging.getLogger(__name__)
        self.commands: Dict[str, Callable] = {}
        self._register_commands()
    
    def _register_commands(self) -> None:
        """Register all available commands."""
        self.commands = {
            'speak': self._handle_speak_command,
            'join': self._handle_join_command,
            'leave': self._handle_leave_command,
            'markov': self._handle_markov_command,
            'status': self._handle_status_command,
            'help': self._handle_help_command,
        }
    
    async def process_command(self, ctx: CommandContext, command: str, args: List[str]) -> Optional[str]:
        """Process a bot command and return response."""
        try:
            if command not in self.commands:
                return f"Unknown command: {command}. Type !help for available commands."
            
            # Check permissions for protected commands
            if not await self._check_command_permissions(ctx, command):
                return "You don't have permission to use this command."
            
            # Execute command
            handler = self.commands[command]
            return await handler(ctx, args)
            
        except Exception as e:
            self.logger.error(f"Error processing command {command}: {e}")
            return "An error occurred while processing the command."
    
    async def _check_command_permissions(self, ctx: CommandContext, command: str) -> bool:
        """Check if user has permission to execute command."""
        try:
            # Get channel configuration
            channel_config = await self.database_manager.get_channel_config(ctx.channel_name)
            
            # Owner can always execute commands
            if ctx.is_owner:
                return True
            
            # Check mod-only commands
            mod_only_commands = ['join', 'leave']
            if command in mod_only_commands and not ctx.is_mod:
                return False
            
            # Check if command is enabled for channel
            if channel_config:
                if command == 'speak' and not channel_config.tts_enabled:
                    return False
                if command == 'markov' and not channel_config.markov_enabled:
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking permissions: {e}")
            return False
    
    async def _handle_speak_command(self, ctx: CommandContext, args: List[str]) -> Optional[str]:
        """Handle TTS speak command."""
        if not args:
            return "Usage: !speak <text>"
        
        text = ' '.join(args)
        success = await self.tts_controller.handle_speak_command(ctx.channel_name, text)
        
        if success:
            return f"Speaking: {text[:50]}{'...' if len(text) > 50 else ''}"
        else:
            return "Failed to process TTS request."
    
    async def _handle_join_command(self, ctx: CommandContext, args: List[str]) -> Optional[str]:
        """Handle channel join command."""
        if not args:
            return "Usage: !join <channel_name>"
        
        channel_name = args[0].lower().lstrip('#')
        # This would need to be coordinated with the main bot instance
        # For now, return a placeholder response
        return f"Join request for #{channel_name} received."
    
    async def _handle_leave_command(self, ctx: CommandContext, args: List[str]) -> Optional[str]:
        """Handle channel leave command."""
        # Leave current channel or specified channel
        target_channel = args[0].lower().lstrip('#') if args else ctx.channel_name
        return f"Leave request for #{target_channel} received."
    
    async def _handle_markov_command(self, ctx: CommandContext, args: List[str]) -> Optional[str]:
        """Handle markov generation command."""
        # This would trigger markov generation
        return "Generating markov response..."
    
    async def _handle_status_command(self, ctx: CommandContext, args: List[str]) -> Optional[str]:
        """Handle bot status command."""
        try:
            channel_state = await self.state_manager.get_channel_state(ctx.channel_name)
            if not channel_state:
                return "Channel status unavailable."
            
            return (f"Channel: {ctx.channel_name} | "
                   f"Connected: {channel_state.connected} | "
                   f"Messages: {channel_state.chat_line_count}")
                   
        except Exception as e:
            self.logger.error(f"Error getting status: {e}")
            return "Status unavailable."
    
    async def _handle_help_command(self, ctx: CommandContext, args: List[str]) -> Optional[str]:
        """Handle help command."""
        available_commands = []
        
        for cmd in self.commands.keys():
            if await self._check_command_permissions(ctx, cmd):
                available_commands.append(f"!{cmd}")
        
        return f"Available commands: {', '.join(available_commands)}"