#ansv.py
import argparse

from threading import Thread
from utils.bot import setup_bot
from utils.db_setup import ensure_db_setup


bot_instance = None

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild-cache", help="rebuild the Markov model cache at startup", action="store_true")
    args = parser.parse_args()

    db_file = "messages.db"
    ensure_db_setup(db_file)



    bot_instance = setup_bot(db_file)

    #bot_instance.run()