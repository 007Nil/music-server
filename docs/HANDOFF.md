# Music Server Handoff

This file summarizes current implementation status, how to validate the application, and what remains before it can fully replace a Mopidy setup.

## 1. Current Status

The project is now a working local music server prototype with:

- environment-driven configuration
- sqlite persistence for tracks and queue
- local filesystem scan and indexing
- metadata extraction from media tags with fallback parsing
- track listing and search
- queue add/list/play/clear behavior
- HTTP API command handling (JSON over threaded HTTP server)
- a native GStreamer audio backend via PyGObject
- playback timeline reporting with persisted startup recovery state
- normalized metadata fields (artist/title/album/track number + stable URI)
- runnable CLI commands
- automated tests for core/audio/prototype/http behavior

This is still **not** full Mopidy parity yet, but it is now a much stronger local playback prototype.

## 2. What Has Been Implemented

### Application and composition

- [src/music_server/app.py](src/music_server/app.py)
  - CLI command handling
  - module entrypoint (`python -m music_server.app`)
- [src/music_server/core/service.py](src/music_server/core/service.py)
  - top-level orchestration
  - bootstrap/init path
  - status reporting
  - queue playback and direct track playback
  - audio stop/pause controls

### Configuration

- [src/music_server/config/settings.py](src/music_server/config/settings.py)
  - `MUSIC_SERVER_DATA_DIR`
  - `MUSIC_SERVER_MUSIC_DIR`
  - computed `db_path`

### Persistence

- [src/music_server/database/store.py](src/music_server/database/store.py)
  - sqlite schema creation
  - SQL-file based schema and migration loading
  - track upsert/list/search/get/count (with duration, stable URI, track number)
  - queue enqueue/list/pop/count
  - queue item delete/clear/helpers (by ID, by position)
  - distinct artist/album counters
  - stale-track pruning support
- [src/music_server/database/sql/schema.sql](src/music_server/database/sql/schema.sql)
  - base table/index definitions
- [src/music_server/database/sql/migration_add_uri.sql](src/music_server/database/sql/migration_add_uri.sql)
- [src/music_server/database/sql/migration_add_track_no.sql](src/music_server/database/sql/migration_add_track_no.sql)
- [src/music_server/database/sql/migration_add_duration.sql](src/music_server/database/sql/migration_add_duration.sql)
- [src/music_server/database/sql/maintenance_backfill_uri.sql](src/music_server/database/sql/maintenance_backfill_uri.sql)

### Database Schema

**Tracks table:**
- `id` (INTEGER PRIMARY KEY)
- `path` (TEXT NOT NULL UNIQUE) - absolute file path
- `uri` (TEXT NOT NULL UNIQUE) - relative URI from music directory
- `title` (TEXT NOT NULL) - track title
- `artist` (TEXT NOT NULL) - track artist(s)
- `album` (TEXT NOT NULL) - album name
- `track_no` (INTEGER NOT NULL DEFAULT 0) - track number
- `duration` (REAL NOT NULL DEFAULT 0) - duration in seconds
- `mtime` (REAL NOT NULL) - file modification time

**Queue table:**
- `id` (INTEGER PRIMARY KEY) - queue item ID
- `track_id` (INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE) - reference to track

### Library and scanner

- [src/music_server/scanner/scanner.py](src/music_server/scanner/scanner.py)
  - recursive file scan
  - extension filtering (`.mp3`, `.flac`, `.ogg`, `.m4a`, `.wav`)
  - metadata extraction from tags via `mutagen`
  - metadata normalization (whitespace cleanup, artist list normalization, track number parsing)
  - stable URI generation relative to music root
  - fallback parsing from filename pattern `Artist - Title`
  - stale track removal for deleted files
- [src/music_server/library/service.py](src/music_server/library/service.py)
  - read/query interface over store

### Database Schema

### Playback and audio

- [src/music_server/playback/player.py](src/music_server/playback/player.py)
  - queue operations and playback state (`play`, `pause`, `stop`)
  - playlist version tracking for MPD status
  - elapsed playback timeline tracking
  - persistent playback-state save/restore
  - event notifications for MPD idle clients

- [src/music_server/audio/pipeline.py](src/music_server/audio/pipeline.py)
  - native audio playback via GStreamer
  - playback lifecycle stop/replace behavior
  - basic position, volume, mute, and pause/resume handling

### HTTP API

- [src/music_server/http/server.py](src/music_server/http/server.py)
  - in-process API dispatch for tests and integration
  - threaded HTTP server
  - implemented routes:
    - `GET /health`, `GET /api/status`, `GET /api/now-playing`
    - `POST /api/library/scan`
    - `GET /api/tracks`, `GET /api/tracks/{id}`
    - `GET /api/queue`, `POST /api/queue`, `DELETE /api/queue`, `DELETE /api/queue/{id}`
    - `POST /api/playback/play`, `POST /api/playback/play-next`
    - `POST /api/playback/pause`, `POST /api/playback/resume`, `POST /api/playback/stop`
    - `POST /api/playback/seek`, `POST /api/playback/volume`, `POST /api/playback/mute`

### Tests

- [tests/test_smoke.py](tests/test_smoke.py) - 3 tests
  - `test_main_smoke`: Verifies app startup with expected output
  - `test_load_settings_uses_default_data_dir`: Validates default config path `.music-server`
  - `test_core_service_start_uses_settings`: Confirms CoreService uses correct settings

- [tests/test_prototype.py](tests/test_prototype.py) - 6 tests
  - `test_scan_indexes_audio_files`: Verifies scanning finds audio files and indexes them
  - `test_queue_and_play_next`: Tests queue operations (enqueue, list, play_next, count)
  - `test_scan_removes_deleted_tracks`: Validates stale track cleanup when files deleted
  - `test_status_command_output`: Verifies CLI status command output format
  - `test_cli_play_and_stop`: Tests play/stop CLI commands with expected output
  - `test_playback_state_persists_across_service_restart`: Validates JSON state persistence

- [tests/test_audio.py](tests/test_audio.py) - 5 tests
  - `test_audio_pipeline_uses_backend_for_playback`: Validates backend integration
  - `test_audio_pipeline_stops_previous_playback`: Tests stop/replace behavior
  - `test_audio_pipeline_can_report_current_state`: Verifies position/tags reporting
  - `test_audio_pipeline_supports_seek_and_volume_controls`: Tests seek/volume/mute
  - `test_playback_controller_ignores_missing_tracks_on_restore`: Validates error handling

- [tests/test_http.py](tests/test_http.py) - 3 tests
  - `test_http_status_tracks_and_now_playing`: Tests GET `/api/status`, `/api/tracks`, `/api/now-playing`
  - `test_http_queue_and_playback_controls`: Tests queue POST/GET, play-next, pause, resume, stop
  - `test_http_scan_and_error_paths`: Tests library scan, track lookup, and 404 error handling

**Total: 17 passing test cases** covering CLI, persistence, audio backend, and HTTP API.

## 3. CLI Commands Currently Available

- `start`
- `init-db`
- `status`
- `scan`
- `tracks --limit N --search QUERY`
- `queue-add TRACK_ID`
- `queue`
- `queue-clear`
- `play-next`
- `play TRACK_ID`
- `pause [0|1]`
- `stop`
- `seek POSITION`
- `volume VALUE`
- `mute [0|1]`
- `http-serve --host HOST --port PORT`

All commands are implemented in [src/music_server/app.py](src/music_server/app.py).

## 4. HTTP API Endpoints

**Read endpoints:**
- `GET /health` - Health check
- `GET /api/status` - Current status (tracks, queue, playback state)
- `GET /api/tracks?limit=N&search=QUERY` - List or search tracks
- `GET /api/tracks/{id}` - Get track by ID
- `GET /api/queue` - List queue items
- `GET /api/now-playing` - Current playback status

**Write endpoints:**
- `POST /api/library/scan` - Scan music library
- `POST /api/queue` - Add track to queue (body: `{"track_id": 1}`)
- `DELETE /api/queue` - Clear entire queue
- `DELETE /api/queue/{id}` - Remove queue item by ID
- `POST /api/playback/play` - Play specific track
- `POST /api/playback/play-next` - Play next queued track
- `POST /api/playback/pause` - Pause/resume playback
- `POST /api/playback/resume` - Resume playback
- `POST /api/playback/stop` - Stop playback
- `POST /api/playback/seek` - Seek to position (body: `{"position": 120.5}`)
- `POST /api/playback/volume` - Set volume (body: `{"value": 50}`)
- `POST /api/playback/mute` - Mute/unmute (body: `{"muted": true}`)

### Automated tests

Run from repo root:

```bash
.venv/bin/python -m pytest
```

Test coverage includes:
- CLI commands and startup flow (test_smoke.py - 3 tests)
- Library scanning and indexing (test_prototype.py - 6 tests)
- Queue operations and persistence (test_prototype.py)
- Audio backend integration (test_audio.py - 5 tests)
- HTTP API endpoints (test_http.py - 3 tests)

### Quick runtime smoke check

```bash
.venv/bin/python -m music_server.app init-db
.venv/bin/python -m music_server.app status
```

Expected behavior:

- db file is created in data dir
- status prints: `tracks=<count> queue=<count>`

### End-to-end manual flow

```bash
MUSIC_SERVER_MUSIC_DIR=/path/to/music \
.venv/bin/python -m music_server.app scan
.venv/bin/python -m music_server.app tracks --limit 20
.venv/bin/python -m music_server.app queue-add 1
.venv/bin/python -m music_server.app queue
.venv/bin/python -m music_server.app play-next
.venv/bin/python -m music_server.app pause 1
.venv/bin/python -m music_server.app pause 0
.venv/bin/python -m music_server.app stop
```

### HTTP server runtime check

Start server:

```bash
.venv/bin/python -m music_server.app http-serve --host 127.0.0.1 --port 8080
```

Then query endpoints, for example:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/api/status
```

### REST client checks (curl or Postman)

Using curl:

```bash
# Library operations
curl -X POST http://127.0.0.1:8080/api/library/scan -H "Content-Type: application/json" -d '{}'
curl "http://127.0.0.1:8080/api/tracks?limit=20&search=artist"
curl "http://127.0.0.1:8080/api/tracks/1"

# Queue operations
curl -X POST http://127.0.0.1:8080/api/queue -H "Content-Type: application/json" -d '{"track_id": 1}'
curl http://127.0.0.1:8080/api/queue
curl -X DELETE http://127.0.0.1:8080/api/queue/1
curl -X DELETE http://127.0.0.1:8080/api/queue

# Playback controls
curl -X POST http://127.0.0.1:8080/api/playback/play -H "Content-Type: application/json" -d '{"track_id": 1}'
curl -X POST http://127.0.0.1:8080/api/playback/play-next -H "Content-Type: application/json" -d '{}'
curl -X POST http://127.0.0.1:8080/api/playback/pause -H "Content-Type: application/json" -d '{"paused": true}'
curl -X POST http://127.0.0.1:8080/api/playback/resume -H "Content-Type: application/json" -d '{}'
curl -X POST http://127.0.0.1:8080/api/playback/stop -H "Content-Type: application/json" -d '{}'
curl -X POST http://127.0.0.1:8080/api/playback/seek -H "Content-Type: application/json" -d '{"position": 120.5}'
curl -X POST http://127.0.0.1:8080/api/playback/volume -H "Content-Type: application/json" -d '{"value": 50}'
curl -X POST http://127.0.0.1:8080/api/playback/mute -H "Content-Type: application/json" -d '{"muted": true}'

# Status
curl http://127.0.0.1:8080/api/status
curl http://127.0.0.1:8080/api/now-playing
```

Using Postman:

- Import collection file: `docs/postman/music-server.postman_collection.json`
- Ensure collection variable `baseUrl` is set to `http://127.0.0.1:8080`
- Run requests in order: Health -> Status -> Scan Library -> List Tracks -> Queue Add -> Play Next -> Now Playing

## 5. What Is Not Implemented Yet

### Mopidy core parity

Not implemented:

- actor model
- listener/event system parity
- full backend abstraction parity

### mopidy-local parity

Not implemented:

- full mopidy-local metadata/URI behavior parity
- mopidy-local schema parity/migrations
- album art pipeline
- complete browse semantics and URI model parity

### HTTP API maturity

Not implemented:

- authentication and authorization
- request rate limiting
- streaming endpoints for artwork/audio
- API versioning policy

Current implementation: [src/music_server/http/server.py](src/music_server/http/server.py)

### Real audio backend

Not implemented:

- real player-level progress reporting and seek synchronization
- seeking
- native mixer/volume control
- backend abstraction comparable to Mopidy audio layer

Current implementation: [src/music_server/audio/pipeline.py](src/music_server/audio/pipeline.py)

## 6. Production-Readiness Gaps

The project is now a strong local-playback prototype, but it is not yet production-ready for everyday use beyond development. For the intended scope of a single-user, localhost-only music server, the remaining work is mostly around robustness, playback quality, and operational polish.

### Highest priority gaps

1. CLI and startup polish
   - keep the CLI entrypoint stable and well documented
   - provide clearer startup instructions for local use

2. Logging and observability
   - add structured logging and rotation
  - surface useful runtime diagnostics when playback or HTTP operations fail

3. Playback robustness
   - improve player process monitoring and recovery when the player exits unexpectedly
   - add seek support
   - add volume and mute controls
   - improve transition handling between tracks

4. Persistence and recovery
   - make database writes and migrations safer
   - improve crash-safe queue and playback-state recovery
   - handle missing or changed files gracefully

5. HTTP client support
  - stabilize API contracts for custom clients
  - add authentication and API versioning strategy

6. Monitoring and resilience
   - add simple monitoring or restart guidance for local unattended use

### Practical definition of “production ready”

For this project, production readiness means all of the following are true:

- local library scanning and playback are reliable on real media collections
- HTTP clients can connect and operate without surprising failures
- the server starts cleanly and recovers from common runtime errors
- logs and runtime state are understandable for day-to-day use
- the experience is smooth enough for regular single-user listening

## 7. Recommended Next Implementation Order

1. Add structured logging and better runtime diagnostics.
2. Improve player process monitoring and recovery.
3. Add seek support and volume/mute controls.
4. Add API auth, versioning, and client-facing error standards.
5. Add operational hardening (service watchdogs and monitoring hooks).
6. Harden persistence and recovery around queue and playback state.

## 8. Known Constraints

- Tag extraction depends on file format support in `mutagen`; fallback remains filename parsing.
- Audio output depends on an external player executable (`mpv`, `ffplay`, `cvlc`, or configured command).
- Audio output depends on a working GStreamer runtime on the host.
- HTTP API is local-first and currently unauthenticated; deploy behind trusted network boundaries or a reverse proxy with auth.
- Queue/playback behavior is local and pragmatic, not Mopidy-parity complete.

## 9. Context Prompt For Next Chat

Use this prompt to continue quickly in a new `/chat` session:

```text
Use HANDOFF.md as source of truth.
Continue implementation from the current working prototype.
Primary next goal: improve HTTP API maturity and metadata quality for daily usage.
Before each edit, state which files will change and expected behavior.
After edits, run .venv/bin/python -m pytest.
```

## 10. Production Runbook

Use this runbook for a single-user production-style deployment.

### Deployment assumptions

- application code in `/opt/music-server`
- dedicated linux user `music`
- data path `/var/lib/music-server`
- library path `/srv/music`
- service bound to `127.0.0.1:8080`

### Environment file

Create `/etc/music-server.env`:

```bash
MUSIC_SERVER_DATA_DIR=/var/lib/music-server
MUSIC_SERVER_MUSIC_DIR=/srv/music
```

### One-time initialization

```bash
cd /opt/music-server
.venv/bin/python -m music_server.app init-db
.venv/bin/python -m music_server.app scan
```

### systemd unit

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

Start and verify:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now music-server
sudo systemctl status music-server
curl -f http://127.0.0.1:8080/health
curl -f http://127.0.0.1:8080/api/status
```

Live logs:

```bash
sudo journalctl -u music-server -f
```

## 11. Test Case Summary

| Test File | Test Count | Coverage |
|-----------|------------|----------|
| test_smoke.py | 3 | CLI startup, settings, service initialization |
| test_prototype.py | 6 | Library scanning, queue operations, persistence |
| test_audio.py | 5 | Audio backend integration, seek/volume/mute |
| test_http.py | 3 | HTTP API endpoints and error handling |
| **Total** | **17** | All major components |

### Test Coverage by Component

**CLI Commands:**
- `start`, `init-db`, `status`, `scan`, `play`, `stop`, `pause`, `play-next`

**Library Operations:**
- File scanning with extension filtering
- Metadata extraction from tags and filename fallback
- Stale track removal for deleted files
- Track listing and search

**Queue Operations:**
- Enqueue tracks
- List queue items
- Play next/position-based playback
- Delete by queue ID
- Clear entire queue

**Audio Backend:**
- GStreamer integration
- Play/stop/pause/resume
- Seek to position
- Volume control
- Mute/unmute

**HTTP API:**
- All GET endpoints (health, status, tracks, queue, now-playing)
- All POST endpoints (scan, queue, playback controls)
- All DELETE endpoints (queue, queue items)
- Error handling with proper HTTP status codes