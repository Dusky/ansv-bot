#!/usr/bin/env python3
"""
Promote User to Admin Tool

Promotes an existing user to admin or super_admin role.
Usage: python3 promote_admin.py [username]
"""

import sys
import os

# Add the project root to the path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from utils.user_db import UserDatabase

def promote_user_to_admin(username=None):
    """Promote a user to super_admin role."""

    print("=" * 60)
    print("👑 PROMOTE USER TO ADMIN")
    print("=" * 60)
    print()

    # Initialize database
    user_db = UserDatabase('users.db')

    # Get all users
    users = user_db.get_all_users()

    if not users:
        print("❌ No users found in database.")
        print("Please create a user account first by registering on the web interface.")
        return False

    # If username not provided, show list
    if not username:
        print("Available users:")
        for i, user in enumerate(users, 1):
            print(f"  {i}. {user['username']} ({user['email']}) - Role: {user['role_display_name']}")
        print()

        choice = input("Enter username or number to promote: ").strip()

        # Check if it's a number
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(users):
                username = users[idx]['username']
            else:
                print("❌ Invalid selection")
                return False
        else:
            username = choice

    # Get user
    user = user_db.get_user_by_username(username)
    if not user:
        print(f"❌ User '{username}' not found")
        return False

    # Check if already admin
    if user['role_name'] in ['admin', 'super_admin']:
        print(f"✓ User '{username}' is already an admin ({user['role_display_name']})")
        return True

    # Get super_admin role
    conn = user_db.get_connection()
    try:
        super_admin_role = conn.execute(
            "SELECT id FROM roles WHERE name = 'super_admin'"
        ).fetchone()

        if not super_admin_role:
            print("❌ Super admin role not found in database")
            return False

        # Update user role
        conn.execute(
            "UPDATE users SET role_id = ? WHERE id = ?",
            (super_admin_role['id'], user['user_id'])
        )
        conn.commit()

        print()
        print(f"✅ SUCCESS!")
        print(f"   User '{username}' promoted to Super Admin")
        print(f"   Email: {user['email']}")
        print()
        print("🎉 You can now access the admin panel at:")
        print("   http://localhost:5001/admin")
        print()

        return True

    except Exception as e:
        print(f"❌ Error promoting user: {e}")
        return False
    finally:
        conn.close()

def main():
    """Main function."""
    username = sys.argv[1] if len(sys.argv) > 1 else None

    if not os.path.exists('users.db'):
        print("❌ users.db not found.")
        print("Please run this script from the project root directory.")
        return 1

    try:
        success = promote_user_to_admin(username)
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user.")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
