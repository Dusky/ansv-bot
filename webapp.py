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

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('WEB_SECRET_KEY', 'default-insecure-key')  # Read from settings.conf
CORS(app, supports_credentials=True)  # Update CORS config
socketio = SocketIO(app, cors_allowed_origins="*")  # Restrict in production

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
    global bot_instance  # Ensure you're working with the global instance
    if bot_instance:  # Ensure bot_instance is not None
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
            return jsonify({'success': False, 'message': str(e)})
    else:
        return jsonify({'success': False, 'message': 'Bot instance is not initialized'})

@app.route('/bot_status')
def bot_status():
    """Check if the bot is running"""
    try:
        is_running = False
        if os.path.exists('bot.pid'):
            try:
                with open('bot.pid', 'r') as pid_file:
                    pid = int(pid_file.read().strip())
                    os.kill(pid, 0)  # Checks if process exists
                    is_running = True
            except:
                pass
                
        return jsonify({"running": is_running})  # Use 'running' field, not 'status'
    except Exception as e:
        app.logger.error(f"Error checking bot status: {e}")
        return jsonify({"running": False, "error": str(e)})


@app.route('/toggle_tts', methods=['POST'])
def toggle_tts():
    global enable_tts
    enable_tts = not enable_tts
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


@app.route('/start_bot', methods=['POST'])
def start_bot():
    global bot_running, enable_tts
    if not bot_running:
        enable_tts = request.form.get('enable_tts') == 'on'
        bot_thread = Thread(target=lambda: run_bot(enable_tts=enable_tts))
        bot_thread.start()
        bot_running = True
    return redirect(url_for('bot_control'))


# Route to stop the bot
@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    global bot_running
    if bot_running:
        bot_instance.stop()
        bot_running = False
    return redirect(url_for('bot_control'))

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
    global bot_running, enable_tts
    theme = request.cookies.get("theme", "darkly")  # Get theme from cookie
    
    # Pass both bot_running and enable_tts status to the template
    return render_template(
        "bot_control.html", 
        theme=theme, 
        bot_running=bot_running, 
        enable_tts=enable_tts
    )

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
    cache_dir = 'cache'
    logs_dir = 'logs'
    cache_files = os.listdir(cache_dir)
    log_files = os.listdir(logs_dir)

    total_line_count = 0  
    stats_data = []

    for file in cache_files:
        if file.endswith("_model.json"):
            channel_name = file.replace("_model.json", "")
            log_file = f"{channel_name}.txt"
            cache_file_path = os.path.join(cache_dir, file)
            
            if log_file in log_files:
                log_file_path = os.path.join(logs_dir, log_file)
                cache_size = os.path.getsize(cache_file_path)
                with open(log_file_path, 'r') as f:
                    line_count = sum(1 for line in f)
                total_line_count += line_count  
                stats_data.append({
                    'channel': channel_name,
                    'cache': file,
                    'log': log_file,
                    'cache_size': cache_size,
                    'line_count': line_count
                })


    general_model_row = {
        'channel': 'General Model',
        'cache': 'general_markov_model.json',
        'log': 'N/A',
        'cache_size': os.path.getsize(os.path.join(cache_dir, 'general_markov_model.json')),
        'line_count': total_line_count
    }
    stats_data.insert(0, general_model_row)  

    return jsonify(stats_data)


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
        
        # Map the theme parameter to a valid Bootswatch theme
        valid_themes = {
            'dark': 'darkly', 
            'light': 'flatly',
            'darkly': 'darkly',
            'flatly': 'flatly',
            'cyborg': 'cyborg',
            'slate': 'slate',
            'solar': 'solar',
            'superhero': 'superhero',
            'vapor': 'vapor'
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
        # Convert from '20240127-190809' to '2024-01-27 19:08:09'
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
    try:
        with sqlite3.connect(db_file) as conn:  # Auto-closes connection
            c = conn.cursor()
            c.execute(
                "SELECT channel_name, tts_enabled, voice_enabled, join_channel, owner, trusted_users, ignored_users, use_general_model, lines_between_messages, time_between_messages FROM channel_configs"
            )
            channels = c.fetchall()
            return jsonify(channels)
    except sqlite3.Error as e:
        app.logger.error(f"Database error: {e}")
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


@app.route('/latest-messages', methods=['GET'])
def get_latest_messages():
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get latest TTS messages from database
        c.execute("""
            SELECT channel, timestamp, voice_preset, file_path, message 
            FROM tts_logs 
            ORDER BY timestamp DESC 
            LIMIT 10
        """)
        
        rows = c.fetchall()
        conn.close()
        
        # Format the data for the frontend
        formatted_entries = []
        for row in rows:
            formatted_entries.append({
                'channel': row['channel'],
                'timestamp': row['timestamp'],
                'voice_preset': row['voice_preset'],
                'file_path': row['file_path'],
                'message': row['message']
            })
            
        return jsonify(formatted_entries)
    except Exception as e:
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

@app.route('/trigger-tts', methods=['POST'])
def trigger_tts():
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
            
            stats.append({
                'name': channel,
                'log_file': f"{channel}.txt",
                'cache_file': f"{channel}_model.json" if os.path.exists(cache_file) else None,
                'log_size': log_size_formatted,
                'cache_size': cache_size_formatted,
                'line_count': line_count
            })
        
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

