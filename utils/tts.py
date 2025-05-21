import os
import time
import asyncio
import logging
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

# Add lock to prevent concurrent TTS processing
tts_lock = asyncio.Lock()

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
        
def get_bark_model_for_channel(channel_name, db_file):
    try:
        # Check for default model from environment
        default_model = os.environ.get("DEFAULT_BARK_MODEL")
        if default_model:
            return default_model
        
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT bark_model FROM channel_configs WHERE channel_name = ?", (channel_name,))
        result = c.fetchone()
        return result[0] if result else 'bark-small'
    except Exception as e:
        print(f"Error getting bark model for channel {channel_name}: {e}")
        return 'bark-small'
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

def process_text_thread(input_text, channel_name, db_file='./messages.db', full_path=None, timestamp=None, message_id=None, voice_preset=None, bark_model=None):
    """Process TTS in a separate thread with silenced output"""
    global original_stdout, original_stderr
    
    # Log parameters *before* silencing, for critical debugging
    logging.info(f"[TTS THREAD ENTRY] Params: input_text='{str(input_text)[:30]}...', channel='{channel_name}', db_file='{db_file}', full_path='{full_path}', timestamp='{timestamp}', message_id='{message_id}', voice_preset='{voice_preset}', bark_model='{bark_model}'")
    if message_id is None:
        logging.error("[TTS THREAD CRITICAL] message_id is None at entry. This will likely cause DB insert to fail or be incorrect.")
    if full_path is None:
        logging.error("[TTS THREAD CRITICAL] full_path is None at entry. Cannot save audio or log correctly.")
    if timestamp is None: # This is the original message timestamp
        logging.warning("[TTS THREAD WARNING] Original message timestamp (timestamp param) is None at entry.")


    silence_output() # Now silence output for Bark

    try:
        # Make sure we have the necessary TTS dependencies
        if 'AutoProcessor' not in globals():
            initialize_tts()
            
        import torch
        import scipy.io.wavfile
        from transformers import AutoProcessor, BarkModel
        from nltk.tokenize import sent_tokenize
        
        try:
            # Get channel-specific bark model if available
            if not bark_model:
                bark_model = get_bark_model_for_channel(channel_name, db_file)
            
            # Default to bark-small if no model specified
            if not bark_model:
                bark_model = "bark-small"
                
            print(f"Using Bark model: {bark_model}")
            model_path = f"suno/{bark_model}"
            
            # Initialize TTS model
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            processor = AutoProcessor.from_pretrained(model_path)
            model = BarkModel.from_pretrained(model_path).to(device)

            if torch.cuda.is_available():
                model.to_bettertransformer()
                model.enable_cpu_offload()
            
            # Handle voice preset (built-in vs custom)
            if voice_preset and voice_preset.startswith('v2/'):
                # Built-in Bark preset - nothing special needed
                print(f"Using built-in Bark preset: {voice_preset}")
                # The preset will be used directly in the processor call
            else:
                # Try to load custom voice if available
                custom_voice_data = load_custom_voice(voice_preset)
                if custom_voice_data and 'weights' in custom_voice_data:
                    model.load_state_dict(custom_voice_data['weights'])
                    print(f"Loaded custom voice: {voice_preset}")
                else:
                    # Fall back to default preset if custom voice not found
                    voice_preset = 'v2/en_speaker_5'
                    print(f"Using fallback voice preset: {voice_preset}")

            # Process text in chunks for better performance
            all_audio_pieces = []
            sentences = sent_tokenize(input_text)
            
            for sentence in sentences:
                pieces = split_sentence(sentence, 165)  # Split long sentences
                for piece in pieces:
                    # Generate speech with the selected voice preset
                    inputs = processor(text=piece, voice_preset=voice_preset).to(device)
                    audio_array = model.generate(**inputs)
                    audio_array = audio_array.cpu().numpy().squeeze()
                    all_audio_pieces.append(audio_array)

            # Combine all audio pieces and save
            final_audio_array = np.concatenate(all_audio_pieces)
            scipy.io.wavfile.write(full_path, rate=model.generation_config.sample_rate, data=final_audio_array)
            
            # Record in database and notify web interface
            # Ensure message_id is used here. It's passed as an argument to process_text_thread.
            # The timestamp argument should also be used.
            # The full_path should be relative to static/ for consistency with log_tts_file.
            db_file_path_relative = full_path.replace('static/', '', 1)

            conn = sqlite3.connect(db_file)
            c = conn.cursor()
            # Use the passed message_id, channel_name, timestamp, voice_preset, and input_text
            c.execute('''INSERT INTO tts_logs 
                        (message_id, channel, timestamp, voice_preset, file_path, message)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                    (message_id, channel_name, timestamp, voice_preset, db_file_path_relative, input_text))
            conn.commit()
            # new_id is not strictly needed here if message_id is already known and used as primary key for this log.
            # If tts_logs has its own auto-incrementing ID, then c.lastrowid would be that.
            # For now, assuming message_id from the original message is the key link.
            logged_tts_id = c.lastrowid # This would be the auto-incremented ID of tts_logs table if it has one.
                                        # If message_id is the PK, this might not be what you expect.
                                        # Let's assume tts_logs has its own PK for now.
            conn.close()
            
            # Notify with the ID of the tts_logs entry
            notify_new_audio_available(channel_name, logged_tts_id) 
            
            # Log internally without printing to console
            logging.info(f"TTS audio file generated: {full_path} and logged with tts_logs ID: {logged_tts_id} (original message_id: {message_id})")
            
            return full_path, logged_tts_id # Return the ID of the tts_logs entry
            
        except Exception as e:
            print(f"[TTS] Thread processing error: {e}")
            return None
            
    finally:
        # Always restore original stdout and stderr
        sys.stdout = original_stdout
        sys.stderr = original_stderr

def load_custom_voice(voice_preset):
    """Load a custom voice file if it exists"""
    # Handle built-in presets
    if voice_preset.startswith('v2/'):
        # These are built-in to Bark, no file needed
        print(f"Using built-in Bark voice preset: {voice_preset}")
        return None
    
    # For custom voices, check file existence
    voice_file = os.path.join(VOICES_DIRECTORY, f"{voice_preset}.npz")
    if not os.path.exists(voice_file):
        print(f"Custom voice file not found: {voice_file}")
        # Fall back to default
        return None
    
    try:
        # Load custom voice data
        voice_data = np.load(voice_file, allow_pickle=True)
        weights = {k: torch.tensor(v) for k, v in voice_data.items()}
        return {'weights': weights}
    except Exception as e:
        print(f"Error loading custom voice: {e}")
        return None

def ensure_nltk_resources():
    """Ensure NLTK resources are downloaded"""
    import nltk
    try:
        from nltk.tokenize import sent_tokenize
        # Test if punkt is working
        sent_tokenize("Test sentence.")
    except (LookupError, ImportError):
        print("Downloading required NLTK resources...")
        try:
            nltk.download('punkt')
            return True
        except Exception as e:
            print(f"Failed to download NLTK resources: {e}")
            return False
    return True

async def process_text(channel, text, model_type="bark"):
    """Process text to speech with proper locking and error handling"""
    # Use locking to prevent concurrent TTS processing
    async with tts_lock:
        try:
            logging.info(f"Starting TTS for channel {channel}")
            
            # Create output directory if it doesn't exist
            output_dir = f"static/outputs/{channel}"
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            output_file = f"{output_dir}/{channel}-{timestamp}.wav"
            
            # Don't write file before processing - wait until after successful generation
            if model_type == "bark":
                # Import inside function to avoid loading models unnecessarily
                from bark import SAMPLE_RATE, generate_audio, preload_models
                from scipy.io.wavfile import write as write_wav
                
                # Make sure models are loaded
                preload_models()
                
                # Log which voice we're using
                logging.info(f"Using built-in Bark voice preset: v2/en_speaker_0")
                
                # Generate audio with minimal parameters to avoid API issues
                # The Bark API might have changed, so we only use params we know are supported
                audio_array = generate_audio(
                    text,
                    history_prompt="v2/en_speaker_0",
                    text_temp=0.7,
                    waveform_temp=0.7
                )
                
                # Only write file AFTER successful generation
                write_wav(output_file, SAMPLE_RATE, audio_array)
                logging.info(f"TTS audio file generated: {output_file}")
                
                return True, output_file
            elif model_type == "elevenlabs":
                # Handle other TTS providers
                # ...implementation for elevenlabs...
                pass
            else:
                logging.error(f"Unknown TTS model type: {model_type}")
                return False, None
                
        except Exception as e:
            logging.error(f"TTS processing error: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return False, None

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
