# ANSV Bot

![ANSV Bot Banner](docs/images/banner.png)

A Twitch bot that learns from chat messages and responds with AI-generated text using Markov chains and text-to-speech capabilities.

## ✨ Features

- 🤖 Learns from chat messages using Markov chain models
- 🔊 Text-to-speech capabilities with multiple voice options
- 🌐 Web interface for monitoring and control
- 📊 Channel-specific settings and voice configurations
- 🎛️ Custom TTS message generation through web interface
- 🚀 Easy setup with an interactive launcher

## 🔧 Installation

### Prerequisites

- Python 3.11+
- ffmpeg (for TTS audio processing)
- Twitch API credentials

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/ansv-bot.git
cd ansv-bot

# Run the launcher
./launch.sh

# Pre-download TTS models (optional but recommended)
./launch.sh --download-models
```

## ⚙️ Configuration

1. Copy `settings.example.conf` to `settings.conf` (done automatically on first run)
2. Edit `settings.conf` with your Twitch credentials:
   ```
   [auth]
   tmi_token = oauth:your_token_here
   client_id = your_client_id_here
   nickname = your_bot_name
   owner = your_twitch_username
   
   [channels]
   channels = channel1, channel2
   ```

3. Run the setup wizard with `./launch.sh`

## 🎤 Text-to-Speech

ANSV Bot includes advanced text-to-speech capabilities:

### Voice Options

- Built-in voices: v2/en_speaker_0 through v2/en_speaker_9
- Custom voices: Place `.npz` files in the `voices/` directory

### Using TTS

1. **Launch with TTS**: `./launch.sh --tts`
2. **Specify a voice**: `./launch.sh --tts --voice-preset v2/en_speaker_6`
3. **Web Interface**: Send custom TTS messages through the web panel

### Managing TTS

- **Download models**: `./launch.sh --download-models`
- **Enable per channel**: Toggle TTS in channel settings
- **Audio files**: Stored in `static/outputs/<channel>/`

## 🖥️ Web Interface

The bot includes a web interface for management:

1. Start with `./launch.sh --web --tts`
2. Access at `http://localhost:5001`

### Web Features

- Monitor bot status and connected channels
- Send custom TTS messages
- View TTS message history with playback
- Configure channel settings

## 📋 Command-Line Options

```
./launch.sh [options]
```

Options:
- `--web`: Enable web interface
- `--tts`: Enable text-to-speech
- `--voice-preset PRESET`: Use specific voice preset
- `--download-models`: Pre-download TTS models
- `--rebuild`: Rebuild Markov cache
- `--dev`: Start in development mode
- `--web-only`: Start web interface without bot
- `--clean`: Perform fresh install

## 🔍 Troubleshooting

### TTS Issues

- **Missing models**: Run `./launch.sh --download-models`
- **Audio not playing**: Ensure ffmpeg is installed
- **Slow generation**: TTS works best with GPU (CUDA)

### Bot Connection Issues

- Check your Twitch token validity
- Ensure channel names are correctly specified

## 📦 Directory Structure

- `/static/outputs/`: TTS audio files
- `/voices/`: Custom voice presets
- `/models/tts/`: Cached TTS models
- `/cache/`: Markov chain models

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

**Web Interface** (Port 5001)
- `http://localhost:5001` - Main dashboard
- `http://localhost:5001/stats` - Model statistics
- `http://localhost:5001/tts` - TTS management

### Bot Commands
| Command | Description | Example |
|---------|-------------|---------|
| `!ansv speak` | Generate message | `!ansv speak` |
| `!ansv trust <user>` | Manage trusted users | `!ansv trust nightbot` |
| `!ansv config <setting>` | Modify channel settings | `!ansv config lines 50` |
| `!ansv tts <on/off>` | Toggle TTS | `!ansv tts on` |
| `!ansv join/part` | Channel management | `!ansv join new_channel` |

## Web Interface Features 🌐

**Dashboard**
- Real-time message statistics
- Model performance metrics
- Channel configuration management

**Model Management**
- Cache rebuilding
- Model version control
- Training data inspection

**TTS System**
- Voice preset selection
- Audio file management
- Synthesis history

## Troubleshooting 🔧

**Common Issues**
1. **TTS Failures**
   - Verify NVIDIA drivers are up-to-date
   - Check free disk space (>5GB recommended)
   - Run `python -m bark_hubert_quantizer` to initialize Bark model

2. **Database Errors**
   ```bash
   rm messages.db  # WARNING: Deletes all data
   python utils/db_setup.py
   ```

3. **Cache Issues**
   ```bash
   python ansv.py --rebuild-cache
   ```

## License 📄
MIT License - See [LICENSE](LICENSE) for details

## Contributing 🤝
Pull requests welcome! Please follow our [contribution guidelines](CONTRIBUTING.md).

---

> **Note**: Requires Twitch developer account. TTS functionality needs substantial system resources.

# Installation

## Core System
```bash
python -m pip install -r requirements.txt
python -m spacy download en_core_web_sm  # For NLTK integration
```

## TTS Support (macOS)
```bash
# Install system dependencies first
brew install portaudio ffmpeg

# Install Python packages
python -m pip install -r requirements-tts.txt
```

### Configuration
1. Copy the example configuration:
```bash
cp settings.example.conf settings.conf
```

2. Edit settings.conf with your Twitch credentials:
```ini
[auth]
tmi_token = oauth:your_actual_token  # From Twitch console
client_id = your_client_id           # Twitch application ID
nickname = YourBotName                # Bot's username
owner = YourUsername                 # Your Twitch username
```

3. Initialize database:
```bash
python utils/db_setup.py
```

> **Warning**: Never commit settings.conf! It contains sensitive credentials. We've added it to .gitignore for you.