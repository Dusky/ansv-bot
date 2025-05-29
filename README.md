# ANSV Bot

A sophisticated Twitch chat bot with AI-powered text generation using Markov chains, advanced text-to-speech capabilities, and a comprehensive web management interface.

## Overview

ANSV Bot is a Python-based Twitch chat bot that learns from channel conversations and generates contextually relevant responses. It features real-time TTS synthesis, multi-channel management, and a modern web interface for monitoring and control.

## Key Features

- **AI Text Generation**: Markov chain-based message generation trained on channel history
- **Text-to-Speech**: Bark model integration with multiple voice presets and custom voices
- **Multi-User Management**: Role-based access control with admin, streamer, and viewer roles
- **Web Interface**: Modern beta dashboard with real-time monitoring and configuration
- **Multi-Channel Support**: Per-channel settings, voice presets, and model training
- **Authentication System**: Secure user accounts with session management and audit logging
- **Theme System**: 15+ UI themes with dark/light variants and auto-detection
- **Real-Time Monitoring**: WebSocket-based status updates and live activity feeds

## Requirements

- Python 3.11+
- FFmpeg (for audio processing)
- Twitch API credentials
- SQLite database support

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ansv-bot.git
cd ansv-bot

# Run the interactive setup
./launch.sh
```

The launcher will guide you through:
- Virtual environment setup
- Dependency installation
- Configuration file creation
- TTS model downloads (optional)

### Configuration

1. Copy the example configuration:
   ```bash
   cp settings.example.conf settings.conf
   ```

2. Edit `settings.conf` with your Twitch credentials:
   ```ini
   [auth]
   tmi_token = oauth:your_token_here
   client_id = your_client_id_here
   nickname = your_bot_name
   owner = your_twitch_username

   [channels]
   channels = channel1, channel2
   ```

3. Get Twitch credentials:
   - Visit [Twitch Developer Console](https://dev.twitch.tv/console)
   - Create an application to get your Client ID
   - Generate an OAuth token for the bot account

4. Initialize the user management system:
   ```bash
   # Run migration to set up user accounts
   python utils/migrate_to_users.py --db ansv_bot.db
   ```
   
   This creates the default admin account with your current admin password.

### Running the Bot

**Interactive Mode:**
```bash
./launch.sh
```

**Command Line Options:**
```bash
# Bot with web interface and TTS
./launch.sh --web --tts

# Development mode with hot reload
./launch.sh --dev

# Web interface only
./launch.sh --web-only

# Pre-download TTS models
./launch.sh --download-models

# Clean installation
./launch.sh --clean
```

## Usage

### Web Interface

Access the web dashboard at `http://localhost:5001` when running with `--web`:

**Authentication Required**: Login with your user account to access the beta interface.

- **Dashboard**: Bot status, channel activity, quick actions
- **Channel Management**: Per-channel settings, voice presets, model training
- **Settings**: Global configuration, theme selection, system preferences
- **Analytics**: Model performance, message statistics, usage trends
- **TTS History**: Audio playback, voice management, generation queue
- **Logs**: Chat history with filtering, search, and export
- **User Management** (Admin only): Create users, assign roles, manage permissions

### Bot Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `!ansv speak` | Generate and send message | `!ansv speak` |
| `!ansv tts <text>` | Generate TTS audio | `!ansv tts Hello world` |
| `!ansv config <setting> <value>` | Modify settings | `!ansv config lines 50` |
| `!ansv trust <user>` | Manage trusted users | `!ansv trust moderator_name` |
| `!ansv join <channel>` | Join new channel | `!ansv join new_channel` |
| `!ansv part <channel>` | Leave channel | `!ansv part old_channel` |

## Development

### Project Structure

```
ansv-bot/
├── ansv.py                   # Main application entry point
├── webapp.py                # Flask web interface with authentication
├── twitchio_bot.py          # Bot implementation stub
├── launch.sh                # Interactive launcher script
├── utils/                   # Core utilities
│   ├── bot.py              # TwitchIO bot implementation
│   ├── user_db.py          # User management and authentication
│   ├── auth.py             # Authentication decorators and utilities
│   ├── markov_handler.py   # Text generation system
│   ├── tts.py              # Text-to-speech processing
│   ├── db_setup.py         # Database schema and setup
│   ├── migrate_to_users.py # User system migration script
│   └── logger.py           # Logging configuration
├── commands/               # Bot command handlers
│   └── ansv_command.py     # Main command processor
├── static/                 # Web interface assets
│   ├── scripts/            # JavaScript modules and beta components
│   ├── css/                # Stylesheets and beta themes
│   └── outputs/            # Generated TTS audio files
├── templates/              # Jinja2 templates
│   ├── beta/               # Modern authenticated UI templates
│   ├── login.html          # Authentication interface
│   ├── profile.html        # User profile management
│   ├── admin_users.html    # Admin user management
│   └── *.html              # Legacy and error page templates
└── voices/                 # Custom voice presets (.npz files)
```

### Architecture

**Core Components:**
- **Bot Core**: TwitchIO-based chat bot with async event handling
- **Authentication System**: Role-based access control with secure session management
- **User Management**: Multi-user support with admin, streamer, and viewer roles
- **Markov Engine**: Text corpus analysis and message generation
- **TTS System**: Bark model integration with voice management
- **Web API**: RESTful endpoints with authentication and real-time WebSocket updates
- **Database Layer**: SQLite with proper schema, migrations, and audit logging

**Key Design Patterns:**
- Async/await for I/O operations
- Thread-safe TTS processing
- Component-based frontend architecture
- Configuration-driven behavior
- Graceful error handling and recovery

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-tts.txt

# Run in development mode
./launch.sh --dev

# Run tests (if available)
python -m pytest

# Database operations
python utils/db_setup.py  # Initialize database
```

## Configuration Options

### Bot Settings

```ini
[auth]
tmi_token = oauth:token      # Twitch OAuth token
client_id = client_id        # Twitch application ID
nickname = bot_name          # Bot username
owner = your_username        # Owner username

[channels]
channels = channel1,channel2 # Comma-separated channel list

[settings]
verbose_logs = false         # Enable detailed logging
lines_between_messages = 100 # Messages to learn before speaking
time_between_messages = 0    # Minimum seconds between responses
```

### Channel-Specific Configuration

Each channel supports individual settings:
- TTS enabled/disabled
- Voice preset selection
- Trusted user management
- Message frequency controls
- Model training preferences

### TTS Configuration

- **Voice Presets**: Built-in speaker models (v2/en_speaker_0 through v2/en_speaker_9)
- **Custom Voices**: Place `.npz` files in `voices/` directory
- **Audio Output**: Files saved to `static/outputs/<channel>/`
- **Model Caching**: Automatic model download and caching

## Deployment

### Docker

```bash
# Build image
docker build -t ansv-bot .

# Run with docker-compose
docker-compose up -d
```

### Production Considerations

- Use a production WSGI server (Gunicorn, uWSGI)
- Configure reverse proxy (nginx, Apache)
- Set up log rotation and monitoring
- Secure sensitive configuration files
- Regular database backups

## Troubleshooting

### Common Issues

**TTS Not Working:**
- Ensure FFmpeg is installed
- Check TTS model downloads: `./launch.sh --download-models`
- Verify sufficient disk space (2GB+ for models)

**Bot Not Connecting:**
- Validate Twitch OAuth token
- Check channel names in configuration
- Verify network connectivity

**Web Interface Issues:**
- Confirm port 5001 is available
- Check browser console for JavaScript errors
- Verify WebSocket connections

**Performance Issues:**
- Monitor memory usage with large message histories
- Consider GPU acceleration for TTS
- Optimize database queries for large datasets

### Logs

- **Application logs**: `app.log`
- **Bot status**: Check web interface dashboard
- **TTS processing**: Monitor console output
- **Database operations**: Enable verbose logging

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

Please follow the existing code style and include appropriate documentation.

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Acknowledgments

- TwitchIO library for Twitch chat integration
- Bark by Suno AI for text-to-speech synthesis
- Bootstrap and community themes for UI components
- NLTK for natural language processing
- Flask and SocketIO for web interface