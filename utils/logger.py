import logging
import random
from datetime import datetime
from .color_control import ColorManager 
YELLOW = "\x1b[33m" #xterm colors. dunno why tbh
RESET = "\x1b[0m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
PURPLE = "\x1b[35m"



class Logger:
    def __init__(self):
        self.color_manager = ColorManager()  # Initialize the ColorManager
        self.logger = logging.getLogger('bot')
        '''
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
        handler = logging.FileHandler(filename='bot.log', encoding='utf-8', mode='w')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # Setup logger once when the Logger object is created
        self.logger = logging.getLogger('twitch_bot')
        if not self.logger.handlers:  # Avoid adding handlers if they are already present
            self.logger.setLevel(logging.DEBUG)  # Set to lowest level to capture all messages

            formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')

            # File handler
            file_handler = logging.FileHandler(filename='twitch_bot.log', encoding='utf-8', mode='w')
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.INFO)  # Capture info and above in file
            self.logger.addHandler(file_handler)

            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            console_handler.setLevel(logging.DEBUG)  # Modify as needed
            self.logger.addHandler(console_handler)
            '''

    def log_message(self, channel, username, message):
        month_colors = {
            "Jan": "94",  # Light Blue
            "Feb": "13",  # Pink
            "Mar": "34",  # Emerald Green
            "Apr": "184",  # Pale Yellow
            "May": "177",  # Lilac
            "Jun": "214",  # Pale Orange
            "Jul": "210",  # Coral
            "Aug": "124",  # Burnt Red
            "Sep": "130",  # Rust
            "Oct": "54",  # Indigo
            "Nov": "130",  # Brown
            "Dec": "88"  # Dark Red
        }

        timestamp = datetime.now()
        month = timestamp.strftime("%b")
        colored_month = f"\x1b[38;5;{month_colors[month]}m{month}\x1b[0m"
        timestamp = f"{colored_month} {timestamp.strftime('%d %y %H:%M:%S')}"


        # Get the color for this user and channel
        color_index = self.color_manager.get_user_color(username)
        channel_color_index = self.color_manager.get_channel_color(channel)

        # Apply color to username and channel using xterm index
        colored_username = f"\x1b[38;5;{color_index}m{username}\x1b[0m"  # ANSI escape sequence for 256 xterm color
        colored_channel = f"\x1b[38;5;{channel_color_index}m{channel}\x1b[0m"  # Constructing colored channel string)
        # Construct the log message
        log_msg = f"{timestamp} - #{colored_channel} | <{colored_username}>: {message}"

        # Log the message to console or main log file
        self.logger.info(log_msg)

        # Save just the message text to a channel-specific log file
        # Determine the log file path based on the channel name
        log_file_path = f"logs/{channel}.txt"

        try:
            # Open the log file in append mode and write the message to it
            with open(log_file_path, "a", encoding='utf-8') as file:
                file.write(message + "\n")  # Write the message and a newline character
        except Exception as e:
            print(f"Failed to log message to {log_file_path}: {str(e)}")

        pass
    
    def log_warning(self, message):
        self.logger.warning(message)

    def log_info(self, message):
        self.logger.info(message)

    def log_error(self, message):
        self.logger.error(message)

    def info(self, message):
        self.logger.info(message)

    def print_message(self, message):
        print(message)

    def error(self, message):
        self.logger.info(message)

    def setup_logger(self):
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)

        # Check if the logger already has handlers, and if so, don't add them again
        if not self.logger.handlers:
            file_handler = logging.FileHandler('app.log')
            file_handler.setLevel(logging.INFO)

            custom_handler = CustomHandler()
            custom_handler.setLevel(logging.INFO)

            self.logger.addHandler(file_handler)
            self.logger.addHandler(custom_handler)

        return self.logger
    
    
#####################################################
    # This section is for modifying the
    # "successfully logged onto twitch ws" message
    # that is provided by twitchio
#####################################################
class CustomHandler(logging.StreamHandler):
    def emit(self, record):
        if 'Successfully logged onto Twitch WS' in str(record.msg):
            record.msg = f"{GREEN}Successfully logged onto Twitch {PURPLE}Bot is now ready. {RESET}"
        super().emit(record)


