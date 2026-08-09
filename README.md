# music-server

A lightweight local music server for browsing a local music library, queueing tracks, and playing them with MPD-compatible behavior.

This project is designed for a single-user, localhost-only workflow. It focuses on local files, simple queue control, and compatibility with MPD-style clients rather than a full multi-user or remote deployment stack.

The current implementation uses a native Python audio path via soundfile/sounddevice when a hardware audio backend is available, and it can also honor an explicit configured player command for compatibility or scripted testing.

## Features

- Scan and index local music files from a configured music directory
- Extract metadata from media files using mutagen with filename fallback
- Persist tracks and queue state in SQLite
- Play tracks through a native Python audio backend when available
- Honor an explicit configured player command such as mpv, ffplay, or vlc when needed
- Provide a basic MPD-compatible protocol server on localhost
- Support queue operations, playback state, seek, volume, and mute controls

## Requirements

- Python 3.11+
- A compatible local audio player installed in the environment, such as:
  - mpv
  - ffplay
  - vlc

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
- MUSIC_SERVER_AUDIO_PLAYER: optional custom audio player command

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

Start the MPD-compatible server:

```bash
.venv/bin/python -m music_server.app mpd-serve --host 127.0.0.1 --port 6600
```

## End-to-End Smoke Test

A simple local smoke test can be run without a real audio device by pointing the configured player at a temporary script:

```bash
mkdir -p /tmp/music-server-e2e/music/Demo
printf 'dummy-audio' > /tmp/music-server-e2e/music/Demo/Alpha\ -\ First.mp3
cat > /tmp/music-server-e2e/player.py <<'PY'
import pathlib
import sys
pathlib.Path(sys.argv[1]).write_text(sys.argv[2], encoding='utf-8')
PY

PYTHON_BIN="$PWD/.venv/bin/python"
export MUSIC_SERVER_DATA_DIR="/tmp/music-server-e2e/data"
export MUSIC_SERVER_MUSIC_DIR="/tmp/music-server-e2e/music"
export MUSIC_SERVER_AUDIO_PLAYER="$PYTHON_BIN /tmp/music-server-e2e/player.py /tmp/music-server-e2e/marker.txt"

$PYTHON_BIN -m music_server.app init-db
$PYTHON_BIN -m music_server.app scan
$PYTHON_BIN -m music_server.app tracks --limit 5
$PYTHON_BIN -m music_server.app queue-add 1
$PYTHON_BIN -m music_server.app play-next
cat /tmp/music-server-e2e/marker.txt
```

If you want actual audio output instead of the marker-file smoke test, use an installed player such as mpv and set:

```bash
export MUSIC_SERVER_AUDIO_PLAYER="mpv --no-video --really-quiet --"
```

## Development

For a detailed walkthrough of the runtime flow, module responsibilities, and the function call chain for startup, scanning, queueing, playback, and MPD commands, see [DEVELOPMENT.md](DEVELOPMENT.md).

Run the test suite:

```bash
.venv/bin/python -m pytest
```

## Notes

- The project is intentionally focused on local playback and MPD-like control for personal use.
- It is a strong local prototype, but it is not yet a fully hardened production deployment. It is suitable for local testing and everyday single-user use when your environment provides a working audio backend.
