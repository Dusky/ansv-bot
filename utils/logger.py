import logging
from colorama import Fore
from datetime import datetime
import re
import os
from .color_control import ColorManager 
from logging.handlers import RotatingFileHandler

# ANSI color codes for consistent styling
YELLOW = "\x1b[33m"
RESET = "\x1b[0m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
PURPLE = "\x1b[35m"
CYAN = "\x1b[36m"
BLUE = "\x1b[34m"
BRIGHT_GREEN = "\x1b[92m"
BRIGHT_RED = "\x1b[91m"
BRIGHT_YELLOW = "\x1b[93m"
BRIGHT_BLUE = "\x1b[94m"

APP_LOG_FILE = 'app.log'

class Logger:
    def __init__(self):
        self.color_manager = ColorManager()  # Initialize the ColorManager
        self.logger = logging.getLogger('bot')
        self.bad_words = self.load_bad_patterns()
        
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

            # Add the custom handler for colorized terminal output
            custom_handler = CustomHandler()
            custom_handler.setFormatter(formatter)
            self.logger.addHandler(custom_handler)

    def load_bad_patterns(self):
        patterns = []
        filepath = 'badwords.txt'
        
        # Ensure the file exists, create if not
        if not os.path.exists(filepath):
            print(f"'{filepath}' not found. Creating an empty file.")
            open(filepath, 'a').close()  # Create an empty file
        
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                for line in file:
                    pattern = line.strip()
                    if pattern:
                        # Compile each pattern to a regex object for faster matching
                        patterns.append(re.compile(pattern, re.IGNORECASE))
        except FileNotFoundError:
            # This block is now redundant but kept for clarity
            print(f"Error: '{filepath}' file not found after attempting to create it.")
        
        return patterns

    def message_contains_badword(self, message):
        # Check if the message matches any compiled regex patterns
        return any(pattern.search(message) for pattern in self.bad_words)


    def log_message(self, channel, username, message):
        if self.message_contains_badword(message):
            print(f"Message not logged due to bad word usage: {message}")
            return
        
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
    
    def log_warning(self, message):
        """Log a warning with consistent yellow styling"""
        # Use the same two-tone style for warnings
        parts = message.split(':', 1) if ':' in message else [message, '']
        if len(parts) > 1:
            formatted_msg = f"{YELLOW}{parts[0]}:{BRIGHT_YELLOW}{parts[1]}{RESET}"
        else:
            formatted_msg = f"{YELLOW}{message}{RESET}"
        self.logger.warning(formatted_msg)
    
    def log_error(self, message):
        """Log an error with consistent red styling"""
        # Use the same two-tone style for errors
        parts = message.split(':', 1) if ':' in message else [message, '']
        if len(parts) > 1:
            formatted_msg = f"{RED}{parts[0]}:{BRIGHT_RED}{parts[1]}{RESET}"
        else:
            formatted_msg = f"{RED}{message}{RESET}"
        self.logger.error(formatted_msg)
    
    def log_success(self, message):
        """Log a success message with green styling"""
        # Special method for success messages like bot events
        parts = message.split(':', 1) if ':' in message else [message, '']
        if len(parts) > 1:
            formatted_msg = f"{GREEN}{parts[0]}:{BRIGHT_GREEN}{parts[1]}{RESET}"
        else:
            formatted_msg = f"{GREEN}{message}{RESET}"
        self.logger.info(formatted_msg)
    
    def log_event(self, event_type, details):
        """Log a bot event with consistent styling"""
        # For capturing important events like channel joins, messages, etc.
        event_msg = f"{PURPLE}{event_type}{RESET}: {CYAN}{details}{RESET}"
        self.logger.info(event_msg)
        
    def log_command(self, user, command, result=None):
        """Log a command execution with consistent styling"""
        # For tracking command usage with who used it and the result
        user_colored = f"\x1b[38;5;{self.color_manager.get_user_color(user)}m{user}\x1b[0m"
        cmd_msg = f"{BLUE}Command{RESET}: {user_colored} used {BRIGHT_BLUE}{command}{RESET}"
        if result:
            cmd_msg += f" → {result}"
        self.logger.info(cmd_msg)

    def log_info(self, message, color=None):
        """Log an info message with optional color"""
        if color is None:
            # Default two-tone style for info messages
            parts = message.split(':', 1) if ':' in message else [message, '']
            if len(parts) > 1:
                message = f"{GREEN}{parts[0]}:{CYAN}{parts[1]}{RESET}"
            else:
                message = f"{GREEN}{message}{RESET}"
        else:
            message = f"{color}{message}{RESET}"
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
        msg_str = str(record.msg)
        
        # Skip colorizing if the message already contains color codes
        if '\x1b[' in msg_str:
            super().emit(record)
            return
        
        # Colorize common Twitch bot messages
        if 'Successfully logged onto Twitch WS' in msg_str:
            record.msg = f"{GREEN}Successfully logged onto Twitch {PURPLE}Bot is now ready. {RESET}"
        elif 'Connected to' in msg_str and 'channel' in msg_str:
            # Format channel connection messages
            record.msg = msg_str.replace('Connected to', f"{GREEN}Connected to{RESET}")
            record.msg = record.msg.replace('channel', f"{PURPLE}channel{RESET}")
        elif 'Disconnected from' in msg_str:
            # Format channel disconnection messages
            record.msg = msg_str.replace('Disconnected from', f"{RED}Disconnected from{RESET}")
        elif 'Received message from' in msg_str:
            # Format received message notifications
            parts = msg_str.split(':', 1)
            if len(parts) > 1:
                record.msg = f"{BLUE}{parts[0]}:{CYAN}{parts[1]}{RESET}"
        elif 'Sending message to' in msg_str:
            # Format outgoing message notifications
            parts = msg_str.split(':', 1)
            if len(parts) > 1:
                record.msg = f"{GREEN}Sending message to{PURPLE}{parts[1]}{RESET}"
        elif 'Error' in msg_str or 'Failed' in msg_str:
            # Format error messages
            record.msg = f"{RED}{msg_str}{RESET}"
            
        super().emit(record)