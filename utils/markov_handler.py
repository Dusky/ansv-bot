import os
import markovify
import logging

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
