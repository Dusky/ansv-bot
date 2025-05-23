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

# Add lock to prevent concurrent TTS processing for Bark model
bark_tts_lock = threading.Lock() # For process_text_thread
async_tts_lock = asyncio.Lock() # For async def process_text, renamed from tts_lock for clarity

def fetch_latest_message():
    try:
        logging.debug(f"Fetching latest message from database: {db_file}")
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT id, channel, timestamp, message_length, message FROM messages ORDER BY id DESC LIMIT 1")
        result = c.fetchone()
        logging.debug(f"Latest message fetched: {result}")
        conn.close()
        return result if result else (None, None, None, None, None)
    except sqlite3.Error as e:
        logging.error(f"SQLite error in fetch_latest_message: {e}")
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
    conn = None
    try:
        conn = sqlite3.connect(db_file, timeout=10.0) # Added timeout
        c = conn.cursor()
        # Using INSERT OR IGNORE to handle potential duplicate message_ids gracefully
        c.execute("INSERT OR IGNORE INTO tts_logs (message_id, channel, timestamp, file_path, voice_preset, message) VALUES (?, ?, ?, ?, ?, ?)",
                (message_id, channel_name, timestamp, file_path, voice_preset, input_text))
        conn.commit()
        if c.rowcount == 0:
            logging.warning(f"[log_tts_file] Insert to tts_logs IGNORED for message_id {message_id} (likely duplicate).")
        else:
            logging.info(f"[log_tts_file] Successfully inserted into tts_logs for message_id {message_id}.")
    except sqlite3.Error as e:
        logging.error(f"[log_tts_file] SQLite error for message_id {message_id}: {e}")
    finally:
        if conn:
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
    global original_stdout, original_stderr, bark_tts_lock
    
    # Log parameters *before* silencing, for critical debugging
    logging.info(f"[TTS THREAD ENTRY] Params: input_text='{str(input_text)[:30]}...', channel='{channel_name}', db_file='{db_file}', full_path='{full_path}', timestamp='{timestamp}', message_id='{message_id}', voice_preset='{voice_preset}', bark_model='{bark_model}'")
    if message_id is None:
        logging.error("[TTS THREAD CRITICAL] message_id is None at entry. This will likely cause DB insert to fail or be incorrect.")
    if full_path is None:
        logging.error("[TTS THREAD CRITICAL] full_path is None at entry. Cannot save audio or log correctly.")
    if timestamp is None: # This is the original message timestamp
        logging.warning("[TTS THREAD WARNING] Original message timestamp (timestamp param) is None at entry.")


    # Acquire lock to ensure only one thread generates Bark audio at a time
    with bark_tts_lock:
        logging.info(f"[TTS THREAD] Acquired Bark TTS lock for message_id: {message_id}")
        silence_output() # Silence output for Bark inside the lock

        try:
            # Make sure we have the necessary TTS dependencies
            if 'AutoProcessor' not in globals():
                initialize_tts()
            
            import torch
            import scipy.io.wavfile
            from transformers import AutoProcessor, BarkModel
            from nltk.tokenize import sent_tokenize
        except ImportError as import_err:
            # Restore output for error logging if imports fail
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            logging.error(f"[TTS THREAD FATAL ERROR] Failed to import critical TTS dependencies: {import_err}", exc_info=True)
            # Re-raise the error to be caught by the outer try-except in process_text_thread, which will restore stdout/stderr again
            # and return None, None, preventing further execution in this thread.
            raise
        
        try:
            # Get channel-specific bark model if available
            if not bark_model:
                bark_model = get_bark_model_for_channel(channel_name, db_file)
            
            # Default to bark-small if no model specified
            if not bark_model:
                bark_model = "bark-small"
            
            logging.info(f"Using Bark model: {bark_model} for channel {channel_name}") # Keep as info
            model_path = f"suno/{bark_model}"
            
            # Initialize TTS model
            device_type_str = "cuda" if torch.cuda.is_available() else "cpu"
            device = torch.device(device_type_str)
            
            # This log will be silenced by silence_output() if logging to console, 
            # but visible if logger is configured for files.
            logging.info(f"TTS: Attempting to use device: {device_type_str}")

            processor = AutoProcessor.from_pretrained(model_path)
            
            # Ensure the tokenizer has a pad_token_id. For Bark, this is often the eos_token_id.
            if processor.tokenizer.pad_token_id is None:
                if processor.tokenizer.eos_token_id is not None:
                    processor.tokenizer.pad_token_id = processor.tokenizer.eos_token_id
                    logging.info(f"Set processor.tokenizer.pad_token_id to eos_token_id: {processor.tokenizer.eos_token_id}")
                else:
                    # Fallback if eos_token_id is also None (highly unlikely for Bark)
                    processor.tokenizer.pad_token_id = 10000 # Bark's EOS token ID
                    logging.warning(f"processor.tokenizer.eos_token_id is None. Set pad_token_id to fallback: 10000")

            # The error "module 'torch' has no attribute 'get_default_device'" typically occurs
            # if the PyTorch version is older than 1.9, as this function was introduced then.
            # The 'transformers' library's from_pretrained method seems to internally call this.
            # The best fix is to ensure PyTorch is v1.9+ and transformers is compatible.
            # The following code attempts to load the model, but may still hit the error if versions are mismatched.

            try:
                # Load model to CPU first by default with from_pretrained, then move to target device
                model = BarkModel.from_pretrained(model_path)
                model = model.to(device) 

                if device_type_str == "cuda":
                    logging.info("TTS: Applying CUDA specific optimizations (to_bettertransformer, enable_cpu_offload).")
                    # These operations are for CUDA and require appropriate library versions.
                    model.to_bettertransformer()
                    model.enable_cpu_offload() # Requires 'accelerate' library
            except AttributeError as ae:
                if 'get_default_device' in str(ae):
                    # Restore stdout/stderr to ensure this critical message is visible via standard print/logging
                    sys.stdout = original_stdout
                    sys.stderr = original_stderr
                    logging.error(f"[TTS FATAL ERROR] AttributeError: {ae}. This strongly suggests your PyTorch version is too old (e.g., < 1.9) for the installed 'transformers' version.")
                    logging.error("[TTS FATAL ERROR] Please upgrade PyTorch to 1.9+ or align your 'transformers' library version with your PyTorch version.")
                    raise # Re-raise the error to be caught by the outer try-except in process_text_thread
                else:
                    # Restore stdout/stderr for other AttributeErrors too
                    sys.stdout = original_stdout
                    sys.stderr = original_stderr
                    logging.error(f"[TTS FATAL ERROR] AttributeError during model loading: {ae}")
                    raise # Re-raise other AttributeErrors
            except Exception as model_load_exc:
                # Restore stdout/stderr for general exceptions during model loading
                sys.stdout = original_stdout
                sys.stderr = original_stderr
                logging.error(f"[TTS FATAL ERROR] Failed to load or prepare BarkModel: {model_load_exc}", exc_info=True)
                raise # Re-raise the error
            
            # Handle voice preset (built-in vs custom)
            if voice_preset and voice_preset.startswith('v2/'):
                # Built-in Bark preset - nothing special needed
                logging.info(f"Using built-in Bark preset: {voice_preset} for channel {channel_name}") # Keep as info
                # The preset will be used directly in the processor call
            else:
                # Try to load custom voice if available
                custom_voice_data = load_custom_voice(voice_preset)
                if custom_voice_data and 'weights' in custom_voice_data:
                    model.load_state_dict(custom_voice_data['weights'])
                    logging.info(f"Loaded custom voice: {voice_preset} for channel {channel_name}") # Keep as info
                else:
                    # Fall back to default preset if custom voice not found
                    voice_preset = 'v2/en_speaker_5' # Default preset
                    logging.info(f"Using fallback voice preset: {voice_preset} for channel {channel_name}") # Keep as info

            # Process text in chunks for better performance
            all_audio_pieces = []
            sentences = sent_tokenize(input_text)
            
            for sentence in sentences:
                pieces = split_sentence(sentence, 165)  # Split long sentences
                for piece in pieces:
                    # Generate speech with the selected voice preset
                    # Removed padding=True as it caused TypeError with BarkProcessor.
                    # The processor should handle padding and attention_mask with return_tensors="pt".
                    inputs = processor(text=piece, voice_preset=voice_preset, return_tensors="pt").to(device)
                    
                    # The model.generate call should now use the attention_mask from inputs.
                    # Explicitly passing pad_token_id can also help, using the model's config.
                    # Bark's EOS token ID (10000) is often used as pad_token_id for generation.
                    pad_token_id_for_generation = model.generation_config.pad_token_id or model.generation_config.eos_token_id or 10000

                    audio_array = model.generate(**inputs, pad_token_id=pad_token_id_for_generation)
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

                db_conn_tts_log = None
                try:
                    logging.info(f"[TTS DB LOG] Attempting to log to tts_logs: message_id={message_id}, channel={channel_name}, timestamp={timestamp_for_log}, voice={voice_preset}, path={db_file_path_relative}, text='{str(input_text)[:30]}...'")
                    db_conn_tts_log = sqlite3.connect(db_file, timeout=10.0) # Added timeout
                    c = db_conn_tts_log.cursor()
                    
                    c.execute('''INSERT OR IGNORE INTO tts_logs 
                                (message_id, channel, timestamp, voice_preset, file_path, message)
                                VALUES (?, ?, ?, ?, ?, ?)''', # Ensured INSERT OR IGNORE
                            (message_id, channel_name, timestamp_for_log, voice_preset, db_file_path_relative, input_text))
                    db_conn_tts_log.commit()
                    
                    if c.rowcount == 0:
                        logging.warning(f"[TTS DB LOG] Insert to tts_logs IGNORED for message_id {message_id} (likely duplicate or other constraint).")
                        # Attempt to fetch existing log_id if it was ignored due to duplicate
                        c.execute("SELECT ROWID FROM tts_logs WHERE message_id = ?", (message_id,))
                        existing_row = c.fetchone()
                        if existing_row:
                            logged_tts_table_id = existing_row[0]
                            logging.info(f"[TTS DB LOG] Found existing tts_logs ROWID: {logged_tts_table_id} for message_id {message_id}.")
                        else: # Should not happen if PK is message_id and it was a duplicate
                            logged_tts_table_id = None 
                    else:
                        logged_tts_table_id = c.lastrowid 
                        logging.info(f"[TTS DB LOG] Successfully logged. TTS Log Table ID (ROWID): {logged_tts_table_id}, Original Message ID: {message_id}.")
                
                except sqlite3.IntegrityError as integrity_err:
                    # This block might be hit if "datatype mismatch" is the true issue, not handled by INSERT OR IGNORE.
                    logging.error(f"[TTS DB LOG] SQLite IntegrityError (message_id: {message_id}): {integrity_err}. This might indicate a schema mismatch if not a duplicate.")
                    logging.error(f"[TTS DB LOG] Failed Data: message_id={message_id}, channel={channel_name}, timestamp={timestamp_for_log}, voice={voice_preset}, path={db_file_path_relative}, text='{str(input_text)[:30]}...'")
                    logged_tts_table_id = None 
                except sqlite3.Error as db_err: 
                    logging.error(f"[TTS DB LOG] Other SQLite error during tts_logs insert (message_id: {message_id}): {db_err}")
                    logging.error(f"[TTS DB LOG] Data was: message_id={message_id}, channel={channel_name}, timestamp={timestamp_for_log}, voice={voice_preset}, path={db_file_path_relative}, text='{str(input_text)[:30]}...'")
                    logged_tts_table_id = None 
                except Exception as general_db_err:
                    logging.error(f"[TTS DB LOG] General error during tts_logs insert (message_id: {message_id}): {general_db_err}", exc_info=True)
                    logged_tts_table_id = None
                finally:
                    if db_conn_tts_log:
                        db_conn_tts_log.close()

            # Re-silence output if further Bark/TTS processing was needed (though it's done here)
            silence_output()
            
            # Notify with the ID of the tts_logs table entry only if logging was successful
            if logged_tts_table_id is not None:
                notify_new_audio_available(channel_name, logged_tts_table_id) 
            
            # Log internally without printing to console (already done above with [TTS DB LOG])
            # logging.info(f"TTS audio file generated: {full_path}. Logged to tts_logs with table ID: {logged_tts_table_id} (linked to original message_id: {message_id})")
            
            return full_path, logged_tts_table_id # Return the ID of the tts_logs table entry
            
        except Exception as e:
            # Ensure output is restored before printing error from this broad catch-all
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            # This is a fatal error for this thread, so logging.error is appropriate
            logging.error(f"[TTS THREAD FATAL ERROR] Uncaught exception in process_text_thread: {e}", exc_info=True)
            # import traceback # exc_info=True handles this
            # traceback.print_exc()
            return None, None # Ensure two values are returned as expected if caller unpacks
        finally:
            # Always restore original stdout and stderr
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            logging.info(f"[TTS THREAD] Released Bark TTS lock for message_id: {message_id}")

def load_custom_voice(voice_preset):
    """Load a custom voice file if it exists"""
    # If no voice_preset is provided, it's not a custom voice.
    if voice_preset is None:
        # This print will be silenced if called from process_text_thread during normal operation,
        # but visible if stdout/stderr are restored or if called directly.
        logging.debug("No voice preset provided to load_custom_voice, assuming default will be used by caller.")
        return None

    # Handle built-in presets
    if voice_preset.startswith('v2/'):
        # These are built-in to Bark, no file needed
        logging.debug(f"Using built-in Bark voice preset: {voice_preset}")
        return None
    
    # For custom voices, check file existence
    voice_file = os.path.join(VOICES_DIRECTORY, f"{voice_preset}.npz")
    if not os.path.exists(voice_file):
        logging.warning(f"Custom voice file not found: {voice_file}")
        # Fall back to default
        return None
    
    try:
        # Load custom voice data
        voice_data = np.load(voice_file, allow_pickle=True)
        weights = {k: torch.tensor(v) for k, v in voice_data.items()}
        return {'weights': weights}
    except Exception as e:
        logging.error(f"Error loading custom voice {voice_preset}: {e}")
        return None

def ensure_nltk_resources():
    """Ensure NLTK resources are downloaded"""
    import nltk
    try:
        from nltk.tokenize import sent_tokenize
        # Test if punkt is working
        sent_tokenize("Test sentence.")
    except (LookupError, ImportError):
        logging.info("Downloading required NLTK resources (punkt)...") # Keep as info, important one-time setup
        try:
            nltk.download('punkt')
            return True
        except Exception as e:
            logging.error(f"Failed to download NLTK resources: {e}") # Keep as error
            return False
    return True

async def process_text(channel, text, model_type="bark"): # This is for the !speak command path
    """Process text to speech with proper locking and error handling"""
    # Use locking to prevent concurrent TTS processing
    global async_tts_lock # Use the asyncio lock for this async function
    async with async_tts_lock:
        try:
            logging.info(f"Starting ASYNC TTS for channel {channel} (likely !speak command)")
            
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
                logging.info(f"TTS audio file generated: {output_file}") # This log indicates successful file generation
                
                # Removed the broken internal database logging attempt from here.
                # Logging is now handled by the caller (e.g., handle_speak_command in bot.py).
                
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
    
def start_tts_processing(input_text, channel_name, db_file='./messages.db', message_id=None, timestamp_str=None, voice_preset_override=None):
    """
    Starts the TTS processing in a separate thread.
    message_id: The ID of the original message that triggered this TTS.
    timestamp_str: The timestamp string of the original message.
    voice_preset_override: Optional voice preset to use, otherwise fetched from DB.
    """
    filename_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S") 
    clean_channel_name = channel_name.lstrip('#')
    output_dir = f"static/outputs/{clean_channel_name}"
    os.makedirs(output_dir, exist_ok=True)
    generated_full_path = f"{output_dir}/{clean_channel_name}-{filename_timestamp}.wav"

    logging.info(f"Preparing TTS thread for bot message. Original message_id: {message_id}, original_timestamp_str: {timestamp_str}, voice_preset_override: {voice_preset_override}, generated_path: {generated_full_path}")

    # Arguments for process_text_thread:
    # input_text, channel_name, db_file, full_path, timestamp, message_id, voice_preset, bark_model=None
    tts_thread = threading.Thread(
        target=process_text_thread, 
        args=(
            input_text, 
            channel_name, 
            db_file,
            generated_full_path,      # This becomes 'full_path' in process_text_thread
            timestamp_str,            # This becomes 'timestamp' (original message timestamp)
            message_id,               # This becomes 'message_id'
            voice_preset_override     # This becomes 'voice_preset'
            # bark_model will be fetched by process_text_thread if None
        ), 
        daemon=True
    )
    tts_thread.start()
    # Logging that the thread has been dispatched. The thread itself will log its entry.
    # logging.info(f"TTS processing thread dispatched for original message_id {message_id} in channel {channel_name}.")

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
            logging.debug("Notification sent successfully to webapp for new audio.")
        else:
            logging.warning(f"Failed to send new audio notification to webapp (status: {response.status_code})")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending new audio notification to webapp: {e}")
