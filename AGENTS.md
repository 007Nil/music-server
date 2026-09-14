# AGENTS.md

This is a Python music server project (inspired by Mopidy) that provides local library scanning, queue management, and HTTP API playback control.

## Environment & Setup

- **Python version**: 3.13+
- **Virtual env**: Create with `python3 -m venv .venv && source .venv/bin/activate && pip install -e .`
- **Dependencies**: mutagen, sounddevice, soundfile, PyGObject (requires GStreamer runtime on host)
- **Environment variables**:
  - `MUSIC_SERVER_DATA_DIR` (default: `.music-server`)
  - `MUSIC_SERVER_MUSIC_DIR` (default: `~/Music`)

## CLI Commands

All commands use `python -m music_server.app` or the `music-server` entrypoint:

- `init-db` - Initialize database
- `scan` - Scan music directory and index tracks
- `status` - Show track/queue counts
- `tracks --limit N --search QUERY` - List/search indexed tracks
- `queue-add TRACK_ID` - Add track to queue
- `queue` - List queue items
- `queue-clear` - Clear queue
- `play-next` - Play next queued track
- `play TRACK_ID` - Play specific track
- `pause [0|1]` - Pause/resume
- `stop` - Stop playback
- `seek POSITION` - Seek to position (seconds)
- `volume VALUE` - Set volume (0-100)
- `mute [0|1]` - Mute/unmute
- `http-serve --host HOST --port PORT` - Start HTTP API server (default: 127.0.0.1:8080)

Helper script: `./scripts/run_local.sh <command> [args]`

## Architecture

Key modules:
- `app.py` - CLI entrypoint
- `core/service.py` - Top-level orchestration
- `database/store.py` - SQLite persistence (tracks + queue)
- `scanner/scanner.py` - Library scanning with mutagen metadata extraction
- `playback/player.py` - Queue state and playback control
- `audio/pipeline.py` + `audio/backend/gstreamer_backend.py` - GStreamer-based audio playback
- `http/server.py` - HTTP API server (JSON over HTTP)

Startup flow: CLI → CoreService (bootstrap) → DatabaseStore → PlaybackController + AudioPipeline

## Testing

Run: `.venv/bin/python -m pytest` (17 tests across test_smoke.py, test_prototype.py, test_audio.py, test_http.py)

## Data & Persistence

- Database: SQLite at `data_dir/library.db`
- Playback state: JSON at `data_dir/playback_state.json`
- Migrations: SQL files in `src/music_server/database/sql/` auto-applied on startup

## Audio Backend

Uses GStreamer 1.0 via PyGObject. Requires working GStreamer runtime on host. Fallback to external player commands (mpv, ffplay, cvlc) not currently implemented.

## HTTP API

Endpoints:
- GET `/health`, `/api/status`, `/api/tracks`, `/api/tracks/{id}`, `/api/queue`, `/api/now-playing`
- POST `/api/library/scan`, `/api/queue`, `/api/playback/play`, `/api/playback/play-next`, `/api/playback/pause`, `/api/playback/resume`, `/api/playback/stop`, `/api/playback/seek`, `/api/playback/volume`, `/api/playback/mute`
- DELETE `/api/queue`, `/api/queue/{id}`

## Constraints

- Single-user, localhost-only (HTTP API unauthenticated)
- Local file playback only (no streaming services)
- Music directory must be local filesystem
- Requires GStreamer runtime on host system
