from twitchio.ext import commands
import markovify
import configparser
import os
import time
import logging
from utils.logger import Logger
from utils.color_control import ColorManager  # If you need to import it here
from commands.ansv_command import ansv_command
logger = Logger()
logger.setup_logger()
from termcolor import colored
from colorama import init
import random
import json
from datetime import datetime
init() #init termcolor

# Create a handler for writing to the log file
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.DEBUG)

YELLOW = "\x1b[33m" #xterm colors. dunno why tbh
RESET = "\x1b[0m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
PURPLE = "\x1b[35m"

# Read the configuration file
config = configparser.ConfigParser()
config.read('settings.conf')

# Extract the channels
channels = config['settings']['channels'].split(',')

# Initialize the ChannelManager
from utils.channel_manager import ChannelManager
channel_manager = ChannelManager(channels)

class Bot(commands.Bot):
    def __init__(
        self,
        irc_token,
        client_id,
        nick,
        prefix,
        initial_channels,
        time_between_messages,
        lines_between_messages,
        post_trigger,
        trusted_users,
        owner,
        ignored_users,
    ):
        super().__init__(
            token=irc_token,
            client_id=client_id,
            nick=nick,
            prefix=prefix,
            initial_channels=initial_channels,
        )
        self.prefix = prefix
        self.time_between_messages = time_between_messages
        self.lines_between_messages = lines_between_messages
        self.my_logger = Logger()  
        self.my_logger.setup_logger() 
        self.owner = owner
        self.channels = initial_channels
        self.post_trigger = post_trigger
        self.trusted_users = trusted_users
        self.chat_line_count = 0
        self.last_message_time = time.time()
        self.text = self.load_text()
        self.text_model = self.build_model()
        self.ignored_users = ignored_users
        self.initial_channels = initial_channels
        self.user_colors = {}
        self.channel_colors = {}
        self.logger = logging.getLogger('bot')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
        handler = logging.FileHandler(filename='app.log', encoding='utf-8', mode='w')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.color_manager = ColorManager()
        self.channel_manager = ChannelManager(initial_channels)


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

    def load_text(self):
        directory = "logs/"
        text = ""

        print(
            f"{YELLOW}Loading brain from: {os.path.abspath(directory)}"
        ) 

        # Load all text files in the logs directory
        for filename in os.listdir(directory):
            if filename.endswith(".txt"):
                try:
                    with open(os.path.join(directory, filename), "r") as f:
                        text += f.read()
                    print(f"{GREEN}Loaded file: {filename} - YES{RESET}")
                except Exception as e:
                    print(
                        f"{RED}Failed to load file: {filename} - FAIL. Error: {e}{RESET}"
                    ) 

        # Create a Markov chain model from the loaded text
        self.model = markovify.Text(text)

        return text  # Return the loaded text

    def build_model(self):
        return markovify.Text(self.text)
    
    
    #################
    # Event Handling#
    #################
    async def event_ready(self):
        'Called once when the bot goes online.'
        self.my_logger.info("Bot online!")

    async def event_join(self, user, channel):
        'Called when the bot joins a channel.'
        if user.name == self.nick:
            self.my_logger.info(f"Joined channel: {channel.name}")

    def log_channels(self):
        for channel in self.channels:
            color_code = self.get_channel_color(channel)
            self.my_logger.info(f"Joining \033[38;5;{color_code}m{channel}\033[0m")

    def get_channel_color(self, channel_name):
        """Assign a random xterm color index to a channel."""
        return self.color_manager.get_channel_color(channel_name)

    def get_user_color(self, username):
        """Assign a random xterm color index to a user."""
        return self.color_manager.get_user_color(username)

    async def event_command_error(self, ctx, error):
        """Handle command errors."""
        if isinstance(error, commands.CommandNotFound):
            # Log the unrecognized command attempt or just pass to ignore
            self.my_logger.info(f"Unrecognized command: {ctx.message.content}")
            return  # Ignore the error, preventing it from propagating further
        else:
            # For all other types of errors, you might want to see what's going on
            self.my_logger.error(f"Error in command: {ctx.command.name}, {error}")
    def log_message(self, message):
        self.my_logger.info(message)

    #def log_message(self, message):
    #    self.my_logger.log_message(message)




        
    def log_message(self, message):
        msg = f"{message.author.name}: {message.content}"
        self.my_logger.info(msg)


    def generate_message(self, message=None):
        #print(f"Generating message with text data of size {len(self.text)} and state size {self.text_model.state_size}") #debug info from markovify
        return self.text_model.make_sentence()

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore CommandNotFound exceptions
        raise error  # Re-raise other exceptions
    
    async def send_message(self, channel_name, message):
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
        #print("Received a message.")  # Debug print
        # Don't process messages without an author
        
        if message.author is None:
            return

        # Log the user's message
        self.my_logger.log_message(message.channel.name, message.author.name, message.content)

        # Process the user's message and generate a response
        response = self.generate_message(message)

        # Writing the message content to log file
        try:
            if not message.content.startswith("!"):
                log_file_path = f"logs/{message.channel.name}.txt"
                with open(log_file_path, "a") as f:
                    f.write(message.content + "\n")
        except Exception as e:
            print(f"{RED}Failed to write message to log file: {str(e)}")

        # Increment chat_line_count for every message that's not from the bot itself or ignored users
        self.chat_line_count += 1

        # Calculate current time and elapsed time
        current_time = time.time()
        elapsed_time = current_time - self.last_message_time

        # Flag to control whether to send a response
        send_response = False

        # Check for line-based trigger and Markov chain enabled
        if self.chat_line_count >= self.lines_between_messages and self.channel_manager.is_markov_enabled(message.channel.name):
            send_response = True

        # Check time-based trigger and Markov chain enabled
        elif elapsed_time >= self.time_between_messages * 60 and self.channel_manager.is_markov_enabled(message.channel.name):
            send_response = True

        if send_response:
            response = self.generate_message()  # Generate response
            if response:
                try:
                    #print(f"{GREEN}Bot is able to post again!{RESET}")
                    await self.send_message(message.channel.name, response)
                    # Reset counters and time after sending a message
                    self.chat_line_count = 0
                    self.last_message_time = current_time
                    self.my_logger.log_message(message.channel.name, self.nick, response)  # Log the bot's response
                except Exception as e:
                    print(f"{RED}Failed to send message: {str(e)}{RESET}")

        # Handle any commands if present
        await self.handle_commands(message)

        # Check if Markov chain is enabled for the channel
        if self.channel_manager.is_markov_enabled(message.channel.name):
            # Generate and send Markov chain output...
            # Implement your logic to generate a response using markovify
            response = self.generate_message() # Assuming generate_message generates a response
            if response:  # Ensure response is not None or empty
                await message.channel.send(response)

if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("settings.conf")

    bot = Bot(
        irc_token=config.get("auth", "tmi_token"),
        client_id=config.get("auth", "client_id"),
        nick=config.get("auth", "nickname"),
        prefix=config.get("settings", "command_prefix"),
        initial_channels=[
            channel.strip() for channel in config.get("settings", "channels").split(",")
        ],
        time_between_messages=int(config.get("settings", "time_between_messages")),
        lines_between_messages=int(config.get("settings", "lines_between_messages")),
        post_trigger=config.get(
            "settings", "post_trigger"
        ),
        trusted_users=config.get("settings", "trusted_users").split(","),
        ignored_users=config.get("settings", "ignored_users").split(","),
        owner=config.get("auth", "owner"),
    )

    bot.run()