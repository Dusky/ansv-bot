"""
Database Manager with Connection Pooling and Async Support
Replaces blocking SQLite operations with efficient connection management
"""

import sqlite3
import asyncio
import threading
import queue
import logging
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Dict, Any, Tuple
import time


class DatabaseConnectionPool:
    """Thread-safe SQLite connection pool for improved performance."""
    
    def __init__(self, db_path: str, max_connections: int = 10, timeout: float = 30.0):
        self.db_path = db_path
        self.max_connections = max_connections
        self.timeout = timeout
        self._pool = queue.Queue(maxsize=max_connections)
        self._lock = threading.Lock()
        self._created_connections = 0
        
        # Pre-create some connections
        self._initialize_pool()
        
    def _initialize_pool(self):
        """Pre-create initial connections for better performance."""
        initial_connections = min(3, self.max_connections)
        for _ in range(initial_connections):
            conn = self._create_connection()
            if conn:
                self._pool.put(conn)
                
    def _create_connection(self) -> Optional[sqlite3.Connection]:
        """Create a new database connection with optimized settings."""
        try:
            conn = sqlite3.connect(
                self.db_path,
                timeout=self.timeout,
                check_same_thread=False  # Allow sharing between threads
            )
            
            # Optimize connection settings for performance
            conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for better concurrency
            conn.execute("PRAGMA synchronous=NORMAL")  # Balance between safety and speed
            conn.execute("PRAGMA cache_size=10000")  # Increase cache size
            conn.execute("PRAGMA temp_store=MEMORY")  # Store temp tables in memory
            conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory mapping
            
            # Row factory for easier data access
            conn.row_factory = sqlite3.Row
            
            self._created_connections += 1
            logging.debug(f"Created database connection #{self._created_connections}")
            return conn
            
        except sqlite3.Error as e:
            logging.error(f"Failed to create database connection: {e}")
            return None
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool with automatic cleanup."""
        conn = None
        try:
            # Try to get from pool first
            try:
                conn = self._pool.get_nowait()
            except queue.Empty:
                # Pool empty, create new connection if under limit
                with self._lock:
                    if self._created_connections < self.max_connections:
                        conn = self._create_connection()
                    else:
                        # Wait for available connection
                        conn = self._pool.get(timeout=self.timeout)
            
            if conn is None:
                raise sqlite3.Error("Unable to obtain database connection")
                
            # Test connection
            try:
                conn.execute("SELECT 1").fetchone()
            except sqlite3.Error:
                # Connection is stale, create new one
                conn.close()
                conn = self._create_connection()
                
            yield conn
            
        except Exception as e:
            logging.error(f"Database connection error: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise
        finally:
            # Return connection to pool
            if conn:
                try:
                    conn.commit()  # Ensure any pending transactions are committed
                    self._pool.put_nowait(conn)
                except queue.Full:
                    # Pool is full, close this connection
                    conn.close()
                    with self._lock:
                        self._created_connections -= 1
                except sqlite3.Error:
                    # Connection is broken, close it
                    conn.close()
                    with self._lock:
                        self._created_connections -= 1

    def close_all(self):
        """Close all connections in the pool."""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
                with self._lock:
                    self._created_connections -= 1
            except queue.Empty:
                break
            except Exception as e:
                logging.error(f"Error closing connection: {e}")


class AsyncDatabaseManager:
    """Async database manager for non-blocking database operations."""
    
    def __init__(self, db_path: str, max_workers: int = 4):
        self.db_path = db_path
        self.pool = DatabaseConnectionPool(db_path)
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="db_worker")
        
    async def execute_query(self, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """Execute a SELECT query asynchronously."""
        def _execute():
            with self.pool.get_connection() as conn:
                cursor = conn.execute(query, params)
                # Convert Row objects to dictionaries
                return [dict(row) for row in cursor.fetchall()]
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, _execute)
    
    async def execute_update(self, query: str, params: Tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE query asynchronously."""
        def _execute():
            with self.pool.get_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                return cursor.rowcount
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, _execute)
    
    async def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """Execute multiple queries asynchronously."""
        def _execute():
            with self.pool.get_connection() as conn:
                cursor = conn.executemany(query, params_list)
                conn.commit()
                return cursor.rowcount
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, _execute)
    
    async def execute_transaction(self, queries: List[Tuple[str, Tuple]]) -> bool:
        """Execute multiple queries in a single transaction."""
        def _execute():
            with self.pool.get_connection() as conn:
                try:
                    conn.execute("BEGIN TRANSACTION")
                    for query, params in queries:
                        conn.execute(query, params)
                    conn.commit()
                    return True
                except Exception as e:
                    conn.rollback()
                    raise e
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, _execute)
    
    async def get_bot_status(self) -> Dict[str, Any]:
        """Optimized bot status query with caching."""
        query = """
        SELECT bs.key, bs.value, bs.timestamp,
               (SELECT COUNT(*) FROM messages WHERE timestamp > datetime('now', '-1 hour')) as recent_messages,
               (SELECT COUNT(DISTINCT channel) FROM channel_configs WHERE join_channel = 1) as active_channels
        FROM bot_status bs
        WHERE bs.key IN ('heartbeat', 'uptime', 'status')
        """
        
        rows = await self.execute_query(query)
        
        # Convert to more usable format
        status = {}
        for row in rows:
            if row['key'] in ['heartbeat', 'uptime', 'status']:
                status[row['key']] = row['value']
            elif row['key'] == 'heartbeat':
                status['recent_messages'] = row['recent_messages']
                status['active_channels'] = row['active_channels']
        
        return status
    
    async def get_channel_stats(self, channel_name: str) -> Dict[str, Any]:
        """Get comprehensive channel statistics efficiently."""
        queries = [
            # Basic channel config
            ("SELECT * FROM channel_configs WHERE channel_name = ?", (channel_name,)),
            
            # Message count and recent activity
            ("""SELECT 
                COUNT(*) as total_messages,
                COUNT(CASE WHEN timestamp > datetime('now', '-24 hours') THEN 1 END) as messages_today,
                COUNT(CASE WHEN is_bot_response = 1 THEN 1 END) as bot_responses,
                MAX(timestamp) as last_activity
                FROM messages WHERE channel = ?""", (channel_name,)),
            
            # TTS statistics
            ("""SELECT COUNT(*) as tts_count, MAX(timestamp) as last_tts
                FROM tts_logs WHERE channel = ?""", (channel_name,))
        ]
        
        results = {}
        for i, (query, params) in enumerate(queries):
            data = await self.execute_query(query, params)
            if i == 0:
                results['config'] = data[0] if data else {}
            elif i == 1:
                results['messages'] = data[0] if data else {}
            elif i == 2:
                results['tts'] = data[0] if data else {}
        
        return results
    
    def close(self):
        """Clean shutdown of database manager."""
        self.executor.shutdown(wait=True)
        self.pool.close_all()


# Global database manager instance
_db_manager: Optional[AsyncDatabaseManager] = None


def get_db_manager(db_path: str = "messages.db") -> AsyncDatabaseManager:
    """Get or create the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = AsyncDatabaseManager(db_path)
    return _db_manager


def close_db_manager():
    """Close the global database manager."""
    global _db_manager
    if _db_manager:
        _db_manager.close()
        _db_manager = None


# Synchronous helper functions for backward compatibility
def execute_query_sync(query: str, params: Tuple = (), db_path: str = "messages.db") -> List[Dict[str, Any]]:
    """Synchronous query execution for compatibility."""
    with DatabaseConnectionPool(db_path).get_connection() as conn:
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def execute_update_sync(query: str, params: Tuple = (), db_path: str = "messages.db") -> int:
    """Synchronous update execution for compatibility."""
    with DatabaseConnectionPool(db_path).get_connection() as conn:
        cursor = conn.execute(query, params)
        conn.commit()
        return cursor.rowcount