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

def main():
    try:
        parser = argparse.ArgumentParser(description="ANSV Bot")
        parser.add_argument("--rebuild-cache", action="store_true", help="Rebuild markov models")
        parser.add_argument("--web", action="store_true", help="Enable web interface")
        parser.add_argument("--tts", action="store_true", help="Enable TTS functionality")
        parser.add_argument("--voice-preset", dest="voice_preset", type=str, help="Set default voice preset for TTS")
        args = parser.parse_args()

        print(f"Arguments parsed: {args}")
        
        global enable_tts
        enable_tts = args.tts
        
        # Store voice preset in environment variable for TTS module to access
        if args.voice_preset:
            os.environ["DEFAULT_VOICE_PRESET"] = args.voice_preset
            print(f"Set voice preset: {args.voice_preset}")

        # Check required settings first
        if not os.path.exists('settings.conf'):
            print("Missing settings.conf file")
            raise FileNotFoundError("Missing settings.conf - copy settings.example.conf and modify")

        # Import TTS-related modules only if the TTS flag is set
        if enable_tts:
            try:
                print("Importing TTS modules...")
                from transformers import AutoProcessor, BarkModel
                import torch
                import scipy.io.wavfile
                print("TTS modules imported successfully")
            except Exception as e:
                print(f"Error importing TTS modules: {e}")
                raise

        # Start the webapp in a separate thread if the --web flag is passed
        if args.web:
            print("Starting web thread...")
            web_thread = Thread(target=run_webapp, daemon=True)
            web_thread.start()
            print("Web thread started")

        # Setup and run the bot with detailed error handling
        try:
            print("Setting up database...")
            db_file = "messages.db"
            ensure_db_setup(db_file)
            print("Database setup complete")
            
            print("Setting up bot...")
            global bot_instance
            bot_instance = setup_bot(db_file, rebuild_cache=args.rebuild_cache, enable_tts=enable_tts)
            print("Bot setup complete, starting bot...")
            bot_instance.run()
            print("Bot run completed")
        except Exception as e:
            print(f"Error setting up or running bot: {e}")
            import traceback
            traceback.print_exc()
            raise

        # Validate TTS requirements
        if args.tts and not torch.cuda.is_available():
            print("WARNING: TTS enabled without CUDA - performance will be poor")
    except Exception as e:
        print(f"Error in main function: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    
    print("Starting ANSV Bot...")
    try:
        main()
        print("Main function completed successfully")
    except Exception as e:
        print(f"Error in main function: {e}")
        graceful_shutdown(None, None)
        sys.exit(1)
