
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