#!/bin/bash
set -e

# Create settings.conf if it doesn't exist
if [ ! -f "/app/settings.conf" ]; then
  echo "No settings.conf found, creating from template..."
  cp /app/settings.example.conf /app/settings.conf
  # Add environment variable substitution here if needed
fi

# Check if user management system needs to be initialized
if [ ! -f "/app/users.db" ]; then
  echo "⚠️  No users.db found. User management system needs initialization."
  echo "⚠️  Run 'python3 utils/migrate_to_users.py' to set up users."
  echo "⚠️  Or run 'python3 create_admin.py' for emergency admin creation."
fi

# Download TTS models if enabled
if [ "$TTS_ENABLED" = true ] && [ "$1" = "--tts" ] || [[ "$*" == *"--download-models"* ]]; then
  echo "Checking TTS models..."
  if [ ! -d "/app/voices" ] || [ -z "$(ls -A /app/voices 2>/dev/null)" ]; then
    echo "Downloading TTS models..."
    python -c "from utils.tts import download_models; download_models()"
  fi
fi

# Run the application with args passed to the container
exec ./launch.sh "$@"