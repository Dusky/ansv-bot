import os
import sqlite3
import time
import asyncio
import logging
import re
import psutil
import json
import random
import traceback  # Added import for traceback - used in exception handlers
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, make_response
from datetime import datetime, timedelta
import configparser
from utils.markov_handler import MarkovHandler
from utils.logger import Logger
from utils.db_setup import ensure_db_setup

# Initialize application components
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Setup logging
logger = Logger()
logger.setup_logger()
app.logger.setLevel(logging.INFO)

# Set up database
db_file = "messages.db"
ensure_db_setup(db_file)

# Initialize Markov handler
markov_handler = MarkovHandler(cache_directory="cache")

# Global variable to hold the bot instance
bot_instance = None

# Initialize configuration
config = configparser.ConfigParser()
config.read("settings.conf")

# Cache variable for join status
channel_join_status = {}
last_status_check = 0

def get_last_10_tts_files_with_last_id(db_file):
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT id, voice_file, message, timestamp FROM tts_logs ORDER BY id DESC LIMIT 10")
        rows = c.fetchall()
        conn.close()
        
        # Get the last ID
        last_id = rows[0][0] if rows else 0
        
        # Convert rows to a list of dictionaries
        files = []
        for row in rows:
            files.append({
                "id": row[0],
                "file": row[1],
                "message": row[2],
                "timestamp": row[3]
            })
        
        return files, last_id
    except Exception as e:
        app.logger.error(f"Error getting TTS files: {e}")
        return [], 0

def is_bot_actually_running():
    """Check if the bot is actually running using multiple methods."""
    global last_status_check, channel_join_status
    current_time = time.time()
    
    # Only check every 5 seconds to avoid excessive disk I/O
    if current_time - last_status_check < 5:
        app.logger.debug("Using cached bot status")
        return bool(channel_join_status.get('running', False))
    
    last_status_check = current_time
    bot_running = False
    
    # METHOD 1: Check the PID file
    try:
        if os.path.exists("bot.pid"):
            with open("bot.pid", "r") as f:
                try:
                    pid = int(f.read().strip())
                    if psutil.pid_exists(pid):
                        # Check if it's a Python process
                        try:
                            process = psutil.Process(pid)
                            if "python" in process.name().lower() or "python" in " ".join(process.cmdline()).lower():
                                app.logger.info(f"Bot process exists with PID {pid}")
                                bot_running = True
                        except:
                            app.logger.warning(f"Could not access process details for PID {pid}")
                    else:
                        app.logger.warning(f"PID {pid} doesn't exist")
                except Exception as e:
                    app.logger.error(f"Error parsing PID file: {e}")
    except Exception as e:
        app.logger.error(f"Error checking PID file: {e}")
    
    # METHOD 2: Check the heartbeat file
    try:
        if os.path.exists("bot_heartbeat.json"):
            with open("bot_heartbeat.json", "r") as f:
                heartbeat_data = json.load(f)
                timestamp = heartbeat_data.get("timestamp", 0)
                channels = heartbeat_data.get("channels", [])
                
                # Check if heartbeat is recent (within last 2 minutes)
                if current_time - timestamp < 120:
                    app.logger.info(f"Recent heartbeat found ({len(channels)} channels)")
                    bot_running = True
                    
                    # Update channel status cache
                    channel_join_status = {
                        'timestamp': current_time,
                        'channels': channels,
                        'running': True
                    }
                else:
                    app.logger.warning(f"Heartbeat is stale: {datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        app.logger.error(f"Error checking heartbeat file: {e}")
    
    # METHOD 3: Check the database
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT value FROM bot_status WHERE key = 'last_heartbeat'")
        result = c.fetchone()
        if result:
            try:
                # Parse the timestamp
                last_heartbeat = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
                now = datetime.now()
                delta = now - last_heartbeat
                if delta.total_seconds() < 120:  # Within last 2 minutes
                    app.logger.info(f"Recent database heartbeat: {last_heartbeat}")
                    bot_running = True
                else:
                    app.logger.warning(f"Database heartbeat is stale: {last_heartbeat}")
            except Exception as e:
                app.logger.error(f"Error parsing database heartbeat: {e}")
        conn.close()
    except Exception as e:
        app.logger.error(f"Error checking database heartbeat: {e}")
    
    # Update the cached status
    channel_join_status['running'] = bot_running
    return bot_running

def send_message_via_pid(channel, message):
    """Fallback method to send messages via request file"""
    try:
        # First, check if bot is actually running
        bot_running = False
        
        if not os.path.exists('bot.pid'):
            app.logger.error("Bot PID file does not exist")
        else:
            # Get the actual PID
            try:
                with open('bot.pid', 'r') as f:
                    pid_content = f.read().strip()
                    # Handle possible formats (PID only or other format)
                    if '|' in pid_content:
                        _, pid = pid_content.split('|', 1)
                        pid = int(pid)
                    else:
                        pid = int(pid_content)
                        
                    # Check if process exists and is a Python process
                    if psutil.pid_exists(pid):
                        try:
                            process = psutil.Process(pid)
                            cmd_line = ' '.join(process.cmdline()).lower()
                            if 'python' in process.name().lower() or 'python' in cmd_line:
                                bot_running = True
                                app.logger.info(f"Bot is running with PID {pid}")
                        except Exception as proc_error:
                            app.logger.warning(f"Could not verify process: {proc_error}")
                    else:
                        app.logger.warning(f"No process running with PID {pid}")
            except Exception as pid_error:
                app.logger.error(f"Error reading PID file: {pid_error}")
        
        if not bot_running:
            # Check heartbeat file as alternate way to verify bot is running
            if os.path.exists('bot_heartbeat.json'):
                try:
                    with open('bot_heartbeat.json', 'r') as f:
                        heartbeat_data = json.load(f)
                        timestamp = heartbeat_data.get('timestamp', 0)
                        if time.time() - timestamp < 120:  # Less than 2 minutes old
                            bot_running = True
                            app.logger.info("Bot appears to be running based on recent heartbeat")
                except Exception as e:
                    app.logger.warning(f"Error reading heartbeat file: {e}")
        
        # Force restart the bot's message checker task by creating a special request
        # This should be processed even if the bot isn't verified as running
        try:
            restart_file = 'bot_task_restart.json'
            with open(restart_file, 'w') as f:
                json.dump({
                    'action': 'restart_task',
                    'task': 'message_request_checker',
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }, f)
            app.logger.info("Created task restart request to ensure message checker is running")
        except Exception as e:
            app.logger.warning(f"Could not create task restart request: {e}")
        
        # Remove any existing request file to ensure clean state
        request_file = 'bot_message_request.json'
        if os.path.exists(request_file):
            try:
                os.remove(request_file)
                app.logger.info("Removed existing request file")
            except Exception as e:
                app.logger.warning(f"Could not remove existing request file: {e}")
        
        # Make sure channel name doesn't have # prefix - bot will add it
        clean_channel = channel.lstrip('#')
        
        # Create the format that bot.check_message_requests is expecting
        request_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
        
        data = {
            'action': 'send_message',
            'channel': clean_channel,
            'message': message,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'request_id': request_id,
            'force': True
        }
        
        # Write the request file
        with open(request_file, 'w') as f:
            json.dump(data, f)
            
        app.logger.info(f"Created message request file for channel {clean_channel} with message: {message[:30]}...")
        
        # Wait a moment to give the bot a chance to see the file
        time.sleep(1.0)
        
        # Check if the file was processed
        if not os.path.exists(request_file):
            app.logger.info("Request file was processed by the bot")
            return True
        else:
            app.logger.warning("Request file still exists after waiting - bot may not be checking for requests")
            
            # Try sending a command to the bot database to restart
            try:
                conn = sqlite3.connect(db_file)
                c = conn.cursor()
                # Check if the bot_commands table exists
                c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bot_commands'")
                if not c.fetchone():
                    c.execute('''CREATE TABLE IF NOT EXISTS bot_commands
                                (id INTEGER PRIMARY KEY, bot_id TEXT, command TEXT, 
                                 params TEXT, created_at TEXT, executed INTEGER)''')
                
                # Insert a command to restart the message checker
                c.execute('''INSERT INTO bot_commands 
                           (bot_id, command, params, created_at, executed) 
                           VALUES (?, ?, ?, ?, ?)''',
                         ('1', 'restart_msg_check', json.dumps(data), 
                          datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0))
                conn.commit()
                conn.close()
                app.logger.info("Added restart command to database")
            except Exception as db_error:
                app.logger.error(f"Error adding restart command to database: {db_error}")
            
            # Return True regardless - we'll let the API caller decide what to do
            # based on the message generation success even if sending may have failed
            return True  
        
    except Exception as e:
        app.logger.error(f"Message request failed: {str(e)}")
        app.logger.error(traceback.format_exc())
        return False

@app.route('/send_markov_message/<channel_name>', methods=['POST'])
def send_markov_message(channel_name):
    global bot_instance
    
    try:
        # Always get a JSON body even if empty, preventing 400 errors
        data = request.get_json(silent=True) or {}
        client_verified = data.get('verify_running', False)
        force_channel = data.get('channel')
        
        # Parameters to bypass checks - expanded with more options
        force_send = data.get('force_send', False)
        bypass_check = data.get('bypass_check', False)
        manual_trigger = data.get('manual_trigger', False)
        skip_verification = data.get('skip_verification', False)
        
        # URL parameters (which take precedence)
        force_param = request.args.get('force', 'false').lower() == 'true'
        bypass_param = request.args.get('bypass', 'false').lower() == 'true'
        manual_param = request.args.get('manual', 'false').lower() == 'true'
        skip_param = request.args.get('skip', 'false').lower() == 'true'
        
        # If any of these are true, we'll force sending
        force_operation = (force_send or bypass_check or manual_trigger or skip_verification or 
                          force_param or bypass_param or manual_param or skip_param)
        
        if force_operation:
            # Log that we're bypassing normal checks
            app.logger.info(f"FORCE parameters detected - bypassing normal bot status checks for channel {channel_name}")
        
        # Security: Validate channel name format
        if not re.match(r"^[a-zA-Z0-9_]{1,25}$", channel_name):
            return jsonify({'success': False, 'error': 'Invalid channel name format'}), 400
            
        if force_channel and force_channel != channel_name:
            return jsonify({'success': False, 'error': 'Channel mismatch between URL and body'}), 400

        # Server-side verification - but skip if we're forcing
        server_verified = force_operation or is_bot_actually_running()
        
        # When forcing, we always consider the bot to be running
        actually_running = force_operation or (client_verified and server_verified)
        
        # Generate message regardless of status
        try:
            # Generate message using our enhanced implementation with more attempts & fallbacks
            message = markov_handler.generate_message(channel_name, max_attempts=8, max_fallbacks=2)
            
            # If no message was generated, provide a default
            if not message:
                app.logger.error(f"All attempts to generate message for {channel_name} failed")
                message = "I'm having trouble generating a message right now."
            else:
                app.logger.info(f"Successfully generated message for {channel_name}: {message[:50]}...")
                
            sent = False
            error_reason = None
            
            # Always attempt to send if we're forcing or bot is running
            if actually_running and message:
                try:
                    # Try direct method first
                    if bot_instance:
                        coroutine = bot_instance.send_message_to_channel(channel_name, message)
                        asyncio.run_coroutine_threadsafe(coroutine, bot_instance.loop)
                        sent = True
                        app.logger.info(f"Message sent to {channel_name} via direct bot instance")
                    else:
                        # Fallback to PID-based send
                        sent = send_message_via_pid(channel_name, message)
                        app.logger.info(f"Message sent to {channel_name} via PID method: {sent}")
                        
                    if not sent:
                        error_reason = "Failed to send via all available methods"
                        app.logger.warning(f"Failed to send message to {channel_name}")
                        
                except Exception as send_error:
                    app.logger.error(f"Error sending message: {str(send_error)}")
                    error_reason = f"Send error: {str(send_error)}"
                    # On error, still return the generated message but with sent=False
            elif not actually_running:
                error_reason = "Bot is not running"
                app.logger.info(f"Message not sent because bot is not running (force={force_operation})")
            
            # Message generation is successful if we have a message
            success = message is not None
            
            # Prepare response with detailed status
            response = {
                'success': success,
                'message': message,
                'sent': sent,
                'server_verified': server_verified,
                'client_verified': client_verified,
                'force_applied': force_operation
            }
            
            # Only include error reason if there was an issue sending
            if not sent and error_reason:
                response['error'] = error_reason
                
            return jsonify(response)
            
        except Exception as e:
            app.logger.error(f"Generation error: {str(e)}")
            import traceback
            app.logger.debug(f"Traceback: {traceback.format_exc()}")
            return jsonify({
                'success': False, 
                'error': f"Generation error: {str(e)}",
                'message': "Could not generate a message at this time."
            }), 500
            
    except Exception as e:
        app.logger.error(f"Endpoint error: {str(e)}")
        import traceback
        app.logger.debug(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False, 
            'error': f"Server error: {str(e)}",
            'message': "Could not generate a message due to a server error."
        }), 500

@app.route('/')
def main():
    theme = request.cookies.get("theme", "darkly")  # Get theme from cookie
    tts_files = get_last_10_tts_files_with_last_id(db_file)
    
    global bot_instance
    bot_running = is_bot_actually_running()
    
    # Get bot status info for display
    bot_status = {
        'running': bot_running,
        'uptime': 'Unknown',
        'channels': []
    }
    
    # Try to get more detailed status
    try:
        if os.path.exists('bot_heartbeat.json'):
            with open('bot_heartbeat.json', 'r') as f:
                data = json.load(f)
                
                # Calculate uptime
                if 'uptime' in data:
                    uptime_seconds = data['uptime']
                    days, remainder = divmod(uptime_seconds, 86400)
                    hours, remainder = divmod(remainder, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    uptime_str = []
                    if days > 0:
                        uptime_str.append(f"{int(days)}d")
                    if hours > 0 or days > 0:
                        uptime_str.append(f"{int(hours)}h")
                    if minutes > 0 or hours > 0 or days > 0:
                        uptime_str.append(f"{int(minutes)}m")
                    uptime_str.append(f"{int(seconds)}s")
                    
                    bot_status['uptime'] = " ".join(uptime_str)
                
                # Get joined channels
                if 'channels' in data:
                    bot_status['channels'] = data['channels']
    except:
        # If we can't read the heartbeat file, just continue
        pass
    
    return render_template("index.html", theme=theme, tts_files=tts_files[0], 
                           last_id=tts_files[1], bot_status=bot_status)

@app.route("/generate-message/<channel_name>")
def generate_message(channel_name):
    try:
        # Use our enhanced generator with multiple attempts
        message = markov_handler.generate_message(channel_name, max_attempts=8, max_fallbacks=2)
        
        if message:
            app.logger.info(f"Generated message for {channel_name}: {message[:50]}...")
            return jsonify({
                "success": True,
                "message": message,
                "channel": channel_name
            })
        else:
            # Provide a default message rather than failing
            default_message = "I'm having trouble generating a message right now."
            app.logger.warning(f"Failed to generate message for {channel_name} - providing default")
            return jsonify({
                "success": True,
                "message": default_message,
                "channel": channel_name,
                "default_used": True
            })
    except Exception as e:
        app.logger.error(f"Error in generate_message_route: {str(e)}")
        import traceback
        app.logger.debug(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": f"Error generating message: {str(e)}",
            "message": "Could not generate a message due to an error."
        })

@app.route("/generate-message", methods=["POST"])
def generate_message_post():
    """Generate a message using the selected model and channel"""
    try:
        # Extract model and channel from request, always providing a valid JSON body
        data = request.get_json(silent=True) or {}
        model = data.get('model')
        channel = data.get('channel')
        
        # Log the request
        app.logger.info(f"Generating message with model: {model}, channel: {channel}")
        
        # Load models if not already loaded
        if not markov_handler.models:
            app.logger.info("Models not loaded, loading now...")
            markov_handler.load_models()
        
        # Use channel as model if specified but model not provided
        if not model and channel:
            model = channel
            app.logger.info(f"Using channel '{channel}' as model")
        
        # Default to general if neither model nor channel specified
        if not model:
            model = "general_markov"
            app.logger.info(f"No model specified, using general_markov")
        
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
        
        # Generate the message using the determined model with enhanced reliability
        if model:
            # Use our improved version with multiple attempts and fallbacks
            message = markov_handler.generate_message(model, max_attempts=8, max_fallbacks=2)
            
            if message:
                app.logger.info(f"Generated message: {message[:50]}...")
                return jsonify({
                    "success": True,
                    "message": message, 
                    "model_used": model
                })
            else:
                # Provide a default message rather than failing completely
                default_message = "I'm having trouble generating a message right now."
                app.logger.warning("Failed to generate message - providing default")
                return jsonify({
                    "success": True,
                    "message": default_message, 
                    "model_used": model,
                    "default_used": True
                })
        else:
            app.logger.error("No models available for message generation")
            return jsonify({
                "success": False,
                "error": "No models available for message generation",
                "message": "Could not generate a message - no models available."
            })
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        app.logger.error(f"Error generating message: {str(e)}\n{trace}")
        return jsonify({
            "success": False, 
            "error": f"Error generating message: {str(e)}",
            "message": "Could not generate a message due to an error."
        })


@app.route('/available-models')
def available_models():
    """Get a list of available Markov models"""
    try:
        models = markov_handler.get_available_models()
        return jsonify(models)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/rebuild-general-cache', methods=['POST'])
def rebuild_general_cache():
    """Rebuild the general Markov model cache"""
    try:
        success = markov_handler.rebuild_general_cache('logs')
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Failed to rebuild general cache"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/rebuild-cache/<channel_name>', methods=['POST'])
def rebuild_cache(channel_name):
    """Rebuild the Markov model cache for a specific channel"""
    try:
        success = markov_handler.rebuild_cache_for_channel(channel_name, 'logs')
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Failed to rebuild cache"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/rebuild-all-caches', methods=['POST'])
def rebuild_all_caches():
    """Rebuild all Markov model caches"""
    try:
        if not markov_handler.rebuild_all_caches():
            return jsonify({"success": False, "message": "Failed to rebuild all caches"}), 500
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# Bot control endpoints
@app.route('/start-bot', methods=['POST'])
def start_bot():
    """Start the bot process if it's not already running"""
    if is_bot_actually_running():
        return jsonify({"success": False, "message": "Bot is already running"}), 400
    
    try:
        import subprocess
        process = subprocess.Popen(
            ["./launch.sh", "--only-bot"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(timeout=5)
        
        if process.returncode != 0:
            return jsonify({
                "success": False, 
                "message": f"Failed to start bot: {stderr.decode('utf-8')}"
            }), 500
        
        return jsonify({"success": True, "message": "Bot starting..."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error starting bot: {str(e)}"}), 500


@app.route('/stop-bot', methods=['POST'])
def stop_bot():
    """Stop the bot process if it's running"""
    if not is_bot_actually_running():
        return jsonify({"success": False, "message": "Bot is not running"}), 400
    
    try:
        # Check if PID file exists
        if not os.path.exists("bot.pid"):
            return jsonify({"success": False, "message": "Bot PID file not found"}), 404
        
        # Read the PID
        with open("bot.pid", "r") as f:
            try:
                pid = int(f.read().strip())
                
                # Check if process exists
                if not psutil.pid_exists(pid):
                    return jsonify({"success": False, "message": f"No process found with PID {pid}"}), 404
                
                # Send SIGTERM to the process
                import signal
                os.kill(pid, signal.SIGTERM)
                
                # Wait a moment and verify it's stopped
                time.sleep(1)
                if psutil.pid_exists(pid):
                    # Try SIGKILL if SIGTERM didn't work
                    os.kill(pid, signal.SIGKILL)
                    
                return jsonify({"success": True, "message": "Bot stopped"})
            except Exception as e:
                return jsonify({"success": False, "message": f"Error stopping bot: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": f"Error stopping bot: {str(e)}"}), 500


@app.route('/bot-status')
def bot_status():
    """Get the bot's current status"""
    bot_running = is_bot_actually_running()
    
    # Basic status response
    status = {
        "running": bot_running,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Try to get more detailed info if the bot is running
    if bot_running:
        try:
            if os.path.exists("bot_heartbeat.json"):
                with open("bot_heartbeat.json", "r") as f:
                    heartbeat_data = json.load(f)
                    
                    # Add heartbeat data to response
                    status.update({
                        "heartbeat_time": datetime.fromtimestamp(heartbeat_data.get("timestamp", 0)).strftime('%Y-%m-%d %H:%M:%S'),
                        "uptime": heartbeat_data.get("uptime", 0),
                        "joined_channels": heartbeat_data.get("channels", []),
                        "pid": heartbeat_data.get("pid", None)
                    })
        except Exception as e:
            app.logger.error(f"Error getting detailed bot status: {e}")
    
    return jsonify(status)


@app.route('/settings')
def settings():
    """Render the settings page"""
    # Get theme from cookie
    theme = request.cookies.get("theme", "darkly") 
    
    # Get bot status
    bot_running = is_bot_actually_running()
    
    # Get channels from database
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("""
            SELECT channel_name, owner, tts_enabled, voice_enabled, join_channel, 
                   trusted_users, ignored_users, use_general_model, lines_between_messages, 
                   time_between_messages, voice_preset, currently_connected
            FROM channel_configs
        """)
        channels = c.fetchall()
        conn.close()
    except Exception as e:
        channels = []
        app.logger.error(f"Error fetching channels: {e}")
    
    return render_template("settings.html", theme=theme, channels=channels, bot_running=bot_running)


# Channel configuration endpoints
@app.route('/get-channels')
def get_channels():
    """Get a list of all channels"""
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("""
            SELECT channel_name, tts_enabled, voice_enabled, join_channel, owner, 
                   trusted_users, ignored_users, use_general_model, lines_between_messages, 
                   time_between_messages, voice_preset, currently_connected
            FROM channel_configs
        """)
        channels = c.fetchall()
        conn.close()
        return jsonify(channels)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/channels')
def api_channels():
    """API endpoint to get channel list in standardized format"""
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("""
            SELECT channel_name, tts_enabled, voice_enabled, join_channel, currently_connected
            FROM channel_configs
        """)
        channels_data = c.fetchall()
        conn.close()
        
        # Convert to list of standardized objects
        channels = []
        for row in channels_data:
            channels.append({
                "name": row[0],
                "tts_enabled": bool(row[1]),
                "voice_enabled": bool(row[2]),
                "join_channel": bool(row[3]),
                "connected": bool(row[4])
            })
        
        return jsonify(channels)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get-channel-settings/<channel_name>')
def get_channel_settings(channel_name):
    """Get settings for a specific channel"""
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("""
            SELECT * FROM channel_configs WHERE channel_name = ?
        """, (channel_name,))
        
        columns = [col[0] for col in c.description]
        row = c.fetchone()
        conn.close()
        
        if row:
            # Convert row to dictionary
            settings = {columns[i]: row[i] for i in range(len(columns))}
            return jsonify(settings)
        else:
            return jsonify({"error": "Channel not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/update-channel-settings', methods=['POST'])
def update_channel_settings():
    """Update settings for a channel"""
    try:
        data = request.json
        channel_name = data.get('channel_name')
        
        if not channel_name:
            return jsonify({"success": False, "message": "Channel name is required"}), 400
        
        # Get fields to update
        fields = [
            'tts_enabled', 'voice_enabled', 'join_channel', 'owner',
            'trusted_users', 'ignored_users', 'use_general_model',
            'lines_between_messages', 'time_between_messages', 'voice_preset', 'bark_model'
        ]
        
        # Build update query
        update_fields = []
        params = []
        
        for field in fields:
            if field in data:
                update_fields.append(f"{field} = ?")
                params.append(data[field])
        
        if not update_fields:
            return jsonify({"success": False, "message": "No fields to update"}), 400
        
        # Add channel name to params
        params.append(channel_name)
        
        # Execute update
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute(f"""
            UPDATE channel_configs
            SET {', '.join(update_fields)}
            WHERE channel_name = ?
        """, params)
        conn.commit()
        conn.close()
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/add-channel', methods=['POST'])
def add_channel():
    """Add a new channel"""
    try:
        data = request.json
        channel_name = data.get('channel_name')
        
        if not channel_name:
            return jsonify({"success": False, "message": "Channel name is required"}), 400
        
        # Check if channel already exists
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT 1 FROM channel_configs WHERE channel_name = ?", (channel_name,))
        if c.fetchone():
            conn.close()
            return jsonify({"success": False, "message": "Channel already exists"}), 400
        
        # Get field values with defaults
        tts_enabled = data.get('tts_enabled', 0)
        voice_enabled = data.get('voice_enabled', 0)
        join_channel = data.get('join_channel', 1)
        owner = data.get('owner', channel_name)
        trusted_users = data.get('trusted_users', '')
        ignored_users = data.get('ignored_users', '')
        use_general_model = data.get('use_general_model', 1)
        lines_between_messages = data.get('lines_between_messages', 100)
        time_between_messages = data.get('time_between_messages', 0)
        voice_preset = data.get('voice_preset', 'v2/en_speaker_0')
        bark_model = data.get('bark_model', 'regular')
        
        # Insert new channel
        c.execute("""
            INSERT INTO channel_configs (
                channel_name, tts_enabled, voice_enabled, join_channel, owner,
                trusted_users, ignored_users, use_general_model,
                lines_between_messages, time_between_messages, voice_preset, bark_model
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            channel_name, tts_enabled, voice_enabled, join_channel, owner,
            trusted_users, ignored_users, use_general_model,
            lines_between_messages, time_between_messages, voice_preset, bark_model
        ))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/delete-channel', methods=['POST'])
def delete_channel():
    """Delete a channel"""
    try:
        data = request.json
        channel_name = data.get('channel_name')
        
        if not channel_name:
            return jsonify({"success": False, "message": "Channel name is required"}), 400
        
        # Delete the channel
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("DELETE FROM channel_configs WHERE channel_name = ?", (channel_name,))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/list-voices')
def list_voices():
    """List available TTS voices"""
    try:
        voices_dir = "voices"
        if not os.path.exists(voices_dir):
            return jsonify({"voices": []})
        
        voices = [f for f in os.listdir(voices_dir) if f.endswith('.npz')]
        return jsonify({"voices": voices})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/rebuild-voice-index')
def rebuild_voice_index():
    """Rebuild the voice index"""
    try:
        # Placeholder for actual voice index rebuilding
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get-latest-tts')
def get_latest_tts():
    """Get latest TTS entries after a specific ID"""
    try:
        # Get last_id from request args, default to 0
        last_id_str = request.args.get('last_id', '0')
        
        # Convert to integer safely
        try:
            last_id = int(last_id_str)
        except (ValueError, TypeError):
            app.logger.warning(f"Invalid last_id parameter: {last_id_str}, using 0")
            last_id = 0
        
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("""
            SELECT id, voice_file, message, timestamp
            FROM tts_logs
            WHERE id > ?
            ORDER BY id DESC
            LIMIT 10
        """, (last_id,))
        rows = c.fetchall()
        conn.close()
        
        # Convert rows to list of dictionaries
        files = []
        current_max_id = last_id  # Start with the input id
        
        for row in rows:
            row_id = row[0]  # This should be an integer from the database
            files.append({
                "id": row_id,
                "file": row[1],
                "message": row[2],
                "timestamp": row[3]
            })
            
            # Update the max id if this row's id is higher
            if row_id > current_max_id:
                current_max_id = row_id
        
        return jsonify({"files": files, "last_id": current_max_id})
    except Exception as e:
        app.logger.error(f"Error in get_latest_tts: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({"error": str(e), "files": []}), 500


@app.route('/static/outputs/<filename>')
def serve_tts_output(filename):
    """Serve TTS output files"""
    return send_from_directory(os.path.join(app.root_path, 'static', 'outputs'), filename)


# Theme handling
@app.route('/set-theme/<theme>')
def set_theme(theme):
    """Set the theme cookie"""
    response = make_response(redirect(request.referrer or url_for('main')))
    response.set_cookie('theme', theme, max_age=60*60*24*365)  # 1 year
    return response


# 404 handler
@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    theme = request.cookies.get('theme', 'darkly')
    return render_template('index.html', theme=theme, error=True, error_message="Page not found"), 404


# Error handler
@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    theme = request.cookies.get('theme', 'darkly')
    return render_template('index.html', theme=theme, error=True, error_message="Server error"), 500


if __name__ == "__main__":
    # Load models
    markov_handler.load_models()
    
    # Simple health endpoint for monitoring
    @app.route('/health')
    def health_check():
        return jsonify({"status": "ok"})
    
    # Run the app
    app.run(host="0.0.0.0", port=5001, debug=True)