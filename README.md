# ANSV

Ansv is a robot that posts garbage based on chat history in your twitch channels.

## Features

- **Markov Chain Message Generation**: Automatically generates messages based on chat history.
- **Channel Management**: Join or leave Twitch channels as needed.
- **Customizable Settings**: Adjust time and line thresholds for message posting.
- **Trusted User System**: Designate trusted users for bot control in different channels.

## Getting Started

### Prerequisites

- Python 3.x
- `pip` (Python package manager)
- `pyenv` for Python version management (optional but recommended)



```sudo apt install python3-pip
pip install venv
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
pip install -r requirements-tts.txt #for tts support (roughly 3gigs of dependencies are required.)
```

**TTS requires NLTK punkt.**

```
(env) ~/ansv-bot $ python
>>> import nltk
>>> nltk.download('punkt')
[nltk_data] Downloading package punkt to /home/pi/nltk_data...
[nltk_data]   Unzipping tokenizers/punkt.zip.
True
```

**insert bot info into settings.conf**

    tmi_token = 
    client_id = 
```
python ansv.py #to launch the twitch bot
python webapp.py #to launch the web interface on port 5001
```
Launch ansv.py with --tts to enable tts functionality. 



- **!ansv speak**
  -  Generates and sends a message.

- **!ansv start**
  -  Enables ansv in a channel.

- **!ansv stop**
  -  Disables ansv in a channel.

- **!ansv time**
  -  Sets the time interval between automated messages. (disabled by default)

- **!ansv lines**
  -  Sets the number of chat lines required before the bot sends an automated message. (100 by default)

- **!ansv trust**
  -  Adds a user to the list of trusted users for a channel. 

- **!ansv join**
  -  Makes the ansv join a new channel.

- **!ansv part**
  -  Makes the ansv leave a channel.
