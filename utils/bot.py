from twitchio.ext import commands
import logging
import markovify

import configparser
import time
import sqlite3
from datetime import datetime
import os
import argparse
import math
from termcolor import colored
from colorama import init
from datetime import datetime
import threading
from tabulate import tabulate
from utils.logger import Logger
from utils.color_control import ColorManager
from commands.ansv_command import ansv_command
config = configparser.ConfigParser()
config.read('settings.conf')


logger = Logger()
logger.setup_logger()

init() #init termcolor

# Create a handler for writing to the log file
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.DEBUG)

YELLOW = "\x1b[33m" #xterm colors. dunno why tbh
RESET = "\x1b[0m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
PURPLE = "\x1b[35m"

# Extract the channels
channels = config['settings']['channels'].split(',')


def parse_arguments():
    parser = argparse.ArgumentParser(description='Twitch Chat Bot')
    parser.add_argument('--rebuild-cache', action='store_true', help='Rebuild the Markov model cache at startup')
    return parser.parse_args()

class Bot(commands.Bot):
    def __init__(self, irc_token, client_id, nick, prefix, time_between_messages,
                lines_between_messages, trusted_users, owner, ignored_users, initial_channels):

        super().__init__(
            token=irc_token,
            client_id=client_id,
            nick=nick,
            prefix=prefix,
            ignored_users=ignored_users,  # Fix: Move ignored_users argument before prefix argument
            initial_channels=initial_channels,
        
        )
        self.prefix = prefix
        self.time_between_messages = time_between_messages
        self.lines_between_messages = lines_between_messages
        self.my_logger = Logger()  
        self.my_logger.setup_logger() 
        self.owner = owner
        self.channels = initial_channels
        self.trusted_users = trusted_users
        self.chat_line_count = 0
        self.last_message_time = time.time()
        self.ignored_users = ignored_users
        self.user_colors = {}
        self.channel_colors = {}
        self.logger = logging.getLogger('bot')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
        handler = logging.FileHandler(filename='app.log', encoding='utf-8', mode='w')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.color_manager = ColorManager()
        self.channel_chat_line_count = {channel: 0 for channel in self.channels}
        self.channel_last_message_time = {channel: time.time() for channel in self.channels}
        self.db_file = 'messages.db'
        self.ensure_db_setup()
        self.load_text_and_build_model()
        self.first_model_update = True
#        self.update_model_periodically()      
        self.initial_channels = initial_channels
    
    def ensure_db_setup(self):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()

        try:
            # Create the messages and channel_configs tables if they don't exist
            c.execute('''CREATE TABLE IF NOT EXISTS messages (
                            id INTEGER PRIMARY KEY,
                            message TEXT,
                            timestamp TEXT,
                            channel TEXT,
                            state_size INTEGER,
                            message_length INTEGER,
                            tts_processed BOOLEAN
                        )''')
            c.execute('''CREATE TABLE IF NOT EXISTS channel_configs (
                            channel_name TEXT PRIMARY KEY,
                            tts_enabled BOOLEAN NOT NULL,
                            voice_enabled BOOLEAN NOT NULL,
                            join_channel BOOLEAN NOT NULL,
                            owner TEXT,
                            trusted_users TEXT,
                            time_between_messages INTEGER,
                            lines_between_messages INTEGER
                        )''')

            # Read channels and trusted users from settings.conf
            config = configparser.ConfigParser()
            config.read("settings.conf")
            channels = config.get("settings", "channels").split(",")
            trusted_users = ",".join(config.get("settings", "trusted_users").split(","))

            # Initialize counters for imported and skipped channels
            imported_channels_count = 0
            skipped_channels_count = 0

            # Check and insert channels into channel_configs
            for channel in channels:
                if channel:  # Check that channel is not empty
                    c.execute("SELECT COUNT(*) FROM channel_configs WHERE channel_name = ?", (channel,))
                    if c.fetchone()[0] == 0:
                        c.execute("INSERT INTO channel_configs (channel_name, tts_enabled, voice_enabled, join_channel, owner, trusted_users) VALUES (?, ?, ?, ?, ?, ?)",
                                (channel, False, False, True, channel, trusted_users))
                        imported_channels_count += 1
                    else:
                        skipped_channels_count += 1
                else:
                    self.my_logger.log_warning("Skipped adding an empty channel name to the database.")

            conn.commit()

            # Query the number of rows in messages and channels in channel_configs
            c.execute('SELECT COUNT(*) FROM messages')
            messages_count = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM channel_configs')
            channels_count = c.fetchone()[0]

            # Log database status and counts of imported and skipped channels
            self.my_logger.log_info(f"{YELLOW}Database loaded. Messages: {messages_count}, Channels: {channels_count}. {imported_channels_count} channels imported, {skipped_channels_count} channels skipped.{RESET}")

        except Exception as e:
            # Log any errors encountered during database setup
            self.my_logger.log_error(f"{RED}Database setup failed: {e}{RESET}")

        finally:
            conn.close()
    '''legacy markov logic
    def load_text_and_build_model(self):
        directory = "logs/"
        self.text = ""  # Initialize the text attribute
        total_lines = 0

        print(f"{YELLOW}Loading brain...{RESET}")
        files_data = []  # Initialize files_data as an empty list
        for filename in os.listdir(directory):
            if filename.endswith(".txt"):
                with open(os.path.join(directory, filename), "r") as f:
                    file_text = f.read()
                    line_count = file_text.count('\n')
                    total_lines += line_count
                    self.text += file_text
                    name, _ = os.path.splitext(filename)  # Split the filename into name and extension

                    # Fetch color for the channel
                    channel_color = self.color_manager.get_channel_color(name)
                    colored_name = f"\033[38;5;{channel_color}m{name}\033[0m"  # Apply color to channel name

                    files_data.append([colored_name, line_count])  # Add file data to list

        # Print the table
        print(tabulate(files_data, headers=["Channel", "Line Count"], tablefmt="pretty"))
        
        print(f"{YELLOW}Brain size: {total_lines}{RESET}")
        self.model = markovify.Text(self.text)
        self.save_model_to_cache("markov_model.json")
        #self.my_logger.info(f"Brain reloaded {total_lines} lines.")
    

    def generate_message(self, channel_name=None):
        message = self.model.make_sentence()
        if message:
            message = ''.join(char for char in message if char.isprintable())
            self.save_message(message, channel_name)
        return message
    '''
    def load_text_and_build_model(self, create_individual_caches=False):
        directory = "logs/"
        cache_directory = "cache/"
        if not os.path.exists(cache_directory):
            os.makedirs(cache_directory)

        self.text = ""
        self.models = {}
        total_lines = 0
        line_threshold = 2000  # Threshold for individual model
        files_data = []

        # Connect to the SQLite database to fetch valid channels
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT channel_name FROM channel_configs")
        valid_channels = set(row[0] for row in c.fetchall())

        for filename in os.listdir(directory):
            if filename.endswith(".txt"):
                channel_name, _ = os.path.splitext(filename)
                channel_color = self.color_manager.get_channel_color(channel_name)
                colored_channel = f"\x1b[38;5;{channel_color}m{channel_name}\x1b[0m"

                # Skip processing if channel is not in channel_configs
                if channel_name not in valid_channels:
                    cache_file_path = os.path.join(cache_directory, f"{channel_name}_model.json")
                    if os.path.exists(cache_file_path):
                        os.remove(cache_file_path)  # Delete the cache file
                    continue  # Skip to the next file

                file_path = os.path.join(directory, filename)
                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        file_text = f.read()
                    line_count = file_text.count('\n')
                    total_lines += line_count
                    self.text += file_text

                    cache_file_name = f"{channel_name}_model.json"
                    cache_file_path = os.path.join(cache_directory, cache_file_name)
                    cache_exists = os.path.exists(cache_file_path)
                    cache_status = f"{GREEN}✓{RESET}" if cache_exists else f"{RED}-{RESET}"
                    colored_line_count = f"{YELLOW}{line_count:,}{RESET}"

                    if line_count >= line_threshold and create_individual_caches:
                        channel_model = markovify.Text(file_text)
                        self.models[channel_name] = channel_model
                        self.cache_individual_model(channel_name, channel_model, cache_file_path)
                        cache_created = f"{GREEN}Yes{RESET}"
                        cache_file_display = f"\x1b[38;5;2m{cache_file_name}\x1b[0m"
                    else:
                        cache_created = f"{RED}No{RESET}"
                        cache_file_display = f"\x1b[38;5;4mgeneral\x1b[0m" if not cache_exists else f"\x1b[38;5;2m{cache_file_name}\x1b[0m"

                    files_data.append([colored_channel, colored_line_count, cache_status, cache_created, cache_file_display])
                else:
                    # Handle channels with no valid log file
                    files_data.append([colored_channel, "N/A", "N/A", "N/A", f"\x1b[38;5;4mgeneral\x1b[0m"])

        conn.close()

        self.general_model = markovify.Text(self.text)
        general_cache_file_path = os.path.join(cache_directory, "general_markov_model.json")
        general_cache_exists = os.path.exists(general_cache_file_path)
        self.save_general_model_to_cache(general_cache_file_path)

        total_label = f"{YELLOW}Total{RESET}"
        total_lines_formatted = f"\x1b[38;5;45m{total_lines:,}\x1b[0m"
        general_cache_status = f"{GREEN}✓{RESET}" if general_cache_exists else f"{RED}-{RESET}"
        files_data.append([total_label, total_lines_formatted, general_cache_status, "", ""])

        headers = ["Channel", "Brain Size", "Brain Status", "Brain Updated?", "Brain"]
        print(tabulate(files_data, headers=headers, tablefmt="pretty", numalign="right"))


    def cache_individual_model(self, channel_name, model, cache_file_path):
        model_json = model.to_json()
        with open(cache_file_path, 'w') as f:
            f.write(model_json)

    def save_general_model_to_cache(self, cache_file_path):
        try:
            model_json = self.general_model.to_json()
            with open(cache_file_path, 'w') as f:
                f.write(model_json)
        except Exception as e:
            print(f"Failed to save model to cache: {e}")
            
    def load_model_from_cache(self, channel_name):
        cache_file_path = os.path.join("cache", f'{channel_name}_model.json')
        try:
            with open(cache_file_path, 'r') as f:
                model_json = f.read()
                return markovify.Text.from_json(model_json)
        except FileNotFoundError:
            return None

    def generate_message(self, channel_name):
        # Connect to the SQLite database
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        # Check the database to see if this channel should use the general model
        c.execute("SELECT use_general_model FROM channel_configs WHERE channel_name = ?", (channel_name,))
        result = c.fetchone()
        conn.close()

        cache_file_used = ""  # Variable to store the name of the cache file used

        # Determine which model to use and add debug information
        if result and result[0]:
            model = self.general_model
            cache_file_used = "general_markov_model.json"  # Name of the general model cache file
        else:
            model = self.load_model_from_cache(channel_name)
            if model:
                cache_file_used = f"{channel_name}_model.json"  # Specific model cache file
            else:
                model = self.general_model
                cache_file_used = "general_markov_model.json"  # Fallback to general model cache file

        # Debugging information about the cache file used
        #if model:
        #    print(f"[DEBUG] Using cache file: {cache_file_used} for channel: {channel_name}")
        #else:
        #   print("[DEBUG] No model available to generate message.")

        # Generate a message using the chosen model
        message = model.make_sentence()
        if message:
            # Clean up the message to ensure all characters are printable
            message = ''.join(char for char in message if char.isprintable())
            # Save and return the generated message
            self.save_message(message, channel_name)
            return message
        else:
            # If no message was generated, return None and add debug information
            print(f"[DEBUG] Failed to generate message for channel: {channel_name} using cache file: {cache_file_used}")
            return None



    def save_message(self, message, channel_name):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute('''INSERT INTO messages (message, timestamp, channel, state_size, message_length) 
                    VALUES (?, ?, ?, ?, ?)''', 
                (message, datetime.now(), channel_name, self.general_model.state_size, len(message)))
        conn.commit()
        conn.close()
        
        
    def update_model_periodically(self, interval=86400, rebuild_cache=False, initial_delay=3600):
        def delayed_execution():
            if rebuild_cache:
                self.load_text_and_build_model(create_individual_caches=True)  # Rebuild cache including individual caches
                self.my_logger.info("Brain rebuild requested.")
            else:
                cache_loaded = self.load_model_from_cache("markov_model.json")
                if not cache_loaded:
                    self.load_text_and_build_model()  # Just rebuild the general model
                    self.my_logger.info("Markov model updated.")
                else:
                    self.my_logger.info("Markov model loaded from cache.")
            threading.Timer(interval, self.update_model_periodically, [interval, False]).start()

        threading.Timer(initial_delay, delayed_execution).start()

        
        
    ####################################
    # Initialization and Configuration #
    ####################################
    def reload_settings(self):
        config = configparser.ConfigParser()
        config.read("settings.conf")
        self.time_between_messages = int(
            config.get("settings", "time_between_messages")
        )
        self.lines_between_messages = int(
            config.get("settings", "lines_between_messages")
        )
        self.trusted_users = config.get("settings", "trusted_users").split(",")
        self.owner = config.get("auth", "owner")  # new line
        self.channels = config.get("settings", "channels").split(",")

    @commands.command(name="ansv")
    async def ansv_wrapper(self, ctx, setting, new_value=None):
        # Use the command from the other file
        await ansv_command(self, ctx, setting, new_value)
        
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
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT lines_between_messages, time_between_messages FROM channel_configs WHERE channel_name = ?", (channel_name,))
        result = c.fetchone()
        conn.close()

        # If the settings are found in the database, return them, otherwise return defaults
        return result if result else (20, 0)  # Default values: 20 lines and 0 minutes


    #################
    # Event Handling#
    #################
    
    async def try_join_channel(self, channel_name):
        try:
            await self.join_channels([channel_name])
            return True
        except Exception as e:
            print(f"Failed to join channel {channel_name}: {e}")
            return False
        
    async def event_ready(self):
        print(f"{GREEN}Bot online!{RESET}")  # Notifying that bot is online

        # Connect to the database
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()

        table_data = []  # List to store table data
        for channel in self.channels:
            join_success = await self.try_join_channel(channel)

            # Retrieve channel config and additional settings from the database
            c.execute("SELECT owner, trusted_users, voice_enabled, tts_enabled, join_channel, time_between_messages, lines_between_messages FROM channel_configs WHERE channel_name = ?", (channel,))
            row = c.fetchone()

            if row:
                owner, trusted_users, voice_enabled, tts_enabled, join_channel, time_between, lines_between = row
                colored_owner = f"\033[38;5;{self.get_user_color(owner)}m{owner}\033[0m"
                
                if trusted_users:
                    colored_trusted_users = ", ".join(f"\033[38;5;{self.get_user_color(user.strip())}m{user.strip()}\033[0m" for user in trusted_users.split(","))
                else:
                    colored_trusted_users = "None"

                voice_status = GREEN + "enabled" + RESET if voice_enabled else RED + "disabled" + RESET
                tts_status = GREEN + "enabled" + RESET if tts_enabled else RED + "disabled" + RESET
                autojoin_status = GREEN + "enabled" + RESET if join_channel and join_success else RED + "disabled" + RESET

                # Color code time and lines settings
                time_status = GREEN + str(time_between) + RESET if time_between > 0 else RED + str(time_between) + RESET
                lines_status = GREEN + str(lines_between) + RESET if lines_between > 0 else RED + str(lines_between) + RESET

                if not join_success:
                    # Update join_channel status to 0 in database if join failed
                    c.execute("UPDATE channel_configs SET join_channel = 0 WHERE channel_name = ?", (channel,))
                    conn.commit()

                # Add channel information to table data
                table_data.append([f"\033[38;5;{self.get_channel_color(channel)}m{channel}\033[0m", colored_owner, colored_trusted_users, voice_status, tts_status, autojoin_status, time_status, lines_status])
            else:
                table_data.append([f"\033[38;5;1m{channel}\033[0m", "No config found", "", "", "", RED + "disabled" + RESET, RED + "N/A" + RESET, RED + "N/A" + RESET])

        conn.close()

        # Print the table
        headers = ["Channel", "Owner", "Trusted Users", "Voice", "TTS", "Autojoin", "Time", "Lines"]
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
            
            # I dont care about this error right now. UNCOMMENT THIS IF COMMANDS ARENT WORKING
            #self.my_logger.log_info(f"Unrecognized command: {ctx.message.content}")
            return  # Ignore the error, preventing it from propagating further
        else:
            # For all other types of errors, you might want to see what's going on
            self.my_logger.error(f"Error in command: {ctx.command.name}, {error}")

    def log_message(self, message):
        self.my_logger.info(message)
        
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
        # Use the command from the other file
        await ansv_command(self, ctx, setting, new_value)

    async def event_message(self, message):
        if message.author is None or message.author.name == self.nick:
            # Ignore messages from the bot itself or if the author is unknown
            return

        channel_name = message.channel.name

        # Log the user's message
        self.my_logger.log_message(channel_name, message.author.name, message.content)

        # Process any commands in the message
        await self.handle_commands(message)

        # Initialize chat line count for the channel if it's not already
        if channel_name not in self.channel_chat_line_count:
            self.channel_chat_line_count[channel_name] = 0
            self.channel_last_message_time[channel_name] = time.time()

        # Fetch channel-specific settings
        lines_between, time_between = self.fetch_channel_settings(channel_name)

        # Update chat line count for the channel
        self.channel_chat_line_count[channel_name] += 1

        # Calculate elapsed time since the last Markov message for the channel
        elapsed_time = time.time() - self.channel_last_message_time.get(channel_name, 0)

        # Determine if it's time to send a Markov message
        should_send_message = False
        if lines_between > 0 and self.channel_chat_line_count[channel_name] >= lines_between:
            should_send_message = True
        elif time_between > 0 and elapsed_time >= time_between * 60:
            should_send_message = True

        if should_send_message:
            # Check which model to use and if voice is enabled
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            c.execute("SELECT use_general_model, voice_enabled FROM channel_configs WHERE channel_name = ?", (channel_name,))
            row = c.fetchone()
            conn.close()

            if row and row[1]:  # Check if voice_enabled is True
                if row[0]:  # Use general model
                    response = self.general_model.make_sentence()
                else:
                    # Use channel-specific model
                    response = self.models.get(channel_name, self.general_model).make_sentence()

                if response:
                    try:
                        # Get the channel object and send the message
                        channel_obj = self.get_channel(channel_name)
                        if channel_obj:
                            await channel_obj.send(response)
                            self.my_logger.log_message(channel_name, self.nick, response)
                            # Reset counters
                            self.channel_chat_line_count[channel_name] = 0
                            self.channel_last_message_time[channel_name] = time.time()
                        else:
                            self.my_logger.error(f"Channel {channel_name} not found.")
                    except Exception as e:
                        self.my_logger.error(f"Failed to send message in {channel_name}: {str(e)}")



        
if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("settings.conf")

    bot = Bot(
        irc_token=config.get("auth", "tmi_token"),
        client_id=config.get("auth", "client_id"),
        nick=config.get("auth", "nickname"),
        prefix=config.get("settings", "command_prefix"),
        #initial_channels=initial_channels,
        time_between_messages=int(config.get("settings", "time_between_messages")),
        lines_between_messages=int(config.get("settings", "lines_between_messages")),
        
        trusted_users=config.get("settings", "trusted_users").split(","),
        ignored_users=config.get("settings", "ignored_users").split(","),
        owner=config.get("auth", "owner"),
    )

    bot.run()
db_file = 'messages.db'
def fetch_initial_channels(db_file):
    #logger.debug("Fetching initial channels from database...")
    channels = []
    try:
        conn = sqlite3.connect(db_file)
        #logger.debug(f"Connected to database: {db_file}")
        c = conn.cursor()
        c.execute("SELECT channel_name FROM channel_configs WHERE join_channel = 1")
        #logger.debug("Executed SQL query to fetch channels where join_channel = 1")
        
        for row in c.fetchall():
            channel_name = row[0]
            channels.append(channel_name)
            #logger.debug(f"Added channel: {channel_name}")
    except Exception as e:
        logger.error(f"Error fetching initial channels: {e}")
    finally:
        conn.close()
        #logger.debug("Closed database connection")

    return channels


def setup_bot():
    logger = Logger()
    logger.setup_logger()

    # Fetch initial_channels from the database
    initial_channels = fetch_initial_channels('messages.db')

    config = configparser.ConfigParser()
    config.read('settings.conf')

    bot = Bot(
        irc_token=config.get("auth", "tmi_token"),
        client_id=config.get("auth", "client_id"),
        nick=config.get("auth", "nickname"),
        prefix=config.get("settings", "command_prefix"),
        initial_channels=initial_channels,
        time_between_messages=int(config.get("settings", "time_between_messages")),
        lines_between_messages=int(config.get("settings", "lines_between_messages")),
        trusted_users=config.get("settings", "trusted_users").split(","),
        ignored_users=config.get("settings", "ignored_users").split(","),
        owner=config.get("auth", "owner"),
    )

    return bot
