import argparse
from threading import Thread
from utils.bot.factory import create_bot
from utils.db_setup import ensure_db_setup
import os
import torch # Keep torch import for TTS check
import signal
import sys
import time # For shutdown delay
import asyncio # Added import for asyncio

# Global variable to hold the bot instance for graceful shutdown
bot_instance = None
# Global variable for the web thread
web_thread = None
# Global flag for TTS status, to be passed to webapp
enable_tts_global = False


def run_webapp():
    # Import webapp modules inside the function to avoid circular dependencies
    # if webapp.py also imports things from ansv or utils that might depend on ansv's state.
    from webapp import app, socketio, set_enable_tts
    
    # Pass TTS setting to webapp
    global enable_tts_global
    set_enable_tts(enable_tts_global) # Call the function in webapp.py
    
    # Run the webapp using SocketIO's server
    # use_reloader=False is important when running in a thread managed by another script
    socketio.run(app, host="0.0.0.0", port=5001, debug=False, use_reloader=False)

def graceful_shutdown(signum, frame):
    print("\n\n🌀 Received shutdown signal! Cleaning up...")
    
    global bot_instance, web_thread

    # Stop the bot
    if bot_instance:
        print("🛑 Stopping Twitch bot...")
        if bot_instance.loop and bot_instance.loop.is_running():
            # Schedule the close operation on the bot's event loop
            future = asyncio.run_coroutine_threadsafe(bot_instance.close(), bot_instance.loop)
            try:
                future.result(timeout=5) # Wait up to 5 seconds for close to complete
                print("Twitch bot closed.")
            except TimeoutError:
                print("Twitch bot close timed out.")
            except Exception as e:
                print(f"Error during bot close: {e}")
            
            # Stop the bot's event loop
            if bot_instance.loop.is_running():
                bot_instance.loop.call_soon_threadsafe(bot_instance.loop.stop)
                # Give loop a moment to stop
                time.sleep(0.5) 
                if bot_instance.loop.is_running(): # Check again
                    print("Warning: Bot event loop did not stop gracefully.")
        else:
            print("Bot loop not running or not available.")
    else:
        print("Bot instance not found for shutdown.")
    
    # Stop web server (Flask-SocketIO needs specific handling)
    if web_thread and web_thread.is_alive():
        print("🌐 Stopping web server (this might take a moment)...")
        # Flask-SocketIO server running via socketio.run() doesn't have a simple stop()
        # The typical way is to send a SIGINT/SIGTERM to the main process, which we are already handling.
        # If run_webapp is in a daemon thread, it should exit when the main thread exits.
        # For a more explicit stop, one might need to use a different WSGI server or manage the Flask app differently.
        # For now, relying on process termination.
        # If you were using app.run(), you could try to raise a KeyboardInterrupt in the web_thread.
        # from webapp import socketio # This might cause issues if webapp isn't fully loaded
        # if 'socketio' in locals() and hasattr(socketio, 'stop'):
        # socketio.stop() # This method might not exist depending on server (e.g. Werkzeug)
        print("Web server shutdown relies on main process termination.")

    # Clean up PID file
    if os.path.exists("bot.pid"):
        try:
            os.remove("bot.pid")
            print("PID file removed.")
        except OSError as e:
            print(f"Error removing PID file: {e}")
            
    print("✅ Clean shutdown process initiated. Exiting.")
    sys.exit(0)

def main():
    global bot_instance, web_thread, enable_tts_global
    try:
        parser = argparse.ArgumentParser(description="ANSV Bot")
        parser.add_argument("--rebuild-cache", action="store_true", help="Rebuild markov models")
        parser.add_argument("--web", action="store_true", help="Enable web interface")
        parser.add_argument("--tts", action="store_true", help="Enable TTS functionality")
        parser.add_argument("--voice-preset", dest="voice_preset", type=str, help="Set default voice preset for TTS")
        args = parser.parse_args()

        print(f"Arguments parsed: {args}")
        
        enable_tts_global = args.tts # Set the global flag
        
        if args.voice_preset:
            os.environ["DEFAULT_VOICE_PRESET"] = args.voice_preset
            print(f"Set default voice preset via environment: {args.voice_preset}")

        if not os.path.exists('settings.conf'):
            print("FATAL: Missing settings.conf file. Please copy settings.example.conf to settings.conf and configure it.")
            sys.exit(1)

        if enable_tts_global:
            try:
                print("Importing TTS modules (transformers, torch, scipy)...")
                from transformers import AutoProcessor, BarkModel # Required by Bark
                import torch # Required by Bark and for CUDA check
                import scipy.io.wavfile # Used by Bark for saving
                print("TTS core modules imported successfully.")
            except ImportError as e:
                print(f"FATAL: Error importing TTS modules: {e}. TTS cannot be enabled.")
                print("Please ensure you have installed all dependencies from requirements-tts.txt.")
                enable_tts_global = False # Disable TTS if imports fail
            except Exception as e:
                print(f"An unexpected error occurred during TTS module import: {e}")
                enable_tts_global = False


        if args.web:
            print("Starting web thread...")
            web_thread = Thread(target=run_webapp, daemon=True) # Daemon thread will exit when main exits
            web_thread.start()
            print("Web thread started.")
            # Give the web server a moment to start up if needed
            time.sleep(1)


        print("Setting up database...")
        db_file = "messages.db"
        ensure_db_setup(db_file)
        print("Database setup complete.")
            
        print("Setting up bot...")
        bot_instance = asyncio.run(create_bot(
            config_path="settings.conf",
            rebuild_cache=args.rebuild_cache, 
            enable_tts=enable_tts_global
        ))
        print("Bot setup complete, starting bot...")
        
        # Create PID file after bot setup, before run
        try:
            with open("bot.pid", "w") as f:
                f.write(str(os.getpid()))
            print(f"PID file created with PID: {os.getpid()}")
        except IOError as e:
            print(f"Error creating PID file: {e}")
            # Decide if this is fatal or just a warning

        bot_instance.run() # This is a blocking call
        print("Bot run loop has exited.")

        if enable_tts_global and not torch.cuda.is_available(): # Check after bot run, though less relevant here
            print("WARNING: TTS was enabled without CUDA - performance might have been poor.")

    except FileNotFoundError as e:
        print(f"FATAL ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error in main ANSV Bot execution: {e}")
        import traceback
        traceback.print_exc()
        # graceful_shutdown will be called by the finally block or signal handler
        sys.exit(1) # Ensure exit if main crashes before bot.run()
    finally:
        # This finally block might not be reached if bot.run() is blocking indefinitely
        # and is only interrupted by a signal. The signal handler is more reliable for cleanup.
        print("Main function's finally block reached.")
        # Call graceful_shutdown here if not triggered by a signal (e.g., normal exit from bot.run())
        # However, if bot.run() is truly blocking, this won't be hit until it stops.
        # If signals are the primary way to stop, the signal handler is key.


if __name__ == "__main__":
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    
    print("Starting ANSV Bot...")
    main()
    # If main() completes without sys.exit(), it means bot.run() returned.
    print("ANSV Bot main function has completed. Performing final cleanup...")
    graceful_shutdown(None, None) # Ensure cleanup if main() returns normally
