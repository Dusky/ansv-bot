import os
import sqlite3
import time
import asyncio
import logging
import re
import psutil
import json
import random
import traceback
import signal # Added import for signal
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, make_response
from flask_socketio import SocketIO # Import SocketIO
from datetime import datetime, timedelta
import configparser
from utils.markov_handler import MarkovHandler
from utils.logger import Logger
from utils.db_setup import ensure_db_setup

# Initialize application components
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
socketio = SocketIO(app) # Initialize SocketIO with the Flask app

# Setup logging
logger = Logger()
logger.setup_logger() # This was called logger.setup_logger() in your logger.py
app.logger.setLevel(logging.INFO) # Use app.logger for Flask's internal logging

# Set up database
db_file = "messages.db"
ensure_db_setup(db_file)

# Initialize Markov handler
markov_handler = MarkovHandler(cache_directory="cache")

# Global variable to hold the bot instance (can be set by ansv.py if needed, though direct coupling is not ideal)
bot_instance = None

# Initialize configuration
config = configparser.ConfigParser()
config.read("settings.conf")

# Cache variable for join status
channel_join_status = {}
last_status_check = 0

# Helper functions for is_bot_actually_running
def _check_pid_file(verbose_logging):
    """Checks if the bot is running based on the PID file."""
    try:
        if os.path.exists("bot.pid"):
            with open("bot.pid", "r") as f:
                pid_str = f.read().strip()
                if pid_str:  # Ensure pid_str is not empty
                    pid = int(pid_str)
                    if psutil.pid_exists(pid):
                        process = psutil.Process(pid)
                        # Check if the process name or command line indicates it's the bot
                        if "python" in process.name().lower() or "ansv.py" in " ".join(process.cmdline()).lower():
                            if verbose_logging:
                                app.logger.info(f"Bot process (PID {pid}) verified via PID file.")
                            return True
                        else:
                            if verbose_logging:
                                app.logger.warning(f"PID {pid} exists but is not the bot process (Name: {process.name()}, Cmdline: {' '.join(process.cmdline())}).")
                    else:
                        if verbose_logging:
                            app.logger.warning(f"PID {pid} from bot.pid does not exist.")
                else:
                    if verbose_logging:
                        app.logger.warning("bot.pid file is empty.")
    except (ValueError, FileNotFoundError, psutil.NoSuchProcess, psutil.AccessDenied) as e:
        app.logger.error(f"Error checking PID file: {e}")
    return False

def _check_heartbeat_file(current_time, verbose_logging, status_cache):
    """Checks the bot_heartbeat.json file. Updates status_cache if valid."""
    try:
        if os.path.exists("bot_heartbeat.json"):
            with open("bot_heartbeat.json", "r") as f:
                heartbeat_data = json.load(f)
                timestamp = heartbeat_data.get("timestamp", 0)
                if current_time - timestamp < 120:  # Heartbeat within last 2 minutes
                    if verbose_logging:
                        app.logger.info(f"Bot verified via recent heartbeat file (last beat: {datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')}).")
                    status_cache.update(heartbeat_data) # Update cache with heartbeat data
                    status_cache['running'] = True # Explicitly set running from heartbeat
                    return True
                else:
                    if verbose_logging:
                        app.logger.warning(f"Heartbeat file is stale (last beat: {datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')}).")
    except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
        app.logger.error(f"Error checking heartbeat file: {e}")
    return False

def _check_database_heartbeat(verbose_logging):
    """Checks the database for the last heartbeat timestamp."""
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT value FROM bot_status WHERE key = 'last_heartbeat'")
        result = c.fetchone()
        conn.close()
        if result:
            last_heartbeat_dt = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
            if (datetime.now() - last_heartbeat_dt).total_seconds() < 120:  # DB heartbeat within last 2 minutes
                if verbose_logging:
                    app.logger.info(f"Bot verified via recent database heartbeat (last beat: {last_heartbeat_dt}).")
                return True
            else:
                if verbose_logging:
                    app.logger.warning(f"Database heartbeat is stale (last beat: {last_heartbeat_dt}).")
    except (sqlite3.Error, ValueError, Exception) as e:
        app.logger.error(f"Error checking database heartbeat: {e}")
    return False

# Global to store TTS status from ansv.py
_enable_tts_webapp = False

@app.context_processor
def inject_theme():
    """Injects theme information into the template context."""
    theme = request.cookies.get('theme', 'darkly') # Default to 'darkly'
    return dict(theme=theme)

def set_enable_tts(status: bool):
    """Allows ansv.py to set the TTS status for the webapp."""
    global _enable_tts_webapp
    _enable_tts_webapp = status
    app.logger.info(f"Webapp TTS status set by ansv.py to: {_enable_tts_webapp}")


def get_last_10_tts_files_with_last_id(db_file_path): # Renamed db_file to db_file_path for clarity
    try:
        conn = sqlite3.connect(db_file_path)
        c = conn.cursor()
        # Assuming 'message_id' is the primary key for tts_logs
        c.execute("SELECT message_id, file_path, message, timestamp, channel FROM tts_logs ORDER BY message_id DESC LIMIT 10")
        rows = c.fetchall()
        conn.close()
        
        last_id_val = rows[0][0] if rows else 0 # Corrected variable name
        
        files_data = [] # Corrected variable name
        for row in rows:
            files_data.append({
                "id": row[0],       # This is message_id
                "file": row[1],     # This is file_path
                "message": row[2],
                "timestamp": row[3],
                "channel": row[4] if len(row) > 4 else None   # This is channel
            })
        
        return files_data, last_id_val
    except Exception as e:
        app.logger.error(f"Error getting TTS files: {e}")
        return [], 0

def is_bot_actually_running():
    """Check if the bot is actually running using multiple methods."""
    global last_status_check, channel_join_status
    current_time = time.time()

    try:
        verbose_logging = config.getboolean('settings', 'verbose_heartbeat_log')
    except (configparser.NoSectionError, configparser.NoOptionError):
        verbose_logging = False

    # Use cached status if checked recently
    if current_time - last_status_check < 5: # Cache duration of 5 seconds
        if verbose_logging:
            app.logger.debug(f"Using cached bot status: {channel_join_status.get('running', False)}")
        return bool(channel_join_status.get('running', False))

    last_status_check = current_time
    bot_running_status = False

    # Method 1: Check PID file
    if _check_pid_file(verbose_logging):
        bot_running_status = True
    
    # Method 2: Check heartbeat file (if not confirmed by PID)
    # This method also updates channel_join_status if the heartbeat is valid.
    if not bot_running_status:
        if _check_heartbeat_file(current_time, verbose_logging, channel_join_status):
            bot_running_status = True 
            # channel_join_status['running'] is set by _check_heartbeat_file if it returns True

    # Method 3: Check database heartbeat (if still not confirmed)
    if not bot_running_status:
        if _check_database_heartbeat(verbose_logging):
            bot_running_status = True

    # Update the global cache
    channel_join_status['running'] = bot_running_status
    
    if verbose_logging:
        app.logger.debug(f"Final bot running status after checks: {bot_running_status}")
        
    return bot_running_status

def send_message_via_pid(channel, message):
    """Fallback method to send messages via request file"""
    try:
        bot_is_verified_running = is_bot_actually_running() # Use our robust check
        
        if not bot_is_verified_running:
            app.logger.warning(f"Attempting to send message to {channel} via PID, but bot does not appear to be running.")
            # Still proceed to create request file, bot might pick it up if it starts.

        request_file_path = 'bot_message_request.json'
        if os.path.exists(request_file_path):
            try:
                os.remove(request_file_path) # Clean up old request
                app.logger.info("Removed existing message request file.")
            except OSError as e:
                app.logger.warning(f"Could not remove existing request file {request_file_path}: {e}")
        
        clean_channel = channel.lstrip('#')
        request_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
        
        data_to_write = {
            'action': 'send_message',
            'channel': clean_channel,
            'message': message,
            'timestamp': datetime.now().isoformat(), # Use ISO format
            'request_id': request_id,
            'force': True # Indicate this is a forced send attempt
        }
        
        with open(request_file_path, 'w') as f:
            json.dump(data_to_write, f)
            
        app.logger.info(f"Created message request file for channel {clean_channel}: {message[:30]}...")
        
        # Give bot a moment to process
        time.sleep(0.5) 
        
        if not os.path.exists(request_file_path):
            app.logger.info(f"Message request file for {request_id} processed by bot.")
            return True
        else:
            app.logger.warning(f"Message request file {request_id} still exists. Bot might not be processing requests.")
            # Consider this a success for the webapp's perspective of trying to send
            return True 
            
    except Exception as e:
        app.logger.error(f"Failed to create/process message request file: {e}")
        app.logger.error(traceback.format_exc())
        return False

@app.route('/send_markov_message/<channel_name>', methods=['POST'])
def send_markov_message(channel_name):
    global bot_instance # bot_instance might not be set if webapp runs standalone
    
    try:
        data = request.get_json(silent=True) or {}
        # client_verified = data.get('verify_running', False) # Less reliable
        force_send_params = data.get('force_send', False) or \
                            data.get('bypass_check', False) or \
                            data.get('manual_trigger', False) or \
                            data.get('skip_verification', False) or \
                            request.args.get('force', 'false').lower() == 'true'

        if not re.match(r"^[a-zA-Z0-9_]{1,25}$", channel_name):
            return jsonify({'success': False, 'error': 'Invalid channel name format'}), 400
            
        server_verified_running = is_bot_actually_running()
        
        if force_send_params:
            app.logger.info(f"Force send parameters detected for {channel_name}. Assuming bot is available.")
            # If forcing, we act as if the bot is running for the purpose of attempting to send.
            # The actual send might still fail if the bot is truly down.
            server_verified_running = True 
            
        generated_message = markov_handler.generate_message(channel_name, max_attempts=8, max_fallbacks=2)
        
        if not generated_message:
            app.logger.error(f"Failed to generate Markov message for {channel_name}.")
            return jsonify({'success': False, 'error': 'Failed to generate message', 'message': "Could not generate a message."}), 500
        
        app.logger.info(f"Generated Markov message for {channel_name}: {generated_message[:50]}...")
        
        sent_successfully = False
        send_error_reason = None
        
        if server_verified_running: # Attempt to send if bot is (or assumed to be) running
            try:
                if bot_instance and hasattr(bot_instance, 'send_message_to_channel') and hasattr(bot_instance, 'loop'):
                    # Ensure channel name has # prefix for bot's send_message_to_channel
                    target_channel_for_bot = f"#{channel_name.lstrip('#')}"
                    coro = bot_instance.send_message_to_channel(target_channel_for_bot, generated_message)
                    future = asyncio.run_coroutine_threadsafe(coro, bot_instance.loop)
                    future.result(timeout=5) # Wait for the send to complete or timeout
                    sent_successfully = True
                    app.logger.info(f"Message sent to {channel_name} via direct bot instance call.")
                else:
                    app.logger.info("Bot instance not available or not fully initialized for direct send, trying PID method.")
                    sent_successfully = send_message_via_pid(channel_name, generated_message)
                    if sent_successfully:
                         app.logger.info(f"Message request for {channel_name} created via PID method.")
                    else:
                        send_error_reason = "PID-based send method failed."
                        app.logger.warning(f"PID-based send method failed for {channel_name}.")

            except Exception as send_exc:
                app.logger.error(f"Error sending message to {channel_name}: {send_exc}")
                send_error_reason = str(send_exc)
        else:
            send_error_reason = "Bot not running or not verified."
            app.logger.info(f"Message for {channel_name} not sent: Bot not running/verified (force_send_params={force_send_params}).")
            
        return jsonify({
            'success': True, # Message generation was successful
            'message': generated_message,
            'sent': sent_successfully,
            'server_verified': is_bot_actually_running(), # Actual current status
            'force_applied': force_send_params,
            'error': send_error_reason if not sent_successfully else None
        })
            
    except Exception as e:
        app.logger.error(f"General error in /send_markov_message/{channel_name}: {e}")
        app.logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e), 'message': "Server error during message generation/send."}), 500

@app.route('/')
def main():
    # Theme is now injected by context_processor, but can be accessed here if needed
    # theme = request.cookies.get("theme", "darkly") 
    tts_files_data, last_id_val = get_last_10_tts_files_with_last_id(db_file)
    
    bot_running_status = is_bot_actually_running()
    
    bot_status_info = {
        'running': bot_running_status,
        'uptime': 'N/A',
        'channels': []
    }
    
    if bot_running_status and os.path.exists('bot_heartbeat.json'):
        try:
            with open('bot_heartbeat.json', 'r') as f:
                heartbeat = json.load(f)
                uptime_seconds = heartbeat.get('uptime', 0)
                days, rem = divmod(uptime_seconds, 86400)
                hours, rem = divmod(rem, 3600)
                mins, secs = divmod(rem, 60)
                bot_status_info['uptime'] = f"{int(days)}d {int(hours)}h {int(mins)}m {int(secs)}s"
                bot_status_info['channels'] = heartbeat.get('channels', [])
        except (FileNotFoundError, json.JSONDecodeError) as e:
            app.logger.warning(f"Could not read or parse bot_heartbeat.json: {e}")
    
    return render_template("index.html", tts_files=tts_files_data, 
                           last_id=last_id_val, bot_status=bot_status_info) # No need to pass theme explicitly

@app.route("/generate-message/<channel_name>") 
def generate_message_get(channel_name): 
    try:
        message = markov_handler.generate_message(channel_name, max_attempts=8, max_fallbacks=2)
        if message:
            return jsonify({"success": True, "message": message, "channel": channel_name})
        else:
            return jsonify({"success": False, "error": "Failed to generate message", "message": "Could not generate message."}), 500
    except Exception as e:
        app.logger.error(f"Error in GET /generate-message/{channel_name}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/generate-message", methods=["POST"])
def generate_message_post():
    try:
        data = request.get_json(silent=True) or {}
        model_name_req = data.get('model')
        channel_req = data.get('channel') 
        
        model_to_use = model_name_req or channel_req or "general_markov"
        
        app.logger.info(f"Generating message with effective model: {model_to_use} (requested model: {model_name_req}, channel context: {channel_req})")
        
        message = markov_handler.generate_message(model_to_use, max_attempts=8, max_fallbacks=2)
        
        if message:
            return jsonify({"success": True, "message": message, "model_used": model_to_use})
        else:
            return jsonify({"success": False, "error": "Failed to generate message", "message": "Could not generate message."}), 500
    except Exception as e:
        app.logger.error(f"Error in POST /generate-message: {e}")
        app.logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/available-models')
def available_models():
    try:
        models = markov_handler.get_available_models()
        return jsonify(models)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/rebuild-general-cache', methods=['POST'])
def rebuild_general_cache():
    try:
        success = markov_handler.rebuild_general_cache('logs')
        return jsonify({"success": success, "message": "General cache rebuild " + ("succeeded" if success else "failed")})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/rebuild-cache/<channel_name>', methods=['POST'])
def rebuild_cache(channel_name):
    try:
        success = markov_handler.rebuild_cache_for_channel(channel_name, 'logs')
        return jsonify({"success": success, "message": f"Cache rebuild for {channel_name} " + ("succeeded" if success else "failed")})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/rebuild-all-caches', methods=['POST'])
def rebuild_all_caches():
    try:
        success = markov_handler.rebuild_all_caches()
        return jsonify({"success": success, "message": "All caches rebuild " + ("succeeded" if success else "failed")})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/start_bot', methods=['POST']) 
def start_bot_route():
    if is_bot_actually_running():
        return jsonify({"success": False, "message": "Bot is already running"}), 400
    try:
        import subprocess
        subprocess.Popen(["./launch.sh", "--web", "--tts"], creationflags=subprocess.DETACHED_PROCESS if os.name == 'nt' else 0)
        return jsonify({"success": True, "message": "Bot start command issued."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error starting bot: {str(e)}"}), 500

@app.route('/stop_bot', methods=['POST']) 
def stop_bot_route():
    if not is_bot_actually_running():
        return jsonify({"success": False, "message": "Bot is not running"}), 400
    try:
        if os.path.exists("bot.pid"):
            with open("bot.pid", "r") as f:
                pid = int(f.read().strip())
            if psutil.pid_exists(pid):
                os.kill(pid, signal.SIGTERM) 
                time.sleep(1) 
                if psutil.pid_exists(pid): 
                    os.kill(pid, signal.SIGKILL)
                return jsonify({"success": True, "message": "Bot stop command issued."})
            else:
                return jsonify({"success": False, "message": "Bot PID found but process does not exist."}), 404
        else:
            return jsonify({"success": False, "message": "Bot PID file not found."}), 404
    except Exception as e:
        return jsonify({"success": False, "message": f"Error stopping bot: {str(e)}"}), 500

@app.route('/api/bot-status')
def api_bot_status():
    bot_running = is_bot_actually_running()
    is_connected = False  # Default to not connected
    current_uptime_seconds = 0
    bot_tts_status = False
    current_joined_channels = []
    bot_pid = None
    heartbeat_data_available = False
    
    # Read verbose_heartbeat_log setting from config
    try:
        verbose_logging = config.getboolean('settings', 'verbose_heartbeat_log')
    except (configparser.NoSectionError, configparser.NoOptionError):
        verbose_logging = False # Default to False if not found

    if bot_running:
        # If bot is running, try to get details from heartbeat
        if os.path.exists("bot_heartbeat.json"):
            try:
                with open("bot_heartbeat.json", "r") as f:
                    heartbeat = json.load(f)
                heartbeat_data_available = True # Mark that we could read the file
                    
                # Check if heartbeat is recent enough to be considered valid for connection status
                heartbeat_timestamp = heartbeat.get("timestamp", 0)
                if time.time() - heartbeat_timestamp < 120: # Heartbeat within last 2 minutes
                    current_joined_channels = heartbeat.get("channels", [])
                    is_connected = bool(current_joined_channels) # Connected if in at least one channel
                    bot_tts_status = heartbeat.get("tts_enabled", False)
                    current_uptime_seconds = heartbeat.get("uptime", 0)
                    bot_pid = heartbeat.get("pid")
                else:
                    if verbose_logging: # Use the new config setting
                        app.logger.warning(f"Heartbeat file is stale (last beat: {datetime.fromtimestamp(heartbeat_timestamp).strftime('%Y-%m-%d %H:%M:%S')}), considering bot as running but not reliably connected.")
                    # Bot is running (per is_bot_actually_running) but heartbeat is old.
                    # is_connected remains False. Uptime/TTS might be stale.
                    current_uptime_seconds = heartbeat.get("uptime", 0) # Report last known uptime
                    bot_tts_status = heartbeat.get("tts_enabled", False) # Report last known TTS status
                    bot_pid = heartbeat.get("pid")
                    # is_connected is already False, which is appropriate for stale heartbeat

            except (FileNotFoundError, json.JSONDecodeError) as e:
                if verbose_logging: # Use the new config setting
                    app.logger.warning(f"Could not read or parse bot_heartbeat.json for detailed status: {e}")
                # Bot is running, but can't get details, so is_connected remains False.
        else:
            if verbose_logging: # Use the new config setting
                app.logger.warning("Bot is running but bot_heartbeat.json not found. Cannot confirm connection status or details.")
            # Bot is running, but no heartbeat file, so is_connected remains False.

    status_details = {
        "running": bot_running,
        "connected": is_connected,  # True if running, heartbeat recent, and joined_channels is not empty
        "uptime": current_uptime_seconds,  # Expected by JS as 'uptime' (seconds)
        "tts_enabled": bot_tts_status,  # Expected by JS as 'tts_enabled' (bot's actual TTS state)
        "joined_channels": current_joined_channels,
        "pid": bot_pid,
        "timestamp": datetime.now().isoformat(),  # Timestamp of this API response
        "heartbeat_available": heartbeat_data_available, # Info if heartbeat file was read
        # "tts_enabled_webapp": _enable_tts_webapp # This is a webapp-specific setting, less critical for core bot status
    }
    
    return jsonify(status_details)

@app.route('/settings')
def settings_page(): 
    # theme = request.cookies.get("theme", "darkly") # Theme is now injected by context_processor
    bot_running = is_bot_actually_running()
    channels_data = []
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row 
        c = conn.cursor()
        c.execute("SELECT * FROM channel_configs")
        channels_data = [dict(row) for row in c.fetchall()]
        conn.close()
    except Exception as e:
        app.logger.error(f"Error fetching channels for settings page: {e}")
    
    return render_template("settings.html", channels=channels_data, bot_running=bot_running) # No need to pass theme

@app.route('/stats')
def stats_page(): 
    # theme = request.cookies.get("theme", "darkly") # Theme is now injected by context_processor
    return render_template("stats.html") # No need to pass theme

@app.route('/bot-control', endpoint='bot_control_page') # Corrected endpoint name based on previous fixes
def bot_control_page(): 
    """Render the bot control page."""
    # theme = request.cookies.get("theme", "darkly") # Theme is now injected by context_processor
    bot_running_status = is_bot_actually_running() 
    return render_template("bot_control.html", bot_status={'running': bot_running_status}) # No need to pass theme

@app.route('/tts-history')
def tts_history_page():
    """Render the TTS history page."""
    return render_template("tts_history.html")

@app.route('/logs')
def logs_page():
    """Render the chat logs page."""
    return render_template("logs.html")

@app.route('/channel/<channel_name>')
def channel_page(channel_name):
    """Render the channel-specific dashboard page."""
    # Validate channel exists in our database
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM channel_configs WHERE channel_name = ?", (channel_name,))
        channel_config = c.fetchone()
        conn.close()
        
        if not channel_config:
            # Channel doesn't exist in our database
            return render_template("404.html", error_message=f"Channel '{channel_name}' not found in bot configuration"), 404
        
        # Convert to dict for template
        channel_data = dict(channel_config)
        channel_data['name'] = channel_name
        
        # Get current bot status for this channel
        bot_running = is_bot_actually_running()
        
        # Check if bot is currently connected to this channel
        currently_connected = False
        if bot_running and os.path.exists("bot_heartbeat.json"):
            try:
                with open("bot_heartbeat.json", "r") as f:
                    heartbeat = json.load(f)
                if time.time() - heartbeat.get("timestamp", 0) < 120:  # Within 2 minutes
                    heartbeat_channels = [ch.lstrip('#') for ch in heartbeat.get("channels", [])]
                    currently_connected = channel_name in heartbeat_channels
            except (FileNotFoundError, json.JSONDecodeError):
                pass
        
        channel_data['currently_connected'] = currently_connected
        channel_data['bot_running'] = bot_running
        
        return render_template("channel_page.html", channel=channel_data)
        
    except Exception as e:
        app.logger.error(f"Error loading channel page for {channel_name}: {e}")
        return render_template("500.html", error_message=f"Error loading channel data: {str(e)}"), 500

@app.route('/api/channels')
def api_channels_list(): 
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM channel_configs")
        raw_channels_data = [dict(row) for row in c.fetchall()] 
        conn.close()

        heartbeat_joined_channels = []
        bot_is_running_for_heartbeat = is_bot_actually_running() # Check if bot is running to trust heartbeat

        heartbeat_joined_channels = []
        if bot_is_running_for_heartbeat and os.path.exists("bot_heartbeat.json"):
            try:
                with open("bot_heartbeat.json", "r") as f:
                    heartbeat = json.load(f)
                if time.time() - heartbeat.get("timestamp", 0) < 120: # Within 2 minutes
                    heartbeat_joined_channels = [ch.lstrip('#') for ch in heartbeat.get("channels", [])]
                else:
                    app.logger.warning("Heartbeat file is stale for /api/channels, 'currently_connected' status might be inaccurate.")
            except (FileNotFoundError, json.JSONDecodeError) as e:
                app.logger.warning(f"Could not read or parse bot_heartbeat.json for /api/channels: {e}")
        elif bot_is_running_for_heartbeat:
            app.logger.warning("Bot is running but bot_heartbeat.json not found for /api/channels.")

        # Fetch model details (includes line_count)
        model_details_list = markov_handler.get_available_models()
        model_info_map = {model['name']: model for model in model_details_list if isinstance(model, dict) and 'name' in model}

        # Fetch last activity timestamps
        conn_msg = sqlite3.connect(db_file)
        conn_msg.row_factory = sqlite3.Row
        c_msg = conn_msg.cursor()
        c_msg.execute("SELECT channel, MAX(timestamp) as last_activity_ts FROM messages GROUP BY channel")
        last_activities_rows = c_msg.fetchall()
        conn_msg.close()
        last_activities = {row['channel']: row['last_activity_ts'] for row in last_activities_rows}

        channels_data_adapted = []
        for raw_channel_config in raw_channels_data:
            channel_item = dict(raw_channel_config)
            db_channel_name = raw_channel_config.get('channel_name')

            if db_channel_name and 'name' not in channel_item:
                channel_item['name'] = db_channel_name
            elif 'name' not in channel_item and not db_channel_name:
                channel_item['name'] = 'Unknown Channel'
                app.logger.warning(f"Channel config row missing 'channel_name': {raw_channel_config}")

            join_channel_val = raw_channel_config.get('join_channel', 0)
            channel_item['configured_to_join'] = bool(join_channel_val)
        
            current_channel_name_for_check = channel_item.get('name', '').lstrip('#')
            channel_item['currently_connected'] = current_channel_name_for_check in heartbeat_joined_channels
        
            if 'tts_enabled' in raw_channel_config:
                 channel_item['tts_enabled'] = bool(raw_channel_config.get('tts_enabled',0))

            # Add messages_sent (line_count) and last_activity
            model_data = model_info_map.get(current_channel_name_for_check, {})
            channel_item['messages_sent'] = model_data.get('line_count', 0)
            channel_item['last_activity'] = last_activities.get(current_channel_name_for_check, None)
        
            channels_data_adapted.append(channel_item)
        
        return jsonify(channels_data_adapted)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get-channel-settings/<channel_name>')
def get_channel_settings_route(channel_name): 
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM channel_configs WHERE channel_name = ?", (channel_name,))
        row = c.fetchone()
        conn.close()
        if row:
            return jsonify(dict(row))
        else:
            return jsonify({"error": "Channel not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/update-channel-settings', methods=['POST'])
def update_channel_settings_route(): 
    try:
        data = request.json
        channel_name = data.get('channel_name')
        if not channel_name: return jsonify({"success": False, "message": "Channel name required"}), 400
        
        fields_to_update = {k: v for k, v in data.items() if k != 'channel_name'}
        if not fields_to_update: return jsonify({"success": False, "message": "No fields to update"}), 400

        set_clause = ", ".join([f"{key} = ?" for key in fields_to_update.keys()])
        params = list(fields_to_update.values()) + [channel_name]
        
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute(f"UPDATE channel_configs SET {set_clause} WHERE channel_name = ?", params)
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Settings updated."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/add-channel', methods=['POST'])
def add_channel_route(): 
    try:
        data = request.json
        channel_name = data.get('channel_name')
        if not channel_name: return jsonify({"success": False, "message": "Channel name required"}), 400

        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT 1 FROM channel_configs WHERE channel_name = ?", (channel_name,))
        if c.fetchone():
            conn.close()
            return jsonify({"success": False, "message": "Channel already exists"}), 400
        
        fields = {
            'channel_name': channel_name,
            'tts_enabled': data.get('tts_enabled', 0),
            'voice_enabled': data.get('voice_enabled', 0),
            'join_channel': data.get('join_channel', 1),
            'owner': data.get('owner', channel_name),
            'trusted_users': data.get('trusted_users', ''),
            'ignored_users': data.get('ignored_users', ''),
            'use_general_model': data.get('use_general_model', 1),
            'lines_between_messages': data.get('lines_between_messages', 100),
            'time_between_messages': data.get('time_between_messages', 0),
            'voice_preset': data.get('voice_preset', 'v2/en_speaker_0'), 
            'bark_model': data.get('bark_model', 'regular') 
        }
        
        columns = ', '.join(fields.keys())
        placeholders = ', '.join(['?'] * len(fields))
        values = tuple(fields.values())
        
        c.execute(f"INSERT INTO channel_configs ({columns}) VALUES ({placeholders})", values)
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Channel added."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/delete-channel', methods=['POST'])
def delete_channel_route(): 
    try:
        data = request.json
        channel_name = data.get('channel_name')
        if not channel_name: return jsonify({"success": False, "message": "Channel name required"}), 400
        
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("DELETE FROM channel_configs WHERE channel_name = ?", (channel_name,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Channel deleted."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/list-voices')
def list_voices_route(): 
    try:
        voices_dir = "voices"
        if not os.path.exists(voices_dir): os.makedirs(voices_dir) 
        voices = [f for f in os.listdir(voices_dir) if f.endswith('.npz')]
        return jsonify({"voices": voices})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/rebuild-voice-index') 
def rebuild_voice_index_route(): 
    return jsonify({"success": True, "message": "Voice index rebuild (placeholder) successful."})

@app.route('/get-latest-tts')
def get_latest_tts_route(): 
    try:
        last_id = int(request.args.get('last_id', '0'))
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT message_id, file_path, message, timestamp FROM tts_logs WHERE message_id > ? ORDER BY message_id DESC LIMIT 10", (last_id,))
        rows = c.fetchall()
        conn.close()
        
        files_data = [{"id": r[0], "file": r[1], "message": r[2], "timestamp": r[3]} for r in rows]
        current_max_id = files_data[0]['id'] if files_data else last_id
        
        return jsonify({"files": files_data, "last_id": current_max_id})
    except Exception as e:
        app.logger.error(f"Error in /get-latest-tts: {e}")
        return jsonify({"error": str(e), "files": []}), 500

@app.route('/static/outputs/<path:filename>')
def serve_tts_output(filename):
    directory = os.path.join(app.root_path, 'static', 'outputs')
    return send_from_directory(directory, filename)

@app.route('/set-theme/<theme_name>') 
def set_theme_route(theme_name): 
    # Create a JSON response
    response_data = {"success": True, "theme": theme_name, "message": f"Theme set to {theme_name}"}
    response = make_response(jsonify(response_data))
    
    # Set the cookie on this response
    # Added httponly=True and samesite='Lax' for better security
    response.set_cookie('theme', theme_name, max_age=60*60*24*365, httponly=True, samesite='Lax')
    
    return response

@app.errorhandler(404)
def page_not_found_error(e): 
    # theme = request.cookies.get('theme', 'darkly') # Theme is now injected by context_processor
    return render_template('404.html', error_message="404: Page Not Found"), 404 # No need to pass theme

@app.errorhandler(500)
def server_error_handler(e): 
    app.logger.error(f"Server Error: {e}\n{traceback.format_exc()}")
    # theme = request.cookies.get('theme', 'darkly') # Theme is now injected by context_processor
    return render_template('500.html', error_message="500: Internal Server Error"), 500 # No need to pass theme

@app.route('/api/recent-tts')
def api_recent_tts():
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row # To access columns by name
        c = conn.cursor()
        # Fetch necessary fields, including channel and voice_preset
        # Order by message_id DESC as it's likely the primary key and indicates insertion order.
        # The 'created_at' column caused an error, indicating it might not exist or is named differently.
        c.execute("""
            SELECT message_id, channel, file_path, message, timestamp, voice_preset 
            FROM tts_logs 
            ORDER BY message_id DESC 
            LIMIT 10
        """)
        rows = c.fetchall()
        conn.close()
        
        files_data = [{
            "id": row["message_id"], 
            "channel": row["channel"],
            "file_path": row["file_path"], 
            "message": row["message"], 
            "timestamp": row["timestamp"], # Ensure this is in a format JS Date() can parse (ISO 8601 ideally)
            "voice_preset": row["voice_preset"]
        } for row in rows]
        
        return jsonify(files_data)
    except Exception as e:
        app.logger.error(f"Error in /api/recent-tts: {e}")
        return jsonify({"error": str(e), "files": []}), 500

@app.route('/api/tts-stats')
def api_tts_stats():
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()

        now = datetime.now()
        today_start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Assuming 'timestamp' in tts_logs is stored in a format like 'YYYY-MM-DD HH:MM:SS'
        # or any format that allows lexicographical comparison for dates.
        # If timestamp is Unix epoch, adjustments would be needed here.
        # For simplicity, assuming string format that works with direct comparison.
        # A more robust way would be to convert DB timestamp to datetime objects or use SQL date functions.
        today_start_str = today_start_dt.strftime('%Y-%m-%d %H:%M:%S') 
        
        # This query assumes 'timestamp' is text and can be compared.
        # If 'timestamp' is a Unix timestamp (numeric), the query should be:
        # c.execute("SELECT COUNT(*) FROM tts_logs WHERE timestamp >= ?", (today_start_dt.timestamp(),))
        c.execute("SELECT COUNT(*) FROM tts_logs WHERE timestamp >= ?", (today_start_str,))
        today_count = c.fetchone()[0]

        seven_days_ago_dt = now - timedelta(days=7)
        seven_days_ago_str = seven_days_ago_dt.strftime('%Y-%m-%d %H:%M:%S')
        # Similar consideration for timestamp format here
        c.execute("SELECT COUNT(*) FROM tts_logs WHERE timestamp >= ?", (seven_days_ago_str,))
        week_count = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM tts_logs")
        total_count = c.fetchone()[0]
        
        conn.close()
        return jsonify({"today": today_count, "week": week_count, "total": total_count})
    except Exception as e:
        app.logger.error(f"Error in /api/tts-stats: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e), "today": 0, "week": 0, "total": 0}), 500

@app.route('/api/tts-logs')
def api_tts_logs():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)
        offset = (page - 1) * per_page

        # Sorting parameters
        sort_by_input = request.args.get('sort_by', 'timestamp') # Default sort by timestamp
        sort_order_input = request.args.get('sort_order', 'desc').lower() # Default sort descending

        # Filtering parameters
        channel_filter_input = request.args.get('channel_filter', None, type=str)
        message_filter_input = request.args.get('message_filter', None, type=str)

        # Validate sort_order
        sort_order = "ASC" if sort_order_input == "asc" else "DESC"

        # Validate sort_by column to prevent SQL injection
        allowed_sort_columns = {
            "timestamp": "timestamp",
            "channel": "channel",
            "voice_preset": "voice_preset",
            "message": "message",
            "id": "message_id" # Allow sorting by ID if needed
        }
        sort_column = allowed_sort_columns.get(sort_by_input, "timestamp") # Default to timestamp if invalid

        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Build WHERE clause for filtering
        where_clauses = []
        query_params = []

        if channel_filter_input:
            where_clauses.append("channel LIKE ?")
            query_params.append(f"%{channel_filter_input}%")
        
        if message_filter_input:
            where_clauses.append("message LIKE ?")
            query_params.append(f"%{message_filter_input}%")
        
        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        # Get total count with filters
        count_query = f"SELECT COUNT(*) FROM tts_logs {where_sql}"
        c.execute(count_query, tuple(query_params))
        total_items = c.fetchone()[0]
        total_pages = (total_items + per_page - 1) // per_page if per_page > 0 else 0

        app.logger.debug(f"[api_tts_logs] Filters: channel='{channel_filter_input}', message='{message_filter_input}'. DB TotalItems (filtered): {total_items}, TotalPages: {total_pages}")

        # Fetch paginated and sorted data
        sort_clause = f"ORDER BY {sort_column}"
        if sort_column in ["channel", "voice_preset", "message"]:
            sort_clause += " COLLATE NOCASE"
        sort_clause += f" {sort_order}"

        data_query = f"""
            SELECT message_id, channel, file_path, message, timestamp, voice_preset 
            FROM tts_logs 
            {where_sql}
            {sort_clause}
            LIMIT ? OFFSET ?
        """
        final_query_params = tuple(query_params) + (per_page, offset)
        
        app.logger.debug(f"[api_tts_logs] Executing query: {data_query} with params {final_query_params}")
        c.execute(data_query, final_query_params)
        rows = c.fetchall()
        conn.close()
        app.logger.debug(f"[api_tts_logs] Fetched {len(rows)} rows from DB for page {page} with sort: {sort_column} {sort_order}.")
        
        logs_data = [{
            "id": row["message_id"], 
            "channel": row["channel"],
            "file_path": row["file_path"], 
            "message": row["message"], 
            "timestamp": row["timestamp"],
            "voice_preset": row["voice_preset"]
        } for row in rows]
        
        return jsonify({
            "logs": logs_data,
            "page": page,
            "per_page": per_page,
            "total_items": total_items,
            "total_pages": total_pages
        })
    except Exception as e:
        app.logger.error(f"Error in /api/tts-logs: {e}", exc_info=True)
        return jsonify({"error": str(e), "logs": [], "total_pages": 0, "total_items": 0}), 500

@app.route('/get-stats')
def get_stats_route():
    try:
        app.logger.debug("Attempting to connect to database for /get-stats")
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        app.logger.debug("Executing query: SELECT channel_name, use_general_model, lines_between_messages FROM channel_configs")
        c.execute("SELECT channel_name, use_general_model, lines_between_messages FROM channel_configs")
        config_rows = c.fetchall()
        conn.close()
        app.logger.debug(f"Fetched {len(config_rows)} channel_configs rows.")

        stats_data = []
        
        available_models_info = None
        try:
            app.logger.debug("Checking and calling markov_handler.get_available_models()")
            if markov_handler and hasattr(markov_handler, 'get_available_models') and callable(markov_handler.get_available_models):
                available_models_info = markov_handler.get_available_models()
                app.logger.debug(f"markov_handler.get_available_models() returned: {type(available_models_info)} - {str(available_models_info)[:200]}")
            else:
                app.logger.error("markov_handler is not properly initialized or get_available_models is not callable. Proceeding with no model info.")
                # available_models_info remains None
        except Exception as mh_exc:
            app.logger.error(f"Exception during call to markov_handler.get_available_models(): {mh_exc}", exc_info=True)
            # Proceed with available_models_info as None, which is handled by the logic below

        model_info_map = {}
        if isinstance(available_models_info, list): # Check if it's a list
            if not available_models_info: # Handle empty list
                app.logger.debug("markov_handler.get_available_models() returned an empty list.")
            else: # Process non-empty list
                for item_index, item in enumerate(available_models_info):
                    if isinstance(item, dict):
                        model_name = item.get('name')
                        if model_name:
                            model_info_map[model_name] = item
                        else:
                            app.logger.warning(f"Item at index {item_index} in available_models_info is a dict but missing 'name' key: {str(item)[:100]}")
                    elif isinstance(item, str):
                        model_info_map[item] = {'name': item} # Basic info for string items
                    else:
                        app.logger.warning(f"Unexpected type for item at index {item_index} in available_models_info: {type(item)}. Item: {str(item)[:100]}")
        elif available_models_info is None:
             app.logger.warning("markov_handler.get_available_models() returned None or failed. Proceeding with empty model_info_map.")
        else: # Not a list and not None
             app.logger.warning(f"markov_handler.get_available_models() returned non-list type: {type(available_models_info)}. Proceeding with empty model_info_map.")
        
        app.logger.debug(f"Processing {len(config_rows)} config_rows with model_info_map: {str(model_info_map)[:200]}")
        for i, row in enumerate(config_rows):
            try:
                channel_name = row['channel_name'] 
                use_general_model_val = row['use_general_model']
                lines_between_messages_val = row['lines_between_messages']
                
                model_data = model_info_map.get(channel_name, {}) # model_data now contains more details
                
                # Correct log file name and check existence
                log_filename = f"{channel_name}.txt" 
                log_file_path = os.path.join('logs', log_filename)
                log_file_exists = os.path.exists(log_file_path)

                # cache_file filename comes directly from model_data if model exists
                cache_filename_from_model = model_data.get('cache_file') # This is just the filename like 'channel_model.json'
                
                stats_data.append({
                    "name": channel_name,
                    "cache_file": cache_filename_from_model, 
                    "log_file": log_filename if log_file_exists else None,
                    "cache_size_str": model_data.get('cache_size_str', '0 B'), # For individual display
                    "cache_size_bytes": model_data.get('cache_size_bytes', 0), # For summation
                    "line_count": model_data.get('line_count', 0),
                    "use_general_model": bool(use_general_model_val),
                    "lines_between_messages": lines_between_messages_val
                })
            except KeyError as ke:
                app.logger.error(f"KeyError processing row {i} in /get-stats: {ke}. Row data: {dict(row) if row else 'Row is None'}", exc_info=True)
                continue 
            except Exception as row_exc:
                app.logger.error(f"Exception processing row {i} ('{row['channel_name'] if row and 'channel_name' in row else 'UnknownChannel'}') in /get-stats: {row_exc}", exc_info=True)
                continue

        # Add general model if it exists and isn't already covered
        # Add general model if it exists in model_info_map
        # The name "general_markov" is what get_available_models should return for it
        if "general_markov" in model_info_map: 
            general_model_data = model_info_map["general_markov"]
            # Check if it wasn't already added (e.g. if a channel_config was named 'general_markov')
            if not any(s['name'] == "general_markov" for s in stats_data): 
                stats_data.append({
                    "name": "general_markov",
                    "cache_file": general_model_data.get('cache_file'), 
                    "log_file": None, 
                    "cache_size_str": general_model_data.get('cache_size_str', '0 B'), # For individual display
                    "cache_size_bytes": general_model_data.get('cache_size_bytes', 0), # For summation
                    "line_count": general_model_data.get('line_count', 0),
                    "use_general_model": True, # General model is always "using" itself
                    "lines_between_messages": 0 # Not applicable
                })
        
        app.logger.debug(f"Successfully prepared stats_data for {len(stats_data)} items for /get-stats.")
        return jsonify(stats_data)
    except Exception as e:
        app.logger.error(f"Error in /get-stats: {e}", exc_info=True)
        return jsonify({"error": str(e), "data": []}), 500

@app.route('/api/cache-build-performance')
def api_cache_build_performance():
    retries = 0
    max_retries = 1
    while retries <= max_retries:
        try:
            conn = sqlite3.connect(db_file)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            # Fetch data from cache_build_log table
            c.execute("""
                SELECT channel_name as channel, timestamp, duration, success 
                FROM cache_build_log 
                ORDER BY timestamp DESC 
                LIMIT 20 
            """)
            build_times = [dict(row) for row in c.fetchall()]
            conn.close()
            return jsonify(build_times)
        except sqlite3.OperationalError as oe:
            if "no such table: cache_build_log" in str(oe) and retries < max_retries:
                app.logger.warning(f"/api/cache-build-performance: 'cache_build_log' table not found. Attempting to run ensure_db_setup. Retry {retries + 1}/{max_retries}")
                ensure_db_setup(db_file) # Attempt to create the table
                retries += 1
                time.sleep(0.1) # Small delay before retrying
                continue # Retry the loop
            else:
                app.logger.error(f"Error in /api/cache-build-performance after retries or for other OperationalError: {oe}\n{traceback.format_exc()}")
                return jsonify({"error": str(oe), "data": []}), 500
        except Exception as e:
            app.logger.error(f"Error in /api/cache-build-performance: {e}\n{traceback.format_exc()}")
            return jsonify({"error": str(e), "data": []}), 500
    # If loop finishes due to max_retries exceeded
    app.logger.error(f"/api/cache-build-performance: Failed to access 'cache_build_log' after {max_retries} retries.")
    return jsonify({"error": "Failed to access cache build log data after setup attempt.", "data": []}), 500

@app.route('/view-file/<file_type>/<path:filename>')
def view_file(file_type, filename):
    base_dir = None
    if file_type == 'logs':
        base_dir = 'logs'
    elif file_type == 'cache':
        base_dir = 'cache'
    else:
        return "Invalid file type specified.", 400

    # Basic security: prevent directory traversal
    if '..' in filename or filename.startswith('/'):
        return "Invalid filename.", 400

    file_path = os.path.join(base_dir, filename)
    
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return f"File not found: {filename}", 404
        
    try:
        # For JSON cache files, pretty print. For logs, serve as plain text.
        if file_type == 'cache' and filename.endswith('.json'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
            response_content = json.dumps(content, indent=2)
            mimetype = 'application/json'
        else: # Assuming log files are plain text
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                response_content = f.read()
            mimetype = 'text/plain'
        
        response = make_response(response_content)
        response.mimetype = mimetype
        return response
    except Exception as e:
        app.logger.error(f"Error serving file {file_path}: {e}")
        return "Error reading file.", 500

@app.route('/api/bot-response-stats')
def api_bot_response_stats():
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        # Assuming messages in the 'messages' table are bot responses
        c.execute("SELECT COUNT(*) FROM messages")
        total_responses = c.fetchone()[0]
        conn.close()
        return jsonify({"total_responses": total_responses})
    except Exception as e:
        app.logger.error(f"Error in /api/bot-response-stats: {e}", exc_info=True)
        return jsonify({"error": str(e), "total_responses": 0}), 500

@app.route('/api/channel/<channel_name>/toggle-join', methods=['POST'])
def toggle_channel_join_route(channel_name):
    try:
        if not re.match(r"^[a-zA-Z0-9_]{1,25}$", channel_name):
            return jsonify({"success": False, "message": "Invalid channel name format"}), 400

        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT join_channel FROM channel_configs WHERE channel_name = ?", (channel_name,))
        row = c.fetchone()
        if not row:
            conn.close()
            return jsonify({"success": False, "message": "Channel not found"}), 404
        
        current_status = row[0]
        new_status = 1 if current_status == 0 else 0
        
        c.execute("UPDATE channel_configs SET join_channel = ? WHERE channel_name = ?", (new_status, channel_name))
        conn.commit()
        conn.close()
        
        # Optionally, trigger bot to join/leave if running (bot handles this via periodic check)
        # For immediate effect, a mechanism to notify the bot would be needed.
        
        return jsonify({"success": True, "message": f"Channel {channel_name} {'enabled' if new_status else 'disabled'}.", "new_status": new_status})
    except Exception as e:
        app.logger.error(f"Error toggling join for {channel_name}: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/channel/<channel_name>/toggle-tts', methods=['POST'])
def toggle_channel_tts_route(channel_name):
    try:
        if not re.match(r"^[a-zA-Z0-9_]{1,25}$", channel_name):
            return jsonify({"success": False, "message": "Invalid channel name format"}), 400
            
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT tts_enabled FROM channel_configs WHERE channel_name = ?", (channel_name,))
        row = c.fetchone()
        if not row:
            conn.close()
            return jsonify({"success": False, "message": "Channel not found"}), 404

        current_status = row[0]
        new_status = 1 if current_status == 0 else 0

        c.execute("UPDATE channel_configs SET tts_enabled = ? WHERE channel_name = ?", (new_status, channel_name))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": f"TTS for {channel_name} {'enabled' if new_status else 'disabled'}.", "new_status": new_status})
    except Exception as e:
        app.logger.error(f"Error toggling TTS for {channel_name}: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/system-logs')
def api_system_logs():
    try:
        log_file_path = logger.APP_LOG_FILE # Use the path from the logger instance
        if not os.path.exists(log_file_path):
            return jsonify({"logs": ["Log file not found."]})
        
        lines = []
        with open(log_file_path, 'r', encoding='utf-8') as f:
            # Read last N lines (e.g., 200)
            # This is a simple way, for very large files, more efficient methods exist
            all_lines = f.readlines()
            lines = all_lines[-200:] # Get the last 200 lines
        return jsonify({"logs": [line.strip() for line in lines]})
    except Exception as e:
        app.logger.error(f"Error reading system logs: {e}")
        return jsonify({"logs": [f"Error reading logs: {str(e)}"]}), 500

@app.route('/api/chat-logs')
def api_chat_logs():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        channel_filter = request.args.get('channel', None, type=str)
        offset = (page - 1) * per_page

        # --- REAL DATABASE LOGIC ---
        try:
            conn = sqlite3.connect(db_file)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            base_query = "FROM messages"
            count_query = "SELECT COUNT(*) "
            # Select twitch_message_id as id for frontend compatibility if needed, or just use it as twitch_message_id
            data_query = "SELECT twitch_message_id AS id, timestamp, channel, author_name AS username, message "

            conditions = ["is_bot_response = 0"] # Only fetch user messages
            params = []

            if channel_filter:
                conditions.append("channel = ?")
                params.append(channel_filter)
            
            if conditions: # This will always be true now due to is_bot_response
                base_query += " WHERE " + " AND ".join(conditions)

            # Get total count
            c.execute(count_query + base_query, params)
            total_items = c.fetchone()[0]
            total_pages = (total_items + per_page - 1) // per_page if per_page > 0 else 0

            # Get paginated data
            # Ensure ordering is consistent, e.g., by timestamp descending
            c.execute(data_query + base_query + " ORDER BY timestamp DESC LIMIT ? OFFSET ?", tuple(params) + (per_page, offset))
            log_rows = c.fetchall()
            conn.close()

            logs_data = [dict(row) for row in log_rows]
            
            return jsonify({
                "logs": logs_data,
                "page": page,
                "per_page": per_page,
                "total_items": total_items,
                "total_pages": total_pages
            })
        except sqlite3.OperationalError as oe:
            app.logger.error(f"Database schema error for chat logs: {oe}. The 'messages' table might be missing an 'author_name' column or 'message_authors' table, or 'is_bot_response'.")
            return jsonify({
                "error": "Database schema error. Chat logs might be unavailable. Please check server logs.",
                "logs": [], "total_pages": 0, "total_items": 0
            }), 500
        app.logger.error(f"SQLite operational error in /api/chat-logs: {oe}", exc_info=True)
        return jsonify({"error": str(oe), "logs": [], "total_pages": 0, "total_items": 0}), 500
    except Exception as e:
        app.logger.error(f"Error in /api/chat-logs: {e}", exc_info=True)
        return jsonify({"error": str(e), "logs": [], "total_pages": 0, "total_items": 0}), 500

@app.route('/new-audio-notification', methods=['POST'])
def new_audio_notification():
    data = request.json
    app.logger.info(f"Received new audio notification: {data}")
    channel_name = data.get('channel_name')
    # message_id from the request is the tts_logs table ID (ROWID or PK)
    tts_log_id = data.get('message_id') 

    if channel_name and tts_log_id is not None:
        # Emit an event to all connected SocketIO clients
        # The event name 'new_tts_entry' should match what clients listen for.
        socketio.emit('new_tts_entry', {'id': tts_log_id, 'channel': channel_name})
        app.logger.info(f"Emitted 'new_tts_entry' via SocketIO for tts_log_id: {tts_log_id}, channel: {channel_name}")
        return jsonify({"success": True, "message": "Notification emitted"}), 200
    else:
        app.logger.warning(f"Missing channel_name or message_id in /new-audio-notification. Data: {data}")
        return jsonify({"success": False, "message": "Missing channel_name or message_id"}), 400

@app.route('/api/channel/<channel_name>/stats')
def api_channel_stats(channel_name):
    """Get channel-specific statistics."""
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Check if channel exists
        c.execute("SELECT * FROM channel_configs WHERE channel_name = ?", (channel_name,))
        channel_config = c.fetchone()
        if not channel_config:
            conn.close()
            return jsonify({"error": "Channel not found"}), 404
        
        # Get message count for this channel
        c.execute("SELECT COUNT(*) as total_messages FROM messages WHERE channel = ?", (channel_name,))
        message_count = c.fetchone()['total_messages']
        
        # Get today's message count
        today = datetime.now().strftime('%Y-%m-%d')
        c.execute("SELECT COUNT(*) as today_messages FROM messages WHERE channel = ? AND DATE(timestamp) = ?", (channel_name, today))
        today_count = c.fetchone()['today_messages']
        
        # Get TTS count for this channel
        c.execute("SELECT COUNT(*) as tts_count FROM tts_logs WHERE channel = ?", (channel_name,))
        tts_count = c.fetchone()['tts_count']
        
        # Get last activity
        c.execute("SELECT MAX(timestamp) as last_activity FROM messages WHERE channel = ?", (channel_name,))
        last_activity = c.fetchone()['last_activity']
        
        # Get bot response count (messages sent by the bot to this channel)
        bot_nickname = config.get('auth', 'nickname', fallback='ansvbot').lower()
        c.execute("SELECT COUNT(*) as bot_responses FROM messages WHERE channel = ? AND LOWER(author_name) = ?", (channel_name, bot_nickname))
        bot_responses = c.fetchone()['bot_responses']
        
        conn.close()
        
        # Get model info
        model_details = markov_handler.get_available_models()
        model_info = None
        for model in model_details:
            if isinstance(model, dict) and model.get('name') == channel_name:
                model_info = model
                break
        
        return jsonify({
            "channel_name": channel_name,
            "total_messages": message_count,
            "today_messages": today_count,
            "tts_count": tts_count,
            "bot_responses": bot_responses,
            "last_activity": last_activity,
            "model_info": model_info,
            "config": dict(channel_config)
        })
        
    except Exception as e:
        app.logger.error(f"Error getting channel stats for {channel_name}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/channel/<channel_name>/activity')
def api_channel_activity(channel_name):
    """Get recent activity for a specific channel."""
    try:
        limit = request.args.get('limit', 20, type=int)
        
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get recent messages
        c.execute("""
            SELECT author_name as username, message, timestamp, 'message' as type 
            FROM messages 
            WHERE channel = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (channel_name, limit))
        
        messages = [dict(row) for row in c.fetchall()]
        
        # Get recent TTS entries
        c.execute("""
            SELECT message, timestamp, voice_preset, file_path, 'tts' as type
            FROM tts_logs 
            WHERE channel = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (channel_name, limit))
        
        tts_entries = [dict(row) for row in c.fetchall()]
        
        conn.close()
        
        # Combine and sort by timestamp
        all_activity = messages + tts_entries
        all_activity.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({
            "channel_name": channel_name,
            "activity": all_activity[:limit],
            "total_items": len(all_activity)
        })
        
    except Exception as e:
        app.logger.error(f"Error getting channel activity for {channel_name}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/channel/<channel_name>/generate', methods=['POST'])
def api_channel_generate_message(channel_name):
    """Generate a message for a specific channel."""
    try:
        data = request.get_json() or {}
        send_to_chat = data.get('send_to_chat', False)
        use_general_model = data.get('use_general_model', False)
        
        # Check if channel exists
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM channel_configs WHERE channel_name = ?", (channel_name,))
        channel_config = c.fetchone()
        conn.close()
        
        if not channel_config:
            return jsonify({"error": "Channel not found"}), 404
        
        # Determine which model to use
        model_name = "general" if use_general_model or channel_config['use_general_model'] else channel_name
        
        # Generate message using markov handler
        try:
            generated_message = markov_handler.generate_message(model_name)
            if not generated_message:
                return jsonify({"error": "Failed to generate message", "message": None}), 400
        except Exception as e:
            app.logger.error(f"Error generating message for channel {channel_name}: {e}")
            return jsonify({"error": f"Message generation failed: {str(e)}", "message": None}), 500
        
        # If requested, send to chat
        sent_to_chat = False
        if send_to_chat:
            try:
                bot_running = is_bot_actually_running()
                if bot_running:
                    send_message_via_pid(channel_name, generated_message)
                    sent_to_chat = True
                else:
                    app.logger.warning(f"Cannot send message to {channel_name}: bot not running")
            except Exception as e:
                app.logger.error(f"Error sending message to {channel_name}: {e}")
        
        return jsonify({
            "channel_name": channel_name,
            "message": generated_message,
            "sent_to_chat": sent_to_chat,
            "model_used": model_name,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"Error in channel message generation for {channel_name}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/beta')
def beta_dashboard():
    """Render the redesigned beta dashboard."""
    try:
        # Get bot status and basic info for the beta dashboard
        bot_running = is_bot_actually_running()
        
        # Get channels data
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM channel_configs ORDER BY channel_name")
        channels_data = [dict(row) for row in c.fetchall()]
        conn.close()
        
        # Get recent TTS activity
        recent_tts, _ = get_last_10_tts_files_with_last_id(db_file)
        
        return render_template("beta/dashboard.html", 
                             bot_running=bot_running,
                             channels=channels_data,
                             recent_tts=recent_tts[:5])  # Just show 5 most recent
        
    except Exception as e:
        app.logger.error(f"Error loading beta dashboard: {e}")
        return render_template("500.html", error_message=f"Error loading beta dashboard: {str(e)}"), 500

@app.route('/beta/stats')
def beta_stats_page():
    """Render the redesigned beta stats page."""
    try:
        # Get comprehensive stats data
        bot_running = is_bot_actually_running()
        
        # Get model details
        try:
            model_details = markov_handler.get_available_models()
            if not isinstance(model_details, list):
                app.logger.error(f"Model details is not a list, got: {type(model_details)} - {model_details}")
                model_details = []
        except Exception as model_error:
            app.logger.error(f"Error getting model details: {model_error}")
            model_details = []
        
        # Get channels data
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM channel_configs ORDER BY channel_name")
        channels_data = [dict(row) for row in c.fetchall()]
        conn.close()
        
        # Get recent TTS and message stats
        try:
            recent_tts, _ = get_last_10_tts_files_with_last_id(db_file)
            if not isinstance(recent_tts, list):
                app.logger.error(f"Recent TTS is not a list, got: {type(recent_tts)} - {recent_tts}")
                recent_tts = []
        except Exception as tts_error:
            app.logger.error(f"Error getting TTS data: {tts_error}")
            recent_tts = []
        
        return render_template("beta/stats.html", 
                             bot_running=bot_running,
                             channels=channels_data,
                             models=model_details,
                             recent_tts=recent_tts[:10] if recent_tts else [])
        
    except Exception as e:
        app.logger.error(f"Error loading beta stats page: {e}")
        return render_template("500.html", error_message=f"Error loading stats: {str(e)}"), 500

@app.route('/beta/settings')
def beta_settings_page():
    """Render the redesigned beta settings page."""
    try:
        bot_running = is_bot_actually_running()
        
        # Get channels data with additional info
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM channel_configs ORDER BY channel_name")
        channels_data = [dict(row) for row in c.fetchall()]
        conn.close()
        
        # Get bot status for connection info
        bot_status = {}
        if bot_running and os.path.exists("bot_heartbeat.json"):
            try:
                with open("bot_heartbeat.json", "r") as f:
                    bot_status = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass
        
        # Add connection status to channels
        heartbeat_channels = []
        if bot_status.get('channels'):
            heartbeat_channels = [ch.lstrip('#').lower() for ch in bot_status.get('channels', [])]
        
        for channel in channels_data:
            channel['currently_connected'] = channel['channel_name'].lower() in heartbeat_channels
        
        return render_template("beta/settings.html", 
                             bot_running=bot_running,
                             channels=channels_data,
                             bot_status=bot_status)
        
    except Exception as e:
        app.logger.error(f"Error loading beta settings page: {e}")
        return render_template("500.html", error_message=f"Error loading settings: {str(e)}"), 500

@app.route('/beta/channel/<channel_name>')
def beta_channel_page(channel_name):
    """Render the redesigned beta channel page."""
    try:
        # Validate channel exists
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM channel_configs WHERE channel_name = ?", (channel_name,))
        channel_config = c.fetchone()
        conn.close()
        
        if not channel_config:
            return render_template("404.html", error_message=f"Channel '{channel_name}' not found"), 404
        
        # Convert to dict for template
        channel_data = dict(channel_config)
        channel_data['name'] = channel_name
        
        # Get current bot status for this channel
        bot_running = is_bot_actually_running()
        currently_connected = False
        
        if bot_running and os.path.exists("bot_heartbeat.json"):
            try:
                with open("bot_heartbeat.json", "r") as f:
                    heartbeat = json.load(f)
                if time.time() - heartbeat.get("timestamp", 0) < 120:
                    heartbeat_channels = [ch.lstrip('#') for ch in heartbeat.get("channels", [])]
                    currently_connected = channel_name in heartbeat_channels
            except (FileNotFoundError, json.JSONDecodeError):
                pass
        
        channel_data['currently_connected'] = currently_connected
        channel_data['bot_running'] = bot_running
        
        return render_template("beta/channel.html", channel=channel_data)
        
    except Exception as e:
        app.logger.error(f"Error loading beta channel page for {channel_name}: {e}")
        return render_template("500.html", error_message=f"Error loading channel data: {str(e)}"), 500

@app.route('/api/channel/<channel_name>/tts', methods=['POST'])
def api_channel_tts(channel_name):
    """Generate TTS for a specific channel."""
    try:
        data = request.get_json() or {}
        text = data.get('text', '').strip()
        
        if not text:
            return jsonify({"error": "Text is required"}), 400
        
        # Check if channel exists and TTS is enabled
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM channel_configs WHERE channel_name = ?", (channel_name,))
        channel_config = c.fetchone()
        conn.close()
        
        if not channel_config:
            return jsonify({"error": "Channel not found"}), 404
        
        if not channel_config['tts_enabled']:
            return jsonify({"error": "TTS not enabled for this channel"}), 400
        
        # Import TTS module dynamically to avoid import errors if TTS dependencies aren't installed
        try:
            from utils.tts import process_text
            
            # Process TTS with channel-specific settings
            result = asyncio.run(process_text(
                text=text,
                channel=channel_name,
                voice_preset=channel_config['voice_preset'],
                bark_model=channel_config['bark_model']
            ))
            
            if result:
                return jsonify({
                    "success": True,
                    "channel_name": channel_name,
                    "text": text,
                    "file_path": result.get('file_path'),
                    "timestamp": datetime.now().isoformat()
                })
            else:
                return jsonify({"error": "TTS processing failed"}), 500
                
        except ImportError:
            return jsonify({"error": "TTS functionality not available"}), 503
        except Exception as e:
            app.logger.error(f"Error processing TTS for channel {channel_name}: {e}")
            return jsonify({"error": f"TTS processing failed: {str(e)}"}), 500
        
    except Exception as e:
        app.logger.error(f"Error in channel TTS for {channel_name}: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    markov_handler.load_models()
    
    @app.route('/health')
    def health_check_route(): 
        return jsonify({"status": "ok", "tts_enabled_webapp": _enable_tts_webapp})
    
    socketio.run(app, host="0.0.0.0", port=5001, debug=True, use_reloader=False)
