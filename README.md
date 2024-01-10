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

### Installation

```bash
git clone https://github.com/dusky/ansv-bot.git
cd ansv-bot


# Set Up Python Environment
# (Optional but recommended)

# 1. Install `pyenv` (if not already installed)
# [Pyenv Installation Guide](https://github.com/pyenv/pyenv#installation).

# 2. Install Python 3 using pyenv

pyenv install 3.11
pyenv local 3.11

or

apt install pyton3.11-venv

# 3. Create a virtual environment
python -m venv env

# 4. Activate the virtual environment
source env/bin/activate

# 5. Install Dependencies
pip install -r requirements.txt

# Configuration
# - Edit `settings.conf` to include your Twitch bot's token, client ID, nickname, and initial channels.

# Usage
# - Run the bot using:
python ansv.py
```

- **!ansv speak**
  -  Generates and sends a message.

- **!ansv start**
  -  Enables the ansv in a channel.

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
