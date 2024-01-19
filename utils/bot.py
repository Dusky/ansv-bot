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
from utils.db_setup import ensure_db_setup
from utils.tts import process_text
config = configparser.ConfigParser()
config.read('settings.conf')

db_file = "messages.db"  # Replace with your actual database file path
ensure_db_setup(db_file)


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
    def __init__(self, irc_token, client_id, nick, prefix, trusted_users, ignored_users, owner, initial_channels):
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
        self.logger = logging.getLogger('bot')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
        handler = logging.FileHandler(filename='app.log', encoding='utf-8', mode='w')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.color_manager = ColorManager()
        self.channel_chat_line_count = {channel: 0 for channel in self.channels}
        self.channel_last_message_time = {channel: time.time() for channel in self.channels}
        self.channel_settings = {}  # Initialize the channel settings dictionary
        self.load_channel_settings()  # Populate channel settings

        self.db_file = 'messages.db'
        self.load_text_and_build_model()
        self.first_model_update = True

    def load_channel_settings(self):
        self.channel_settings = {}
        conn = sqlite3.connect(db_file)
        c = conn.cursor()

        # Load channel-specific settings
        c.execute("SELECT channel_name, trusted_users, ignored_users, time_between_messages, lines_between_messages FROM channel_configs")
        for row in c.fetchall():
            channel, trusted, ignored, time_between, lines_between = row
            self.channel_settings[channel] = {
                'trusted_users': trusted.split(",") if trusted else [],
                'ignored_users': ignored.split(",") if ignored else [],
                'time_between_messages': time_between,
                'lines_between_messages': lines_between
            }

        conn.close()

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
                file_path = os.path.join(directory, filename)
                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        file_text = f.read()
                    line_count = file_text.count('\n')
                    total_lines += line_count
                    # Determine if file belongs to a valid channel or should be added to general model
                    if channel_name in valid_channels:
                        channel_color = self.color_manager.get_channel_color(channel_name)
                        colored_channel = f"\x1b[38;5;{channel_color}m{channel_name}\x1b[0m"
                        if line_count >= line_threshold and create_individual_caches:
                            channel_model = markovify.Text(file_text)
                            self.models[channel_name] = channel_model
                            cache_file_path = os.path.join(cache_directory, f"{channel_name}_model.json")
                            self.cache_individual_model(channel_name, channel_model, cache_file_path)
                            cache_status = f"{GREEN}✓{RESET}"
                            cache_created = f"{GREEN}Yes{RESET}"
                            cache_file_display = f"\x1b[38;5;2m{channel_name}_model.json\x1b[0m"
                        else:
                            cache_status = f"{RED}-{RESET}"
                            cache_created = f"{RED}No{RESET}"
                            cache_file_display = f"\x1b[38;5;4mgeneral\x1b[0m"
                    else:
                        # Add to general model
                        self.text += file_text
                        colored_channel = f"\x1b[38;5;1m{channel_name}\x1b[0m (General)"
                        cache_status = f"{RED}-{RESET}"
                        cache_created = f"{RED}N/A{RESET}"
                        cache_file_display = f"\x1b[38;5;4mgeneral\x1b[0m"

                    files_data.append([colored_channel, f"{YELLOW}{line_count:,}{RESET}", cache_status, cache_created, cache_file_display])

        conn.close()

        # Build general model
        if self.text:
            self.general_model = markovify.Text(self.text)
            general_cache_file_path = os.path.join(cache_directory, "general_markov_model.json")
            general_cache_exists = os.path.exists(general_cache_file_path)
            self.save_general_model_to_cache(general_cache_file_path)
            general_cache_status = f"{GREEN}✓{RESET}" if general_cache_exists else f"{RED}-{RESET}"
        else:
            general_cache_status = f"{RED}No data{RESET}"

        # Add total and general model status to table
        total_label = f"{YELLOW}Total{RESET}"
        total_lines_formatted = f"\x1b[38;5;45m{total_lines:,}\x1b[0m"
        files_data.append([total_label, total_lines_formatted, general_cache_status, "", ""])

        # Print the table outside the loop, after processing all files
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
        # Use settings from the dictionary or default if not set
        settings = self.channel_settings.get(channel_name, {
            'trusted_users': [],
            'ignored_users': [],
            'time_between_messages': 5,
            'lines_between_messages': 20
        })
        return settings['lines_between_messages'], settings['time_between_messages']

        


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

        await ansv_command(self, ctx, setting, new_value)

    async def event_message(self, message):
        if message.author is None or message.author.name == self.nick:
            # Ignore messages from the bot itself or if the author is unknown
            return

        channel_name = message.channel.name
        # Log the user's message
        self.my_logger.log_message(channel_name, message.author.name, message.content)
        print(f"Received message in {channel_name} from {message.author.name}")

        # Process any commands in the message
        await self.handle_commands(message)

        # Fetch channel-specific settings
        lines_between, time_between = self.fetch_channel_settings(channel_name)
        #print(f"Channel settings for {channel_name}: Lines - {lines_between}, Time - {time_between}")

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

            print(f"Voice settings for {channel_name}: General Model - {row[0]}, Voice Enabled - {row[1]}")

            if row and row[1]:  # Check if voice_enabled is True
                response = self.general_model.make_sentence() if row[0] else self.models.get(channel_name, self.general_model).make_sentence()

                if response:
                    try:
                        # Get the channel object and send the message
                        channel_obj = self.get_channel(channel_name)
                        if channel_obj:
                            await channel_obj.send(response)
                            self.my_logger.log_message(channel_name, self.nick, response)

                            # TTS processing
                            tts_output = process_text(response, channel_name, self.db_file)

                            if tts_output:
                                print(f"TTS audio file generated: {tts_output}")
                            else:
                                print("Failed to generate TTS audio file.")

                            # Reset counters
                            self.channel_chat_line_count[channel_name] = 0
                            self.channel_last_message_time[channel_name] = time.time()
                        else:
                            self.my_logger.error(f"Channel {channel_name} not found.")
                    except Exception as e:
                        self.my_logger.error(f"Failed to send message in {channel_name}: {str(e)}")
                        print(f"Error sending message in {channel_name}: {str(e)}")



def fetch_users(db_file):
    # This function now fetches trusted and ignored users for a specific channel.
    def fetch_users_for_channel(channel_name):
        trusted_users = []
        ignored_users = []
        try:
            conn = sqlite3.connect(db_file)
            c = conn.cursor()
            c.execute("SELECT trusted_users, ignored_users FROM channel_configs WHERE channel_name = ?", (channel_name,))
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

def setup_bot(db_file):
    logger = Logger()
    logger.setup_logger()

    fetch_users_for_channel = fetch_users(db_file)

    initial_channels = fetch_initial_channels(db_file)

    config = configparser.ConfigParser()
    config.read('settings.conf')

    bots = []
    for channel in initial_channels:
        trusted_users, ignored_users = fetch_users_for_channel(channel)

        bot = Bot(
            irc_token=config.get("auth", "tmi_token"),
            client_id=config.get("auth", "client_id"),
            nick=config.get("auth", "nickname"),
            prefix=config.get("settings", "command_prefix"),
            trusted_users=trusted_users,
            ignored_users=ignored_users,
            owner=config.get("auth", "owner"),
            initial_channels=[channel]
        )

        bot.db_file = db_file
        bots.append(bot)

    return bots

# In your main script
bot_instances = setup_bot(db_file)
for bot_instance in bot_instances:
    bot_instance.run()