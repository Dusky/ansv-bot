import requests
import sqlite3
from colors import *
# Twitch API credentials
client_id = 'wstzdcfxzjl8xizx91v65u7a4t7lg1'
client_secret = 'l37uzwt1eyc4ymh54a0svefmjr3s1u'

# Database file
db_file = 'messages.db'

def get_oauth_token(client_id, client_secret):
    url = 'https://id.twitch.tv/oauth2/token'
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    response = requests.post(url, data=payload)
    return response.json()['access_token']

def get_user_info(username, access_token):
    headers = {
        'Client-ID': client_id,
        'Authorization': f'Bearer {access_token}'
    }
    url = f'https://api.twitch.tv/helix/users?login={username}'
    response = requests.get(url, headers=headers)
    return response.json()

def get_user_color(user_id, access_token):
    headers = {
        'Client-ID': client_id,
        'Authorization': f'Bearer {access_token}'
    }
    url = f'https://api.twitch.tv/helix/chat/color?user_id={user_id}'
    response = requests.get(url, headers=headers)
    return response.json()
def get_user_id(self, username, access_token):
    user_info = get_user_info(username, access_token)
    return user_info['data'][0]['id'] if user_info['data'] else None

def get_or_fetch_user_color(username, user_id, access_token):
    print(f"Username: {username}, Type: {type(username)}")

    username_str = str(username)
    print(f"Converted Username: {username_str}, Type: {type(username_str)}")

    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    try:
        c.execute("SELECT color FROM user_colors WHERE username = ?", (username_str,))
        result = c.fetchone()
        print(f"DB Query Result: {result}")

        if result:
            color_hex = result[0]
            print(f"Color found in DB: {color_hex}")
        else:
            user_color_data = get_user_color(user_id, access_token)
            print(f"User Color Data from API: {user_color_data}")

            if user_color_data['data']:
                color_hex = user_color_data['data'][0].get('color')
                print(f"Color from API: {color_hex}")
            else:
                color_hex = None

            if color_hex:
                c.execute("INSERT INTO user_colors (username, color) VALUES (?, ?)", (username_str, color_hex))
                conn.commit()
                print(f"Color inserted into DB: {color_hex}")
    except Exception as e:
        print(f"Error fetching or storing color for user {username}: {e}")
    finally:
        conn.close()

    ansi_color = hex2ansi(color_hex) if color_hex else 'Default Color'
    print(f"ANSI Color: {ansi_color}")

    return ansi_color




if __name__ == "__main__":
    access_token = get_oauth_token(client_id, client_secret)
    username = 'example_username'
    user_info = get_user_info(username, access_token)
    user_id = user_info['data'][0]['id']
    user_color = get_or_fetch_user_color(username, user_id, access_token)

    print(f"User ID: {user_id}")
    print(f"User Color: {user_color if user_color else 'Default Color'}")
