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



    def generate_message(self, channel_name=None):
        """Generate a message using the specified channel's model, or the general model if None"""
        try:
            if channel_name is None or channel_name == 'general':
                # Use the general model
                model_file = os.path.join(self.cache_directory, "general_markov_model.json")
                model_name = "general_markov"
            else:
                # Use the channel-specific model
                model_file = os.path.join(self.cache_directory, f"{channel_name}_model.json")
                model_name = channel_name
            
            # Check if model exists
            if not os.path.exists(model_file):
                self.logger.error(f"Model file not found: {model_file}")
                return None
            
            # Load the model
            model = self.models.get(model_name)
            if not model:
                self.logger.info(f"Loading model: {model_name}")
                with open(model_file, 'r') as f:
                    model_data = json.load(f)
                self.models[model_name] = model_data
                model = model_data
            
            # Generate message using markovify's built-in method
            # The model might be a Markovify model or a JSON representation
            if isinstance(model, dict):
                # It's already the JSON, use it to create a Text model
                model_obj = markovify.Text.from_json(json.dumps(model))
                return model_obj.make_sentence()
            else:
                # It's already a model object
                return model.make_sentence()
        except Exception as e:
            self.logger.error(f"Error generating message: {e}")
            return None

    def get_available_models(self):
        """Get a list of available models from the cache directory."""
        return [filename.replace("_model.json", "") for filename in os.listdir(self.cache_directory) if filename.endswith("_model.json")]




    def rebuild_all_caches(self):
        """
        Rebuilds caches for all .txt files in the logs directory.
        """
        logs_directory = 'logs'  # Directory where log files are stored
        success = True
        for filename in os.listdir(logs_directory):
            if filename.endswith('.txt'):
                channel_name = filename.replace('.txt', '')
                if not self.rebuild_cache_for_channel(channel_name, logs_directory):
                    success = False
        return success

    def rebuild_cache_for_channel(self, channel_name, logs_directory):
        """
        Rebuilds the cache for a single channel.
        """
        log_file_path = os.path.join(logs_directory, f'{channel_name}.txt')
        if not os.path.exists(log_file_path):
            self.logger.error(f'Log file not found: {log_file_path}')
            return False

        try:
            with open(log_file_path, 'r') as file:
                text = file.read()
            model = markovify.Text(text)
            self.models[channel_name] = model
            self.save_model_to_cache(channel_name, model)
            return True
        except Exception as e:
            self.logger.error(f'Error rebuilding cache for {channel_name}: {e}')
            return False

    def save_model_to_cache(self, channel_name, model):
        """
        Saves a Markov model to a cache file.
        """
        cache_file_path = os.path.join(self.cache_directory, f'{channel_name}_model.json')
        model_json = model.to_json()
        with open(cache_file_path, 'w') as cache_file:
            cache_file.write(model_json)
        self.logger.info(f'Saved model to cache: {cache_file_path}')
        
    def rebuild_general_cache(self, logs_directory):
        """
        Rebuilds the general cache from all .txt files in the logs directory.
        """
        combined_text = ""
        for filename in os.listdir(logs_directory):
            if filename.endswith('.txt') and filename != "general_markov.txt":  # Skip the general_markov.txt file
                file_path = os.path.join(logs_directory, filename)
                try:
                    with open(file_path, 'r') as file:
                        combined_text += file.read() + "\n"
                except FileNotFoundError:
                    self.logger.error(f"Log file not found: {file_path}")
                    return False
                except Exception as e:
                    self.logger.error(f"Error reading file {file_path}: {e}")
                    return False

        if combined_text:
            try:
                general_model = markovify.Text(combined_text)
                self.models["general"] = general_model
                self.save_general_model_to_cache(general_model)
                return True
            except Exception as e:
                self.logger.error(f"Error creating general model: {e}")
                return False
        else:
            self.logger.warning("No text found to build general model.")
            return False

    def save_general_model_to_cache(self, model):
        """
        Saves the general Markov model to a cache file.
        """
        cache_file_path = os.path.join(self.cache_directory, 'general_markov_model.json')
        model_json = model.to_json()
        with open(cache_file_path, 'w') as cache_file:
            cache_file.write(model_json)
        self.logger.info(f'Saved general model to cache: {cache_file_path}')