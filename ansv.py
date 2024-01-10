"""
This module implements a Flask app and a Twitch bot.
The Flask app provides a web interface for generating messages using the bot.
"""

import argparse
import logging
from threading import Thread
from flask import Flask, render_template, jsonify
from utils.bot import setup_bot

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.disabled = True

bot_instance = None

@app.route('/')
def home():
    """Serve the home page."""
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    """Generate a message using the bot."""
    global bot_instance
    if bot_instance:
        # Assuming 'generate_message' needs a 'channel_name' argument
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
                        action="store_true"
                        )
    args = parser.parse_args()

    # Start the Markov Chain Bot
    bot_instance = setup_bot()

    # Run the bot
    bot_instance.run()

    # Start the Flask app if the argument is provided
    if args.web:
        flask_thread = Thread(target=run_flask_app, daemon=True)
        flask_thread.start()
