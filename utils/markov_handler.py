import os
import markovify
import logging
import sqlite3
from datetime import datetime

class MarkovHandler:
    def __init__(self, cache_directory):
        self.cache_directory = cache_directory
        self.models = {}
        self.logger = logging.getLogger(__name__)

    def load_models(self):
        """Load all models from cache files in the cache directory."""
        self.logger.info("Loading models from cache...")
        for filename in os.listdir(self.cache_directory):
            if filename.endswith("_model.json"):
                # Extract the channel name (or model name) from the filename
                channel_name = filename.replace("_model.json", "")
                model = self.load_model_from_cache(filename)
                if model:
                    self.models[channel_name] = model
                    self.logger.info(f"Loaded model for channel: {channel_name}")
                else:
                    self.logger.warning(f"Failed to load model for channel: {channel_name}")

    def load_model_from_cache(self, filename):
        cache_file_path = os.path.join(self.cache_directory, filename)
        self.logger.info(f"Trying to load model from: {cache_file_path}")
        try:
            with open(cache_file_path, "r") as f:
                model_json = f.read()
                self.logger.info(f"Successfully loaded model from: {cache_file_path}")
                return markovify.Text.from_json(model_json)
        except FileNotFoundError:
            self.logger.error(f"Cache file not found: {cache_file_path}")
        except Exception as e:
            self.logger.error(f"Error loading model from {cache_file_path}: {e}")
        return None


    def generate_message(self, channel_name):
        """Generate a message from the model corresponding to the given channel."""
        model = self.models.get(channel_name)
        if model:
            message = model.make_sentence()
            if message:
                self.logger.info(f"{message}")
                return message
            else:
                self.logger.warning(f"Failed to generate message for {channel_name}")
        else:
            self.logger.warning(f"No model found for channel: {channel_name}")
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