# ANSV Bot Docker Guide

This guide explains how to run ANSV Bot using Docker.

## Prerequisites

- Docker installed on your system
- Docker Compose installed on your system
- Git repository cloned to your local machine

## Quick Start

1. Copy the example settings file:
   ```
   cp settings.example.conf settings.conf
   ```

2. Edit settings.conf with your configurations

3. Build and start the container:
   ```
   docker-compose up -d
   ```

4. Access the web interface at http://localhost:5001 and login with admin credentials
   - Default admin login: admin / admin123
   - The user management system is automatically initialized on first run

## Container Management

### Start the container
```
docker-compose up -d
```

### Stop the container
```
docker-compose down
```

### View logs
```
docker-compose logs -f
```

### Rebuild the container
```
docker-compose build --no-cache
```

## Development Mode

To run in development mode with hot-reloading:

```
docker-compose --profile dev up -d ansv-dev
```

Access the development instance at http://localhost:5002

## Configuration

### Environment Variables

You can set these in the `docker-compose.yml` file:

- `TTS_ENABLED`: Enable Text-to-Speech (true/false)
- `WEB_ENABLED`: Enable Web Interface (true/false)

### Volume Mounts

The following data is persisted through Docker volumes:

- `/app/messages.db`: Chat messages and channel configs database
- `/app/users.db`: User accounts and authentication database
- `/app/cache`: Markov model cache
- `/app/logs`: Application logs
- `/app/static/outputs`: Generated outputs
- `/app/voices`: TTS voice models

### Custom Configuration

The `settings.conf` file is mounted as a read-only volume. Edit this file on your host machine to change the bot configuration.

## Advanced Usage

### Running with specific options

```
docker-compose run --rm ansv-bot --rebuild
```

### Downloading TTS models manually

```
docker-compose run --rm ansv-bot --download-models
```

### Clean installation

```
docker-compose run --rm ansv-bot --clean
```

## Troubleshooting

### Container fails to start

Check the logs:
```
docker-compose logs
```

### Performance issues

For better performance, you may want to adjust the volume configuration in `docker-compose.yml` to use local directories instead of named volumes:

```yaml
volumes:
  - ./data/messages.db:/app/messages.db
  - ./data/users.db:/app/users.db
  - ./data/cache:/app/cache
  - ./data/logs:/app/logs
  - ./data/outputs:/app/static/outputs
  - ./data/voices:/app/voices
```