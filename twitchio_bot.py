import sqlite3
import threading
import time
from datetime import datetime
import asyncio

class TwitchIOBot:
    def __init__(self, ...):
        # existing code
        self.start_heartbeat()

    def start_heartbeat(self):
        """Starts a thread that updates the bot's heartbeat in the database"""
        def heartbeat_thread():
            while True:
                try:
                    conn = sqlite3.connect('messages.db')
                    c = conn.cursor()
                    
                    # Create table if not exists
                    c.execute('''CREATE TABLE IF NOT EXISTS bot_status
                                (key TEXT PRIMARY KEY, value TEXT)''')
                    
                    # Update heartbeat timestamp
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    c.execute("INSERT OR REPLACE INTO bot_status (key, value) VALUES (?, ?)",
                             ('last_heartbeat', now))
                    
                    # Update current channels with better logging
                    connected_channels = [channel.name for channel in self.connected_channels]
                    print(f"Heartbeat: Connected to {len(connected_channels)} channels: {connected_channels}")
                    c.execute("INSERT OR REPLACE INTO bot_status (key, value) VALUES (?, ?)",
                             ('connected_channels', ','.join(connected_channels)))
                    
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"Error in heartbeat: {str(e)}")
                
                # Sleep for 30 seconds
                time.sleep(30)
        
        # Start heartbeat in a daemon thread
        thread = threading.Thread(target=heartbeat_thread, daemon=True)
        thread.start() 

    async def check_commands(self):
        """Check for commands in the database"""
        try:
            conn = sqlite3.connect('messages.db')
            c = conn.cursor()
            
            # Create command table if it doesn't exist (as a fallback)
            c.execute('''CREATE TABLE IF NOT EXISTS bot_commands
                        (id INTEGER PRIMARY KEY, bot_id TEXT, command TEXT, 
                         params TEXT, created_at TEXT, executed INTEGER)''')
            
            # Get unexecuted commands for this bot
            bot_id = '1'  # Default bot ID
            c.execute('''SELECT id, command, params FROM bot_commands 
                        WHERE bot_id = ? AND executed = 0''', (bot_id,))
                        
            commands = c.fetchall()
            
            for cmd_id, command, params in commands:
                try:
                    # Process command
                    if command == 'reconnect':
                        print(f"[Command] Executing reconnect command")
                        # Force reconnect logic
                        await self._reconnect()
                        
                    # Mark as executed
                    c.execute("UPDATE bot_commands SET executed = 1 WHERE id = ?", (cmd_id,))
                    
                except Exception as e:
                    print(f"Error executing command {command}: {str(e)}")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error checking commands: {str(e)}")

    async def _reconnect(self):
        """Force a reconnection to Twitch"""
        try:
            print("Forcing bot to reconnect...")
            # Get channels to rejoin
            channels_to_join = []
            
            try:
                conn = sqlite3.connect('messages.db')
                c = conn.cursor()
                c.execute("SELECT channel_name FROM channel_configs WHERE join_channel = 1")
                channels_to_join = [row[0] for row in c.fetchall()]
                conn.close()
            except Exception as e:
                print(f"Error fetching channels to join: {str(e)}")
                # Fallback to current channels
                channels_to_join = [channel.name for channel in self.connected_channels]
            
            # Close existing connections
            try:
                await self._ws.close()
            except:
                pass
            
            # Reconnect
            try:
                await self.connect()
                print(f"Reconnected to Twitch, joining channels: {channels_to_join}")
                
                # Join channels
                for channel in channels_to_join:
                    try:
                        print(f"Joining channel: {channel}")
                        await self.join_channels([channel])
                    except Exception as e:
                        print(f"Error joining channel {channel}: {str(e)}")
                        
            except Exception as e:
                print(f"Error reconnecting: {str(e)}")
                
        except Exception as e:
            print(f"General error in reconnect: {str(e)}") 

    async def event_ready(self):
        # Existing code...
        
        # Start background task to check commands
        self.loop.create_task(self._check_commands_loop())

    async def _check_commands_loop(self):
        """Background task to check for commands"""
        while True:
            try:
                await self.check_commands()
            except Exception as e:
                print(f"Error in command check loop: {str(e)}")
            
            # Check every 10 seconds
            await asyncio.sleep(10) 