from twitchio.ext import commands
import logging
import markovify
import asyncio
import configparser
import time
import sqlite3
from datetime import datetime
import os
import math

from colorama import init
from datetime import datetime
import threading
from tabulate import tabulate
from utils.logger import Logger
from utils.color_control import ColorManager
from commands.ansv_command import ansv_command
from utils.db_setup import ensure_db_setup
from utils.tts import process_text

config = configparser.ConfigParser()
config.read("settings.conf")

db_file = "messages.db"  # Replace with your actual database file path
ensure_db_setup(db_file)


logger = Logger()
logger.setup_logger()

init()  # init termcolor

# Create a handler for writing to the log file
file_handler = logging.FileHandler("app.log")
file_handler.setLevel(logging.DEBUG)

YELLOW = "\x1b[33m"  # xterm colors. dunno why tbh
RESET = "\x1b[0m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
PURPLE = "\x1b[35m"

# Extract the channels
channels = config["settings"]["channels"].split(",")



class Bot(commands.Bot):
    def __init__(
        self,
        token,
        client_id,
        nick,
        prefix,
        initial_channels,
        db_file,
        rebuild_cache=False,
        enable_tts=False
    ):
        super().__init__(
            token=token,
            client_id=client_id,
            nick=nick,
            prefix=prefix,
            initial_channels=initial_channels,
        )
        
        # Initialize other variables
        print("Initializing Bot class...")
        self.prefix = prefix
        self.my_logger = Logger()
        self.my_logger.setup_logger()
        self.owner = None
        self.channels = initial_channels
        self.trusted_users = []
        self.ignored_users = []
        self.chat_line_count = 0
        self.last_message_time = time.time()
        self.user_colors = {}
        self.channel_colors = {}
        self.logger = logging.getLogger("bot")
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
        handler = logging.FileHandler(filename="app.log", encoding="utf-8", mode="w")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.color_manager = ColorManager()
        self.channel_chat_line_count = {channel: 0 for channel in self.channels}
        self.channel_last_message_time = {
            channel: time.time() for channel in self.channels
        }
        self.channel_settings = {}  # Initialize the channel settings dictionary
        self.db_file = db_file
        self.load_channel_settings()  # Populate channel settings
        self.rebuild_cache = rebuild_cache
        
        # Add cache update threshold setting
        self.cache_update_threshold = 3600 * 24  # 24 hours by default
        self.cache_build_times = {}  # Initialize as empty dict
        
        self.load_text_and_build_model()
        self.first_model_update = True
        
        # Conditional call to update_model_periodically based on rebuild_cache flag
        if self.rebuild_cache:
            self.update_model_periodically()
        
        self.enable_tts = enable_tts
        if self.enable_tts:
            from utils import tts
            tts.initialize_tts()
        
        self._joined_channels = set()
        
        self.start_time = time.time()
        
        self.message_request_check = None
        
        self.message_request_check = self.loop.create_task(self.message_request_checker())
        
    async def send_message_to_channel(self, channel_name, message):
        """Send a message to a specific channel."""
        # Check if channel starts with # (required for Twitch)
        if not channel_name.startswith('#'):
            channel_name = f'#{channel_name}'
            
        # Make sure we're in the channel
        if channel_name not in self._joined_channels:
            print(f"Joining channel {channel_name} before sending message...")
            await self.join_channel(channel_name)
            
        # Send the message
        channel = self.get_channel(channel_name.lstrip('#'))  # TwitchIO gets channels without #
        if channel:
            await channel.send(message)
            print(f"Message sent to {channel_name}: {message}")
            return True
        else:
            print(f"Failed to find channel {channel_name}")
            return False

    async def join_channel(self, channel_name):
        """Join a channel with proper formatting and error handling."""
        try:
            # Ensure channel has # prefix for our tracking
            if not channel_name.startswith('#'):
                channel_name = f'#{channel_name}'
            
            # TwitchIO join_channels expects channel names with # prefix
            # But it actually needs the channel name without # for some operations
            clean_name = channel_name.lstrip('#')
            
            # Join the channel
            await self.join_channels([clean_name])
            
            # Add to our tracking sets
            self._joined_channels.add(channel_name)
            
            # Make sure it's in self.channels for other parts of the code
            if channel_name not in self.channels:
                self.channels.append(channel_name)
            
            print(f"{GREEN}Successfully joined channel: {channel_name}{RESET}")
            return True
        except Exception as e:
            print(f"{RED}Failed to join channel {channel_name}: {e}{RESET}")
            return False

    def load_channel_settings(self):
        self.channel_settings = {}
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()

        # Load channel-specific settings
        c.execute(
            "SELECT channel_name, trusted_users, ignored_users, time_between_messages, lines_between_messages FROM channel_configs"
        )
        for row in c.fetchall():
            channel, trusted, ignored, time_between, lines_between = row
            self.channel_settings[channel] = {
                "trusted_users": trusted.split(",") if trusted else [],
                "ignored_users": ignored.split(",") if ignored else [],
                "time_between_messages": time_between,
                "lines_between_messages": lines_between,
            }
        conn.close()

    async def check_and_join_channels(self):
        """Join all channels marked for joining in the database."""
        try:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            c.execute("SELECT channel_name FROM channel_configs WHERE join_channel = 1")
            channels_to_join = [row[0] for row in c.fetchall()]
            conn.close()
            
            print(f"Found {len(channels_to_join)} channels to join from database")
            
            for channel in channels_to_join:
                # Make sure channel has # prefix
                channel_name = f"#{channel.lstrip('#')}"
                if channel_name not in self._joined_channels:
                    await self.join_channel(channel_name)
        except Exception as e:
            print(f"Error joining channels: {e}")
    
    async def setup_periodic_channel_check(self, interval=300):  # 5 minutes
        """Set up a periodic task to check for new channels."""
        async def check_periodically():
            while True:
                await asyncio.sleep(interval)
                await self.check_and_join_channels()
        
        # Start the periodic task
        self.loop.create_task(check_periodically())
        print(f"Started periodic channel check (every {interval} seconds)")
    
    def ensure_channel_configs(self):
        """Make sure all channels have config entries in the database with proper defaults."""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        for channel in self.channels:
            # Remove # for database storage
            clean_channel = channel.lstrip('#')
            
            # Check if config exists
            c.execute("SELECT 1 FROM channel_configs WHERE channel_name = ?", (clean_channel,))
            if not c.fetchone():
                print(f"Creating config for channel: {clean_channel}")
                c.execute('''
                    INSERT INTO channel_configs 
                    (channel_name, tts_enabled, voice_enabled, join_channel, owner, 
                     trusted_users, ignored_users, use_general_model, lines_between_messages, time_between_messages)
                    VALUES (?, 0, 1, 1, ?, '', '', 1, 50, 15)
                ''', (clean_channel, clean_channel))
        
        conn.commit()
        conn.close()
        
        # Reload channel settings after updating configs
        self.load_channel_settings()
    
    async def print_channel_status(self):
        """Print a status table showing all channels and their configurations."""
        try:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            
            table_data = []
            c.execute('''
                SELECT channel_name, owner, trusted_users, ignored_users, voice_enabled, tts_enabled, 
                       join_channel, time_between_messages, lines_between_messages, use_general_model
                FROM channel_configs
            ''')
            
            for row in c.fetchall():
                channel, owner, trusted, ignored, voice, tts, join_enabled, time_between, lines_between, use_general = row
                
                # Format owner with color
                owner_display = f"\033[38;5;{self.get_user_color(owner)}m{owner}\033[0m" if owner else "None"
                
                # Format trusted users with colors
                if trusted and trusted.strip():
                    trusted_display = ", ".join(
                        f"\033[38;5;{self.get_user_color(user.strip())}m{user.strip()}\033[0m"
                        for user in trusted.split(",") if user.strip()
                    )
                else:
                    trusted_display = ""
                    
                # Format settings
                voice_status = f"{GREEN}enabled{RESET}" if voice else f"{RED}disabled{RESET}"
                tts_status = f"{GREEN}enabled{RESET}" if tts else f"{RED}disabled{RESET}"
                
                # Check if channel is actually joined
                is_joined = f"#{channel}" in self._joined_channels
                join_status = f"{GREEN}joined{RESET}" if is_joined else f"{RED}not joined{RESET}"
                
                # Format time and lines settings
                time_status = f"{GREEN}{time_between}{RESET}" if time_between > 0 else f"{RED}0{RESET}"
                lines_status = f"{GREEN}{lines_between}{RESET}" if lines_between > 0 else f"{RED}0{RESET}"
                
                # Add to table
                table_data.append([
                    f"\033[38;5;{self.get_channel_color(channel)}m#{channel}\033[0m", 
                    owner_display,
                    trusted_display,
                    voice_status,
                    tts_status,
                    join_status,
                    time_status,
                    lines_status,
                ])
            
            conn.close()
            
            headers = ["Channel", "Owner", "Trusted Users", "Voice", "TTS", "Autojoin", "Time", "Lines"]
            print(tabulate(table_data, headers=headers, tablefmt="pretty"))
        
        except Exception as e:
            print(f"Error printing channel status: {e}")

    def load_text_and_build_model(self, create_individual_caches=False):
        directory = "logs/"
        cache_directory = "cache/"
        if not os.path.exists(cache_directory):
            os.makedirs(cache_directory)
        self.text = ""  # Text for the general model
        self.models = {}  # Dictionary for channel-specific models
        total_lines = 0
        files_data = []  # Initialize files_data list here

        # Load or initialize last cache build times
        self.cache_build_times = self.load_last_cache_build_times()

        line_threshold = 50  # Threshold for individual model creation
        # Connect to the SQLite database to fetch valid channels
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT channel_name FROM channel_configs")
        valid_channels = set(row[0] for row in c.fetchall())

        for filename in os.listdir(directory):
            if filename.endswith(".txt"):
                channel_name, _ = os.path.splitext(filename)
                file_path = os.path.join(directory, filename)
                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        file_text = f.read()
                    line_count = file_text.count('\n')
                    total_lines += line_count
                    self.text += file_text  # Add text to the general model

                    # Check if individual cache should be created
                    if channel_name in valid_channels and line_count >= line_threshold and create_individual_caches:
                        cache_file_path = os.path.join(cache_directory, f"{channel_name}_model.json")
                        cache_status = self.create_channel_model(channel_name, file_text, cache_file_path)
                    else:
                        cache_status = f"{RED}Unchanged{RESET}"

                    files_data.append([
                        channel_name, 
                        f"{line_count:,}", 
                        cache_status, 
                        "General Model" if cache_status == f"{RED}Unchanged{RESET}" else f"{channel_name}_model.json"
                    ])

        # After processing all files, build the general model
        if self.text:
            self.general_model = markovify.Text(self.text)
            general_cache_file_path = os.path.join(cache_directory, "general_markov_model.json")
            last_build_time = self.cache_build_times.get("general_markov_model.json")
            
            if self.rebuild_cache or last_build_time is None:
                self.save_general_model_to_cache(general_cache_file_path)
                general_cache_status = f"{GREEN}Updated{RESET}"
                # Update build time
                self.cache_build_times["general_markov_model.json"] = time.time()
                self.save_cache_build_times()
            else:
                general_cache_status = f"{RED}Unchanged{RESET}"

        conn.close()

        # Add total and general model status to table
        total_label = f"{YELLOW}Total{RESET}"
        files_data.append([total_label, f"{total_lines:,}", general_cache_status, "general_markov_model.json"])

        # Print the table outside the loop, after processing all files
        headers = ["Channel", "Brain Size", "Brain Status", "Brain"]
        print(tabulate(files_data, headers=headers, tablefmt="pretty", numalign="right"))

    def determine_cache_status(self, channel_name, file_text, create_individual_caches, cache_directory):
        cache_file_path = os.path.join(cache_directory, f"{channel_name}_model.json")
        cache_status = "Unchanged"
        cache_file_display = "general_markov_model.json"

        if channel_name in valid_channels and create_individual_caches:
            channel_model = markovify.Text(file_text)
            self.models[channel_name] = channel_model
            # Check if the cache file needs to be updated
            if self.should_update_cache(channel_name):
                with open(cache_file_path, 'w') as cache_file:
                    cache_file.write(channel_model.to_json())
                cache_status = "Updated"
            cache_file_display = f"{channel_name}_model.json"

        return cache_status, cache_file_display

    def cache_individual_model(self, channel_name, model, cache_file_path):
        model_json = model.to_json()
        with open(cache_file_path, "w") as f:
            f.write(model_json)

    def create_channel_model(self, channel_name, file_text, cache_file_path):
        """Create a model for a specific channel and save it to the cache."""
        try:
            channel_model = markovify.Text(file_text)
            self.models[channel_name] = channel_model
            
            # Check if we should update cache
            last_build_time = self.cache_build_times.get(channel_name)
            if self.rebuild_cache or last_build_time is None:
                with open(cache_file_path, 'w') as cache_file:
                    cache_file.write(channel_model.to_json())
            
            # Update build time
            self.cache_build_times[channel_name] = time.time()
            self.save_cache_build_times()
            return f"{GREEN}Updated{RESET}"
        except Exception as e:
            print(f"Error creating model for {channel_name}: {e}")
            return f"{RED}Error{RESET}"

    def save_general_model_to_cache(self, cache_file_path):
        """Save the general model to the cache."""
        try:
            with open(cache_file_path, 'w') as cache_file:
                cache_file.write(self.general_model.to_json())
            return True
        except Exception as e:
            print(f"Error saving general model to cache: {e}")
            return False


    def load_model_from_cache(self, channel_name):
        cache_file_path = os.path.join("cache", f"{channel_name}_model.json")
        try:
            with open(cache_file_path, "r") as f:
                model_json = f.read()
                return markovify.Text.from_json(model_json)
        except FileNotFoundError:
            return None


    def generate_message(self, channel_name):
        # Connect to the SQLite database
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        # Check the database to see if this channel should use the general model
        c.execute(
            "SELECT use_general_model FROM channel_configs WHERE channel_name = ?",
            (channel_name,),
        )
        result = c.fetchone()
        conn.close()

        cache_file_used = ""  # Variable to store the name of the cache file used

        # Determine which model to use and add debug information
        if result and result[0]:
            model = self.general_model
            cache_file_used = (
                "general_markov_model.json"  # Name of the general model cache file
            )
        else:
            model = self.load_model_from_cache(channel_name)
            if model:
                cache_file_used = (
                    f"{channel_name}_model.json"  # Specific model cache file
                )
            else:
                model = self.general_model
                cache_file_used = (
                    "general_markov_model.json"  # Fallback to general model cache file
                )

        # Generate a message using the chosen model
        message = model.make_sentence()
        if message:
            # Clean up the message to ensure all characters are printable
            message = "".join(char for char in message if char.isprintable())
            # Save and return the generated message
            self.save_message(message, channel_name)
            return message
        else:
            # If no message was generated, return None and add debug information
            print(
                f"[DEBUG] Failed to generate message for channel: {channel_name} using cache file: {cache_file_used}"
            )
            return None


    def save_message(self, message, channel_name):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute(
            """INSERT INTO messages (message, timestamp, channel, state_size, message_length) 
                    VALUES (?, ?, ?, ?, ?)""",
            (
                message,
                datetime.now(),
                channel_name,
                self.general_model.state_size,
                len(message),
            ),
        )
        conn.commit()
        conn.close()


    def update_model_periodically(self, interval=86400, initial_delay=120):
        #self.my_logger.info("update_model_periodically called")
        def delayed_execution():
            try:
                if self.rebuild_cache:
                    # Rebuild cache including individual caches
                    self.load_text_and_build_model(create_individual_caches=True)
                    #self.my_logger.info("Brain rebuild requested.")
                else:
                    # Check if the general model cache is loaded
                    cache_loaded = self.load_model_from_cache("general_markov_model.json")
                    if not cache_loaded:
                        # Just rebuild the general model
                        self.load_text_and_build_model(create_individual_caches=False)
                        self.my_logger.info("Markov model updated.")
                    else:
                        self.my_logger.info("Markov model loaded from cache.")
            except Exception as e:
                self.my_logger.error(f"Error during model update: {e}")
            finally:
                # Schedule the next execution
                threading.Timer(interval, delayed_execution).start()

        # Start the first execution after the initial delay
        threading.Timer(initial_delay, delayed_execution).start()

    def load_last_cache_build_times(self):
        """Load the last build times of cache files from the database or create a default."""
        try:
            # Check if a cache_build_times file exists
            cache_time_file = os.path.join("cache", "cache_build_times.json")
            if os.path.exists(cache_time_file):
                with open(cache_time_file, 'r') as f:
                    import json
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error loading cache build times: {e}")
            return {}
        
    def save_cache_build_times(self):
        """Save the current cache build times to a file."""
        try:
            # Ensure cache directory exists
            if not os.path.exists("cache"):
                os.makedirs("cache")
            
            cache_time_file = os.path.join("cache", "cache_build_times.json")
            with open(cache_time_file, 'w') as f:
                import json
                json.dump(self.cache_build_times, f)
        except Exception as e:
            print(f"Error saving cache build times: {e}")

    @commands.command(name="ansv")
    async def ansv_wrapper(self, ctx, setting=None, *args):
        """Enhanced command handler for ansv commands"""
        channel_name = ctx.channel.name
        
        # If no setting provided, show help
        if not setting:
            await ctx.send("Usage: !ansv [setting] [value]. Available settings: trusted, voice, tts, lines, time")
            return
        
        # Convert setting to lowercase for easier comparison
        setting = setting.lower()
        
        if setting == "trusted":
            # Handle trusted users
            if not args:
                # No arguments, show current trusted users
                if channel_name in self.channel_settings:
                    trusted_users = self.channel_settings[channel_name].get('trusted_users', [])
                    if trusted_users:
                        await ctx.send(f"Trusted users: {', '.join(trusted_users)}")
                    else:
                        await ctx.send("No trusted users set")
                else:
                    await ctx.send("Channel settings not found")
            else:
                # Add or remove trusted user
                action = args[0].lower()
                if len(args) < 2:
                    await ctx.send("Usage: !ansv trusted add/remove [username]")
                    return
                    
                username = args[1].lower()
                
                if action == "add":
                    success = await self.add_trusted_user(channel_name, username)
                    if success:
                        await ctx.send(f"Added {username} to trusted users")
                    else:
                        await ctx.send(f"Failed to add {username} to trusted users")
                elif action == "remove":
                    # Implement remove trusted user logic here
                    await ctx.send(f"Removed {username} from trusted users")
                else:
                    await ctx.send("Unknown action. Use add or remove")
        else:
            # Call the original ansv_command for other settings
            await ansv_command(self, ctx, setting, args[0] if args else None, enable_tts=self.enable_tts)

    @staticmethod
    def convert_size(size_bytes):
        if size_bytes == 0:
            return "0B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

    def fetch_channel_settings(self, channel_name):
        try:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            c.execute(
                "SELECT lines_between_messages, time_between_messages, tts_enabled, voice_enabled FROM channel_configs WHERE channel_name = ?",
                (channel_name,)
            )
            row = c.fetchone()
            conn.close()
            if row:
                return row[0], row[1], row[2], row[3]  # returns lines_between, time_between, tts_enabled, voice_enabled
            else:
                return 0, 0, False, False  # Default values if channel settings not found
        except sqlite3.Error as e:
            print(f"SQLite error in fetch_channel_settings: {e}")
            return 0, 0, False, False





    async def event_ready(self):
        """Handle the bot ready event."""
        print(f"Bot is ready! | {self.nick}")
        
        # Initialize channel configs
        self.ensure_channel_configs()
        
        # Join all configured channels
        await self.check_and_join_channels()
        
        # Start periodic channel checking
        await self.setup_periodic_channel_check()
        
        # Print status table
        await self.print_channel_status()
        
        # Create PID file
        try:
            with open("bot.pid", "w") as f:
                f.write(str(os.getpid()))
        except Exception as e:
            print(f"Error creating PID file: {e}")
        
        # Create initial heartbeat file and start heartbeat update task
        self.update_heartbeat_file()
        self.loop.create_task(self.heartbeat_task())
        
        # Extra verification for channels of interest
        for channel in self.channels:
            if channel in self._joined_channels:
                print(f"{GREEN}✓ Successfully joined {channel} channel!{RESET}")
            else:
                print(f"{RED}✗ Failed to join {channel} channel - will retry in next periodic check{RESET}")

    def get_user_color(self, username):
        """Get a consistent color number for a user."""
        if not username or username.strip() == "":
            return 7  # Default gray for empty usernames
        
        if username not in self.user_colors:
            # Generate color based on username (simple hash)
            color_num = sum(ord(c) for c in username) % 200 + 20  # Range 20-220 to avoid dark colors
            self.user_colors[username] = color_num
            
        return self.user_colors[username]

    def get_channel_color(self, channel_name):
        """Get a consistent color number for a channel."""
        clean_channel = channel_name.lstrip('#')
        
        if clean_channel not in self.channel_colors:
            # Generate color based on channel name (simple hash)
            color_num = sum(ord(c) for c in clean_channel) % 200 + 20  # Range 20-220
            self.channel_colors[clean_channel] = color_num
            
        return self.channel_colors[clean_channel]

    async def event_command_error(self, ctx, error):
        """Handle command errors."""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore the error, preventing it from propagating further
        else:
            # For all other types of errors, you might want to see what's going on
            self.my_logger.error(f"Error in command: {ctx.command.name}, {error}")


    def log_message(self, message):
        msg = f"{message.author.name}: {message.content}"
        self.my_logger.info(msg)

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore CommandNotFound exceptions
        raise error  # Re-raise other exceptions

    async def send_message(self, message):
        # Iterate over all channels
        for channel_name in self.channels:
            # Get the channel object
            channel = self.get_channel(channel_name)
            if channel:
                # Send the message to the channel
                await channel.send(message)

    # The function event_message is called whenever a new message is received in a channel.
    async def event_message(self, message):
        # Ignore messages from the bot itself or messages with no author.
        if message.author is None or message.author.name.lower() == self.nick.lower():
            return

        channel_name = message.channel.name.lower()
        # Log the message.
        self.my_logger.log_message(channel_name, message.author.name, message.content)

        # Fetch the channel settings and ignored users for the current channel.
        lines_between, time_between, tts_enabled, voice_enabled = self.fetch_channel_settings(channel_name)
        ignored_users = [user.lower() for user in self.channel_settings[channel_name]['ignored_users']] if channel_name in self.channel_settings else []

        # Ignore messages from ignored users.
        if message.author.name.lower() in ignored_users:
            return

        # Handle any commands in the message.
        await self.handle_commands(message)

        # Make sure the channel is in our dictionaries
        if channel_name not in self.channel_chat_line_count:
            self.channel_chat_line_count[channel_name] = 0
        self.channel_chat_line_count[channel_name] += 1
        
        # Calculate the elapsed time since the last message in the current channel.
        elapsed_time = time.time() - self.channel_last_message_time.get(channel_name, 0)

        # Determine if a message should be sent based on the lines_between and time_between settings.
        should_send_message = False
        if lines_between > 0 and self.channel_chat_line_count[channel_name] >= lines_between:
            should_send_message = True
        elif time_between > 0 and elapsed_time >= time_between * 60:
            should_send_message = True

        # If a message should be sent and voice is enabled for the current channel.
        if should_send_message and voice_enabled:
            # Connect to the database.
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            # Check if the general model should be used for the current channel.
            c.execute("SELECT use_general_model FROM channel_configs WHERE channel_name = ?", (channel_name,))
            row = c.fetchone()
            conn.close()

            # Generate a response using the appropriate model.
            if row:
                response = (self.general_model.make_sentence() if row[0] else self.models.get(channel_name, self.general_model).make_sentence())

                # If a response was generated.
                if response:
                    try:
                        # Send the response in the current channel.
                        channel_obj = self.get_channel(channel_name)
                        if channel_obj:
                            await channel_obj.send(response)
                            # Log the response.
                            self.my_logger.log_message(channel_name, self.nick, response)

                            # If TTS is enabled for the current channel.
                            if self.enable_tts and tts_enabled:
                                # Generate TTS audio for the response.
                                tts_output = process_text(response, channel_name, self.db_file)
                                if tts_output:
                                    print(f"TTS audio file generated: {tts_output}")
                                else:
                                    print("Failed to generate TTS audio file.")

                            # Reset the chat line count and last message time for the current channel.
                            self.channel_chat_line_count[channel_name] = 0
                            self.channel_last_message_time[channel_name] = time.time()
                    except Exception as e:
                        # Log any errors that occur when sending the message.
                        self.my_logger.error(f"Failed to send message in {channel_name}: {str(e)}")
                        print(f"Error sending message in {channel_name}: {str(e)}")

    async def stop(self):
        try:
            # Disconnect the bot from all channels
            await self.close()
            
            # Remove status files
            for file in ["bot.pid", "bot_heartbeat.json"]:
                if os.path.exists(file):
                    os.remove(file)
                
            # Perform any additional cleanup tasks, such as closing database connections or saving data
            print("Bot stopped successfully.")
        except Exception as e:
            print(f"Error stopping bot: {e}")

    async def add_trusted_user(self, channel_name, username):
        """Add a user to the trusted users list for a channel."""
        try:
            # Remove # prefix for database storage
            clean_channel = channel_name.lstrip('#')
            
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            
            # Get current trusted users
            c.execute("SELECT trusted_users FROM channel_configs WHERE channel_name = ?", (clean_channel,))
            row = c.fetchone()
            
            if row:
                current_trusted = row[0]
                
                # Add the new user
                trusted_users = []
                if current_trusted and current_trusted.strip():
                    trusted_users = [u.strip() for u in current_trusted.split(',')]
                    
                if username not in trusted_users:
                    trusted_users.append(username)
                    
                # Update the database
                new_trusted = ','.join(trusted_users)
                c.execute("UPDATE channel_configs SET trusted_users = ? WHERE channel_name = ?", 
                         (new_trusted, clean_channel))
                conn.commit()
                
                # Update the channel settings in memory
                if clean_channel in self.channel_settings:
                    self.channel_settings[clean_channel]['trusted_users'] = trusted_users
                    
                print(f"Added {username} to trusted users for {channel_name}")
                return True
            else:
                print(f"Channel {channel_name} not found in database")
                return False
        except Exception as e:
            print(f"Error adding trusted user: {e}")
            return False
        finally:
            conn.close()

    async def heartbeat_task(self):
        """Update the heartbeat file periodically."""
        while True:
            self.update_heartbeat_file()
            await asyncio.sleep(30)  # Update every 30 seconds

    def update_heartbeat_file(self):
        """Write current bot status to heartbeat file."""
        try:
            import json
            
            data = {
                "timestamp": time.time(),
                "nick": self.nick,
                "channels": list(self._joined_channels),
                "uptime": time.time() - self.start_time
            }
            
            with open("bot_heartbeat.json", "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error updating heartbeat file: {e}")

    async def check_message_requests(self):
        """Check for message requests from the web interface"""
        request_file = 'bot_message_request.json'
        
        if os.path.exists(request_file):
            try:
                with open(request_file, 'r') as f:
                    import json
                    data = json.load(f)
                    
                # Process the message request
                if data['action'] == 'send_message':
                    channel = data['channel']
                    message = data['message']
                    
                    # Send the message
                    await self.send_message_to_channel(channel, message)
                    
                    # Log the successful processing
                    self.logger.info(f"{GREEN}Processed message request{RESET}: Sent to {PURPLE}#{channel}{RESET}")
                    
                # Remove the request file after processing
                os.remove(request_file)
            except Exception as e:
                self.logger.error(f"Error processing message request: {e}")
                
                # Rename the file to avoid repeated errors
                try:
                    os.rename(request_file, f"{request_file}.error")
                except:
                    pass

    async def message_request_checker(self):
        """Periodically check for message requests"""
        while True:
            await self.check_message_requests()
            await asyncio.sleep(2)  # Check every 2 seconds

    async def handle_speak_command(self, ctx):
        """Handle the !speak command with improved TTS processing"""
        channel = ctx.channel.name
        
        try:
            # Get the last message from this channel that wasn't a command
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            c.execute("""
                SELECT message FROM messages 
                WHERE channel = ? AND NOT message LIKE '!%' 
                ORDER BY timestamp DESC LIMIT 1
            """, (channel,))
            
            result = c.fetchone()
            conn.close()
            
            if not result:
                await ctx.send("No recent messages to speak.")
                return
            
            message_to_speak = result[0]
            
            # Check channel TTS settings
            if not self.is_tts_enabled(channel):
                await ctx.send("TTS is not enabled for this channel.")
                return
            
            # Only attempt TTS if it's enabled globally
            if not self.enable_tts:
                await ctx.send("TTS is not currently enabled globally.")
                return
            
            # Process the TTS with proper error handling
            success, audio_file = await process_text(channel, message_to_speak)
            
            if success and audio_file:
                # TTS was successful, log and notify
                await ctx.send(f"Speaking the last message. Audio available at: {audio_file}")
                
                # Log the TTS usage in the database for tracking
                try:
                    conn = sqlite3.connect(self.db_file)
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO tts_logs (timestamp, channel, message) 
                        VALUES (?, ?, ?)
                    """, (datetime.now().isoformat(), channel, message_to_speak))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"Error logging TTS usage: {e}")
            else:
                # TTS failed, inform the user
                await ctx.send("Sorry, there was an error generating the TTS audio.")
        except Exception as e:
            print(f"Error in speak command: {e}")
            await ctx.send(f"Error: {str(e)}")





def fetch_users(db_file):
    # This function now fetches trusted and ignored users for a specific channel.
    def fetch_users_for_channel(channel_name):
        trusted_users = []
        ignored_users = []
        try:
            conn = sqlite3.connect(db_file)
            c = conn.cursor()
            c.execute(
                "SELECT trusted_users, ignored_users FROM channel_configs WHERE channel_name = ?",
                (channel_name,),
            )
            row = c.fetchone()
            if row:
                trusted_users = row[0].split(",") if row[0] else []
                ignored_users = row[1].split(",") if row[1] else []
        except Exception as e:
            print(f"Error fetching users for channel {channel_name}: {e}")
        finally:
            conn.close()
        return trusted_users, ignored_users

    return fetch_users_for_channel


def fetch_initial_channels(db_file):
    channels = []
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT channel_name FROM channel_configs WHERE join_channel = 1")
        for row in c.fetchall():
            channels.append(row[0])
    except Exception as e:
        print(f"Error fetching initial channels: {e}")
    finally:
        conn.close()
    return channels

def insert_initial_channels_to_db(db_file, channels):
    """Insert initial channels with default values into the database if not already present,
    setting the owner name to the name of the channel."""
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    

    for channel in channels:
        c.execute('''
            INSERT INTO channel_configs (channel_name, tts_enabled, voice_enabled, join_channel, owner, trusted_users, ignored_users, use_general_model, lines_between_messages, time_between_messages)
            SELECT ?, 0, 0, 1, ?, '', '', 1, 100, 0
            WHERE NOT EXISTS(SELECT 1 FROM channel_configs WHERE channel_name = ?)
        ''', (channel, channel, channel))  
    
    conn.commit()
    conn.close()





def setup_bot(db_file, rebuild_cache=False, enable_tts=False):
    # Read configuration from file
    config = configparser.ConfigParser()
    config.read('settings.conf')
    
    # Get bot credentials
    token = config.get('auth', 'tmi_token')
    client_id = config.get('auth', 'client_id')
    nick = config.get('auth', 'nickname')
    
    # Get channels to join
    # Try different possible config locations for backward compatibility
    try:
        channels_str = config.get('channels', 'channels')
    except (configparser.NoSectionError, configparser.NoOptionError):
        try:
            # Try old format
            channels_str = config.get('settings', 'channels')
        except (configparser.NoSectionError, configparser.NoOptionError):
            print("⚠️ No channels found in config. Using single channel.")
            channels_str = nick  # Default to bot's own channel as fallback
    
    print(f"Found channels string: {channels_str}")
    
    # Strip whitespace and ensure channels start with #
    channels = [f"#{ch.strip()}" if not ch.strip().startswith('#') else ch.strip() 
                for ch in channels_str.split(',')]
    
    print(f"Bot will join these channels: {channels}")
    
    # Initialize bot instance
    bot = Bot(
        token=token,
        client_id=client_id, 
        nick=nick,
        prefix='!',
        initial_channels=channels,
        db_file=db_file,
        rebuild_cache=rebuild_cache,
        enable_tts=enable_tts
    )
    
    return bot
