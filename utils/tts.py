import os
import time
from datetime import datetime
import sqlite3
import requests
import threading
import sys
from contextlib import contextmanager
import nltk
import numpy as np
from nltk.tokenize import sent_tokenize

import numpy as np

VOICES_DIRECTORY = './voices'
db_file = 'messages.db'

# Define original stdout and stderr globals
original_stdout = sys.stdout
original_stderr = sys.stderr

def fetch_latest_message():
    try:
        print(f"Fetching latest message from database: {db_file}")
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT id, channel, timestamp, message_length, message FROM messages ORDER BY id DESC LIMIT 1")
        result = c.fetchone()
        print(f"Latest message fetched: {result}")
        conn.close()
        return result if result else (None, None, None, None, None)
    except sqlite3.Error as e:
        print(f"SQLite error in fetch_latest_message: {e}")
        raise

def get_voice_preset(channel_name, db_file):
    try:
        # Check for default preset from command line
        default_preset = os.environ.get("DEFAULT_VOICE_PRESET")
        if default_preset:
            return default_preset
        
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT voice_preset FROM channel_configs WHERE channel_name = ?", (channel_name,))
        result = c.fetchone()
        return result[0] if result else 'v2/en_speaker_5'
    finally:
        conn.close()
        

def log_tts_file(message_id, channel_name, timestamp, file_path, voice_preset, input_text, db_file):
    file_path = file_path.replace('static/', '', 1)
    if not voice_preset:
        voice_preset = 'v2/en_speaker_5'
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("INSERT INTO tts_logs (message_id, channel, timestamp, file_path, voice_preset, message) VALUES (?, ?, ?, ?, ?, ?)",
                (message_id, channel_name, timestamp, file_path, voice_preset, input_text))
        conn.commit()
    finally:
        conn.close()

def initialize_tts():
    global AutoProcessor, BarkModel, torch, scipy
    from transformers import AutoProcessor, BarkModel
    import torch
    import scipy.io.wavfile

def silence_output():
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

def process_text_thread(input_text, channel_name, db_file='./messages.db'):
    global original_stdout, original_stderr
    silence_output()

    try:
        return process_text(input_text, channel_name, db_file)
    finally:
        # Restore original stdout and stderr
        sys.stdout = original_stdout
        sys.stderr = original_stderr


def load_custom_voice(voice_name):
    """Load a custom voice file if it exists."""
    voice_path = os.path.join(VOICES_DIRECTORY, f"{voice_name}.npz")
    if os.path.isfile(voice_path):
        voice_data = np.load(voice_path, allow_pickle=True)
        if 'weights' in voice_data:
            return voice_data
        else:
            print(f"No 'weights' key found in {voice_name}.npz")
    else:
        print(f"Custom voice file not found: {voice_path}")
    return None


def process_text(input_text, channel_name, db_file='./messages.db'):
    try:
        voice_preset = get_voice_preset(channel_name, db_file)
        if not voice_preset:
            voice_preset = 'v2/en_speaker_5'  # Default fallback
        
        # Initialize TTS and other setups
        if 'AutoProcessor' not in globals():
            initialize_tts()

        # Define message_id at the start of the function
        message_id = int(time.time())

        # Get voice preset or custom voice
        custom_voice_data = load_custom_voice(voice_preset)

        # Generate file name and output directory
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{channel_name}-{timestamp}.wav"
        channel_directory = os.path.join("static/outputs", channel_name)
        if not os.path.exists(channel_directory):
            os.makedirs(channel_directory)

        full_path = os.path.join(channel_directory, filename)

        # TTS processing
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        processor = AutoProcessor.from_pretrained("suno/bark-small")
        model = BarkModel.from_pretrained("suno/bark-small").to(device)
        if torch.cuda.is_available():
            model.to_bettertransformer()
            model.enable_cpu_offload()

        if custom_voice_data is not None:
            # Apply custom voice parameters
            model.load_state_dict(custom_voice_data['weights'])

        # Prepare TTS inputs
        all_audio_pieces = []
        sentences = sent_tokenize(input_text)
        for sentence in sentences:
            pieces = split_sentence(sentence, 165)  # Split long sentences
            for piece in pieces:
                inputs = processor(piece).to(device)
                audio_array = model.generate(**inputs)
                audio_array = audio_array.cpu().numpy().squeeze()
                all_audio_pieces.append(audio_array)

        final_audio_array = np.concatenate(all_audio_pieces)
        scipy.io.wavfile.write(full_path, rate=model.generation_config.sample_rate, data=final_audio_array)

        # Store in database
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute('''INSERT INTO tts_logs 
                    (channel, timestamp, voice_preset, file_path, message)
                    VALUES (?, ?, ?, ?, ?)''',
                (channel_name, datetime.now().isoformat(), voice_preset, full_path, input_text))
        conn.commit()
        new_id = c.lastrowid  # Get the ID of the new entry
        conn.close()
        
        notify_new_audio_available(channel_name, new_id)

        return full_path, new_id  # Return both values

    except Exception as e:
        print(f"[TTS] An error occurred during TTS processing: {e}")
        return None, None


def split_sentence(sentence, max_length):
    """Split a sentence into smaller parts if it's longer than max_length."""
    pieces = []
    while len(sentence) > max_length:
        split_index = sentence.rfind(' ', 0, max_length)
        if split_index == -1:  # No space found, forced split
            split_index = max_length - 1
        pieces.append(sentence[:split_index + 1])
        sentence = sentence[split_index + 1:]
    pieces.append(sentence)
    return pieces
    
def start_tts_processing(input_text, channel_name, db_file='./messages.db'):
    tts_thread = threading.Thread(target=process_text_thread, args=(input_text, channel_name, db_file), daemon=True)
    tts_thread.start()

def notify_new_audio_available(channel_name, message_id):
    # Define the URL of the Flask endpoint
    url = 'http://localhost:5001/new-audio-notification'  # Update with the correct URL if needed

    # Data to send (optional, you can customize this)
    data = {
        'channel_name': channel_name,
        'message_id': message_id
    }

    # Send POST request
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            print("Notification sent successfully")
        else:
            print("Failed to send notification")
    except requests.exceptions.RequestException as e:
        print(f"Error sending notification: {e}")