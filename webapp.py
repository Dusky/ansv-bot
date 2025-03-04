from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    make_response,
    url_for,
    redirect,
    send_from_directory,
)
from flask_socketio import SocketIO
from flask_socketio import emit, disconnect  # Add missing imports
from flask_cors import CORS  # Import CORS
import sqlite3
from datetime import datetime
from utils.markov_handler import MarkovHandler
import os
from utils.bot import setup_bot
from utils.db_setup import ensure_db_setup
from threading import Thread, Lock
import asyncio
import logging
from utils.tts import process_text
import time
import signal
import json
from datetime import timedelta
from flask.logging import default_handler
import sys
import subprocess
import socket
from utils.web_utils import get_available_models
import re
import psutil

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('WEB_SECRET_KEY', 'default-insecure-key')  # Read from settings.conf
CORS(app, supports_credentials=True)  # Update CORS config
socketio = SocketIO(app, cors_allowed_origins="*")  # Restrict in production

# Create a custom filter to suppress specific messages
class SocketIOFilter(logging.Filter):
    def filter(self, record):
        # Allow all messages except the noisy connection ones
        if record.getMessage().startswith('Client connected') or record.getMessage().startswith('Client disconnected'):
            return False
        return True

# Apply the filter to the default Flask logger
default_handler.addFilter(SocketIOFilter())

db_file = "messages.db"
markov_handler = MarkovHandler(cache_directory="cache")
bot_instance = None
bot_thread = None
bot_running = False
enable_tts = False  # Default value, will be set from ansv.py
markov_handler.load_models()

def set_enable_tts(value):
    """Set the global enable_tts variable from ansv.py"""
    global enable_tts
    enable_tts = bool(value)
    print(f"[WEBAPP] TTS enabled set to: {enable_tts}")
    app.logger.info(f"TTS setting initialized to: {enable_tts}")

#logging.getLogger('werkzeug').disabled = True
logging.getLogger('werkzeug').setLevel(logging.ERROR)
#app.logger.setLevel(logging.ERROR)

# Add thread locking for bot control
bot_lock = Lock()

def is_bot_actually_running():
    """Check if bot is running through multiple verification methods"""
    # 1. Check global instance
    if bot_instance and bot_instance.is_connected():
        return True
        
    # 2. Check PID file with process existence
    try:
        with open('bot.pid', 'r') as f:
            parts = f.read().strip().split('|')
            if len(parts) == 2 and psutil.pid_exists(int(parts[1])):
                return True
    except Exception as e:
        app.logger.error(f"PID check error: {str(e)}")
        
    # 3. Process list check
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if 'ansv.py' in ' '.join(proc.info['cmdline']):
                return True
    except:
        pass
        
    # 4. Check Twitch connection status via heartbeats
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT timestamp FROM heartbeats ORDER BY timestamp DESC LIMIT 1")
        last_heartbeat = c.fetchone()
        if last_heartbeat:
            last_time = datetime.strptime(last_heartbeat[0], '%Y-%m-%d %H:%M:%S')
            if (datetime.now() - last_time).total_seconds() < 120:  # 2 minutes
                return True  # Connected and active
    except Exception as e:
        app.logger.error(f"Heartbeat check failed: {e}")
    finally:
        conn.close()
    
    return False

def send_message_via_pid(channel, message):
    """Fallback method to send messages via PID file"""
    try:
        if not os.path.exists('bot.pid'):
            return False
            
        with open('bot.pid', 'r') as f:
            _, pid = f.read().split('|')
            pid = int(pid)
            
        # Use cross-process communication
        with open(f'bot_queue_{pid}.tmp', 'a') as f:
            f.write(f"{channel}|{message}\n")
            
        return True
    except Exception as e:
        app.logger.error(f"PID fallback failed: {str(e)}")
        return False

@app.route('/send_markov_message/<channel_name>', methods=['POST'])
def send_markov_message(channel_name):
    global bot_instance
    
    try:
        data = request.get_json()
        client_verified = data.get('verify_running', False)
        force_channel = data.get('channel')  # Validate channel match
        
        # Security: Validate channel name format
        if not re.match(r"^[a-zA-Z0-9_]{1,25}$", channel_name):
            return jsonify({'success': False, 'error': 'Invalid channel name'}), 400
            
        if force_channel and force_channel != channel_name:
            return jsonify({'success': False, 'error': 'Channel mismatch'}), 400

        # Final authority: Server-side verification
        server_verified = is_bot_actually_running()
        
        # Only allow sending if both client and server agree
        actually_running = client_verified and server_verified
        
        # Generate message regardless of status
        try:
            message = markov_handler.generate_message(channel_name)
            sent = False
            
            if actually_running:
                # Try all possible sending methods
                if bot_instance:
                    # Direct method
                    coroutine = bot_instance.send_message_to_channel(channel_name, message)
                    asyncio.run_coroutine_threadsafe(coroutine, bot_instance.loop)
                    sent = True
                else:
                    # Fallback to PID-based send
                    sent = send_message_via_pid(channel_name, message)
                    
            return jsonify({
                'success': True,
                'message': message,
                'sent': sent,
                'server_verified': server_verified,
                'client_verified': client_verified
            })
            
        except Exception as e:
            app.logger.error(f"Generation error: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
            
    except Exception as e:
        app.logger.error(f"Endpoint error: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/')
def main():
    theme = request.cookies.get("theme", "darkly")  # Get theme from cookie
    tts_files = get_last_10_tts_files_with_last_id(db_file)
    return render_template(
        "main_content.html", tts_files=tts_files, last_id=None, theme=theme
    )

@app.route('/settings')
def settings():
    theme = request.cookies.get("theme", "darkly")
    return render_template('settings.html', last_id=None, theme=theme, current_theme=theme)

@app.route('/toggle_tts', methods=['POST'])
@app.route('/api/toggle_tts', methods=['POST'])  # Add an alternate route
def toggle_tts():
    """Toggle the TTS setting for the bot"""
    global enable_tts, bot_instance
    
    # Add these prints to check if the endpoint is being called
    print("==== TOGGLE TTS ENDPOINT CALLED ====")
    print(f"Request method: {request.method}")
    print(f"Request headers: {request.headers}")
    print(f"Request data: {request.data}")
    app.logger.info("Toggle TTS endpoint called!")
    
    try:
        # Get the requested TTS state from the request
        data = request.get_json()
        print(f"Parsed JSON data: {data}")
        app.logger.info(f"Toggle TTS request data: {data}")
        
        if data is None:
            app.logger.error("No JSON data in toggle_tts request")
            return jsonify({"success": False, "message": "No data provided"}), 400
            
        # Get the requested state
        requested_tts_state = data.get('enable_tts', False)
        app.logger.info(f"Toggling TTS to: {requested_tts_state}")
        
        # Update the global variable
        enable_tts = bool(requested_tts_state)
        
        # If bot is running, update the bot instance
        if bot_instance:
            bot_instance.enable_tts = enable_tts
            app.logger.info(f"Updated bot instance TTS to: {enable_tts}")
            
            # Update the heartbeat file to reflect new TTS status
            try:
                heartbeat_path = 'bot_heartbeat.json'
                if os.path.exists(heartbeat_path):
                    with open(heartbeat_path, 'r') as f:
                        heartbeat_data = json.load(f)
                    
                    # Update TTS status
                    heartbeat_data['tts_enabled'] = enable_tts
                    
                    with open(heartbeat_path, 'w') as f:
                        json.dump(heartbeat_data, f)
                        
                    app.logger.info(f"Updated heartbeat file with new TTS status: {enable_tts}")
            except Exception as e:
                app.logger.error(f"Error updating heartbeat file: {e}")
        
        return jsonify({"success": True, "tts_enabled": enable_tts})
    except Exception as e:
        app.logger.error(f"Error toggling TTS: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/bot_control')
def bot_control():
    theme = request.cookies.get("theme", "darkly")
    
    # Get current bot status
    is_running = False
    current_tts_status = enable_tts  # Use the global variable as default
    
    if os.path.exists('bot.pid'):
        try:
            with open('bot.pid', 'r') as pid_file:
                pid = int(pid_file.read().strip())
                os.kill(pid, 0)  # Checks if process exists
                is_running = True
                
                # If the bot is running, get its actual TTS status
                if bot_instance:
                    # Get the TTS status directly from the bot instance
                    current_tts_status = getattr(bot_instance, 'tts_enabled', enable_tts)
        except:
            pass
    
    # Pass bot status and accurate TTS setting to the template
    bot_status = {'running': is_running}
    
    return render_template('bot_control.html', bot_status=bot_status, enable_tts=current_tts_status, theme=theme)

@app.route('/stats')
def stats():
    theme = request.cookies.get("theme", "darkly")
    cache_dir = 'cache'
    logs_dir = 'logs'
    cache_files = os.listdir(cache_dir)
    log_files = os.listdir(logs_dir)
    
    total_line_count = 0  # Initialize total line count for general model
    stats_data = []
    for file in cache_files:
        channel_name = file.replace('_model.json', '')
        corresponding_log = f"{channel_name}.txt"
        if corresponding_log in log_files:
            # Calculate line count for each log file
            with open(os.path.join(logs_dir, corresponding_log), 'r') as f:
                line_count = sum(1 for line in f)
            total_line_count += line_count  # Add to total line count
            stats_data.append({
                'channel': channel_name,
                'cache': file,
                'log': corresponding_log,
                'line_count': line_count
            })

    # Add the general model row at the beginning
    general_model_row = {
        'channel': 'General Model',
        'cache': 'general_markov_model.json',
        'log': 'N/A',  # Since general model doesn't have a corresponding log file
        'line_count': total_line_count
    }
    stats_data.insert(0, general_model_row)  # Insert at the top

    return render_template('stats.html', stats_data=stats_data, theme=theme)


@app.route('/rebuild-cache/<channel_name>', methods=['POST'])
def rebuild_cache(channel_name):
    try:
        app.logger.info(f"Rebuilding cache for channel: {channel_name}")

        # Define the logs directory path
        logs_directory = 'logs'

        # Call the rebuild_cache_for_channel method with the necessary arguments
        success = markov_handler.rebuild_cache_for_channel(channel_name, logs_directory)

        if success:
            return jsonify({'success': True, 'message': 'Cache rebuilt successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to rebuild cache'}), 400
    except Exception as e:
        app.logger.error(f"Error in rebuild_cache: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/rebuild-all-caches', methods=['POST'])
def rebuild_all_caches():
    try:
        app.logger.info("Rebuilding all caches")

        # Implement the logic to rebuild caches for all channels
        success = markov_handler.rebuild_all_caches()  # Assuming this method exists in your MarkovHandler

        if success:
            return jsonify({'success': True, 'message': 'All caches rebuilt successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to rebuild all caches'}), 400
    except Exception as e:
        app.logger.error(f"Error in rebuild_all_caches: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/api/stats')
def api_stats():
    """Get overall bot statistics in the format expected by event_listener.js"""
    from utils.web_utils import get_db_stats
    
    try:
        # Get stats from database first
        db_stats = get_db_stats()
        
        # Now build the format expected by event_listener.js
        logs_directory = 'logs'
        cache_directory = 'cache'
        all_channels = set()
        converted_stats = []
        
        # Add channels from cache files
        if os.path.exists(cache_directory):
            for file in os.listdir(cache_directory):
                if file.endswith('_model.json') and file != 'cache_build_times.json':
                    channel_name = file.replace('_model.json', '')
                    if channel_name != 'general_markov':  # Skip general model for now
                        all_channels.add(channel_name)
        
        # Get line counts per channel (for non-general models)
        channel_line_counts = {}
        if os.path.exists(logs_directory):
            for channel in all_channels:
                log_file = f"{logs_directory}/{channel}.txt"
                if os.path.exists(log_file):
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        line_count = sum(1 for _ in f)
                    channel_line_counts[channel] = line_count
        
        # Calculate total line count for general model
        total_line_count = sum(channel_line_counts.values())
        
        # Add the general model first
        general_cache_file = f"{cache_directory}/general_markov_model.json"
        general_cache_size = 0
        if os.path.exists(general_cache_file):
            general_cache_size = os.path.getsize(general_cache_file)
            
        converted_stats.append({
            'channel': 'General Model',
            'cache': 'general_markov_model.json',
            'log': 'N/A',
            'cache_size': general_cache_size,
            'line_count': total_line_count
        })
        
        # Add each channel model
        for channel in all_channels:
            cache_file = f"{cache_directory}/{channel}_model.json"
            cache_size = 0
            if os.path.exists(cache_file):
                cache_size = os.path.getsize(cache_file)
                
            converted_stats.append({
                'channel': channel,
                'cache': f"{channel}_model.json",
                'log': f"{channel}.txt" if os.path.exists(f"{logs_directory}/{channel}.txt") else 'N/A',
                'cache_size': cache_size,
                'line_count': channel_line_counts.get(channel, 0)
            })
        
        return jsonify(converted_stats)
    except Exception as e:
        app.logger.error(f"Error getting stats: {e}")
        return jsonify([]), 500


@app.route('/rebuild-general-cache', methods=['POST'])
def rebuild_general_cache_route():
    try:
        app.logger.info("Rebuilding general cache")
        # Specify the path to your logs directory
        logs_directory = 'logs'  
        success = markov_handler.rebuild_general_cache(logs_directory)
        if success:
            return jsonify({'success': True, 'message': 'General cache rebuilt successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to rebuild general cache'}), 400
    except Exception as e:
        app.logger.error(f"Error in rebuild_general_cache: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500



@app.route("/set_theme/<theme>")
def set_theme(theme):
    try:
        app.logger.info(f"Setting theme to: {theme}")
        
        # Expanded list of all valid Bootswatch themes
        valid_themes = {
            # Basic themes
            'dark': 'darkly', 
            'light': 'flatly',
            
            # Standard Bootswatch themes
            'cerulean': 'cerulean',
            'cosmo': 'cosmo',
            'cyborg': 'cyborg',
            'darkly': 'darkly',
            'flatly': 'flatly',
            'journal': 'journal',
            'litera': 'litera',
            'lumen': 'lumen',
            'lux': 'lux',
            'materia': 'materia',
            'minty': 'minty',
            'morph': 'morph',
            'pulse': 'pulse',
            'quartz': 'quartz',
            'sandstone': 'sandstone',
            'simplex': 'simplex',
            'sketchy': 'sketchy',
            'slate': 'slate',
            'solar': 'solar',
            'spacelab': 'spacelab',
            'superhero': 'superhero',
            'united': 'united',
            'vapor': 'vapor',
            'yeti': 'yeti',
            'zephyr': 'zephyr',
            
            # Custom theme
            'ansv': 'ansv'
        }
        
        # Check if the requested theme is valid
        theme_to_set = valid_themes.get(theme, 'darkly')  # Default to darkly if invalid
        
        # Log what we're actually setting
        app.logger.info(f"Requested theme '{theme}' mapped to '{theme_to_set}'")
        
        # Create a response based on request type
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # For AJAX requests, return JSON
            resp = jsonify({'success': True, 'theme': theme_to_set})
        else:
            # For direct requests, redirect to the referrer or main page
            referrer = request.referrer
            if referrer and '/settings' in referrer:
                # Return to settings page if that's where request came from
                resp = make_response(redirect(url_for("settings")))
            else:
                # Otherwise go to main page
                resp = make_response(redirect(url_for("main")))
            
        # Set the cookie with path and expiration
        resp.set_cookie(
            "theme", 
            theme_to_set, 
            path='/',
            max_age=30 * 24 * 60 * 60,
            secure=request.is_secure,
            httponly=False  # Allow JavaScript to read it
        )
        
        return resp
    except Exception as e:
        app.logger.error(f"Error in set_theme: {e}")
        return jsonify({'error': f"Failed to set theme: {str(e)}"}), 500




@app.route("/list-voices", methods=["GET"])
def list_available_voices():
    try:
        voices_directory = "voices"  # Adjust the path if necessary
        voices = [
            voice for voice in os.listdir(voices_directory) if voice.endswith(".npz")
        ]
        return jsonify({"voices": voices})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/set-voice", methods=["POST"])
def set_voice():
    data = request.json
    voice_name = data.get("voice")
    channel_name = (
        ""  # Replace with actual channel name or logic to determine it
    )
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute(
            "UPDATE channel_configs SET voice_preset = ? WHERE channel_name = ?",
            (voice_name, channel_name),
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/generate-message/<channel_name>")
def generate_message(channel_name):
    try:
        message = markov_handler.generate_message(channel_name)
        if message:
            return jsonify({"message": message})
        else:
            return jsonify({"error": "Failed to generate message"}), 400
    except Exception as e:
        app.logger.error(f"Error in generate_message_route: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route("/generate-message", methods=["POST"])
def generate_message_post():
    """Generate a message using the selected model and channel"""
    try:
        # Extract model and channel from request
        data = request.json
        model = data.get('model')
        channel = data.get('channel')
        
        # Log the request
        app.logger.info(f"Generating message with model: {model}, channel: {channel}")
        
        # Load models if not already loaded
        if not markov_handler.models:
            app.logger.info("Models not loaded, loading now...")
            markov_handler.load_models()
        
        # Handle model fallbacks for better reliability
        if model and model not in markov_handler.models:
            available_models = list(markov_handler.models.keys())
            app.logger.warning(f"Model '{model}' not found. Available models: {available_models}")
            
            # Try channel name as fallback
            if channel and f"{channel}" in markov_handler.models:
                model = channel
                app.logger.info(f"Using channel name '{channel}' as model instead")
            # Try explicit model file name if provided
            elif model and f"{model}_model" in markov_handler.models:
                model = f"{model}_model"
                app.logger.info(f"Using modified model name '{model}'")
            # Fall back to general model
            elif "general_markov" in markov_handler.models:
                model = "general_markov"
                app.logger.info("Falling back to general_markov model")
            else:
                # Last resort: use first available model
                model = available_models[0] if available_models else None
                app.logger.info(f"Falling back to first available model: {model}")
        
        # Generate the message using the determined model
        if model:
            message = markov_handler.generate_message(model)
            
            if message:
                app.logger.info(f"Generated message: {message[:50]}...")
                return jsonify({"message": message, "model_used": model})
            else:
                app.logger.warning("Failed to generate message - empty result")
                return jsonify({"error": "Failed to generate message - no content produced"}), 400
        else:
            app.logger.error("No models available for message generation")
            return jsonify({"error": "No models available for message generation"}), 400
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        app.logger.error(f"Error generating message: {str(e)}\n{trace}")
        return jsonify({"error": f"Error generating message: {str(e)}"}), 500


@app.route('/available-models')
def available_models():
    """Get a list of available Markov models"""
    try:
        # Ensure models are loaded
        if not markov_handler.models:
            app.logger.info("Models not loaded, loading now...")
            markov_handler.load_models()
        
        # Get models from the handler first (already loaded models)
        loaded_models = list(markov_handler.models.keys())
        app.logger.info(f"Loaded models from handler: {loaded_models}")
        
        # Also check files on disk for thoroughness
        file_models = []
        if os.path.exists('cache'):
            for file in os.listdir('cache'):
                if file.endswith('_model.json'):
                    model_name = file.replace('_model.json', '')
                    file_models.append(model_name)
        
        # Combine and deduplicate
        all_models = list(set(loaded_models + file_models))
        
        # Add general_markov first if it exists
        models = []
        if 'general_markov' in all_models:
            models.append('general_markov')
            all_models.remove('general_markov')
        
        # Add remaining models, sorted for consistency
        models.extend(sorted(all_models))
        
        app.logger.info(f"Returning available models: {models}")
        return jsonify(models)
    except Exception as e:
        app.logger.error(f"Error getting available models: {e}")
        return jsonify(['general_markov'])  # Return at least general_markov if errored


@app.route("/new-audio-notification", methods=["POST"])
def new_audio_notification():
    global new_audio_available
    new_audio_available = True
    socketio.emit("refresh_table", {"data": "New audio available"})
    return jsonify({"success": True})


@app.route("/check-new-audio", methods=["GET"])
def check_new_audio():
    global new_audio_available
    response = {"newAudioAvailable": new_audio_available}
    new_audio_available = False  # Reset flag after checking
    return jsonify(response)

def get_stats_data(cache_dir='cache', logs_dir='logs'):
    stats_data = []

    # List all files in the cache directory
    cache_files = os.listdir(cache_dir)

    # For each cache file, find the corresponding log file
    for cache_file in cache_files:
        channel_name = cache_file.split('.')[0]  # Assuming cache file name format is 'channel_name.extension'
        log_file = f'{channel_name}.txt'

        # Check if the log file exists in the logs directory
        if log_file in os.listdir(logs_dir):
            stats_data.append({
                'channel_name': channel_name,
                'cache_file': cache_file,
                'log_file': log_file
            })
    
    return stats_data

def format_timestamp(timestamp):
    try:
        # Handle ISO format like '2025-02-24T21:03:12.265976'
        if 'T' in timestamp:
            dt = datetime.fromisoformat(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
            
        # Handle format like '20240127-190809'
        dt = datetime.strptime(timestamp, "%Y%m%d-%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        print(f"Error parsing timestamp: {timestamp} - {e}")
        return timestamp  # Return original timestamp in case of an error


def format_data_for_frontend(data):
    formatted_data = []
    for record in data:
        channel, message_id, timestamp, voice_preset, file_path, message = record
        truncated_message_id = (
            str(message_id)[4:] if len(str(message_id)) > 4 else str(message_id)
        )  # Added closing parenthesis
        if (
            len(timestamp) == 19
            and timestamp[4] == "-"
            and timestamp[7] == "-"
            and timestamp[13] == ":"
        ):
            formatted_timestamp = timestamp
        else:
            formatted_timestamp = format_timestamp(timestamp)

        formatted_record = (
            channel,
            truncated_message_id,
            formatted_timestamp,
            voice_preset,
            file_path,
            message,
        )
        formatted_data.append(formatted_record)
    return formatted_data


def get_total_tts_files_count(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM tts_logs"
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


@app.route("/messages/<int:page>")
def paginated_messages(page):
    per_page = 10
    total_items = get_total_tts_files_count(
        db_file
    )
    tts_files = get_paginated_tts_files(db_file, page, per_page)
    return jsonify(
        {"items": format_data_for_frontend(tts_files), "totalItems": total_items}
    )


def get_paginated_tts_files(db_file, page, per_page):
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        offset = (page - 1) * per_page
        c.execute(
            "SELECT channel, message_id, timestamp, voice_preset, file_path, message FROM tts_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        )
        files = c.fetchall()
        return files
    except sqlite3.Error as e:
        print("[ERROR] Database error:", e)
        return []
    finally:
        conn.close()


@app.route("/update-channel-settings", methods=["POST"])
def update_channel_settings():
    data = request.json
    channel_name = data.get("channel_name")

    # Validation to ensure channel_name is provided
    if not channel_name:
        return jsonify({"success": False, "message": "Channel name is required"})

    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute(
            """
            UPDATE channel_configs
            SET tts_enabled = ?, voice_enabled = ?, join_channel = ?, owner = ?, trusted_users = ?, ignored_users = ?, use_general_model = ?, lines_between_messages = ?, time_between_messages = ?, voice_preset = ?
            WHERE channel_name = ?""",
            (
                data["tts_enabled"],
                data["voice_enabled"],
                data["join_channel"],
                data["owner"],
                data["trusted_users"],
                data["ignored_users"],
                data["use_general_model"],
                data["lines_between_messages"],
                data["time_between_messages"],
                data["voice_preset"],
                data["channel_name"],
            ),
        )
        conn.commit()
        return jsonify({"success": True})
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        return jsonify({"success": False, "message": str(e)})
    finally:
        conn.close()


@app.route("/channel-stats")
def channel_stats():
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        query = "SELECT channel_name, message_count, last_active FROM channel_info"
        cursor.execute(query)
        channels = cursor.fetchall()
        channel_stats = [
            dict(channel_name=row[0], message_count=row[1], last_active=row[2])
            for row in channels
        ]
        return jsonify(channel_stats)
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        conn.close()


@app.route("/save-channel-settings", methods=["POST"])
def save_channel_settings():
    data = request.json
    print("Received data for saving:", data)

    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute(
            """
            UPDATE channel_configs 
            SET tts_enabled = ?, voice_enabled = ?, join_channel = ?, owner = ?, trusted_users = ?, ignored_users = ?, use_general_model = ?, lines_between_messages = ?, time_between_messages = ?
            WHERE channel_name = ?""",
            (
                data["tts_enabled"],
                data["voice_enabled"],
                data["join_channel"],
                data["owner"],
                data["trusted_users"],
                data["ignored_users"],
                data["use_general_model"],
                data["lines_between_messages"],
                data["time_between_messages"],
                data["channel_name"],
            ),
        )
        rows_affected = conn.total_changes
        conn.commit()
        print(f"{rows_affected} rows updated in database.")
        return jsonify({"success": True})
    except sqlite3.Error as e:
        print(f"SQLite error in save_channel_settings: {e}")
        return jsonify({"success": False})


@app.route("/get-channels")
def get_channels():
    """Get information about connected channels"""
    try:
        # Always return channel information, even if bot is not running
        # This allows viewing and configuring channels when bot is stopped
        # if not bot_instance:
        #    return jsonify([])
            
        channels = []
        
        # Open the database
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Get channel configuration with all necessary fields
        try:
            cursor.execute("SELECT channel_name, tts_enabled, join_channel FROM channel_configs")
            
            # Create configs dict with explicit debugging
            channel_configs = {}
            for row in cursor.fetchall():
                channel_name = row[0]
                tts_enabled = bool(row[1])
                join_channel = bool(row[2])
                
                # Log raw and converted values
                app.logger.info(f"Channel {channel_name}: join_channel raw={row[2]}, converted={join_channel}")
                
                channel_configs[channel_name] = {
                    'tts_enabled': tts_enabled,
                    'join_channel': join_channel
                }
            
            app.logger.info(f"Loaded {len(channel_configs)} channels with join_channel field")
        except sqlite3.OperationalError as e:
            app.logger.error(f"Error getting channel configs: {e}")
            # Final fallback if schema doesn't match expected
            cursor.execute("SELECT channel_name, tts_enabled FROM channel_configs")
            channel_configs = {row[0]: {'tts_enabled': bool(row[1]), 'join_channel': False} for row in cursor.fetchall()}
        
        # Get message counts
        cursor.execute("SELECT channel, COUNT(*) FROM messages GROUP BY channel")
        message_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get last activity with properly formatted timestamps
        cursor.execute("SELECT channel, MAX(timestamp) FROM messages GROUP BY channel")
        
        last_activities = {}
        for row in cursor.fetchall():
            channel = row[0]
            timestamp = row[1]
            
            # Format timestamp for better JavaScript parsing
            try:
                # Try to convert the timestamp to a standard ISO format if it's not already
                if timestamp:
                    # Parse the timestamp based on the database format (e.g., "YYYY-MM-DD HH:MM:SS")
                    dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                    # Convert to ISO format for reliable JS parsing
                    formatted_timestamp = dt.isoformat()
                    last_activities[channel] = formatted_timestamp
                else:
                    last_activities[channel] = "Never"
            except Exception as e:
                app.logger.warning(f"Failed to format timestamp for {channel}: {e}")
                last_activities[channel] = timestamp  # Use original as fallback
        
        conn.close()
        
        # Get connected channels from bot heartbeat or bot status
        connected_channels = []
        
        # Method 1: Try to get from heartbeat file first (most reliable)
        if os.path.exists('bot_heartbeat.json'):
            try:
                with open('bot_heartbeat.json', 'r') as f:
                    heartbeat_data = json.load(f)
                    if 'channels' in heartbeat_data:
                        # Debug the channel names being processed
                        raw_channels = heartbeat_data['channels']
                        app.logger.info(f"Raw channels from heartbeat: {raw_channels}")
                        
                        # Bot now writes channel names without # to heartbeat file
                        # Only convert to lowercase for consistent matching
                        connected_channels = [c.lower() for c in raw_channels]
                        app.logger.info(f"Processed connected channels: {connected_channels}")
            except Exception as e:
                app.logger.warning(f"Failed to read connected channels from heartbeat: {e}")
        
        # Method 2: Try to get from bot status table
        if not connected_channels:
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM bot_status WHERE key = 'connected_channels'")
                result = cursor.fetchone()
                if result and result[0]:
                    connected_channels = result[0].split(',')
                conn.close()
            except Exception as e:
                app.logger.warning(f"Failed to read connected channels from bot_status: {e}")
        
        # Method 3: Fallback to bot instance if available
        if not connected_channels and bot_instance:
            try:
                connected_channels = [c.lstrip('#').lower() for c in getattr(bot_instance, '_joined_channels', [])]
            except Exception as e:
                app.logger.warning(f"Failed to get channels from bot instance: {e}")
                
        app.logger.info(f"Found connected channels: {connected_channels}")
        
        # Get is_running status for additional fallback
        is_running = False
        if os.path.exists('bot_heartbeat.json'):
            try:
                with open('bot_heartbeat.json', 'r') as f:
                    heartbeat_data = json.load(f)
                    # If heartbeat is recent (less than 2 minutes old), consider the bot running
                    if time.time() - heartbeat_data.get('timestamp', 0) < 120:
                        is_running = True
            except Exception:
                pass
                
        # Format the channel data
        # Check if we should apply the fallback for all active channels
        use_fallback = is_running and not connected_channels
        if use_fallback:
            app.logger.warning("No connected channels found but bot is running - using fallback")
        
        # Get active channels from database for fallback
        active_channels = []
        if use_fallback:
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                cursor.execute("SELECT channel_name FROM channel_configs WHERE join_channel = 1")
                active_channels = [row[0].lower() for row in cursor.fetchall()]
                conn.close()
                app.logger.info(f"Fallback active channels: {active_channels}")
            except Exception as e:
                app.logger.error(f"Error getting fallback channels: {e}")
        
        for channel_name, config in channel_configs.items():
            # Check using multiple methods:
            # 1. Check against connected_channels from heartbeat
            connected = channel_name.lower() in connected_channels
            
            # 2. Check in-database currently_connected value if available
            if not connected and 'currently_connected' in config and config['currently_connected']:
                connected = True
                app.logger.info(f"Using in-database connected status for {channel_name}")
            
            # 3. Apply fallback if needed
            if not connected and use_fallback and channel_name.lower() in active_channels:
                connected = True
                app.logger.info(f"Applied fallback connected status for {channel_name}")
            
            # Create channel data with join_channel status (explicitly as boolean)
            join_channel_value = bool(config.get('join_channel', False))
            
            channel_data = {
                'name': channel_name,
                'connected': connected,
                'tts_enabled': config['tts_enabled'],
                'join_channel': join_channel_value,
                'messages_sent': message_counts.get(channel_name, 0),
                'last_activity': last_activities.get(channel_name, 'Never')
            }
            
            # Log full channel data for debugging
            app.logger.info(f"Channel data for {channel_name}: join_channel={join_channel_value}")
            
            # Debug log to help diagnose issues
            app.logger.debug(f"Channel {channel_name} join_channel status: {channel_data['join_channel']}")
            
            channels.append(channel_data)
            
        return jsonify(channels)
    except Exception as e:
        app.logger.error(f"Error getting channels: {e}")
        return jsonify([])


@app.route("/get-channel-settings/<channelName>")
def get_channel_settings(channelName):
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute(
            "SELECT tts_enabled, voice_enabled, join_channel, owner, trusted_users, ignored_users, use_general_model, lines_between_messages, time_between_messages FROM channel_configs WHERE channel_name = ?",
            (channelName,),
        )
        settings = c.fetchone()
        if settings:
            keys = [
                "tts_enabled",
                "voice_enabled",
                "join_channel",
                "owner",
                "trusted_users",
                "ignored_users",
                "use_general_model",
                "lines_between_messages",
                "time_between_messages",
            ]
            return jsonify(dict(zip(keys, settings)))
        else:
            return jsonify({"error": "Channel not found"}), 404
    except sqlite3.Error as e:
        print(f"[ERROR] SQLite error in get_channel_settings: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


@app.route("/add-channel", methods=["POST"])
def add_channel():
    data = request.json
    channel_name = data.get("channel_name")

    # Debug: Print the received data
    print("Received data for adding channel:", data)

    if not channel_name:
        print("No channel name provided.")
        return jsonify({"success": False, "message": "No channel name provided"})

    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()

        # Check if the channel already exists
        c.execute(
            "SELECT COUNT(*) FROM channel_configs WHERE channel_name = ?",
            (channel_name,),
        )
        count = c.fetchone()[0]
        print(f"Existing count for channel '{channel_name}': {count}")

        if count == 0:
            # Insert new channel as it does not exist
            c.execute(
                """
                INSERT INTO channel_configs (channel_name, tts_enabled, voice_enabled, join_channel, owner, trusted_users, ignored_users, use_general_model, lines_between_messages, time_between_messages)
                VALUES (?, 0, 0, 1, ?, '', '', 1, 100, 0)""",
                (channel_name, channel_name),
            )
            conn.commit()
            print(f"Channel '{channel_name}' added successfully.")
            return jsonify(
                {"success": True, "message": f"Channel {channel_name} added."}
            )
        else:
            print(f"Channel '{channel_name}' already exists.")
            return jsonify(
                {"success": False, "message": f"Channel {channel_name} already exists."}
            )
    except Exception as e:
        print(f"Exception occurred in add_channel: {e}")
        return jsonify({"success": False, "message": str(e)})
    finally:
        conn.close()


@app.route('/api/recent-tts', methods=['GET'])
@app.route('/latest-messages', methods=['GET'])  # Keep for backward compatibility
def get_latest_messages():
    try:
        limit = request.args.get('limit', 10, type=int)
        channel = request.args.get('channel', None)
        
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # First, get stats for the sidebar counters
        stats_query = """
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN timestamp LIKE ? THEN 1 END) as today,
                COUNT(CASE WHEN timestamp >= date('now', '-7 days') THEN 1 END) as week
            FROM tts_logs
        """
        
        today_pattern = datetime.now().strftime('%Y%m%d') + '%'  # Format: YYYYMMDD%
        c.execute(stats_query, (today_pattern,))
        stats_row = c.fetchone()
        
        stats = {
            'total': stats_row['total'] if stats_row else 0,
            'today': stats_row['today'] if stats_row else 0,
            'week': stats_row['week'] if stats_row else 0
        }
        
        # Prepare query with optional channel filter for the main entries
        query = """
            SELECT message_id as id, channel, timestamp, voice_preset, file_path, message 
            FROM tts_logs 
        """
        
        params = []
        if channel:
            query += " WHERE channel = ? "
            params.append(channel)
            
        query += " ORDER BY timestamp DESC LIMIT ? "
        params.append(limit)
        
        # Execute the query
        c.execute(query, params)
        
        rows = c.fetchall()
        conn.close()
        
        # Format the data for the frontend
        formatted_entries = []
        for row in rows:
            # Handle timestamp formats - normalize for display
            timestamp = row['timestamp']
            
            formatted_entries.append({
                'id': row['id'],
                'channel': row['channel'],
                'timestamp': timestamp,
                'voice_preset': row['voice_preset'] or 'default',
                'file_path': row['file_path'],
                'message': row['message']
            })
            
        # Return both stats and entries
        return jsonify({
            'stats': stats,
            'entries': formatted_entries
        })
    except Exception as e:
        app.logger.error(f"Error getting recent TTS: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/check-updates/<int:last_id>")
def check_updates(last_id):
    new_entries = get_new_tts_entries(db_file, last_id)
    return jsonify(
        {
            "newData": len(new_entries) > 0,
            "entries": format_data_for_frontend(new_entries),
        }
    )


@app.route('/api/build-times', methods=['GET'])
@app.route('/api/cache-build-performance', methods=['GET'])  # Add an alternate route
def get_build_times():
    try:
        # Try to read build times from cache file
        cache_file = os.path.join('cache', 'cache_build_times.json')
        
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                build_times = json.load(f)
            app.logger.info(f"Loaded {len(build_times)} build time records")
            return jsonify(build_times)
        else:
            # If file doesn't exist, return empty array
            app.logger.warning(f"Cache build times file not found at {cache_file}")
            return jsonify([])
    except Exception as e:
        app.logger.error(f"Error reading build times: {e}")
        return jsonify([])

def get_new_tts_entries(db_file, last_id):
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute(
            "SELECT channel, message_id, timestamp, voice_preset, file_path, message FROM tts_logs WHERE message_id > ? ORDER BY timestamp DESC",
            (last_id,),
        )
        entries = c.fetchall()
        return entries
    except sqlite3.Error as e:
        print("[ERROR] Database error:", e)
        return []
    finally:
        conn.close()


def get_last_10_tts_files_with_last_id(db_file):
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute(
            "SELECT channel, message_id, timestamp, voice_preset, file_path, message FROM tts_logs ORDER BY timestamp DESC LIMIT 10"
        )
        files = c.fetchall()
        return format_data_for_frontend(files)  # Return only the formatted data
    except sqlite3.Error as e:
        print("[ERROR] Database error:", e)
        return []  # Return an empty list on error
    finally:
        conn.close()


# def run_flask_app():
#     app.run(debug=True, host="0.0.0.0", port=5001)


# Add SocketIO events for real-time updates
@socketio.on('connect')
def handle_connect(auth):  # Add proper parameters
    app.logger.info('Client connected')
    emit('status_update', {'bot_running': bot_running})

@socketio.on('disconnect')
def handle_disconnect():
    app.logger.info('Client disconnected')

@socketio.on('request_update')
def handle_update_request(data):  # Add proper parameters
    emit('full_update', {
        'bot_status': bot_running,
        'channels': get_channels(),
        'stats': get_stats_data()
    })


def run_webapp():
    from webapp import app, socketio
    try:
        socketio.run(app, host="0.0.0.0", port=5001, debug=False)
    except KeyboardInterrupt:
        print("Web server shutting down...")
    finally:
        print("Cleaning up web resources...")
        # Add any web-specific cleanup here


if __name__ == "__main__":
    #markov_handler.load_models()
    run_webapp()

__all__ = ['app', 'socketio']

@app.route('/send-message-to-channel', methods=['POST'])
def send_message_to_channel():
    try:
        data = request.json
        channel = data.get('channel')
        message = data.get('message')
        
        if not channel or not message:
            return jsonify({'success': False, 'error': 'Missing channel or message'}), 400
        
        coroutine = bot_instance.send_message_to_channel(channel, message)
        asyncio.run_coroutine_threadsafe(coroutine, bot_instance.loop)
        
        # Use asyncio.run to run the async function in a sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success, output_file = loop.run_until_complete(process_text(channel, message))
        loop.close()
        
        if not success or not output_file:
            raise Exception("TTS processing failed")
        
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT MAX(message_id) FROM tts_logs")
        new_id = c.fetchone()[0]
        conn.close()
        
        socketio.emit('new_tts_entry', {'id': new_id})
        
        return jsonify({
            'success': True,
            'file_path': output_file,
            'message': 'TTS message generated successfully'
        })
    except Exception as e:
        app.logger.error(f"Error generating TTS: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/tts-audio/<path:filename>')
def serve_tts_audio(filename):
    # Security check to prevent directory traversal
    if '..' in filename or filename.startswith('/'):
        return "Invalid file path", 400
        
    # Return the audio file
    return send_from_directory('static/tts_output', filename)

@app.route('/rebuild-channel-model/<channel_name>', methods=['POST'])
def rebuild_channel_model(channel_name):
    """Legacy endpoint - calls rebuild_cache_for_channel directly to ensure it works"""
    app.logger.info(f"Legacy endpoint called for channel: {channel_name}")
    
    try:
        # Define logs directory
        logs_directory = 'logs'
        
        # Call the correct method directly
        app.logger.info(f"Calling rebuild_cache_for_channel directly for channel: {channel_name}")
        success = markov_handler.rebuild_cache_for_channel(channel_name, logs_directory)
        
        if success:
            app.logger.info(f"Successfully rebuilt model for channel: {channel_name}")
            return jsonify({'success': True, 'message': f'Model for {channel_name} rebuilt successfully'})
        else:
            app.logger.error(f"Failed to rebuild model for channel: {channel_name}")
            return jsonify({'success': False, 'message': 'Failed to rebuild channel model'}), 400
    except Exception as e:
        app.logger.error(f"Exception in rebuild_channel_model: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/get-stats')
def get_stats():
    """Get statistics for all channels"""
    try:
        stats = []
        
        # Get all log files in the logs directory
        logs_directory = 'logs'
        cache_directory = 'cache'
        
        if not os.path.exists(logs_directory):
            app.logger.warning(f"Logs directory '{logs_directory}' does not exist")
            return jsonify([])
            
        # Get list of channels from log files
        channels = []
        for file in os.listdir(logs_directory):
            if file.endswith('.txt'):
                channel_name = file.replace('.txt', '')
                channels.append(channel_name)
        
        # Add the general model which might not have a log file
        if 'general_markov' not in channels:
            general_cache_file = f"{cache_directory}/general_markov_model.json"
            if os.path.exists(general_cache_file):
                channels.append('general_markov')
        
        # Get stats for each channel
        for channel in channels:
            log_file = f"{logs_directory}/{channel}.txt"
            cache_file = f"{cache_directory}/{channel}_model.json"
            
            # Get log file size and line count
            line_count = 0
            log_size = 0
            if os.path.exists(log_file):
                log_size = os.path.getsize(log_file)
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    line_count = sum(1 for _ in f)
            
            # Get cache file size
            cache_size = 0
            if os.path.exists(cache_file):
                cache_size = os.path.getsize(cache_file)
            
            # Format sizes
            log_size_formatted = format_size(log_size)
            cache_size_formatted = format_size(cache_size)
            
            # For general_markov model, use proper display name
            display_name = "General Model" if channel == "general_markov" else channel
            
            stats.append({
                'name': display_name,
                'log_file': f"{channel}.txt",
                'cache_file': f"{channel}_model.json" if os.path.exists(cache_file) else None,
                'log_size': log_size_formatted,
                'cache_size': cache_size_formatted,
                'line_count': line_count
            })
        
        # Log stats data to help with debugging
        app.logger.info(f"get-stats: returning {len(stats)} model stats")
        return jsonify(stats)
    except Exception as e:
        app.logger.error(f"Error getting stats: {e}")
        return jsonify([]), 500

def format_size(size_bytes):
    """Format file size in bytes to human-readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ("B", "KB", "MB", "GB", "TB")
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"

@app.route('/join-channel/<channel_name>', methods=['POST'])
def join_channel(channel_name):
    """Join a channel"""
    try:
        if not bot_instance:
            return jsonify({'success': False, 'message': 'Bot is not running'})
            
        # Call the bot's join_channel method
        coroutine = bot_instance.join_channel(channel_name)
        asyncio.run_coroutine_threadsafe(coroutine, bot_instance.loop)
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error joining channel: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/leave-channel/<channel_name>', methods=['POST'])
def leave_channel(channel_name):
    """Leave a channel"""
    try:
        if not bot_instance:
            return jsonify({'success': False, 'message': 'Bot is not running'})
            
        # Call the bot's leave_channel method
        coroutine = bot_instance.leave_channel(channel_name)
        asyncio.run_coroutine_threadsafe(coroutine, bot_instance.loop)
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error leaving channel: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/bot-status-detailed')  # Legacy endpoint
@app.route('/api/bot-status')  # New endpoint to match frontend code
def bot_status_api():
    """Enhanced API endpoint for checking bot status with more detailed information"""
    try:
        # Check if PID file exists
        if not os.path.exists('bot.pid'):
            return jsonify({
                'running': False,
                'connected': False,
                'tts_enabled': enable_tts,
                'pid': None,
                'uptime': None,
                'error': None,
                'last_check': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
        # Read PID from file
        with open('bot.pid', 'r') as f:
            pid_data = f.read().strip()
            
        # Handle different PID file formats (some have ID|PID format)
        if '|' in pid_data:
            pid = int(pid_data.split('|')[1])
        else:
            pid = int(pid_data)
            
        # Check if process is actually running
        is_running = False
        uptime = None
        
        try:
            # On Unix/Linux
            if os.name == 'posix':
                # Check if process exists
                os.kill(pid, 0)
                is_running = True
                
                # Get process start time if possible
                if hasattr(os, 'sysconf') and os.path.exists(f'/proc/{pid}'):
                    start_time = os.path.getmtime(f'/proc/{pid}')
                    uptime = time.time() - start_time
            
            # On Windows
            elif os.name == 'nt':
                process = psutil.Process(pid)
                is_running = process.is_running()
                uptime = time.time() - process.create_time()
                
            if uptime:
                # Format uptime nicely
                m, s = divmod(int(uptime), 60)
                h, m = divmod(m, 60)
                d, h = divmod(h, 24)
                uptime_str = f"{d}d {h}h {m}m {s}s" if d > 0 else f"{h}h {m}m {s}s"
            else:
                uptime_str = "Unknown"
                
        except (ProcessLookupError, psutil.NoSuchProcess):
            # Process doesn't exist
            is_running = False
            uptime_str = None
            
        # Check actual IRC/Twitch connection status
        connected_status = False
        if is_running:
            # Method 1: Check database heartbeat (most reliable)
            try:
                conn = sqlite3.connect(db_file)
                c = conn.cursor()
                c.execute("SELECT value FROM bot_status WHERE key = 'last_heartbeat'")
                last_heartbeat = c.fetchone()
                conn.close()
                
                if last_heartbeat:
                    # Check if heartbeat is recent (within last 2 minutes)
                    last_time = datetime.strptime(last_heartbeat[0], '%Y-%m-%d %H:%M:%S')
                    heartbeat_age = (datetime.now() - last_time).total_seconds()
                    connected_status = heartbeat_age < 120  # 2 minutes
                    app.logger.info(f"Found database heartbeat from {last_time}, age: {heartbeat_age}s")
                else:
                    app.logger.info("No database heartbeat found")
            except Exception as e:
                # Log the error for debugging
                app.logger.error(f"Error checking database heartbeat: {e}")
                
            # Method 2: Check heartbeat file if database check failed
            if not connected_status and os.path.exists('bot_heartbeat.json'):
                try:
                    with open('bot_heartbeat.json', 'r') as f:
                        heartbeat_data = json.load(f)
                        heartbeat_timestamp = heartbeat_data.get('timestamp', 0)
                        
                        # Check if heartbeat is recent (within last 2 minutes)
                        heartbeat_age = time.time() - heartbeat_timestamp
                        connected_status = heartbeat_age < 120  # 2 minutes
                        app.logger.info(f"Found file heartbeat, age: {heartbeat_age}s")
                        
                        # If we have channels in the heartbeat file, consider connected
                        channels = heartbeat_data.get('channels', [])
                        if channels and not connected_status:
                            app.logger.info(f"Bot has {len(channels)} channels but heartbeat expired")
                            connected_status = True  # If we have channels, assume connected                    
                except Exception as e:
                    app.logger.error(f"Error checking heartbeat file: {e}")
            
            # Method 3: Fall back to process status if all else fails
            if not connected_status:
                app.logger.info("Falling back to process status for connection check")
                connected_status = is_running
            
        return jsonify({
            'running': is_running,
            'connected': connected_status,
            'tts_enabled': enable_tts,
            'pid': pid,
            'uptime': uptime_str,
            'error': None,
            'last_check': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        # Log the full error
        print(f"Error in bot status API: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'running': False,
            'connected': False,
            'tts_enabled': enable_tts,
            'pid': None,
            'uptime': None,
            'error': str(e),
            'last_check': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

def format_uptime(seconds):
    """Formats uptime in seconds to a human-readable string"""
    if seconds is None:
        return None
        
    try:
        seconds = float(seconds)
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if days > 0:
            return f"{int(days)}d {int(hours)}h {int(minutes)}m"
        elif hours > 0:
            return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
        elif minutes > 0:
            return f"{int(minutes)}m {int(seconds)}s"
        else:
            return f"{int(seconds)}s"
    except Exception as e:
        app.logger.error(f"Error formatting uptime: {e}")
        return str(seconds)

def get_bot_pid():
    """Get the bot process ID from the PID file"""
    if not os.path.exists('bot.pid'):
        return None
        
    try:
        with open('bot.pid', 'r') as f:
            content = f.read().strip()
            # Handle both formats: plain PID or "1|<pid>"
            if '|' in content:
                _, pid = content.split('|', 1)
                return int(pid)
            else:
                # Try to parse it as a direct integer
                return int(content)
    except (ValueError, OSError):
        return None

def is_bot_running():
    """Check if the bot process is actually running"""
    pid = get_bot_pid()
    if pid is None:
        return False
    
    try:
        # This sends no actual signal but checks if process exists
        os.kill(pid, 0)
        return True
    except OSError:
        # Process doesn't exist
        if os.path.exists('bot.pid'):
            try:
                os.remove('bot.pid')  # Clean up stale PID file
            except:
                pass
        return False

def check_and_cleanup_bot_state():
    """Check bot state on startup and clean up if needed"""
    if os.path.exists('bot.pid'):
        if not is_bot_running():
            app.logger.warning("Found stale bot.pid file on startup, removing")
            try:
                os.remove('bot.pid')
            except:
                pass
            app.logger.info("Stale bot.pid file removed")
        else:
            app.logger.info(f"Bot appears to be running with PID {get_bot_pid()}")
    
    # Also check heartbeat file
    if os.path.exists('bot_heartbeat.json'):
        try:
            with open('bot_heartbeat.json', 'r') as f:
                heartbeat_data = json.load(f)
                timestamp = heartbeat_data.get('timestamp', 0)
                
                # If heartbeat is stale (over 5 minutes old)
                if time.time() - timestamp > 300:
                    app.logger.warning("Found stale bot_heartbeat.json file, removing")
                    try:
                        os.remove('bot_heartbeat.json')
                    except:
                        pass
                    app.logger.info("Stale bot_heartbeat.json file removed")
        except Exception as e:
            app.logger.warning(f"Error processing heartbeat file: {e}")
            # If file exists but is corrupted, remove it
            try:
                os.remove('bot_heartbeat.json')
                app.logger.info("Corrupted bot_heartbeat.json file removed")
            except:
                pass

# Call this during app initialization
check_and_cleanup_bot_state()

# Add more verbose debug endpoint
@app.route('/debug/bot-status')
def debug_bot_status():
    """Detailed debug endpoint for bot status with all detection methods"""
    debug_info = {
        "pid_file": {
            "exists": os.path.exists('bot.pid'),
            "content": None,
            "parsed_pid": None,
            "process_exists": False
        },
        "heartbeat_file": {
            "exists": os.path.exists('bot_heartbeat.json'),
            "content": None,
            "timestamp": None,
            "timestamp_age_seconds": None,
            "is_recent": False
        },
        "conclusion": {
            "is_running": False,
            "is_connected": False
        }
    }
    
    # Check PID file
    if debug_info["pid_file"]["exists"]:
        try:
            with open('bot.pid', 'r') as f:
                content = f.read().strip()
                debug_info["pid_file"]["content"] = content
                
                try:
                    if '|' in content:
                        _, pid = content.split('|', 1)
                        pid = int(pid)
                    else:
                        pid = int(content)
                        
                    debug_info["pid_file"]["parsed_pid"] = pid
                    
                    # Check if process exists
                    try:
                        os.kill(pid, 0)
                        debug_info["pid_file"]["process_exists"] = True
                        debug_info["conclusion"]["is_running"] = True
                    except OSError:
                        debug_info["pid_file"]["process_exists"] = False
                except ValueError:
                    debug_info["pid_file"]["parsed_pid"] = None
        except Exception as e:
            debug_info["pid_file"]["error"] = str(e)
    
    # Check heartbeat file
    if debug_info["heartbeat_file"]["exists"]:
        try:
            with open('bot_heartbeat.json', 'r') as f:
                content = json.load(f)
                debug_info["heartbeat_file"]["content"] = content
                
                timestamp = content.get('timestamp', 0)
                debug_info["heartbeat_file"]["timestamp"] = timestamp
                
                age = time.time() - timestamp
                debug_info["heartbeat_file"]["timestamp_age_seconds"] = age
                debug_info["heartbeat_file"]["is_recent"] = age < 120
                
                if debug_info["heartbeat_file"]["is_recent"]:
                    debug_info["conclusion"]["is_running"] = True
                    debug_info["conclusion"]["is_connected"] = True
        except Exception as e:
            debug_info["heartbeat_file"]["error"] = str(e)
    
    return jsonify(debug_info)

@app.route('/api/channels')
def channels_api():
    """Enhanced API endpoint for getting channel information with connection status"""
    try:
        # Get configured channels from database
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get channel configs with TTS and join status
        c.execute("SELECT channel_name, tts_enabled, join_channel FROM channel_configs")
        configured_channels = [dict(row) for row in c.fetchall()]
        
        # Get currently connected channels from bot status
        try:
            c.execute("SELECT value FROM bot_status WHERE key = 'connected_channels'")
            connected_result = c.fetchone()
            
            if connected_result and connected_result[0]:
                connected_channels = connected_result[0].split(',')
            else:
                connected_channels = []
        except sqlite3.OperationalError:
            # If bot_status table doesn't exist yet, use empty list
            app.logger.warning("bot_status table doesn't exist yet, using empty connected channels list")
            connected_channels = []
        
        # Get message counts
        c.execute("SELECT channel, COUNT(*) FROM messages GROUP BY channel")
        message_counts = {row[0]: row[1] for row in c.fetchall()}
        
        # Get last activity
        c.execute("SELECT channel, MAX(timestamp) FROM messages GROUP BY channel")
        last_activities = {row[0]: row[1] for row in c.fetchall()}
            
        conn.close()
        
        # Combine information
        channel_info = []
        for channel in configured_channels:
            channel_name = channel['channel_name']
            channel_info.append({
                'name': channel_name,
                'tts_enabled': bool(channel['tts_enabled']),
                'configured_to_join': bool(channel['join_channel']),
                'currently_connected': channel_name in connected_channels,
                'messages_sent': message_counts.get(channel_name, 0),
                'last_activity': last_activities.get(channel_name, 'Never')
            })
            
        return jsonify(channel_info)
        
    except Exception as e:
        print(f"Error in channels API: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify([])

@app.route('/trigger-tts', methods=['POST'])
def trigger_tts():
    """Trigger a TTS message from the web interface"""
    global enable_tts
    if not enable_tts:
        return jsonify({'success': False, 'error': 'TTS is not enabled'})
    
    try:
        data = request.json
        channel = data.get('channel', 'web')
        message = data.get('message')
        
        if not message:
            return jsonify({'success': False, 'error': 'Missing message'})
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        
        output_dir = os.path.join('static', 'outputs', channel)
        os.makedirs(output_dir, exist_ok=True)
        
        # Use asyncio.run to run the async function in a sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success, output_file = loop.run_until_complete(process_text(channel, message))
        loop.close()
        
        if success and output_file and os.path.exists(output_file):
            conn = sqlite3.connect(db_file)
            c = conn.cursor()
            
            c.execute("""
                CREATE TABLE IF NOT EXISTS tts_logs (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    voice_preset TEXT,
                    file_path TEXT,
                    message TEXT
                )
            """)
            
            voice_preset = "v2/en_speaker_0"
            
            c.execute(
                "INSERT INTO tts_logs (channel, timestamp, voice_preset, file_path, message) VALUES (?, ?, ?, ?, ?)",
                (channel, timestamp, voice_preset, output_file, message)
            )
            conn.commit()
            new_id = c.lastrowid
            conn.close()
            
            # Send WebSocket notification
            # Only send one event to avoid duplicate refreshes
            socketio.emit("new_tts_entry", {"id": new_id})
            
            return jsonify({
                'success': True,
                'file_path': output_file,
                'message': 'TTS message generated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to generate TTS audio'
            })
    except Exception as e:
        app.logger.error(f"Error generating TTS: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reconnect-bot', methods=['POST'])
def reconnect_bot_api():
    """API endpoint to force a bot reconnection"""
    try:
        # Check if bot is running
        if not os.path.exists('bot.pid'):
            return jsonify({
                'success': False,
                'message': 'Bot is not running'
            })
            
        # Get PID
        with open('bot.pid', 'r') as f:
            pid_data = f.read().strip()
            
        if '|' in pid_data:
            bot_id = pid_data.split('|')[0]
        else:
            bot_id = '1'  # Default bot ID
            
        # Signal the bot to reconnect
        # Since we can't directly control the bot's connection from here,
        # we'll add a command to the database that the bot will check
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        
        # Create command table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS bot_commands
                    (id INTEGER PRIMARY KEY, bot_id TEXT, command TEXT, 
                     params TEXT, created_at TEXT, executed INTEGER)''')
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('''INSERT INTO bot_commands 
                    (bot_id, command, params, created_at, executed)
                    VALUES (?, ?, ?, ?, ?)''',
                 (bot_id, 'reconnect', '', now, 0))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Reconnect command sent to bot'
        })
        
    except Exception as e:
        print(f"Error in reconnect API: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': str(e)
        })

@app.route('/api/tts-stats')
def tts_stats_api():
    """API endpoint for TTS statistics"""
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        
        # Get current date and time
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
        week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
        
        # Count TTS messages for today
        c.execute("SELECT COUNT(*) FROM tts_logs WHERE timestamp >= ?", (today_start,))
        today_count = c.fetchone()[0]
        
        # Count TTS messages for this week
        c.execute("SELECT COUNT(*) FROM tts_logs WHERE timestamp >= ?", (week_start,))
        week_count = c.fetchone()[0]
        
        # Count total TTS messages
        c.execute("SELECT COUNT(*) FROM tts_logs")
        total_count = c.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'today': today_count,
            'week': week_count,
            'total': total_count
        })
    except Exception as e:
        print(f"Error getting TTS stats: {e}")
        return jsonify({
            'today': 0,
            'week': 0,
            'total': 0,
            'error': str(e)
        })

@app.route('/api/system-info')
def system_info_api():
    """API endpoint for system information"""
    try:
        version = "1.0.0"  # Replace with actual version
        
        # Get bot uptime if running
        uptime_str = "Not running"
        if is_bot_running():
            pid = get_bot_pid()
            if pid:
                try:
                    process = psutil.Process(pid)
                    uptime = time.time() - process.create_time()
                    m, s = divmod(int(uptime), 60)
                    h, m = divmod(m, 60)
                    d, h = divmod(h, 24)
                    uptime_str = f"{d}d {h}h {m}m {s}s" if d > 0 else f"{h}h {m}m {s}s"
                except:
                    uptime_str = "Running (uptime unknown)"
        
        # Get message count
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM messages")
        message_count = c.fetchone()[0]
        
        # Get channel count
        c.execute("SELECT COUNT(*) FROM channel_configs")
        channel_count = c.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'version': version,
            'uptime': uptime_str,
            'message_count': message_count,
            'channel_count': channel_count
        })
    except Exception as e:
        print(f"Error getting system info: {e}")
        return jsonify({
            'version': '1.0.0',
            'uptime': 'Error',
            'message_count': 0,
            'channel_count': 0,
            'error': str(e)
        })

@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    """Stop the bot process"""
    try:
        # Check if bot is running
        if not is_bot_running():
            return jsonify({
                'success': False, 
                'message': 'Bot is not running'
            })
        
        pid = get_bot_pid()
        if not pid:
            return jsonify({
                'success': False,
                'message': 'Could not determine bot process ID'
            })
        
        app.logger.info(f"Attempting to stop bot process with PID {pid}")
        
        # Try SIGTERM first (graceful shutdown)
        try:
            os.kill(pid, signal.SIGTERM)
            app.logger.info(f"SIGTERM signal sent to process {pid}")
            
            # Wait up to 5 seconds for the process to exit
            for _ in range(10):
                time.sleep(0.5)
                try:
                    # Check if process still exists
                    os.kill(pid, 0)
                except OSError:
                    # Process no longer exists
                    app.logger.info(f"Process {pid} has terminated successfully")
                    
                    # Remove PID file
                    if os.path.exists('bot.pid'):
                        os.remove('bot.pid')
                    
                    return jsonify({
                        'success': True,
                        'message': 'Bot stopped successfully'
                    })
            
            # If we're here, process didn't exit with SIGTERM
            app.logger.warning(f"Process {pid} did not terminate with SIGTERM, sending SIGKILL")
            os.kill(pid, signal.SIGKILL)
            
            # Remove PID file
            if os.path.exists('bot.pid'):
                os.remove('bot.pid')
            
            return jsonify({
                'success': True,
                'message': 'Bot forcefully terminated'
            })
        except Exception as e:
            app.logger.error(f"Error stopping bot: {e}")
            return jsonify({
                'success': False,
                'message': f'Error stopping bot: {str(e)}'
            })
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        app.logger.error(f"Error in stop_bot: {e}\n{trace}")
        return jsonify({
            'success': False,
            'message': str(e)
        })

def is_bot_healthy():
    """Check if the bot is not only running but also responsive"""
    if not is_bot_running():
        return False
    
    # Check heartbeat file if it exists
    try:
        if os.path.exists('bot_heartbeat.json'):
            with open('bot_heartbeat.json', 'r') as f:
                heartbeat = json.load(f)
                last_time = datetime.fromisoformat(heartbeat.get('time', '2000-01-01T00:00:00'))
                if datetime.now() - last_time > timedelta(minutes=5):
                    # Heartbeat is stale
                    return False
                return True
    except:
        pass
    
    return True  # Default to true if process exists

@app.route('/debug/tts-status')
def debug_tts_status():
    """Debug endpoint to check TTS status"""
    try:
        # Check if bot is running
        is_running = is_bot_running()
        pid = get_bot_pid() if is_running else None
        
        # Get any available TTS logs
        tts_logs = []
        try:
            conn = sqlite3.connect(db_file)
            c = conn.cursor()
            c.execute("SELECT * FROM tts_logs ORDER BY timestamp DESC LIMIT 10")
            tts_logs = [dict(timestamp=row[0], channel=row[1], message=row[2]) for row in c.fetchall()]
            conn.close()
        except Exception as e:
            tts_logs = [{"error": str(e)}]
        
        # Try to determine TTS status in the running process
        tts_enabled = "Unknown"
        if is_running and pid:
            try:
                # Look for command line arguments of the process
                process = psutil.Process(pid)
                cmdline = process.cmdline()
                tts_enabled = "--tts" in cmdline
            except Exception as e:
                tts_enabled = f"Error checking: {e}"
        
        return jsonify({
            'bot_running': is_running,
            'pid': pid,
            'tts_enabled': tts_enabled,
            'tts_logs': tts_logs,
            'command_line': cmdline if 'cmdline' in locals() else None
        })
    except Exception as e:
        return jsonify({
            'error': str(e)
        })

def ensure_db_setup():
    """Make sure all required tables exist"""
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    
    # Create channel_configs table if it doesn't exist
    c.execute("""
    CREATE TABLE IF NOT EXISTS channel_configs (
        channel_name TEXT PRIMARY KEY,
        tts_enabled INTEGER DEFAULT 0,
        join_channel INTEGER DEFAULT 1,
        last_joined TEXT
    )
    """)
    
    # Create TTS logs table if it doesn't exist
    c.execute("""
    CREATE TABLE IF NOT EXISTS tts_logs (
        timestamp TEXT,
        channel TEXT,
        message TEXT
    )
    """)
    
    conn.commit()
    conn.close()

# Call this at startup
ensure_db_setup()

@app.route('/debug/channels')
def debug_channels():
    """Debug endpoint to check channel configuration"""
    try:
        # Connect to DB and get channels
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get channel data with more details
        c.execute("""
            SELECT channel_name, tts_enabled, join_channel, 
                   (SELECT COUNT(*) FROM messages WHERE channel = channel_name) as message_count
            FROM channel_configs
        """)
        channels = [dict(row) for row in c.fetchall()]
        
        # Get database schema info
        c.execute("PRAGMA table_info(channel_configs)")
        schema = [dict(row) for row in c.fetchall()]
        
        # Check if table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='channel_configs'")
        table_exists = c.fetchone() is not None
        
        conn.close()
        
        return jsonify({
            'channels': channels,
            'schema': schema,
            'table_exists': table_exists,
            'count': len(channels)
        })
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        })

@app.route('/check_existing_instance')
def check_existing_instance():
    """Check if bot is already running from launch script and sync UI state"""
    try:
        # Look for existing bot processes
        for process in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = process.info['cmdline']
                if cmdline and 'ansv.py' in ' '.join(cmdline):
                    # Found a running bot instance
                    pid = process.info['pid']
                    tts_enabled = "--tts" in cmdline
                    
                    # Write PID file if it doesn't exist
                    if not os.path.exists('bot.pid'):
                        with open('bot.pid', 'w') as f:
                            f.write(f"1|{pid}")
                    
                    return jsonify({
                        'success': True,
                        'pid': pid,
                        'tts_enabled': tts_enabled,
                        'message': f'Bot already running with PID {pid}'
                    })
            except:
                continue
                
        return jsonify({
            'success': False,
            'message': 'No existing bot instances found'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/models')
def api_models():
    """Get available models with metadata"""
    try:
        models = get_available_models()
        return jsonify(models)
    except Exception as e:
        app.logger.error(f"Error getting models: {e}")
        return jsonify({"error": str(e)}), 500

# Looking for routes like /dashboard, /home, or similar that might conflict
@app.route('/dashboard')
def dashboard():
    # This route may exist and potentially conflict with the main route
    # Need to check what template it renders and what data it passes
    pass

@app.route('/api/flush-tts-entries', methods=['POST'])
def flush_tts_entries():
    """Remove TTS entries where the audio file doesn't exist anymore"""
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        
        # Get all TTS entries
        c.execute("SELECT message_id, file_path FROM tts_logs")
        entries = c.fetchall()
        
        # Track statistics
        total = len(entries)
        removed = 0
        
        # Check each entry
        for entry_id, file_path in entries:
            if not file_path:
                # If file path is None or empty, remove the entry
                c.execute("DELETE FROM tts_logs WHERE message_id = ?", (entry_id,))
                removed += 1
                continue
                
            # Normalize the path
            if file_path.startswith('static/'):
                full_path = os.path.join(os.getcwd(), file_path)
            else:
                full_path = os.path.join(os.getcwd(), 'static', file_path)
            
            # Check if file exists
            if not os.path.exists(full_path):
                # If file doesn't exist, remove the entry
                c.execute("DELETE FROM tts_logs WHERE message_id = ?", (entry_id,))
                removed += 1
        
        # Commit changes and close connection
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Cleaned up TTS entries ({removed} of {total} entries removed)',
            'removed': removed,
            'total': total
        })
    except Exception as e:
        app.logger.error(f"Error flushing TTS entries: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500