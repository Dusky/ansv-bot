import os
import time
from datetime import datetime
import sqlite3
import requests
import threading
import sys
import warnings
import nltk
import numpy as np
from nltk.tokenize import sent_tokenize

# Database connection setup
db_file = './messages.db'  # Update with the correct path




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
        #print(f"Getting voice preset for channel: {channel_name}")
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT voice_preset FROM channel_configs WHERE channel_name = ?", (channel_name,))
        result = c.fetchone()
        #print(f"Voice preset for channel {channel_name}: {result[0] if result else 'v2/en_speaker_5'}")
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

def process_text_thread(input_text, channel_name, db_file='./messages.db'):
    # Suppress console output
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

    try:
        process_text(input_text, channel_name, db_file)
    finally:
        # Restore original stdout and stderr
        sys.stdout.close()
        sys.stderr.close()
        sys.stdout = original_stdout
        sys.stderr = original_stderr

def process_text(input_text, channel_name, db_file='./messages.db'):
    # Initialize TTS and other setups
    if 'AutoProcessor' not in globals():
        initialize_tts()

    # Get voice preset
    voice_preset = get_voice_preset(channel_name, db_file)

    # Generate file name and output directory
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{channel_name}-{timestamp}.wav"
    channel_directory = os.path.join("static/outputs", channel_name)
    if not os.path.exists(channel_directory):
        os.makedirs(channel_directory)

    full_path = os.path.join(channel_directory, filename)

    try:
        # TTS processing
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        processor = AutoProcessor.from_pretrained("suno/bark-small")
        model = BarkModel.from_pretrained("suno/bark-small").to(device)
        model.to_bettertransformer()
        model.enable_cpu_offload()

        # Splitting input text into sentences
        sentences = sent_tokenize(input_text)
        all_audio_pieces = []
        for sentence in sentences:
            # Split long sentences into smaller parts
            pieces = []
            while len(sentence) > 165:
                split_index = sentence.rfind(' ', 0, 165)
                if split_index == -1:  # No space found, forced split
                    split_index = 164
                pieces.append(sentence[:split_index + 1])
                sentence = sentence[split_index + 1:]
            pieces.append(sentence)

            # Process each piece with TTS
            for piece in pieces:
                inputs = processor(piece, voice_preset=voice_preset).to(device)
                audio_array = model.generate(**inputs)
                audio_array = audio_array.cpu().numpy().squeeze()
                all_audio_pieces.append(audio_array)

        # Concatenate all audio pieces
        final_audio_array = np.concatenate(all_audio_pieces)

        # Writing concatenated audio data to file
        scipy.io.wavfile.write(full_path, rate=model.generation_config.sample_rate, data=final_audio_array)

        # Logging the TTS file
        message_id = int(time.time())
        log_tts_file(message_id, channel_name, timestamp, full_path, voice_preset, input_text, db_file)

        # Notify the Flask app that a new audio file is available
        notify_new_audio_available(channel_name, message_id)

        return full_path

    except Exception as e:
        print(f"[TTS] An error occurred during TTS processing: {e}")
        return None
    
def start_tts_processing(input_text, channel_name, db_file='./messages.db'):
    tts_thread = threading.Thread(target=process_text_thread, args=(input_text, channel_name, db_file))
    tts_thread.start()
    # Suppress specific warnings from TTS libraries
    warnings.filterwarnings('ignore', message='The BetterTransformer implementation does not support padding during training*')
    warnings.filterwarnings('ignore', message='The attention mask and the pad token id were not set*')
    warnings.filterwarnings('ignore', message='Setting `pad_token_id` to `eos_token_id`*')
    warnings.filterwarnings("ignore", category=UserWarning)

    
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