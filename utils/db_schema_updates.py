"""
Database schema updates for the modular bot architecture.
This adds missing tables and columns needed by the new modular system.
"""

import sqlite3
import logging
from typing import Optional


def update_database_schema(db_file: str) -> bool:
    """Update database schema to support modular architecture."""
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        
        logging.info("Starting database schema updates for modular architecture...")
        
        # 1. Add missing columns to channel_configs table
        c.execute("PRAGMA table_info(channel_configs)")
        existing_columns = [row[1] for row in c.fetchall()]
        
        missing_columns = [
            ('markov_enabled', 'BOOLEAN DEFAULT 1'),
            ('markov_response_threshold', 'INTEGER DEFAULT 50')
        ]
        
        for column_name, column_def in missing_columns:
            if column_name not in existing_columns:
                try:
                    c.execute(f'ALTER TABLE channel_configs ADD COLUMN {column_name} {column_def}')
                    logging.info(f"Added column '{column_name}' to channel_configs")
                except sqlite3.Error as e:
                    logging.error(f"Failed to add column {column_name}: {e}")
        
        # 2. Create missing trusted_users table
        c.execute('''CREATE TABLE IF NOT EXISTS trusted_users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        channel_name TEXT NOT NULL,
                        username TEXT NOT NULL,
                        added_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(channel_name, username)
                    )''')
        logging.info("Created trusted_users table")
        
        # 3. Create missing cache_build_times table
        c.execute('''CREATE TABLE IF NOT EXISTS cache_build_times (
                        channel_name TEXT PRIMARY KEY,
                        build_time REAL NOT NULL,
                        updated_timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                    )''')
        logging.info("Created cache_build_times table")
        
        # 4. Add indexes for new tables
        new_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_trusted_users_channel ON trusted_users(channel_name)",
            "CREATE INDEX IF NOT EXISTS idx_trusted_users_username ON trusted_users(username)",
            "CREATE INDEX IF NOT EXISTS idx_cache_build_times_channel ON cache_build_times(channel_name)",
            "CREATE INDEX IF NOT EXISTS idx_cache_build_times_time ON cache_build_times(build_time)"
        ]
        
        for index_sql in new_indexes:
            try:
                c.execute(index_sql)
                logging.debug(f"Created index: {index_sql}")
            except sqlite3.Error as e:
                logging.warning(f"Failed to create index: {index_sql} - {e}")
        
        # 5. Migrate existing cache_build_log data to cache_build_times if needed
        c.execute("SELECT COUNT(*) FROM cache_build_log")
        cache_log_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM cache_build_times")
        cache_times_count = c.fetchone()[0]
        
        if cache_log_count > 0 and cache_times_count == 0:
            logging.info("Migrating cache_build_log data to cache_build_times...")
            c.execute('''
                INSERT OR REPLACE INTO cache_build_times (channel_name, build_time)
                SELECT channel_name, MAX(timestamp) 
                FROM cache_build_log 
                WHERE success = 1 
                GROUP BY channel_name
            ''')
            logging.info(f"Migrated cache data for channels")
        
        conn.commit()
        logging.info("Database schema updates completed successfully")
        return True
        
    except sqlite3.Error as e:
        logging.error(f"Database error during schema update: {e}")
        if conn:
            conn.rollback()
        return False
    except Exception as e:
        logging.error(f"Unexpected error during schema update: {e}")
        return False
    finally:
        if conn:
            conn.close()


def verify_schema_compatibility(db_file: str) -> dict:
    """Verify that the database schema is compatible with modular architecture."""
    results = {
        'compatible': True,
        'missing_tables': [],
        'missing_columns': [],
        'issues': []
    }
    
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        
        # Check required tables
        required_tables = [
            'messages', 'channel_configs', 'tts_logs', 'bot_status',
            'trusted_users', 'cache_build_times'
        ]
        
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in c.fetchall()]
        
        for table in required_tables:
            if table not in existing_tables:
                results['missing_tables'].append(table)
                results['compatible'] = False
        
        # Check required columns in key tables
        table_columns = {
            'channel_configs': ['markov_enabled', 'markov_response_threshold'],
            'messages': ['channel', 'author_name', 'message', 'timestamp'],
            'tts_logs': ['channel', 'message', 'file_path', 'voice_preset'],
            'trusted_users': ['channel_name', 'username'],
            'cache_build_times': ['channel_name', 'build_time']
        }
        
        for table_name, required_cols in table_columns.items():
            if table_name in existing_tables:
                c.execute(f"PRAGMA table_info({table_name})")
                existing_cols = [row[1] for row in c.fetchall()]
                
                for col in required_cols:
                    if col not in existing_cols:
                        results['missing_columns'].append(f"{table_name}.{col}")
                        results['compatible'] = False
        
        # Check for potential data issues
        try:
            c.execute("SELECT COUNT(*) FROM messages WHERE channel IS NULL OR author_name IS NULL")
            null_data_count = c.fetchone()[0]
            if null_data_count > 0:
                results['issues'].append(f"{null_data_count} messages with NULL channel or author")
        except sqlite3.Error:
            pass
        
        conn.close()
        
    except sqlite3.Error as e:
        results['compatible'] = False
        results['issues'].append(f"Database access error: {e}")
    
    return results


if __name__ == "__main__":
    import sys
    
    db_file = sys.argv[1] if len(sys.argv) > 1 else "messages.db"
    
    # First verify current schema
    print("Checking current database schema...")
    compat = verify_schema_compatibility(db_file)
    
    if compat['compatible']:
        print("✅ Database schema is already compatible!")
    else:
        print("❌ Database schema needs updates:")
        if compat['missing_tables']:
            print(f"  Missing tables: {', '.join(compat['missing_tables'])}")
        if compat['missing_columns']:
            print(f"  Missing columns: {', '.join(compat['missing_columns'])}")
        if compat['issues']:
            print(f"  Issues: {', '.join(compat['issues'])}")
        
        print("\nApplying schema updates...")
        if update_database_schema(db_file):
            print("✅ Schema updates completed successfully!")
        else:
            print("❌ Schema updates failed!")
            sys.exit(1)