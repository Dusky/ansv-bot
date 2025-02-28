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
enable_tts = False
markov_handler.load_models()

#logging.getLogger('werkzeug').disabled = True
logging.getLogger('werkzeug').setLevel(logging.ERROR)
#app.logger.setLevel(logging.ERROR)

# Add thread locking for bot control
bot_lock = Lock()

@app.route('/send_markov_message/<channel_name>', methods=['POST'])
def send_markov_message(channel_name):
    """Send a Markov-generated message to a channel"""
    global bot_instance
    
    # Better detection of bot instance availability
    if not bot_instance:
        # Check if the bot is running in a different process
        if os.path.exists('bot.pid'):
            try:
                with open('bot.pid', 'r') as pid_file:
                    pid = int(pid_file.read().strip())
                    # Process exists, so bot is running
                    os.kill(pid, 0)
                    
                    # Since bot is running but bot_instance is None, we need to reconnect
                    app.logger.warning(f"{YELLOW}Bot is running but instance not available in web context{RESET}")
                    
                    # Use direct file-based communication with the bot
                    try:
                        # Generate a message via the web interface's markov handler
                        message = markov_handler.generate_message(channel_name)
                        if not message:
                            return jsonify({'success': False, 'message': 'Failed to generate message'})
                            
                        # Store the message request in a file for the bot to pick up
                        request_data = {
                            'action': 'send_message',
                            'channel': channel_name,
                            'message': message,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        with open('bot_message_request.json', 'w') as f:
                            import json
                            json.dump(request_data, f)
                            
                        return jsonify({'success': True, 'message': 'Message request submitted'})
                    except Exception as e:
                        app.logger.error(f"Error communicating with bot: {e}")
                        return jsonify({'success': False, 'message': f'Error: {str(e)}'})
            except:
                # Process not running, remove stale PID file
                try:
                    os.remove('bot.pid')
                except:
                    pass
                return jsonify({'success': False, 'message': 'Bot is not running'})
        return jsonify({'success': False, 'message': 'Bot instance is not initialized'})
    
    # Original code for when bot_instance is available
    try:
        message = bot_instance.generate_message(channel_name)
        if message:
            # Ensure that send_message_to_channel is an async method
            coroutine = bot_instance.send_message_to_channel(channel_name, message)
            # Properly schedule the coroutine in the bot's event loop
            asyncio.run_coroutine_threadsafe(coroutine, bot_instance.loop)
            return jsonify({'success': True, 'message': 'Message sent successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to generate message'})
    except Exception as e:
        app.logger.error(f"Error sending message: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/bot_status')  # Keep for backwards compatibility
@app.route('/api/bot-status')  # Standardized endpoint
def bot_status():
    """Check if the bot is running with enhanced TTS detection and connection status"""
    try:
        is_running = False
        tts_enabled = False
        is_connected = False
        uptime = None
        connected_channels = []
        
        # Check if bot process is running
        if os.path.exists('bot.pid'):
            try:
                pid = get_bot_pid()
                if pid:
                    # Check if process exists
                    os.kill(pid, 0)
                    is_running = True
                    
                    # Check if TTS is enabled by examining the command line
                    try:
                        import psutil
                        process = psutil.Process(pid)
                        cmdline = process.cmdline()
                        tts_enabled = "--tts" in cmdline
                    except:
                        # Default to false if we can't determine
                        pass
            except:
                pass
        
        # Check heartbeat for connection status and uptime
        if is_running and os.path.exists('bot_heartbeat.json'):
            try:
                with open('bot_heartbeat.json', 'r') as f:
                    heartbeat_data = json.load(f)
                    
                    # Check heartbeat timestamp - consider stale if older than 2 minutes
                    if time.time() - heartbeat_data.get('timestamp', 0) < 120:
                        is_connected = True
                        uptime = heartbeat_data.get('uptime')
                        connected_channels = heartbeat_data.get('channels', [])
            except Exception as e:
                app.logger.warning(f"Failed to read heartbeat file: {e}")
                
        return jsonify({
            "running": is_running,
            "connected": is_connected,
            "tts_enabled": tts_enabled,
            "uptime": format_uptime(uptime) if uptime else None,
            "channels": connected_channels
        })
    except Exception as e:
        app.logger.error(f"Error checking bot status: {e}")
        return jsonify({"running": False, "error": str(e)})


@app.route('/toggle_tts', methods=['POST'])
@app.route('/api/toggle-tts', methods=['POST'])  # Standardized endpoint
def toggle_tts():
    try:
        global enable_tts
        
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
            if 'enable_tts' in data:
                enable_tts = bool(data['enable_tts'])
            else:
                enable_tts = not enable_tts
        else:
            # Form submission
            form_value = request.form.get('enable_tts')
            if form_value is not None:
                enable_tts = (form_value == 'on' or form_value == 'true')
            else:
                enable_tts = not enable_tts
                
        # Return JSON for API requests, redirect for form submissions
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': True, 'tts_enabled': enable_tts})
        else:
            return redirect(url_for('bot_control'))
    except Exception as e:
        app.logger.error(f"Error toggling TTS: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': False, 'error': str(e)})
        else:
            flash(f"Error toggling TTS: {e}", "error")
            return redirect(url_for('bot_control'))

def run_bot(enable_tts=False):
    global bot_instance
    with bot_lock:  # Prevent concurrent access
        if not bot_instance:
            db_file = "messages.db"
            ensure_db_setup(db_file)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            bot_instance = setup_bot(db_file, rebuild_cache=False, enable_tts=enable_tts)
            loop.run_until_complete(bot_instance.start())


@app.route('/start-bot', methods=['POST'])
def start_bot_dash():
    """Alternative route for /start_bot"""
    return start_bot()

@app.route('/stop-bot', methods=['POST'])
def stop_bot_dash():
    """Alternative route for /stop_bot"""
    return stop_bot()

@app.route('/start_bot', methods=['POST'])
def start_bot():
    """Start the bot process with enhanced error handling"""
    try:
        # Handle both JSON and form data with better logging
        if request.is_json:
            data = request.get_json()
            enable_tts = data.get('enable_tts', False)
            app.logger.info(f"Starting bot with TTS: {enable_tts} (from JSON)")
        else:
            # Form handling is different - checkboxes come as 'on' if checked
            enable_tts = request.form.get('enable_tts') == 'on'
            app.logger.info(f"Starting bot with TTS: {enable_tts} (from form)")
            
        # Check if bot is already running
        if is_bot_running():
            return jsonify({
                'success': False,
                'message': 'Bot is already running'
            })
        
        # Start bot using the direct path to ansv.py (main bot file) instead of run_bot.py
        success, message, log_output = start_bot_directly(enable_tts)
        
        return jsonify({
            'success': success,
            'message': message,
            'log': log_output
        })
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        app.logger.error(f"Error starting bot: {e}\n{trace}")
        return jsonify({
            'success': False,
            'message': f"Error starting bot: {str(e)}",
            'trace': trace
        })

def start_bot_directly(enable_tts=False):
    """Start the bot directly using ansv.py with proper command line arguments"""
    try:
        # Get python executable
        python_executable = sys.executable
        
        # Get the direct path to the main bot file
        bot_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ansv.py')
        
        # Check if the file exists
        if not os.path.exists(bot_file):
            return False, f"Bot file not found at {bot_file}", ""
        
        # Prepare command line arguments based on settings
        cmd_args = [python_executable, bot_file]
        
        # Add arguments based on settings - ENSURE BOOLEAN CONVERSION
        if enable_tts is True:  # Explicitly check for True
            app.logger.info("TTS enabled, adding --tts flag")
            cmd_args.append('--tts')
        else:
            app.logger.info("TTS disabled, not adding --tts flag")
        
        # Create a timestamp for log file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = f"bot_start_{timestamp}.log"
        
        app.logger.info(f"Starting bot with command: {' '.join(cmd_args)}")
        app.logger.info(f"Output will be captured in: {log_file}")
        
        # Check if another instance might be running the web interface
        web_port = 5001  # Default web port for the bot
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', web_port))
        sock.close()
        
        if result == 0:
            # Port is in use - likely another instance is running the web interface
            app.logger.warning(f"Port {web_port} is already in use - possible web interface running")
        
        # Launch the process with output directed to a log file
        with open(log_file, 'w') as f:
            # Write a header to the log file
            f.write(f"=== Bot Start Log: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            f.write(f"Command: {' '.join(cmd_args)}\n\n")
            f.flush()
            
            # Start the process
            process = subprocess.Popen(
                cmd_args,
                stdout=f,
                stderr=f,
                text=True,
                start_new_session=True
            )
            
            # Give it time to start
            time.sleep(3)
            
            # Check if the process is still running
            if process.poll() is None:
                # Process is still running, but is it working?
                with open(log_file, 'r') as log_f:
                    log_content = log_f.read()
                    # Look for indicators of successful startup
                    if "Error" in log_content or "Exception" in log_content:
                        # Log contains error messages
                        return False, "Bot process started but encountered errors", log_content
                
                # Write PID file with proper format - critical step!
                with open('bot.pid', 'w') as pid_file:
                    pid_file.write(f"1|{process.pid}")
                
                # Read log output
                with open(log_file, 'r') as log_f:
                    log_output = log_f.read()
                
                return True, f"Bot started with PID {process.pid}", log_output
            else:
                # Process exited quickly, likely an error
                with open(log_file, 'r') as log_f:
                    log_output = log_f.read()
                
                return False, f"Bot process exited with code {process.returncode}", log_output
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        app.logger.error(f"Error in start_bot_directly: {e}\n{trace}")
        return False, str(e), trace

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
    return render_template('settings.html',  last_id=None, theme=theme)

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
        
        # Map the theme parameter to a valid Bootswatch theme or custom theme
        valid_themes = {
            'dark': 'darkly', 
            'light': 'flatly',
            'darkly': 'darkly',
            'flatly': 'flatly',
            'cyborg': 'cyborg',
            'slate': 'slate',
            'solar': 'solar',
            'superhero': 'superhero',
            'vapor': 'vapor',
            'ansv': 'ansv'  # Our custom ANSV theme
        }
        
        theme_to_set = valid_themes.get(theme, 'darkly')  # Default to darkly if invalid
        
        # Create a response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # For AJAX requests, return JSON
            resp = jsonify({'success': True, 'theme': theme_to_set})
        else:
            # For direct requests, redirect to the main page
            resp = make_response(redirect(url_for("main")))
            
        # Set the cookie in either case
        resp.set_cookie("theme", theme_to_set, max_age=30 * 24 * 60 * 60)
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
        data = request.json
        model = data.get('model')
        
        # Log the request
        app.logger.info(f"Generating message with model: {model}")
        
        # Use the existing markov_handler to generate the message
        message = markov_handler.generate_message(model)
            
        if message:
            return jsonify({"message": message})
        else:
            return jsonify({"error": "Failed to generate message"}), 400
    except Exception as e:
        app.logger.error(f"Error generating message: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/available-models')
def available_models():
    """Get a list of available Markov models"""
    try:
        # Get all models from the cache directory
        models = []
        if os.path.exists('cache'):
            for file in os.listdir('cache'):
                if file.endswith('_model.json'):
                    model_name = file.replace('_model.json', '')
                    if model_name != 'general_markov':  # Skip the general model
                        models.append(model_name)
        
        app.logger.info(f"Available models: {models}")
        return jsonify(models)
    except Exception as e:
        app.logger.error(f"Error getting available models: {e}")
        return jsonify([])


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
        )

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
        if not bot_instance:
            return jsonify([])
            
        channels = []
        
        # Open the database
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Get channel configuration
        cursor.execute("SELECT channel_name, tts_enabled FROM channel_configs")
        channel_configs = {row[0]: {'tts_enabled': bool(row[1])} for row in cursor.fetchall()}
        
        # Get message counts
        cursor.execute("SELECT channel, COUNT(*) FROM messages GROUP BY channel")
        message_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get last activity
        cursor.execute("SELECT channel, MAX(timestamp) FROM messages GROUP BY channel")
        last_activities = {row[0]: row[1] for row in cursor.fetchall()}
        
        conn.close()
        
        # Get connected channels from bot heartbeat or bot status
        connected_channels = []
        
        # Method 1: Try to get from heartbeat file first (most reliable)
        if os.path.exists('bot_heartbeat.json'):
            try:
                with open('bot_heartbeat.json', 'r') as f:
                    heartbeat_data = json.load(f)
                    if 'channels' in heartbeat_data:
                        connected_channels = [c.lstrip('#') for c in heartbeat_data['channels']]
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
                connected_channels = [c.lstrip('#') for c in getattr(bot_instance, '_joined_channels', [])]
            except Exception as e:
                app.logger.warning(f"Failed to get channels from bot instance: {e}")
                
        app.logger.info(f"Found connected channels: {connected_channels}")
                
        # Format the channel data
        for channel_name, config in channel_configs.items():
            # Check if channel is connected
            connected = channel_name in connected_channels
            
            channels.append({
                'name': channel_name,
                'connected': connected,
                'tts_enabled': config['tts_enabled'],
                'messages_sent': message_counts.get(channel_name, 0),
                'last_activity': last_activities.get(channel_name, 'Never')
            })
            
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
        
        # Prepare query with optional channel filter
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
            formatted_entries.append({
                'id': row['id'],
                'channel': row['channel'],
                'timestamp': row['timestamp'],
                'voice_preset': row['voice_preset'],
                'file_path': row['file_path'],
                'message': row['message']
            })
            
        return jsonify(formatted_entries)
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
def get_build_times():
    try:
        # Try to read build times from cache file
        cache_file = os.path.join('cache', 'cache_build_times.json')
        
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                build_times = json.load(f)
            return jsonify(build_times)
        else:
            # If file doesn't exist, return empty array
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
        
        # Send message through normal bot flow
        coroutine = bot_instance.send_message_to_channel(channel, message)
        asyncio.run_coroutine_threadsafe(coroutine, bot_instance.loop)
        
        # Process TTS
        tts_file, new_id = process_text(message, channel, db_file)
        
        if not tts_file or not new_id:
            raise Exception("TTS processing failed")
        
        # Notify all clients BEFORE returning
        socketio.emit('new_tts_entry', {'id': new_id})
        
        return jsonify({
            'success': True,
            'message': 'TTS processed successfully',
            'tts_file': tts_file,
            'new_id': new_id  # Return the database ID
        })
    except Exception as e:
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
    """Rebuild the Markov model for a specific channel"""
    try:
        app.logger.info(f"Rebuilding model for channel: {channel_name}")
        
        if markov_handler:
            success = markov_handler.build_model_for_channel(channel_name)
            if success:
                return jsonify({'success': True, 'message': f'Model for {channel_name} rebuilt successfully'})
            else:
                return jsonify({'success': False, 'message': 'Failed to rebuild channel model'}), 400
        else:
            return jsonify({'success': False, 'message': 'Markov handler not initialized'}), 500
    except Exception as e:
        app.logger.error(f"Error rebuilding channel model: {e}")
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
def bot_status_api():
    """Enhanced API endpoint for checking bot status with more detailed information"""
    try:
        # Check if PID file exists
        if not os.path.exists('bot.pid'):
            return jsonify({
                'running': False,
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
                import psutil
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
            
        # Check actual IRC/Twitch connection status via database if process is running
        connected_status = False
        if is_running:
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
            except:
                # Fall back to process status if we can't check heartbeat
                connected_status = is_running
            
        return jsonify({
            'running': is_running,
            'connected': connected_status,
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

# Call this during app initialization
check_and_cleanup_bot_state()

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
        channel = data.get('channel', 'web')  # Default to 'web' if channel not specified
        message = data.get('message')
        
        if not message:
            return jsonify({'success': False, 'error': 'Missing message'})
        
        # Default voice preset if not specified or channel doesn't exist
        voice_preset = "v2/en_speaker_6"
        
        # Try to get channel voice preset if it's a real channel
        if channel != 'web' and channel != 'bot':
            conn = sqlite3.connect(db_file)
            c = conn.cursor()
            c.execute("SELECT voice_preset FROM channel_configs WHERE channel_name = ?", (channel,))
            result = c.fetchone()
            if result and result[0]:
                voice_preset = result[0]
            conn.close()
        
        # Generate a timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        
        # Create outputs directory if it doesn't exist
        output_dir = os.path.join('static', 'outputs', channel)
        os.makedirs(output_dir, exist_ok=True)
        
        # Create the file path
        file_path = os.path.join(output_dir, f"{channel}-{timestamp}.wav")
        
        # Process the TTS
        result = process_text(
            text=message,
            output_path=file_path,
            voice_preset=voice_preset
        )
        
        if result and os.path.exists(file_path):
            # Log the TTS entry
            conn = sqlite3.connect(db_file)
            c = conn.cursor()
            
            # Make sure tts_logs table exists
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
            
            c.execute(
                "INSERT INTO tts_logs (channel, timestamp, voice_preset, file_path, message) VALUES (?, ?, ?, ?, ?)",
                (channel, timestamp, voice_preset, file_path, message)
            )
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'file_path': file_path,
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
                    import psutil
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
                import psutil
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
        import psutil
        
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

