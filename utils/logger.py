import logging
from colorama import Fore
from datetime import datetime
import re
from .color_control import ColorManager 
from logging.handlers import RotatingFileHandler

YELLOW = "\x1b[33m" #xterm colors. dunno why tbh
RESET = "\x1b[0m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
PURPLE = "\x1b[35m"


APP_LOG_FILE = 'app.log' 


class Logger:
    def __init__(self):
        self.color_manager = ColorManager()  # Initialize the ColorManager
        self.logger = logging.getLogger('bot')
        
        
    def setup_logger(self):
        self.logger = logging.getLogger('bot')
        self.logger.setLevel(logging.INFO)

        # Prevent adding multiple handlers to the same logger
        if not self.logger.handlers:
            # Define log format
            formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')

            # Set up a rotating file handler
            file_handler = RotatingFileHandler(
                APP_LOG_FILE, 
                maxBytes=1048576,  # 1MB
                backupCount=5  # Keep at most 5 log files
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.INFO)

            # Add the handlers to the logger
            self.logger.addHandler(file_handler)

            # If you have a custom handler, add it too
            custom_handler = CustomHandler()
            custom_handler.setFormatter(formatter)
            self.logger.addHandler(custom_handler)

    def log_message(self, channel, username, message):
        month_colors = {
            "JAN": "196",  # Bright Red
            "FEB": "201",  # Bright Pink
            "MAR": "46",  # Bright Green
            "APR": "226",  # Bright Yellow
            "MAY": "201",  # Bright Pink
            "JUN": "214",  # Bright Orange
            "JUL": "196",  # Bright Red
            "AUG": "46",  # Bright Green
            "SEP": "214",  # Bright Orange
            "OCT": "201",  # Bright Pink
            "NOV": "226",  # Bright Yellow
            "DEC": "46"  # Bright Green
        }

        timestamp = datetime.now()
        day_year_time = timestamp.strftime('%d %y %H:%M:%S')
        month = timestamp.strftime("%b").upper()
        colored_month = f"\x1b[38;5;{month_colors[month]}m{month}\x1b[0m"
        timestamp_color_index = 14  # Cyan color index in xterm color
        colored_timestamp = f"\x1b[38;5;{timestamp_color_index}m{day_year_time}\x1b[0m"

        # Get the color for this user and channel
        color_index = self.color_manager.get_user_color(username)
        channel_color_index = self.color_manager.get_channel_color(channel)

        # Apply color to username and channel using xterm index
        colored_username = f"\x1b[38;5;{color_index}m{username}\x1b[0m"  # ANSI escape sequence for 256 xterm color
        colored_channel = f"\x1b[38;5;{channel_color_index}m{channel}\x1b[0m"  # Constructing colored channel string)

        # Construct the log message
        log_msg = f"{colored_month} {colored_timestamp} - #{colored_channel} | <{colored_username}>: {message}"

        # Check if message starts with '!' and exclude it from channel-specific log
        if not message.startswith('!'):
            # Save just the message text to a channel-specific log file
            log_file_path = f"logs/{channel}.txt"

            try:
                # Open the log file in append mode and write the message to it
                with open(log_file_path, "a", encoding='utf-8') as file:
                    file.write(message + "\n")  # Write the message and a newline character

                # If the write was successful, append a green checkmark to the log message
                #log_msg += " ✅"
            except Exception as e:
                print(f"Failed to log message to {log_file_path}: {str(e)}")

                # If the write failed, append a red X to the log message
                #log_msg += " ❌"

        # Log the unsanitized message with success/failure indicator to console
        self.logger.info(log_msg)

        # Log the sanitized message to app.log
        sanitized_message = re.sub(r'<[^>]*>', '', message)  # Remove HTML tags using regex
        sanitized_log_msg = f"{timestamp} - #{channel} | <{username}>: {sanitized_message}"

        try:
            with open(APP_LOG_FILE, "a", encoding='utf-8') as app_file:
                app_file.write(sanitized_log_msg + "\n")
        except Exception as e:
            print(f"Failed to log sanitized message to {APP_LOG_FILE}: {str(e)}")
    
    def log_warning(self, message): ## I AM NOT GOOD AT DEBUGGING LOOK AT THIS MESS
        self.logger.warning(message)

    def log_info(self, message, color=None):
        if color:
            message = f"{color}{message}{Fore.RESET}"
        self.logger.info(message)

    def log_error(self, message):
        self.logger.error(message)

    def info(self, message, color=None):
        if color:
            message = f"{color}{message}{Fore.RESET}"
        self.logger.info(message)

    def print_message(self, message):
        print(message)

    def log_settings(self, time_between_messages, lines_between_messages):
        self.log_info(f"time_between_messages: {time_between_messages}", Fore.YELLOW)
        self.log_info(f"lines_between_messages: {lines_between_messages}",Fore.YELLOW)

    def error(self, message):
        self.logger.info(message)

    def setup_logger(self):
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)

        # Check if the logger already has handlers, and if so, don't add them again
        if not self.logger.handlers:
            file_handler = logging.FileHandler(APP_LOG_FILE)
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


