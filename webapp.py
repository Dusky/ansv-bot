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
        c.execute("SELECT message_id, file_path, message, timestamp FROM tts_logs ORDER BY message_id DESC LIMIT 10")
        rows = c.fetchall()
        conn.close()
        
        last_id_val = rows[0][0] if rows else 0 # Corrected variable name
        
        files_data = [] # Corrected variable name
        for row in rows:
            files_data.append({
                "id": row[0],       # This is message_id
                "file": row[1],     # This is file_path
                "message": row[2],
                "timestamp": row[3]
            })
        
        return files_data, last_id_val
    except Exception as e:
        app.logger.error(f"Error getting TTS files: {e}")
        return [], 0

def is_bot_actually_running():
    """Check if the bot is actually running using multiple methods."""
    global last_status_check, channel_join_status
    current_time = time.time()
    
    if current_time - last_status_check < 5: # Check every 5 seconds
        app.logger.debug("Using cached bot status")
        return bool(channel_join_status.get('running', False))
    
    last_status_check = current_time
    bot_running = False
    
    # METHOD 1: Check the PID file
    try:
        if os.path.exists("bot.pid"):
            with open("bot.pid", "r") as f:
                pid_str = f.read().strip()
                if pid_str: # Ensure pid_str is not empty
                    pid = int(pid_str)
                    if psutil.pid_exists(pid):
                        process = psutil.Process(pid)
                        if "python" in process.name().lower() or "ansv.py" in " ".join(process.cmdline()).lower():
                            app.logger.info(f"Bot process (PID {pid}) verified via PID file.")
                            bot_running = True
                        else:
                            app.logger.warning(f"PID {pid} exists but is not the bot process.")
                    else:
                        app.logger.warning(f"PID {pid} from bot.pid does not exist.")
                else:
                    app.logger.warning("bot.pid file is empty.")
    except (ValueError, FileNotFoundError, psutil.NoSuchProcess, psutil.AccessDenied) as e:
        app.logger.error(f"Error checking PID file: {e}")
    
    # METHOD 2: Check the heartbeat file (if bot not confirmed by PID)
    if not bot_running:
        try:
            if os.path.exists("bot_heartbeat.json"):
                with open("bot_heartbeat.json", "r") as f:
                    heartbeat_data = json.load(f)
                    timestamp = heartbeat_data.get("timestamp", 0)
                    if current_time - timestamp < 120: # Heartbeat within last 2 minutes
                        app.logger.info(f"Bot verified via recent heartbeat file (last beat: {datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')}).")
                        bot_running = True
                        channel_join_status.update(heartbeat_data) # Update cache with heartbeat data
                        channel_join_status['running'] = True
                    else:
                        app.logger.warning(f"Heartbeat file is stale (last beat: {datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')}).")
        except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
            app.logger.error(f"Error checking heartbeat file: {e}")

    # METHOD 3: Check the database heartbeat (if bot still not confirmed)
    if not bot_running:
        try:
            conn = sqlite3.connect(db_file)
            c = conn.cursor()
            c.execute("SELECT value FROM bot_status WHERE key = 'last_heartbeat'")
            result = c.fetchone()
            conn.close()
            if result:
                last_heartbeat_dt = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
                if (datetime.now() - last_heartbeat_dt).total_seconds() < 120: # DB heartbeat within last 2 minutes
                    app.logger.info(f"Bot verified via recent database heartbeat (last beat: {last_heartbeat_dt}).")
                    bot_running = True
                else:
                    app.logger.warning(f"Database heartbeat is stale (last beat: {last_heartbeat_dt}).")
        except (sqlite3.Error, ValueError, Exception) as e:
            app.logger.error(f"Error checking database heartbeat: {e}")
    
    channel_join_status['running'] = bot_running
    return bot_running

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
                    app.logger.warning(f"Heartbeat file is stale (last beat: {datetime.fromtimestamp(heartbeat_timestamp).strftime('%Y-%m-%d %H:%M:%S')}), considering bot as running but not reliably connected.")
                    # Bot is running (per is_bot_actually_running) but heartbeat is old.
                    # is_connected remains False. Uptime/TTS might be stale.
                    current_uptime_seconds = heartbeat.get("uptime", 0) # Report last known uptime
                    bot_tts_status = heartbeat.get("tts_enabled", False) # Report last known TTS status
                    bot_pid = heartbeat.get("pid")
                    # is_connected is already False, which is appropriate for stale heartbeat

            except (FileNotFoundError, json.JSONDecodeError) as e:
                app.logger.warning(f"Could not read or parse bot_heartbeat.json for detailed status: {e}")
                # Bot is running, but can't get details, so is_connected remains False.
        else:
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

        if bot_is_running_for_heartbeat and os.path.exists("bot_heartbeat.json"):
            try:
                with open("bot_heartbeat.json", "r") as f:
                    heartbeat = json.load(f)
                # Check if heartbeat is recent
                if time.time() - heartbeat.get("timestamp", 0) < 120: # Within 2 minutes
                    heartbeat_joined_channels = [ch.lstrip('#') for ch in heartbeat.get("channels", [])]
                else:
                    app.logger.warning("Heartbeat file is stale for /api/channels, 'currently_connected' status might be inaccurate.")
            except (FileNotFoundError, json.JSONDecodeError) as e:
                app.logger.warning(f"Could not read or parse bot_heartbeat.json for /api/channels: {e}")
        elif bot_is_running_for_heartbeat:
            app.logger.warning("Bot is running but bot_heartbeat.json not found for /api/channels.")


        channels_data_adapted = []
        for raw_channel_config in raw_channels_data:
            channel_item = dict(raw_channel_config)
            db_channel_name = raw_channel_config.get('channel_name')

            # Ensure 'name' field exists
            if db_channel_name and 'name' not in channel_item:
                channel_item['name'] = db_channel_name
            elif 'name' not in channel_item and not db_channel_name:
                channel_item['name'] = 'Unknown Channel'
                app.logger.warning(f"Channel config row missing 'channel_name': {raw_channel_config}")

            # Set 'configured_to_join' (boolean) based on 'join_channel' (integer 0 or 1)
            # Defaults to False (0) if 'join_channel' is missing from the DB row for some reason.
            join_channel_val = raw_channel_config.get('join_channel', 0) # Default to 0 if missing
            channel_item['configured_to_join'] = bool(join_channel_val)
            app.logger.debug(f"Channel: {channel_item.get('name', 'N/A')}, DB join_channel raw value: {join_channel_val}, configured_to_join set to: {channel_item['configured_to_join']}")

            # Set 'currently_connected' (boolean)
            # Ensure comparison is with channel name without '#' prefix
            current_channel_name_for_check = channel_item.get('name', '').lstrip('#')
            channel_item['currently_connected'] = current_channel_name_for_check in heartbeat_joined_channels
            
            # Pass through tts_enabled from DB if it exists
            if 'tts_enabled' in raw_channel_config:
                 channel_item['tts_enabled'] = bool(raw_channel_config.get('tts_enabled',0))


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
    response = make_response(redirect(request.referrer or url_for('main')))
    response.set_cookie('theme', theme_name, max_age=60*60*24*365)
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
        per_page = request.args.get('per_page', 15, type=int) # Number of items per page
        offset = (page - 1) * per_page

        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row 
        c = conn.cursor()

        # Get total count for pagination
        c.execute("SELECT COUNT(*) FROM tts_logs")
        total_items = c.fetchone()[0]
        total_pages = (total_items + per_page - 1) // per_page # Ceiling division

        # Fetch paginated data
        c.execute("""
            SELECT message_id, channel, file_path, message, timestamp, voice_preset 
            FROM tts_logs 
            ORDER BY message_id DESC 
            LIMIT ? OFFSET ?
        """, (per_page, offset))
        rows = c.fetchall()
        conn.close()
        
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
                
                model_data = model_info_map.get(channel_name, {})
                
                log_file_path = os.path.join('logs', f"{channel_name}.log")
                log_file_exists = os.path.exists(log_file_path)

                stats_data.append({
                    "name": channel_name,
                    "cache_file": model_data.get('cache_file', 'N/A'),
                    "log_file": f"{channel_name}.log" if log_file_exists else 'N/A',
                    "cache_size": model_data.get('cache_size_str', model_data.get('cache_size', '0 KB')),
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
        if "general_markov" in model_info_map:
            general_model_data = model_info_map["general_markov"]
            if not any(s['name'] == "general_markov" for s in stats_data):
                 stats_data.append({
                    "name": "general_markov",
                    "cache_file": general_model_data.get('cache_file', 'N/A'),
                    "log_file": "N/A (Combined)", 
                    "cache_size": general_model_data.get('cache_size_str', general_model_data.get('cache_size', '0 KB')),
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
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # Fetch data from cache_build_log table
        # Adjust column names if they are different in your schema
        c.execute("""
            SELECT channel_name as channel, timestamp, duration, success 
            FROM cache_build_log 
            ORDER BY timestamp DESC 
            LIMIT 20 
        """) # Assuming 'channel_name' is the column
        build_times = [dict(row) for row in c.fetchall()]
        conn.close()
        return jsonify(build_times)
    except Exception as e:
        app.logger.error(f"Error in /api/cache-build-performance: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e), "data": []}), 500

if __name__ == "__main__":
    markov_handler.load_models()
    
    @app.route('/health')
    def health_check_route(): 
        return jsonify({"status": "ok", "tts_enabled_webapp": _enable_tts_webapp})
    
    socketio.run(app, host="0.0.0.0", port=5001, debug=True, use_reloader=False)
