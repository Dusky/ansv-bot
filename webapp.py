#webapp.py
from flask import Flask, render_template, url_for, jsonify, request
import sqlite3
from datetime import datetime

app = Flask(__name__)
db_file = "messages.db"

new_audio_available = False  # Flag to indicate new audio availability

@app.route('/new-audio-notification', methods=['POST'])
def new_audio_notification():
    global new_audio_available
    new_audio_available = True
    return jsonify({'success': True})

@app.route('/check-new-audio', methods=['GET'])
def check_new_audio():
    global new_audio_available
    response = {'newAudioAvailable': new_audio_available}
    new_audio_available = False  # Reset flag after checking
    return jsonify(response)

def format_timestamp(timestamp):
    dt = datetime.strptime(timestamp, '%Y%m%d-%H%M%S')
    return dt.strftime('%b %d %I:%M %p').upper()  # Format like 'JAN 1 04:51 PM'

def format_data_for_frontend(data):
    formatted_data = []
    for record in data:
        channel, message_id, timestamp, voice_preset, file_path, message = record
        truncated_message_id = str(message_id)[4:] if len(str(message_id)) > 4 else str(message_id)
        formatted_record = (channel, truncated_message_id, format_timestamp(timestamp), voice_preset, file_path, message)
        formatted_data.append(formatted_record)
    return formatted_data

@app.route('/messages/<int:page>')
def paginated_messages(page):
    per_page = 10  # Number of items per page
    tts_files = get_paginated_tts_files(db_file, page, per_page)
    return jsonify(format_data_for_frontend(tts_files))

def get_paginated_tts_files(db_file, page, per_page):
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        offset = (page - 1) * per_page
        c.execute("SELECT channel, message_id, timestamp, voice_preset, file_path, message FROM tts_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?", (per_page, offset))
        files = c.fetchall()
        return files
    except sqlite3.Error as e:
        print("[ERROR] Database error:", e)
        return []
    finally:
        conn.close()
        
@app.route('/')
def index():
    
    tts_files, last_id = get_last_10_tts_files_with_last_id(db_file)
    return render_template('files_list.html', tts_files=tts_files, last_id=last_id)



def get_paginated_tts_files(db_file, page, per_page):
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        offset = (page - 1) * per_page
        c.execute("SELECT channel, message_id, timestamp, voice_preset, file_path, message FROM tts_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?", (per_page, offset))
        files = c.fetchall()
        return files
    except sqlite3.Error as e:
        print("[ERROR] Database error:", e)
        return []
    finally:
        conn.close()
        

@app.route('/update-channel-settings', methods=['POST'])
def update_channel_settings():
    data = request.json
    channel_name = data.get('channel_name')
    
    # Validation to ensure channel_name is provided
    if not channel_name:
        return jsonify({'success': False, 'message': 'Channel name is required'})

    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("""
            UPDATE channel_configs
            SET tts_enabled = ?, voice_enabled = ?, join_channel = ?, owner = ?, trusted_users = ?, ignored_users = ?, use_general_model = ?, lines_between_messages = ?, time_between_messages = ?
            WHERE channel_name = ?""",
            (data['tts_enabled'], data['voice_enabled'], data['join_channel'], data['owner'], data['trusted_users'], data['ignored_users'], data['use_general_model'], data['lines_between_messages'], data['time_between_messages'], channel_name))
        conn.commit()
        return jsonify({'success': True, 'message': 'Channel settings updated successfully'})
    except sqlite3.Error as e:
        print(f"[ERROR] SQLite error in update_channel_settings: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/channel-stats')
def channel_stats():
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        query = "SELECT channel_name, message_count, last_active FROM channel_info"
        cursor.execute(query)
        channels = cursor.fetchall()
        channel_stats = [dict(channel_name=row[0], message_count=row[1], last_active=row[2]) for row in channels]
        return jsonify(channel_stats)
    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        conn.close()



@app.route('/save-channel-settings', methods=['POST'])
def save_channel_settings():
    data = request.json
    print("Received data for saving:", data)
    
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("""
            UPDATE channel_configs 
            SET tts_enabled = ?, voice_enabled = ?, join_channel = ?, owner = ?, trusted_users = ?, ignored_users = ?, use_general_model = ?, lines_between_messages = ?, time_between_messages = ?
            WHERE channel_name = ?""",
            (data['tts_enabled'], data['voice_enabled'], data['join_channel'], data['owner'], data['trusted_users'], data['ignored_users'], data['use_general_model'], data['lines_between_messages'], data['time_between_messages'], data['channel_name']))
        rows_affected = conn.total_changes
        conn.commit()
        print(f"{rows_affected} rows updated in database.")
        return jsonify({'success': True})
    except sqlite3.Error as e:
        print(f"SQLite error in save_channel_settings: {e}")
        return jsonify({'success': False})

    
@app.route('/get-channels')
def get_channels():
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT channel_name, tts_enabled, voice_enabled, join_channel, owner, trusted_users, ignored_users, use_general_model, lines_between_messages, time_between_messages FROM channel_configs")
        channels = c.fetchall()
        return jsonify(channels)
    except sqlite3.Error as e:
        print(f"SQLite error in get_channels: {e}")
        return jsonify([])

@app.route('/add-channel', methods=['POST'])
def add_channel():
    data = request.json
    channel_name = data.get('channel_name')
    
    # Debug: Print the received data
    print("Received data for adding channel:", data)

    if not channel_name:
        print("No channel name provided.")
        return jsonify({'success': False, 'message': 'No channel name provided'})

    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()

        # Check if the channel already exists
        c.execute("SELECT COUNT(*) FROM channel_configs WHERE channel_name = ?", (channel_name,))
        count = c.fetchone()[0]
        print(f"Existing count for channel '{channel_name}': {count}")

        if count == 0:
            # Insert new channel as it does not exist
            c.execute("""
                INSERT INTO channel_configs (channel_name, tts_enabled, voice_enabled, join_channel, owner, trusted_users, ignored_users, use_general_model, lines_between_messages, time_between_messages)
                VALUES (?, 0, 0, 1, ?, '', '', 1, 100, 0)""", 
                (channel_name, channel_name))
            conn.commit()
            print(f"Channel '{channel_name}' added successfully.")
            return jsonify({'success': True, 'message': f"Channel {channel_name} added."})
        else:
            print(f"Channel '{channel_name}' already exists.")
            return jsonify({'success': False, 'message': f"Channel {channel_name} already exists."})
    except Exception as e:
        print(f"Exception occurred in add_channel: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()




    
@app.route('/latest-messages')
def latest_messages():
    tts_files = get_last_10_tts_files_with_last_id(db_file)
    return jsonify(format_data_for_frontend(tts_files))

@app.route('/check-updates/<int:last_id>')
def check_updates(last_id):
    new_entries = get_new_tts_entries(db_file, last_id)
    return jsonify({'newData': len(new_entries) > 0, 'entries': format_data_for_frontend(new_entries)})

def get_new_tts_entries(db_file, last_id):
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT channel, message_id, timestamp, voice_preset, file_path, message FROM tts_logs WHERE message_id > ? ORDER BY timestamp DESC", (last_id,))
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
        c.execute("SELECT channel, message_id, timestamp, voice_preset, file_path, message FROM tts_logs ORDER BY timestamp DESC LIMIT 10")
        files = c.fetchall()
        last_id = files[0][1] if files else 0
        return format_data_for_frontend(files), last_id
    except sqlite3.Error as e:
        print("[ERROR] Database error:", e)
        return [], 0
    finally:
        conn.close()

def run_flask_app():
    app.run(debug=True, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    run_flask_app()
