import argparse
from threading import Thread
from utils.bot import setup_bot
from utils.db_setup import ensure_db_setup
import os
import torch
import signal
import sys

enable_tts = False



def run_webapp():
    from webapp import app, socketio
    socketio.run(app, host="0.0.0.0", port=5001, debug=False)

def graceful_shutdown(signum, frame):
    print("\n\n🌀 Received shutdown signal! Cleaning up...")
    
    # Stop the bot
    if 'bot_instance' in globals():
        print("🛑 Stopping Twitch bot...")
        if bot_instance.loop.is_running():
            bot_instance.loop.create_task(bot_instance.close())
            bot_instance.loop.stop()
    
    # Stop web server
    if 'web_thread' in globals() and web_thread.is_alive():
        print("🌐 Stopping web server...")
        from webapp import socketio
        socketio.stop()
    
    print("✅ Clean shutdown complete!")
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    
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

    # Setup and run the bot with exception handling
    try:
        db_file = "messages.db"
        ensure_db_setup(db_file)
        bot_instance = setup_bot(db_file, rebuild_cache=args.rebuild_cache, enable_tts=enable_tts)
        bot_instance.run()
    except Exception as e:
        graceful_shutdown(None, None)
        raise

    # Check required settings
    if not os.path.exists('settings.conf'):
        raise FileNotFoundError("Missing settings.conf - copy settings.example.conf and modify")
    
    # Validate TTS requirements
    if args.tts and not torch.cuda.is_available():
        print("WARNING: TTS enabled without CUDA - performance will be poor")
