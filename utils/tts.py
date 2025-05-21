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
            db_file_path_relative = full_path.replace('static/', '', 1)
            
            # Restore stdout/stderr temporarily for critical DB logging
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            
            logged_tts_table_id = None # Renamed from logged_tts_id for clarity
            timestamp_for_log = timestamp # Use the passed original message timestamp

            # Validate critical parameters before database operation
            if message_id is None:
                logging.error(f"[TTS DB LOG] Critical: message_id is None for channel {channel_name}, text: '{str(input_text)[:30]}...'. Cannot log TTS entry without message_id.")
                # Do not proceed to DB insert if message_id is None
            elif full_path is None:
                logging.error(f"[TTS DB LOG] Critical: full_path is None for message_id {message_id}. Cannot log TTS entry.")
            else:
                if timestamp_for_log is None: # This is the original message timestamp string
                    logging.warning(f"[TTS DB LOG] Warning: Original message timestamp (timestamp param) is None for message_id {message_id}. Using current time for TTS log.")
                    timestamp_for_log = datetime.now().strftime("%Y%m%d-%H%M%S")

                try:
                    logging.info(f"[TTS DB LOG] Attempting to log to tts_logs: message_id={message_id}, channel={channel_name}, timestamp={timestamp_for_log}, voice={voice_preset}, path={db_file_path_relative}, text='{str(input_text)[:30]}...'")
                    conn = sqlite3.connect(db_file)
                    c = conn.cursor()
                    # It's good practice to ensure message_id is not None if it's a key part of your log.
                    # The earlier check for message_id being None should prevent this block from running if it's critical.
                    c.execute('''INSERT INTO tts_logs 
                                (message_id, channel, timestamp, voice_preset, file_path, message)
                                VALUES (?, ?, ?, ?, ?, ?)''',
                            (message_id, channel_name, timestamp_for_log, voice_preset, db_file_path_relative, input_text))
                    conn.commit()
                    
                    # lastrowid gets the ROWID of the last inserted row.
                    # If message_id is the primary key and not an alias for ROWID, lastrowid might not be message_id.
                    # If tts_logs has its own auto-incrementing integer primary key (e.g., log_id INTEGER PRIMARY KEY AUTOINCREMENT),
                    # then lastrowid will be that new log_id.
                    logged_tts_table_id = c.lastrowid 
                    
                    # Verify the insert by trying to fetch the row using message_id if it's supposed to be unique or a key.
                    # This is optional but good for debugging.
                    c.execute("SELECT COUNT(*) FROM tts_logs WHERE message_id = ?", (message_id,))
                    count_for_message_id = c.fetchone()[0]
                    
                    conn.close()
                    logging.info(f"[TTS DB LOG] Successfully logged. TTS Log Table ID (ROWID): {logged_tts_table_id}, Original Message ID: {message_id}. Count for this message_id in tts_logs: {count_for_message_id}.")
                    if count_for_message_id > 1:
                        logging.warning(f"[TTS DB LOG] Multiple tts_logs entries found for message_id {message_id}. This might indicate an issue if message_id should be unique per TTS event.")

                except sqlite3.Error as db_err:
                    logging.error(f"[TTS DB LOG] SQLite error during tts_logs insert: {db_err}")
                    logging.error(f"[TTS DB LOG] Data was: message_id={message_id}, channel={channel_name}, timestamp={timestamp_for_log}, voice={voice_preset}, path={db_file_path_relative}, text='{str(input_text)[:30]}...'")
                    logged_tts_table_id = None # Ensure it's None on error
                except Exception as general_db_err:
                    logging.error(f"[TTS DB LOG] General error during tts_logs insert: {general_db_err}", exc_info=True)
                    logged_tts_table_id = None # Ensure it's None on error

            # Re-silence output if further Bark/TTS processing was needed (though it's done here)
            silence_output()
            
            # Notify with the ID of the tts_logs table entry only if logging was successful
            if logged_tts_table_id is not None:
                notify_new_audio_available(channel_name, logged_tts_table_id) 
            
            # Log internally without printing to console (already done above with [TTS DB LOG])
            # logging.info(f"TTS audio file generated: {full_path}. Logged to tts_logs with table ID: {logged_tts_table_id} (linked to original message_id: {message_id})")
            
            return full_path, logged_tts_table_id # Return the ID of the tts_logs table entry
            
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
