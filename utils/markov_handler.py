import os
import markovify
import logging
import json


class MarkovHandler:
    def __init__(self, cache_directory):
        self.cache_directory = cache_directory
        self.models = {}
        self.logger = logging.getLogger(__name__)


    def load_models(self):
        """Load all models from cache files in the cache directory."""
        self.logger.info("Loading models from cache...")
        successful_loads = []  # Initialize a list to keep track of successful loads
        failed_loads = []  # Optionally, track failed loads as well
        for filename in os.listdir(self.cache_directory):
            if filename.endswith("_model.json"):
                # Extract the channel name (or model name) from the filename
                channel_name = filename.replace("_model.json", "")
                model = self.load_model_from_cache(filename)
                if model:
                    self.models[channel_name] = model
                    successful_loads.append(channel_name)  # Add to successful loads
                else:
                    failed_loads.append(channel_name)  # Optionally, add to failed loads
                    self.logger.warning(f"Failed to load model for channel: {channel_name}")

        # Log a summary of loaded models
        if successful_loads:
            self.logger.info(f"Successfully loaded models for channels: {', '.join(successful_loads)}")
        # Optionally, log a summary of failed loads
        if failed_loads:
            self.logger.warning(f"Failed to load models for channels: {', '.join(failed_loads)}")

    def load_model_from_cache(self, filename):
        cache_file_path = os.path.join(self.cache_directory, filename)
        # Change to debug or remove to reduce verbosity
        self.logger.debug(f"Trying to load model from: {cache_file_path}")
        try:
            with open(cache_file_path, "r") as f:
                model_json = f.read()
                # Optionally, change to debug or remove this log
                self.logger.debug(f"Successfully loaded model from: {cache_file_path}")
                return markovify.Text.from_json(model_json)
        except FileNotFoundError:
            self.logger.error(f"Cache file not found: {cache_file_path}")
        except Exception as e:
            self.logger.error(f"Error loading model from {cache_file_path}: {e}")
        return None



    def generate_message(self, channel_name=None, max_attempts=8, max_fallbacks=2):
        """
        Generate a message using the specified channel's model, or the general model if None.
        
        Args:
            channel_name (str, optional): Channel name to generate message for. Defaults to None (general).
            max_attempts (int, optional): Maximum attempts to generate a message. Defaults to 8.
            max_fallbacks (int, optional): Maximum number of fallback attempts. Defaults to 2.
            
        Returns:
            str: Generated message or None if generation failed
        """
        # Keep track of fallbacks to prevent infinite recursion
        fallback_count = getattr(self, '_fallback_count', 0)
        self._fallback_count = fallback_count 
        
        # If we've exceeded max fallbacks, return a default message
        if fallback_count > max_fallbacks:
            self.logger.warning(f"Max fallback attempts ({max_fallbacks}) reached")
            self._fallback_count = 0  # Reset for next call
            return "Could not generate a message after multiple attempts."
            
        try:
            # Use general model as fallback if specified channel not found
            fallback_to_general = True
            
            if channel_name is None or channel_name == 'general':
                # Use the general model
                model_file = os.path.join(self.cache_directory, "general_markov_model.json")
                model_name = "general_markov"
                # Don't fallback to general since we're already using it
                fallback_to_general = False 
            else:
                # Use the channel-specific model
                model_file = os.path.join(self.cache_directory, f"{channel_name}_model.json")
                model_name = channel_name
            
            # Check if model exists
            if not os.path.exists(model_file):
                self.logger.error(f"Model file not found: {model_file}")
                # Try general model as fallback if appropriate
                if fallback_to_general:
                    self.logger.info(f"Falling back to general model for channel: {channel_name}")
                    self._fallback_count = fallback_count + 1
                    return self.generate_message("general", max_attempts, max_fallbacks)
                return None
            
            # Load the model
            model = self.models.get(model_name)
            if not model:
                self.logger.info(f"Loading model: {model_name}")
                try:
                    with open(model_file, 'r') as f:
                        model_data = json.load(f)
                    self.models[model_name] = model_data
                    model = model_data
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse model JSON for {model_name}: {e}")
                    if fallback_to_general:
                        self.logger.info(f"JSON error with {channel_name} model, trying general model")
                        self._fallback_count = fallback_count + 1
                        return self.generate_message("general", max_attempts, max_fallbacks)
                    return None
                except Exception as e:
                    self.logger.error(f"Error loading model {model_name}: {e}")
                    if fallback_to_general:
                        self.logger.info(f"Error loading {channel_name} model, trying general model")
                        self._fallback_count = fallback_count + 1
                        return self.generate_message("general", max_attempts, max_fallbacks)
                    return None
            
            # Generate message using markovify's built-in method with multiple attempts
            # The model might be a Markovify model or a JSON representation
            message = None
            
            # Log the generation attempt for monitoring
            self.logger.info(f"Attempting to generate message for {channel_name} (attempt 1/{max_attempts})")
            
            if isinstance(model, dict):
                # It's already the JSON, use it to create a Text model
                try:
                    model_obj = markovify.Text.from_json(json.dumps(model))
                    
                    # Make multiple attempts
                    for attempt in range(1, max_attempts + 1):
                        try:
                            message = model_obj.make_sentence(tries=100)  # More internal tries as well
                            if message:
                                self.logger.info(f"Generated message on attempt {attempt}/{max_attempts}")
                                break
                            elif attempt < max_attempts:
                                self.logger.debug(f"Failed to generate on attempt {attempt}/{max_attempts}, trying again")
                        except Exception as e:
                            self.logger.error(f"Error during sentence generation (attempt {attempt}): {e}")
                except Exception as e:
                    self.logger.error(f"Failed to create model from JSON for {channel_name}: {e}")
                    # Try fallback if appropriate
                    if fallback_to_general:
                        self.logger.info(f"Error creating model for {channel_name}, trying general model")
                        self._fallback_count = fallback_count + 1
                        return self.generate_message("general", max_attempts, max_fallbacks)
                    return None
            else:
                # It's already a model object
                # Make multiple attempts
                for attempt in range(1, max_attempts + 1):
                    try:
                        message = model.make_sentence(tries=100)  # More internal tries as well
                        if message:
                            self.logger.info(f"Generated message on attempt {attempt}/{max_attempts}")
                            break
                        elif attempt < max_attempts:
                            self.logger.debug(f"Failed to generate on attempt {attempt}/{max_attempts}, trying again")
                    except Exception as e:
                        self.logger.error(f"Error during sentence generation (attempt {attempt}): {e}")
            
            # If still no message, try fallback to general model
            if not message and fallback_to_general:
                self.logger.info(f"Couldn't generate message for {channel_name}, trying general model")
                self._fallback_count = fallback_count + 1
                return self.generate_message("general", max_attempts, max_fallbacks)
            
            # Return either the generated message or a default message
            if message:
                # Reset fallback counter on success
                self._fallback_count = 0
                return message
            else:
                # Only provide a default message if we can't fallback or are already in a fallback
                if not fallback_to_general or fallback_count > 0:
                    self.logger.warning(f"Failed to generate message for {channel_name or 'general'} after {max_attempts} attempts")
                    self._fallback_count = 0  # Reset for next call
                    return "Could not generate a message at this time."
                return None
                
        except Exception as e:
            self.logger.error(f"Error generating message: {e}")
            if fallback_to_general and channel_name != "general":
                self.logger.info(f"Error with {channel_name} model, trying general model")
                try:
                    self._fallback_count = fallback_count + 1
                    return self.generate_message("general", max_attempts, max_fallbacks)
                except Exception as e2:
                    self.logger.error(f"Error with fallback to general model: {e2}")
            
            # Reset fallback counter and return default message
            self._fallback_count = 0  # Reset for next call
            return "Could not generate a message due to an error."

    def get_available_models(self):
        """Get a list of available models from the cache directory."""
        return [filename.replace("_model.json", "") for filename in os.listdir(self.cache_directory) if filename.endswith("_model.json")]




    def rebuild_all_caches(self):
        """
        Rebuilds caches for all .txt files in the logs directory.
        """
        logs_directory = 'logs'  # Directory where log files are stored
        success = True
        rebuilt_count = 0
        try:
            # Create cache directory if it doesn't exist
            if not os.path.exists(self.cache_directory):
                os.makedirs(self.cache_directory)
                self.logger.info(f"Created cache directory: {self.cache_directory}")
            
            # Check if logs directory exists
            if not os.path.exists(logs_directory):
                self.logger.error(f"Logs directory does not exist: {logs_directory}")
                return False
            
            for filename in os.listdir(logs_directory):
                if filename.endswith('.txt'):
                    channel_name = filename.replace('.txt', '')
                    try:
                        if self.rebuild_cache_for_channel(channel_name, logs_directory):
                            rebuilt_count += 1
                        else:
                            success = False
                    except Exception as e:
                        self.logger.error(f"Error rebuilding cache for channel {channel_name}: {e}")
                        success = False
            
            # Also rebuild the general cache
            try:
                general_result = self.rebuild_general_cache(logs_directory)
                if general_result:
                    rebuilt_count += 1
                else:
                    success = False
            except Exception as e:
                self.logger.error(f"Error rebuilding general cache: {e}")
                success = False
            
            self.logger.info(f"Rebuilt {rebuilt_count} caches with overall success: {success}")
            return success
        except Exception as e:
            self.logger.error(f"Error in rebuild_all_caches: {e}")
            return False

    def rebuild_cache_for_channel(self, channel_name, logs_directory):
        """
        Rebuilds the cache for a single channel and tracks build time.
        """
        import time
        
        # Check if inputs are valid
        if not channel_name:
            self.logger.error("Empty channel name provided to rebuild_cache_for_channel")
            return False
            
        if not logs_directory or not os.path.exists(logs_directory):
            self.logger.error(f"Invalid logs directory: {logs_directory}")
            return False
            
        # Create cache directory if it doesn't exist
        if not os.path.exists(self.cache_directory):
            try:
                os.makedirs(self.cache_directory)
                self.logger.info(f"Created cache directory: {self.cache_directory}")
            except Exception as e:
                self.logger.error(f"Failed to create cache directory: {e}")
                return False
        
        # Check if log file exists
        log_file_path = os.path.join(logs_directory, f'{channel_name}.txt')
        if not os.path.exists(log_file_path):
            self.logger.error(f'Log file not found: {log_file_path}')
            return False

        try:
            # Record start time
            start_time = time.time()
            self.logger.info(f"Starting rebuild of cache for channel: {channel_name}")
            
            # Build the model
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as file:
                text = file.read()
                
            if not text or len(text.strip()) == 0:
                self.logger.warning(f"Empty log file for channel {channel_name}")
                self.record_build_time(channel_name, start_time, 0, False)
                return False
                
            # Create the Markov model
            model = markovify.Text(text)
            
            # Store in memory and save to cache
            self.models[channel_name] = model
            self.save_model_to_cache(channel_name, model)
            
            # Calculate duration and record build time
            end_time = time.time()
            duration = end_time - start_time
            success = True
            
            # Save build time information
            self.record_build_time(channel_name, start_time, duration, success)
            
            self.logger.info(f"Successfully rebuilt cache for channel {channel_name} in {duration:.2f}s")
            return True
        except Exception as e:
            self.logger.error(f'Error rebuilding cache for {channel_name}: {e}')
            # Record failed build
            try:
                self.record_build_time(channel_name, time.time(), 0, False)
            except Exception as record_error:
                self.logger.error(f"Failed to record build time: {record_error}")
            return False

    def save_model_to_cache(self, channel_name, model):
        """
        Saves a Markov model to a cache file.
        
        Args:
            channel_name (str): Name of the channel/model
            model (markovify.Text): Markov model to save
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create cache directory if it doesn't exist
            if not os.path.exists(self.cache_directory):
                os.makedirs(self.cache_directory)
                self.logger.info(f"Created cache directory: {self.cache_directory}")
            
            # Generate file path
            cache_file_path = os.path.join(self.cache_directory, f'{channel_name}_model.json')
            
            # Convert model to JSON
            model_json = model.to_json()
            
            # Save to file with atomic write pattern
            temp_path = cache_file_path + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as cache_file:
                cache_file.write(model_json)
                cache_file.flush()
                os.fsync(cache_file.fileno())  # Ensure data is written to disk
                
            # Rename temp file to actual file (atomic operation)
            if os.path.exists(cache_file_path):
                os.remove(cache_file_path)  # Remove old file if it exists
            os.rename(temp_path, cache_file_path)
            
            self.logger.info(f'Successfully saved model to cache: {cache_file_path}')
            return True
        except Exception as e:
            self.logger.error(f'Error saving model to cache for {channel_name}: {e}')
            return False
        
    def rebuild_general_cache(self, logs_directory):
        """
        Rebuilds the general cache from all .txt files in the logs directory.
        
        Args:
            logs_directory (str): Path to directory containing log files
            
        Returns:
            bool: True if successful, False otherwise
        """
        import time
        
        # Check if logs directory exists
        if not logs_directory or not os.path.exists(logs_directory):
            self.logger.error(f"Invalid logs directory: {logs_directory}")
            return False
            
        # Start time tracking
        start_time = time.time()
        self.logger.info(f"Starting rebuild of general cache")
        
        try:
            # Create cache directory if it doesn't exist
            if not os.path.exists(self.cache_directory):
                os.makedirs(self.cache_directory)
                self.logger.info(f"Created cache directory: {self.cache_directory}")
            
            # Read and combine all text from log files
            combined_text = ""
            file_count = 0
            total_chars = 0
            
            for filename in os.listdir(logs_directory):
                if filename.endswith('.txt') and filename != "general_markov.txt":  # Skip the general_markov.txt file
                    file_path = os.path.join(logs_directory, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                            file_text = file.read()
                            combined_text += file_text + "\n"
                            total_chars += len(file_text)
                            file_count += 1
                    except Exception as e:
                        self.logger.warning(f"Error reading file {file_path}: {e}")
                        # Continue with other files rather than failing completely
                        continue

            # Check if we have enough text
            if not combined_text or len(combined_text.strip()) < 100:
                self.logger.warning(f"Insufficient text found to build general model. Found {len(combined_text)} characters from {file_count} files.")
                self.record_build_time("general_markov", start_time, 0, False)
                return False
                
            # Log progress
            self.logger.info(f"Read {file_count} files with total {total_chars} characters for general model")
                
            # Create the model
            general_model = markovify.Text(combined_text)
            
            # Save to memory and file
            self.models["general_markov"] = general_model
            
            # Save to cache
            cache_file_path = os.path.join(self.cache_directory, 'general_markov_model.json')
            model_json = general_model.to_json()
            
            # Use atomic write pattern
            temp_path = cache_file_path + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as cache_file:
                cache_file.write(model_json)
                cache_file.flush()
                os.fsync(cache_file.fileno())  # Ensure data is written to disk
                
            # Rename temp file to actual file (atomic operation)
            if os.path.exists(cache_file_path):
                os.remove(cache_file_path)  # Remove old file if it exists
            os.rename(temp_path, cache_file_path)
            
            # Record timing
            end_time = time.time()
            duration = end_time - start_time
            self.record_build_time("general_markov", start_time, duration, True)
            
            self.logger.info(f'Successfully built and saved general model in {duration:.2f}s')
            return True
        except Exception as e:
            self.logger.error(f"Error creating general model: {e}")
            
            # Record failed build
            try:
                self.record_build_time("general_markov", start_time, 0, False)
            except Exception as record_error:
                self.logger.error(f"Failed to record build time: {record_error}")
                
            return False
        
    def record_build_time(self, channel, timestamp, duration, success):
        """
        Records build time information to a JSON file for tracking performance.
        
        Args:
            channel (str): Channel name
            timestamp (float): Unix timestamp when build started
            duration (float): Duration in seconds
            success (bool): Whether the build was successful
        """
        try:
            # Cache file path
            cache_file_path = os.path.join(self.cache_directory, 'cache_build_times.json')
            
            # Create structured record
            record = {
                "channel": channel,
                "timestamp": timestamp,
                "duration": duration,
                "success": success
            }
            
            # Load existing records if file exists
            build_times = []
            if os.path.exists(cache_file_path):
                try:
                    with open(cache_file_path, 'r') as f:
                        content = f.read().strip()
                        if content:
                            build_times = json.loads(content)
                        if not isinstance(build_times, list):
                            # Convert old format to new format if needed
                            build_times = [{"channel": k, "timestamp": v, "duration": 0, "success": True} 
                                          for k, v in build_times.items()]
                except Exception as e:
                    self.logger.warning(f"Error loading existing build times, creating new file: {e}")
                    # Start with empty list if file was corrupted
                    build_times = []
            
            # Add new record
            build_times.append(record)
            
            # Keep only last 100 records to prevent file from growing too large
            if len(build_times) > 100:
                build_times = build_times[-100:]
            
            # Save updated records
            with open(cache_file_path, 'w') as f:
                json.dump(build_times, f)
                
            self.logger.info(f"Recorded build time for {channel}: {duration:.2f}s")
            
        except Exception as e:
            self.logger.error(f"Error recording build time: {e}")