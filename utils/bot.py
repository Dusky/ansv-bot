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
        irc_token,
        client_id,
        nick,
        prefix,
        trusted_users,
        ignored_users,
        owner,
        initial_channels,
        rebuild_cache=False,
        enable_tts=False
    ):
        super().__init__(
            token=irc_token,
            client_id=client_id,
            nick=nick,
            prefix=prefix,
            initial_channels=initial_channels,
        )
        self.prefix = prefix
        self.my_logger = Logger()
        self.my_logger.setup_logger()
        self.owner = owner
        self.channels = initial_channels
        self.trusted_users = trusted_users
        self.ignored_users = ignored_users
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
        self.load_channel_settings()  # Populate channel settings
        self.rebuild_cache = rebuild_cache
        self.db_file = "messages.db"
        self.load_text_and_build_model()
        self.first_model_update = True
        
        # Conditional call to update_model_periodically based on rebuild_cache flag
        if self.rebuild_cache:
            self.update_model_periodically()
        
        self.enable_tts = enable_tts
        if self.enable_tts:
            from utils import tts
            tts.initialize_tts()

    def load_channel_settings(self):
        self.channel_settings = {}
        conn = sqlite3.connect(db_file)
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

    async def check_and_join_new_channels(self):
        """Check the database for new channels to join."""
        try:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            c.execute("SELECT channel_name FROM channel_configs WHERE join_channel = 1")
            all_channels = set(row[0] for row in c.fetchall())
            conn.close()

            new_channels = all_channels - set(self.channels)

            for channel in new_channels:
                joined = await self.try_join_channel(channel)
                if joined:
                    self.channels.append(channel)
                    print(f"Joined new channel: {channel}")

        except Exception as e:
            print(f"Error checking for new channels: {e}")

    def start_periodic_channel_check(self, interval=3600):
        """Start a periodic check for new channels."""
        def channel_check():
            asyncio.run(self.check_and_join_new_channels())
            threading.Timer(interval, channel_check).start()

        threading.Timer(interval, channel_check).start()

    def should_update_cache(self, channel_name, last_build_time):
        # Immediately return True if rebuild_cache is set
        if self.rebuild_cache:
            return True

        current_time = time.time()
        # If last_build_time is None, which means the file was never built, we need to update
        if last_build_time is None:
            return True

        # Update cache if it is older than the threshold
        return current_time - last_build_time > self.cache_update_threshold


    async def try_join_channel(self, channel_name):
        try:
            await self.join_channels([channel_name])
            print(f"{GREEN}Joined channel: {channel_name}{RESET}")  # Add this line
            return True
        except Exception as e:
            print(f"Failed to join channel {channel_name}: {e}")
            return False

    
    def load_last_cache_build_times(self):
        # This method should load the last cache build times from a file or database
        # For demonstration purposes, we'll assume it's stored in a JSON file
        try:
            with open('cache_build_times.json', 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            # If the file does not exist, return an empty dictionary
            return {}
        
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
        last_cache_build_times = self.load_last_cache_build_times()

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
                        channel_model = markovify.Text(file_text)
                        self.models[channel_name] = channel_model
                        cache_file_path = os.path.join(cache_directory, f"{channel_name}_model.json")
                        # Always write to cache file
                        with open(cache_file_path, 'w') as cache_file:
                            cache_file.write(channel_model.to_json())
                        cache_status = f"{GREEN}Updated{RESET}"
                    else:
                        cache_status = f"{RED}Unchanged{RESET}"

                    files_data.append([channel_name, f"{line_count:,}", cache_status, cache_file_path if cache_status == f"{GREEN}Updated{RESET}" else "General Model"])

        # After processing all files, build the general model
        if self.text:
            self.general_model = markovify.Text(self.text)
            general_cache_file_path = os.path.join(cache_directory, "general_markov_model.json")
            if self.should_update_cache('general', last_cache_build_times.get("general_markov_model.json")):
                self.save_general_model_to_cache(general_cache_file_path)
                general_cache_status = f"{GREEN}Updated{RESET}"
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


    def save_general_model_to_cache(self, cache_file_path):
        try:
            model_json = self.general_model.to_json()
            with open(cache_file_path, "w") as f:
                f.write(model_json)
        except Exception as e:
            print(f"Failed to save model to cache: {e}")


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




    @commands.command(name="ansv")
    async def ansv_wrapper(self, ctx, setting, new_value=None):
        await ansv_command(self, ctx, setting, new_value,enable_tts=enable_tts)

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





    async def try_join_channel(self, channel_name):
        try:
            await self.join_channels([channel_name])
            return True
        except Exception as e:
            print(f"Failed to join channel {channel_name}: {e}")
            return False

    async def event_ready(self):
        print(f"{GREEN}Bot online!{RESET}")  # Notifying that bot is online
        self.start_periodic_channel_check()
        # Connect to the database
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()

        table_data = []  # List to store table data
        for channel in self.channels:
            join_success = await self.try_join_channel(channel)

            # Retrieve channel config and additional settings from the database
            c.execute(
                "SELECT owner, trusted_users, voice_enabled, tts_enabled, join_channel, time_between_messages, lines_between_messages FROM channel_configs WHERE channel_name = ?",
                (channel,),
            )
            row = c.fetchone()

            if row:
                (
                    owner,
                    trusted_users,
                    voice_enabled,
                    tts_enabled,
                    join_channel,
                    time_between,
                    lines_between,
                ) = row
                colored_owner = f"\033[38;5;{self.get_user_color(owner)}m{owner}\033[0m"

                if trusted_users:
                    colored_trusted_users = ", ".join(
                        f"\033[38;5;{self.get_user_color(user.strip())}m{user.strip()}\033[0m"
                        for user in trusted_users.split(",")
                    )
                else:
                    colored_trusted_users = "None"

                voice_status = (
                    GREEN + "enabled" + RESET
                    if voice_enabled
                    else RED + "disabled" + RESET
                )
                tts_status = (
                    GREEN + "enabled" + RESET
                    if tts_enabled
                    else RED + "disabled" + RESET
                )
                autojoin_status = (
                    GREEN + "enabled" + RESET
                    if join_channel and join_success
                    else RED + "disabled" + RESET
                )

                # Color code time and lines settings
                time_status = (
                    GREEN + str(time_between) + RESET
                    if time_between > 0
                    else RED + str(time_between) + RESET
                )
                lines_status = (
                    GREEN + str(lines_between) + RESET
                    if lines_between > 0
                    else RED + str(lines_between) + RESET
                )

                if not join_success:
                    # Update join_channel status to 0 in database if join failed
                    c.execute(
                        "UPDATE channel_configs SET join_channel = 0 WHERE channel_name = ?",
                        (channel,),
                    )
                    conn.commit()

                # Add channel information to table data
                table_data.append(
                    [
                        f"\033[38;5;{self.get_channel_color(channel)}m{channel}\033[0m",
                        colored_owner,
                        colored_trusted_users,
                        voice_status,
                        tts_status,
                        autojoin_status,
                        time_status,
                        lines_status,
                    ]
                )
            else:
                table_data.append(
                    [
                        f"\033[38;5;1m{channel}\033[0m",
                        "No config found",
                        "",
                        "",
                        "",
                        RED + "disabled" + RESET,
                        RED + "N/A" + RESET,
                        RED + "N/A" + RESET,
                    ]
                )

        conn.close()

        # Print the table
        headers = [
            "Channel",
            "Owner",
            "Trusted Users",
            "Voice",
            "TTS",
            "Autojoin",
            "Time",
            "Lines",
        ]
        print(tabulate(table_data, headers=headers, tablefmt="pretty"))

    def get_channel_color(self, channel_name):
        """Assign a random xterm color index to a channel."""
        return self.color_manager.get_channel_color(channel_name)

    def get_user_color(self, username):
        """Assign a random xterm color index to a user."""
        return self.color_manager.get_user_color(username)

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

    @commands.command(name="ansv")
    async def ansv_wrapper(self, ctx, setting, new_value=None):
        await ansv_command(self, ctx, setting, new_value)

    async def event_message(self, message):
        if message.author is None or message.author.name.lower() == self.nick.lower():
            return

        channel_name = message.channel.name.lower()
        self.my_logger.log_message(channel_name, message.author.name, message.content)

        lines_between, time_between, tts_enabled, voice_enabled = self.fetch_channel_settings(channel_name)
        ignored_users = [user.lower() for user in self.channel_settings[channel_name]['ignored_users']] if channel_name in self.channel_settings else []

        if message.author.name.lower() in ignored_users:
            return  # Ignore messages from ignored users

        await self.handle_commands(message)

        self.channel_chat_line_count[channel_name] += 1
        elapsed_time = time.time() - self.channel_last_message_time.get(channel_name, 0)

        should_send_message = False
        if lines_between > 0 and self.channel_chat_line_count[channel_name] >= lines_between:
            should_send_message = True
        elif time_between > 0 and elapsed_time >= time_between * 60:
            should_send_message = True

        if should_send_message and voice_enabled:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            c.execute("SELECT use_general_model FROM channel_configs WHERE channel_name = ?", (channel_name,))
            row = c.fetchone()
            conn.close()

            if row:
                response = (self.general_model.make_sentence() if row[0] else self.models.get(channel_name, self.general_model).make_sentence())

                if response:
                    try:
                        channel_obj = self.get_channel(channel_name)
                        if channel_obj:
                            await channel_obj.send(response)
                            self.my_logger.log_message(channel_name, self.nick, response)

                            if self.enable_tts and tts_enabled:
                                tts_output = process_text(response, channel_name, self.db_file)
                                if tts_output:
                                    print(f"TTS audio file generated: {tts_output}")
                                else:
                                    print("Failed to generate TTS audio file.")

                            self.channel_chat_line_count[channel_name] = 0
                            self.channel_last_message_time[channel_name] = time.time()
                    except Exception as e:
                        self.my_logger.error(f"Failed to send message in {channel_name}: {str(e)}")
                        print(f"Error sending message in {channel_name}: {str(e)}")


    async def stop(self):
        try:
            # Disconnect the bot from all channels
            await self.close()
            # Perform any additional cleanup tasks, such as closing database connections or saving data
            print("Bot stopped successfully.")
        except Exception as e:
            print(f"Error stopping bot: {e}")



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





def setup_bot(db_file, rebuild_cache, enable_tts=False):
    logger = Logger()
    logger.setup_logger()

    # Fetch all channels to join
    initial_channels = fetch_initial_channels(db_file)

    config = configparser.ConfigParser()
    config.read("settings.conf")

    bot = Bot(
        irc_token=config.get("auth", "tmi_token"),
        client_id=config.get("auth", "client_id"),
        nick=config.get("auth", "nickname"),
        prefix=config.get("settings", "command_prefix"),
        trusted_users=[],  # This can be managed within the bot
        ignored_users=[],
        owner=config.get("auth", "owner"),
        initial_channels=initial_channels,
        rebuild_cache=rebuild_cache,
        enable_tts=enable_tts
    )

    bot.db_file = db_file
    insert_initial_channels_to_db(db_file, channels)
    return bot