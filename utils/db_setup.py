import sqlite3
import configparser

def ensure_db_setup(db_file):
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()

        # Create 'messages' table
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY,
                        message TEXT,
                        timestamp TEXT,
                        channel TEXT,
                        state_size INTEGER,
                        message_length INTEGER,
                        tts_processed BOOLEAN NOT NULL DEFAULT 0
                    )''')

        # Create 'channel_configs' table with default columns
        c.execute('''CREATE TABLE IF NOT EXISTS channel_configs (
                        channel_name TEXT PRIMARY KEY,
                        tts_enabled BOOLEAN NOT NULL,
                        voice_enabled BOOLEAN NOT NULL,
                        join_channel BOOLEAN NOT NULL,
                        owner TEXT,
                        trusted_users TEXT,
                        ignored_users TEXT,
                        use_general_model BOOLEAN NOT NULL DEFAULT 1,
                        lines_between_messages INTEGER DEFAULT 100,
                        time_between_messages INTEGER DEFAULT 0
                        -- Note: 'voice_preset' column will be checked and added below if missing
                    )''')

        # Create 'user_colors' table
        c.execute('''CREATE TABLE IF NOT EXISTS user_colors (
                        username TEXT PRIMARY KEY,
                        color TEXT
                    )''')

        # Create 'tts_logs' table for TTS file logging
        c.execute('''CREATE TABLE IF NOT EXISTS tts_logs (
                        message_id INTEGER PRIMARY KEY,
                        channel TEXT,
                        timestamp TEXT,
                        file_path TEXT,
                        voice_preset TEXT,
                        message TEXT
                    )''')

        # Check and add missing columns in 'channel_configs'
        c.execute("PRAGMA table_info(channel_configs)")
        channel_config_columns = [row[1] for row in c.fetchall()]
        if 'lines_between_messages' not in channel_config_columns:
            c.execute('ALTER TABLE channel_configs ADD COLUMN lines_between_messages INTEGER DEFAULT 100')
            print("Column 'lines_between_messages' added to 'channel_configs'.")
        if 'time_between_messages' not in channel_config_columns:
            c.execute('ALTER TABLE channel_configs ADD COLUMN time_between_messages INTEGER DEFAULT 0')
            print("Column 'time_between_messages' added to 'channel_configs'.")
        if 'voice_preset' not in channel_config_columns:
            c.execute('ALTER TABLE channel_configs ADD COLUMN voice_preset TEXT DEFAULT \'v2/en_speaker_5\'')
            print("Column 'voice_preset' added to 'channel_configs'.")

        # Further code for initializing channels and handling settings...

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()
