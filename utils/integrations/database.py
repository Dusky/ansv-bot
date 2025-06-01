"""
Centralized database operations for bot functionality.
"""

import sqlite3
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from contextlib import asynccontextmanager
from dataclasses import dataclass

# Conditional import for aiosqlite with fallback
try:
    import aiosqlite
    AIOSQLITE_AVAILABLE = True
except ImportError:
    AIOSQLITE_AVAILABLE = False
    aiosqlite = None
    logging.warning("aiosqlite not available - database operations will use sync fallback")


@dataclass
class ChannelConfig:
    """Channel configuration data."""
    channel_name: str
    join_channel: bool = True
    tts_enabled: bool = False
    voice_enabled: bool = False
    voice_preset: Optional[str] = None
    bark_model: Optional[str] = None
    lines_between_messages: int = 100
    time_between_messages: int = 0
    use_general_model: bool = False
    currently_connected: bool = False
    markov_enabled: bool = True
    markov_response_threshold: int = 50


@dataclass
class MessageData:
    """Message data for database storage."""
    channel_name: str
    username: str
    content: str
    timestamp: datetime
    message_id: Optional[str] = None


class DatabaseManager:
    """Centralized database operations with async support."""
    
    def __init__(self, db_file: str):
        self.db_file = db_file
        self._connection_pool = {}
        self._lock = asyncio.Lock()
        self._fallback_mode = not AIOSQLITE_AVAILABLE
        
        if self._fallback_mode:
            logging.warning("DatabaseManager running in sync fallback mode - install aiosqlite for better performance")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get an async database connection with proper cleanup."""
        conn = None
        try:
            conn = await aiosqlite.connect(self.db_file)
            conn.row_factory = aiosqlite.Row
            yield conn
        except Exception as e:
            logging.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                await conn.close()
    
    async def execute_query(self, query: str, params: Tuple = ()) -> aiosqlite.Cursor:
        """Execute a query and return the cursor."""
        async with self.get_connection() as conn:
            try:
                cursor = await conn.execute(query, params)
                await conn.commit()
                return cursor
            except Exception as e:
                logging.error(f"Database query error: {query} with params {params}: {e}")
                raise
    
    async def fetch_one(self, query: str, params: Tuple = ()) -> Optional[aiosqlite.Row]:
        """Execute a query and fetch one result."""
        async with self.get_connection() as conn:
            try:
                cursor = await conn.execute(query, params)
                result = await cursor.fetchone()
                return result
            except Exception as e:
                logging.error(f"Database fetch_one error: {query}: {e}")
                raise
    
    async def fetch_all(self, query: str, params: Tuple = ()) -> List[aiosqlite.Row]:
        """Execute a query and fetch all results."""
        async with self.get_connection() as conn:
            try:
                cursor = await conn.execute(query, params)
                results = await cursor.fetchall()
                return results
            except Exception as e:
                logging.error(f"Database fetch_all error: {query}: {e}")
                raise
    
    # Channel Configuration Operations
    async def get_channel_config(self, channel_name: str) -> Optional[ChannelConfig]:
        """Get channel configuration from database."""
        query = "SELECT * FROM channel_configs WHERE channel_name = ?"
        row = await self.fetch_one(query, (channel_name,))
        
        if row:
            return ChannelConfig(
                channel_name=row['channel_name'],
                join_channel=bool(row['join_channel']),
                tts_enabled=bool(row['tts_enabled']),
                voice_enabled=bool(row['voice_enabled']),
                voice_preset=row['voice_preset'],
                bark_model=row['bark_model'],
                lines_between_messages=row['lines_between_messages'] or 100,
                time_between_messages=row['time_between_messages'] or 0,
                use_general_model=bool(row['use_general_model']),
                currently_connected=bool(row['currently_connected']),
                markov_enabled=bool(row['markov_enabled'] if 'markov_enabled' in row.keys() else True),
                markov_response_threshold=row['markov_response_threshold'] if 'markov_response_threshold' in row.keys() else 50
            )
        return None
    
    async def save_channel_config(self, config: ChannelConfig) -> None:
        """Save channel configuration to database."""
        query = """
        INSERT OR REPLACE INTO channel_configs 
        (channel_name, join_channel, tts_enabled, voice_enabled, voice_preset, 
         bark_model, lines_between_messages, time_between_messages, use_general_model, 
         currently_connected, markov_enabled, markov_response_threshold)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            config.channel_name,
            config.join_channel,
            config.tts_enabled,
            config.voice_enabled,
            config.voice_preset,
            config.bark_model,
            config.lines_between_messages,
            config.time_between_messages,
            config.use_general_model,
            config.currently_connected,
            config.markov_enabled,
            config.markov_response_threshold
        )
        await self.execute_query(query, params)
    
    async def ensure_channel_configs(self, channels: List[str]) -> None:
        """Ensure all channels have configuration entries."""
        for channel in channels:
            existing = await self.get_channel_config(channel)
            if not existing:
                config = ChannelConfig(channel_name=channel)
                await self.save_channel_config(config)
    
    async def update_channel_connection_status(self, channel_name: str, connected: bool) -> None:
        """Update channel connection status."""
        query = "UPDATE channel_configs SET currently_connected = ? WHERE channel_name = ?"
        await self.execute_query(query, (connected, channel_name))
    
    async def get_channels_to_join(self) -> List[str]:
        """Get list of channels that should be joined."""
        query = "SELECT channel_name FROM channel_configs WHERE join_channel = 1"
        rows = await self.fetch_all(query)
        return [row['channel_name'] for row in rows]
    
    # Message Operations
    async def save_message(self, message_data: MessageData) -> None:
        """Save a message to the database."""
        query = """
        INSERT INTO messages (channel, author_name, message, timestamp)
        VALUES (?, ?, ?, ?)
        """
        params = (
            message_data.channel_name,
            message_data.username,
            message_data.content,
            message_data.timestamp.isoformat()
        )
        await self.execute_query(query, params)
    
    async def get_channel_message_count(self, channel_name: str) -> int:
        """Get total message count for a channel."""
        query = "SELECT COUNT(*) as count FROM messages WHERE channel = ?"
        row = await self.fetch_one(query, (channel_name,))
        return row['count'] if row else 0
    
    async def get_recent_messages(self, channel_name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent messages for a channel."""
        query = """
        SELECT author_name, message, timestamp FROM messages 
        WHERE channel = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
        """
        rows = await self.fetch_all(query, (channel_name, limit))
        return [dict(row) for row in rows]
    
    # TTS Operations
    async def log_tts_generation(self, channel_name: str, text: str, file_path: str, 
                                voice_preset: str, message_id: Optional[str] = None) -> None:
        """Log TTS generation to database."""
        query = """
        INSERT INTO tts_logs (channel, message, file_path, voice_preset, message_id, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            channel_name,
            text,
            file_path,
            voice_preset,
            message_id,
            datetime.now().isoformat()
        )
        await self.execute_query(query, params)
    
    async def get_tts_history(self, channel_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get TTS history for a channel."""
        query = """
        SELECT message, file_path, voice_preset, timestamp FROM tts_logs
        WHERE channel = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """
        rows = await self.fetch_all(query, (channel_name, limit))
        return [dict(row) for row in rows]
    
    # Bot Status Operations
    async def update_bot_heartbeat(self, status_data: Dict[str, Any]) -> None:
        """Update bot heartbeat status."""
        timestamp = datetime.now().isoformat()
        
        for key, value in status_data.items():
            query = "INSERT OR REPLACE INTO bot_status (key, value, timestamp) VALUES (?, ?, ?)"
            await self.execute_query(query, (key, str(value), timestamp))
    
    async def get_bot_status(self, key: str) -> Optional[str]:
        """Get bot status value by key."""
        query = "SELECT value FROM bot_status WHERE key = ?"
        row = await self.fetch_one(query, (key,))
        return row['value'] if row else None
    
    # User Management Operations
    async def is_user_trusted(self, channel_name: str, username: str) -> bool:
        """Check if user is trusted in a channel."""
        query = """
        SELECT COUNT(*) as count FROM trusted_users 
        WHERE channel_name = ? AND username = ?
        """
        row = await self.fetch_one(query, (channel_name, username))
        return row['count'] > 0 if row else False
    
    async def add_trusted_user(self, channel_name: str, username: str) -> None:
        """Add a trusted user for a channel."""
        query = "INSERT OR IGNORE INTO trusted_users (channel_name, username) VALUES (?, ?)"
        await self.execute_query(query, (channel_name, username))
    
    async def remove_trusted_user(self, channel_name: str, username: str) -> None:
        """Remove a trusted user from a channel."""
        query = "DELETE FROM trusted_users WHERE channel_name = ? AND username = ?"
        await self.execute_query(query, (channel_name, username))
    
    async def get_trusted_users(self, channel_name: str) -> List[str]:
        """Get list of trusted users for a channel."""
        query = "SELECT username FROM trusted_users WHERE channel_name = ?"
        rows = await self.fetch_all(query, (channel_name,))
        return [row['username'] for row in rows]
    
    # Cleanup and Maintenance
    async def cleanup_old_messages(self, days: int = 30) -> int:
        """Clean up messages older than specified days."""
        query = """
        DELETE FROM messages 
        WHERE timestamp < datetime('now', '-' || ? || ' days')
        """
        cursor = await self.execute_query(query, (str(days),))
        return cursor.rowcount
    
    async def vacuum_database(self) -> None:
        """Vacuum the database to reclaim space."""
        async with self.get_connection() as conn:
            await conn.execute("VACUUM")
    
    # Cache Management Operations
    async def get_cache_build_times(self) -> Dict[str, float]:
        """Get cache build times from database."""
        query = "SELECT channel_name, build_time FROM cache_build_times"
        rows = await self.fetch_all(query)
        return {row['channel_name']: float(row['build_time']) for row in rows}
    
    async def save_cache_build_time(self, channel_name: str, build_time: float) -> None:
        """Save cache build time to database."""
        query = "INSERT OR REPLACE INTO cache_build_times (channel_name, build_time) VALUES (?, ?)"
        await self.execute_query(query, (channel_name, build_time))
    
    # Message Operations for Markov Processing
    async def store_message(self, channel_name: str, author: str, content: str, timestamp: datetime) -> None:
        """Store a message in the database."""
        message_data = MessageData(
            channel_name=channel_name,
            username=author,
            content=content,
            timestamp=timestamp
        )
        await self.save_message(message_data)
    
    async def get_channel_messages(self, channel_name: str, limit: int = 1000) -> List[MessageData]:
        """Get messages for markov model building."""
        query = """
        SELECT channel, author_name, message, timestamp FROM messages 
        WHERE channel = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
        """
        rows = await self.fetch_all(query, (channel_name, limit))
        
        messages = []
        for row in rows:
            messages.append(MessageData(
                channel_name=row['channel'],
                username=row['author_name'],
                content=row['message'],
                timestamp=datetime.fromisoformat(row['timestamp'])
            ))
        return messages
    
    async def get_all_channels(self) -> List[ChannelConfig]:
        """Get all channel configurations."""
        query = "SELECT * FROM channel_configs"
        rows = await self.fetch_all(query)
        
        channels = []
        for row in rows:
            channels.append(ChannelConfig(
                channel_name=row['channel_name'],
                join_channel=bool(row['join_channel']),
                tts_enabled=bool(row['tts_enabled']),
                voice_enabled=bool(row['voice_enabled']),
                voice_preset=row['voice_preset'],
                bark_model=row['bark_model'],
                lines_between_messages=row['lines_between_messages'] or 100,
                time_between_messages=row['time_between_messages'] or 0,
                use_general_model=bool(row['use_general_model']),
                currently_connected=bool(row['currently_connected']),
                markov_enabled=bool(row['markov_enabled'] if 'markov_enabled' in row.keys() else True),
                markov_response_threshold=row['markov_response_threshold'] if 'markov_response_threshold' in row.keys() else 50
            ))
        return channels
    
    # Initialization and Cleanup
    async def initialize(self) -> None:
        """Initialize database connections and ensure schema."""
        try:
            # Test connection
            await self.health_check()
            logging.info("Database manager initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize database manager: {e}")
            raise
    
    async def close(self) -> None:
        """Close database connections."""
        # Connections are auto-closed in context managers
        # This method is for future connection pooling
        logging.info("Database manager connections closed")
    
    # Health Check
    async def health_check(self) -> bool:
        """Perform a health check on the database."""
        try:
            await self.fetch_one("SELECT 1")
            return True
        except Exception as e:
            logging.error(f"Database health check failed: {e}")
            return False


# Legacy synchronous wrapper for backward compatibility
class SyncDatabaseManager:
    """Synchronous wrapper for DatabaseManager for legacy code."""
    
    def __init__(self, db_file: str):
        self.db_file = db_file
    
    def _run_async(self, coro):
        """Run async function in new event loop if needed."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, we can't use run_until_complete
                # This is a limitation that should be addressed in the calling code
                raise RuntimeError("Cannot run sync database operation from async context")
            return loop.run_until_complete(coro)
        except RuntimeError:
            # Create new event loop for sync operations
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
    
    def get_channel_config(self, channel_name: str) -> Optional[ChannelConfig]:
        """Synchronous version of get_channel_config."""
        async_db = DatabaseManager(self.db_file)
        return self._run_async(async_db.get_channel_config(channel_name))
    
    def save_message(self, message_data: MessageData) -> None:
        """Synchronous version of save_message."""
        async_db = DatabaseManager(self.db_file)
        return self._run_async(async_db.save_message(message_data))