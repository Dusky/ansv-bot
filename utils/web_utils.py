"""
Web interface utility functions for ANSV Bot
"""
import os
import math
import json
import configparser
from typing import List, Dict, Any
from datetime import datetime

def get_available_models() -> List[Dict[str, Any]]:
    """
    Get a list of all available Markov models with metadata
    
    Returns:
        List of dictionaries with model information:
        {
            'name': str,            # Model name (typically channel name)
            'file_path': str,       # Path to the model file
            'size': int,            # Size in bytes
            'formatted_size': str,  # Human-readable size
            'last_modified': str,   # Timestamp of last modification
            'tokens': int,          # Number of tokens in model (if available)
            'messages': int,        # Number of messages used to build model (if available)
        }
    """
    cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
    results = []
    
    try:
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
            return results  # Empty list if directory was just created
            
        for filename in os.listdir(cache_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(cache_dir, filename)
                stats = os.stat(file_path)
                
                # Get model name from filename (remove .json extension)
                model_name = os.path.splitext(filename)[0]
                
                # Get last modified time
                last_modified = stats.st_mtime
                last_modified_str = format_timestamp(last_modified)
                
                # Get file size
                size_bytes = stats.st_size
                formatted_size = convert_size(size_bytes)
                
                # Try to get token and message counts from model file
                tokens = 0
                messages = 0
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        model_data = json.load(f)
                        # Different model formats might store these differently
                        if isinstance(model_data, dict):
                            if 'tokens' in model_data:
                                tokens = len(model_data['tokens'])
                            elif 'model' in model_data and isinstance(model_data['model'], dict):
                                tokens = len(model_data['model'].keys())
                            
                            # Try to get message count
                            if 'messages' in model_data:
                                messages = model_data['messages']
                            elif 'message_count' in model_data:
                                messages = model_data['message_count']
                except Exception as e:
                    print(f"Error reading model file {file_path}: {e}")
                
                # Add model info to results
                results.append({
                    'name': model_name,
                    'file_path': file_path,
                    'size': size_bytes,
                    'formatted_size': formatted_size,
                    'last_modified': last_modified_str,
                    'tokens': tokens,
                    'messages': messages
                })
        
        # Sort by name
        results.sort(key=lambda x: x['name'])
        return results
    
    except Exception as e:
        print(f"Error getting available models: {e}")
        return []

def convert_size(size_bytes: int) -> str:
    """
    Convert bytes to human-readable format
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Human-readable string (e.g., "2.5 MB")
    """
    if size_bytes == 0:
        return "0 B"
        
    size_names = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"

def format_timestamp(timestamp: float) -> str:
    """
    Format a timestamp into a human-readable date/time
    
    Args:
        timestamp: Unix timestamp
        
    Returns:
        Formatted date string
    """
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def get_db_stats() -> Dict[str, Any]:
    """
    Get statistics about the database
    
    Returns:
        Dictionary with database statistics
    """
    import sqlite3
    
    db_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'messages.db')
    stats = {
        'total_messages': 0,
        'channels': 0,
        'users': 0,
        'oldest_message': None,
        'newest_message': None,
        'channel_counts': [],
        'db_size': 0,
        'db_size_formatted': '0 B'
    }
    
    try:
        if not os.path.exists(db_file):
            return stats
            
        # Get file size
        stats['db_size'] = os.path.getsize(db_file)
        stats['db_size_formatted'] = convert_size(stats['db_size'])
        
        # Query database for statistics
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        
        # Total messages
        c.execute("SELECT COUNT(*) FROM messages")
        stats['total_messages'] = c.fetchone()[0]
        
        # Channel count
        c.execute("SELECT COUNT(DISTINCT channel) FROM messages")
        stats['channels'] = c.fetchone()[0]
        
        # User count
        c.execute("SELECT COUNT(DISTINCT user) FROM messages")
        stats['users'] = c.fetchone()[0]
        
        # Oldest message
        c.execute("SELECT MIN(timestamp) FROM messages")
        oldest = c.fetchone()[0]
        if oldest:
            stats['oldest_message'] = oldest
        
        # Newest message
        c.execute("SELECT MAX(timestamp) FROM messages")
        newest = c.fetchone()[0]
        if newest:
            stats['newest_message'] = newest
        
        # Messages per channel
        c.execute("""
            SELECT channel, COUNT(*) as count 
            FROM messages 
            GROUP BY channel 
            ORDER BY count DESC
        """)
        stats['channel_counts'] = [{'channel': row[0], 'count': row[1]} for row in c.fetchall()]
        
        conn.close()
        return stats
        
    except Exception as e:
        print(f"Error getting database stats: {e}")
        return stats 

def get_verbose_logs_setting() -> bool:
    """
    Check if verbose logs are enabled in environment variable or settings.conf
    
    Returns:
        bool: True if verbose logs are enabled, False otherwise
    """
    # First check environment variable (highest priority)
    verbose_env = os.environ.get('VERBOSE', '').lower()
    if verbose_env in ('true', '1', 'yes'):
        return True
    elif verbose_env in ('false', '0', 'no'):
        return False
    
    # If not set in environment, check settings.conf
    try:
        config = configparser.ConfigParser()
        config_file = 'settings.conf'
        
        if not os.path.exists(config_file):
            config_file = 'settings.example.conf'
            
        if os.path.exists(config_file):
            config.read(config_file)
            if 'web' in config and 'verbose_logs' in config['web']:
                return config['web'].getboolean('verbose_logs')
    except Exception as e:
        print(f"Error reading verbose_logs setting: {e}")
    
    # Default to False if not specified or error
    return False