import argparse
import logging
from threading import Thread
from flask import Flask, render_template, jsonify
from utils.bot import setup_bot
from utils.db_setup import ensure_db_setup
# Import the ensure_db_setup function here if it's in a different module


app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.disabled = True

bot_instance = None

# Call ensure_db_setup function with the path to your database file

@app.route('/')
def home():
    """Serve the home page."""
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    """Generate a message using the bot."""
    global bot_instance
    if bot_instance:
        channel_name = 'default_channel'  # Modify as needed
        message = bot_instance.generate_message(channel_name=channel_name)
        return jsonify({'message': message})
    return jsonify({'message': 'Bot instance not available.'}), 500

def run_flask_app():
    """Run the Flask app."""
    app.run(host='0.0.0.0', port=5000)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", help="start the Flask app", action="store_true")
    parser.add_argument("--rebuild-cache",
                        help="rebuild the Markov model cache at startup",
                        action="store_true")
    args = parser.parse_args()

    db_file = "messages.db"  # Define db_file here
    ensure_db_setup(db_file)  # Ensure database setup

    bot_instance = setup_bot(db_file)  # Pass db_file as an argument
    bot_instance.run()  # Run the bot

    if args.web:
        flask_thread = Thread(target=run_flask_app, daemon=True)
        flask_thread.start()