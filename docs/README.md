# music-server

A lightweight local music server for browsing a local music library, queueing tracks, and playing them through an HTTP API.

This project is designed for a single-user, localhost-only workflow. It focuses on local files, simple queue control, and a clean HTTP interface for custom clients rather than a full multi-user or remote deployment stack.

The current implementation uses a native GStreamer backend through PyGObject.

## Features

- Scan and index local music files from a configured music directory
- Extract metadata from media files using mutagen with filename fallback
- Persist tracks and queue state in SQLite
- Play tracks through a native GStreamer audio backend
- Provide a basic HTTP API server on localhost
- Support queue operations, playback state, seek, volume, and mute controls

## Requirements

- Python 3.11+
- GStreamer runtime with playback plugins available on the host
- PyGObject dependencies for `gi.repository.Gst`

## Setup

Create and use the virtual environment in the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

The application reads the following environment variables:

- MUSIC_SERVER_DATA_DIR: directory for SQLite data and playback state (default: .music-server)
- MUSIC_SERVER_MUSIC_DIR: root folder for your local music collection (default: ~/Music)

Example:

```bash
export MUSIC_SERVER_DATA_DIR="$HOME/.music-server"
export MUSIC_SERVER_MUSIC_DIR="$HOME/Music"
```

## Quick Start Helper

A small helper script is available to launch the app with sensible defaults for local use:

```bash
./scripts/run_local.sh init-db
./scripts/run_local.sh scan
./scripts/run_local.sh tracks --limit 20
./scripts/run_local.sh queue-add 1
./scripts/run_local.sh play-next
```

If your music folder is not the default, override the environment variables before running it:

```bash
MUSIC_SERVER_MUSIC_DIR="/path/to/your/music" \
\./scripts/run_local.sh scan
```

The helper uses the project virtual environment and defaults to the local repository data directory and your home music folder.

## Common Commands

Initialize the database:

```bash
.venv/bin/python -m music_server.app init-db
```

Scan and index your music directory:

```bash
.venv/bin/python -m music_server.app scan
```

List indexed tracks:

```bash
.venv/bin/python -m music_server.app tracks --limit 20
```

Queue a track:

```bash
.venv/bin/python -m music_server.app queue-add 1
```

Show the queue:

```bash
.venv/bin/python -m music_server.app queue
```

Play the next queued item:

```bash
.venv/bin/python -m music_server.app play-next
```

Play a specific track:

```bash
.venv/bin/python -m music_server.app play 1
```

Pause or resume playback:

```bash
.venv/bin/python -m music_server.app pause 1
.venv/bin/python -m music_server.app pause 0
```

Seek within the current track:

```bash
.venv/bin/python -m music_server.app seek 120
```

Adjust volume or mute:

```bash
.venv/bin/python -m music_server.app volume 40
.venv/bin/python -m music_server.app mute 1
.venv/bin/python -m music_server.app mute 0
```

Stop playback:

```bash
.venv/bin/python -m music_server.app stop
```

Start the HTTP API server:

```bash
.venv/bin/python -m music_server.app http-serve --host 127.0.0.1 --port 8080
```

Basic HTTP checks:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/api/status
curl http://127.0.0.1:8080/api/tracks?limit=10
```

## Test With REST API Clients

Start the HTTP server in one terminal:

```bash
.venv/bin/python -m music_server.app http-serve --host 127.0.0.1 --port 8080
```

### Test with curl

Health and status:

```bash
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/api/status
```

Scan library and list tracks:

```bash
curl -s -X POST http://127.0.0.1:8080/api/library/scan \
  -H "Content-Type: application/json" \
  -d '{}'

curl -s "http://127.0.0.1:8080/api/tracks?limit=20"
```

Queue and playback controls:

```bash
curl -s -X POST http://127.0.0.1:8080/api/queue \
  -H "Content-Type: application/json" \
  -d '{"track_id": 1}'

curl -s http://127.0.0.1:8080/api/queue

curl -s -X POST http://127.0.0.1:8080/api/playback/play-next \
  -H "Content-Type: application/json" \
  -d '{}'

curl -s -X POST http://127.0.0.1:8080/api/playback/pause \
  -H "Content-Type: application/json" \
  -d '{"paused": true}'

curl -s -X POST http://127.0.0.1:8080/api/playback/resume \
  -H "Content-Type: application/json" \
  -d '{}'

curl -s http://127.0.0.1:8080/api/now-playing
```

### Test with Postman

1. Open Postman and create a new collection named `music-server`.
2. Set a collection variable:
   - `baseUrl` = `http://127.0.0.1:8080`
3. Import the included collection file:
   - `docs/postman/music-server.postman_collection.json`
4. Run requests in this order:
   - `Health`
   - `Status`
   - `Scan Library`
   - `List Tracks`
   - `Queue Add (track_id=1)`
   - `Play Next`
   - `Now Playing`

If you do not want to import, create requests manually in Postman with the same methods and paths listed above.

## End-to-End Smoke Test

```bash
mkdir -p /tmp/music-server-e2e/music/Demo
printf 'dummy-audio' > /tmp/music-server-e2e/music/Demo/Alpha\ -\ First.mp3

PYTHON_BIN="$PWD/.venv/bin/python"
export MUSIC_SERVER_DATA_DIR="/tmp/music-server-e2e/data"
export MUSIC_SERVER_MUSIC_DIR="/tmp/music-server-e2e/music"

$PYTHON_BIN -m music_server.app init-db
$PYTHON_BIN -m music_server.app scan
$PYTHON_BIN -m music_server.app tracks --limit 5
$PYTHON_BIN -m music_server.app queue-add 1
$PYTHON_BIN -m music_server.app play-next
$PYTHON_BIN -m music_server.app status
```

## Production Deployment (HTTP)

This service is local-first. A practical production setup for one user is:

1. Run the app as a dedicated system user.
2. Keep configuration in an environment file.
3. Run the HTTP server using systemd.
4. Validate health/status endpoints after startup.

### 1. Environment file

Create `/etc/music-server.env`:

```bash
MUSIC_SERVER_DATA_DIR=/var/lib/music-server
MUSIC_SERVER_MUSIC_DIR=/srv/music
```

### 2. Bootstrap data

Run once after deployment:

```bash
/opt/music-server/.venv/bin/python -m music_server.app init-db
/opt/music-server/.venv/bin/python -m music_server.app scan
```

### 3. systemd service

Create `/etc/systemd/system/music-server.service`:

```ini
[Unit]
Description=music-server HTTP API
After=network.target

[Service]
Type=simple
User=music
Group=music
WorkingDirectory=/opt/music-server
EnvironmentFile=/etc/music-server.env
ExecStart=/opt/music-server/.venv/bin/python -m music_server.app http-serve --host 127.0.0.1 --port 8080
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Apply and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now music-server
sudo systemctl status music-server
```

### 4. Runtime checks

```bash
curl -f http://127.0.0.1:8080/health
curl -f http://127.0.0.1:8080/api/status
```

Logs:

```bash
sudo journalctl -u music-server -f
```

### 5. Optional reverse proxy

If you need remote client access, put nginx/Caddy in front of `127.0.0.1:8080` and add TLS plus authentication there.

## Development

For a detailed walkthrough of the runtime flow, module responsibilities, and the function call chain for startup, scanning, queueing, playback, and HTTP routes, see [DEVELOPMENT.md](DEVELOPMENT.md).

Run the test suite:

```bash
.venv/bin/python -m pytest
```

## Notes

- The project is intentionally focused on local playback and HTTP control for personal use.
- It is a strong local prototype, but it is not yet a fully hardened production deployment. It is suitable for local testing and everyday single-user use when your environment provides a working audio backend.
