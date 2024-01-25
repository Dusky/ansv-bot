# ansv.py
import argparse
from threading import Thread
from utils.bot import setup_bot
from utils.db_setup import ensure_db_setup
import warnings
# Initialize variable for TTS functionality
enable_tts = False

# Suppress specific warnings from TTS libraries
warnings.filterwarnings('ignore', message='The BetterTransformer implementation does not support padding during training*')
warnings.filterwarnings('ignore', message='The attention mask and the pad token id were not set*')
warnings.filterwarnings('ignore', message='Setting `pad_token_id` to `eos_token_id`*')
warnings.filterwarnings("ignore", category=UserWarning)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild-cache", help="rebuild the Markov model cache at startup", action="store_true")
    parser.add_argument("--tts", help="enable TTS functionality", action="store_true")
    args = parser.parse_args()

    # Set the TTS flag based on the command line argument
    enable_tts = args.tts

    db_file = "messages.db"
    ensure_db_setup(db_file)

    bot_instance = setup_bot(db_file, rebuild_cache=args.rebuild_cache, enable_tts=enable_tts)

    bot_instance.run()
