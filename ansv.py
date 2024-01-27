import argparse
from threading import Thread
from utils.bot import setup_bot
from utils.db_setup import ensure_db_setup
import warnings

# Initialize variable for TTS functionality
enable_tts = False

# Function to run the web application in a separate thread
# Function to run the web application in a separate thread
def run_webapp():
    from webapp import app  # Import the Flask app object

    # Run the Flask app with reloader disabled
    app.run(debug=True, host="0.0.0.0", port=5001, use_reloader=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild-cache", help="rebuild the Markov model cache at startup", action="store_true")
    parser.add_argument("--tts", help="enable TTS functionality", action="store_true")
    parser.add_argument("--web", help="run web server in a separate thread", action="store_true")
    args = parser.parse_args()

    # Set the TTS flag based on the command line argument
    enable_tts = args.tts

    # Import TTS-related modules only if the TTS flag is set
    if enable_tts:
        from transformers import AutoProcessor, BarkModel
        import torch
        import scipy.io.wavfile

    # Start the webapp in a separate thread if the --web flag is passed
    if args.web:
        web_thread = Thread(target=run_webapp, daemon=True)
        web_thread.start()

    # Setup and run the bot
    db_file = "messages.db"
    ensure_db_setup(db_file)
    bot_instance = setup_bot(db_file, rebuild_cache=args.rebuild_cache, enable_tts=enable_tts)
    bot_instance.run()
