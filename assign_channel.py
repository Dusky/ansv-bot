#!/usr/bin/env python3
"""
Script to assign a channel to a user
Usage: python3 assign_channel.py <username> <channel_name>
"""

import sys
import os

# Add the project root to the path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from utils.user_db import UserDatabase

def assign_channel(username, channel_name):
    user_db = UserDatabase('users.db')
    
    # Get user ID
    conn = user_db.get_connection()
    try:
        user = conn.execute("SELECT id, username FROM users WHERE username = ?", (username,)).fetchone()
        if not user:
            print(f"❌ User '{username}' not found")
            return False
        
        user_id = user['id']
        print(f"✅ Found user: {username} (id: {user_id})")
        
        # Assign the channel
        result = user_db.assign_channel_to_user(user_id, channel_name)
        if result:
            print(f"✅ Successfully assigned channel '{channel_name}' to user '{username}'")
            
            # Verify assignment
            channels = user_db.get_user_channels_from_db(user_id)
            print(f"✅ User now has access to channels: {channels}")
            return True
        else:
            print(f"❌ Failed to assign channel '{channel_name}' to user '{username}'")
            return False
            
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 assign_channel.py <username> <channel_name>")
        print("Example: python3 assign_channel.py Skip skip_skipperson")
        sys.exit(1)
    
    username = sys.argv[1]
    channel_name = sys.argv[2]
    
    print(f"🔧 Assigning channel '{channel_name}' to user '{username}'...")
    success = assign_channel(username, channel_name)
    
    if success:
        print("🎉 Channel assignment completed successfully!")
    else:
        print("💥 Channel assignment failed!")
        sys.exit(1)