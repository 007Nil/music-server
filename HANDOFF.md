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
- MPD protocol command handling (direct line protocol + TCP server)
- MPD command-list support and event-driven idle notifications
- broader MPD compatibility for common client commands such as `list`, `listallinfo`, `playlistfind`, and `lsinfo`
- a native Python audio backend via soundfile/sounddevice when available
- compatibility with an explicit configured player command for scripted testing or external playback
- playback timeline reporting with persisted startup recovery state
- normalized metadata fields (artist/title/album/track number + stable URI)
- runnable CLI commands
- automated tests passing (21 tests)

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
  - `MUSIC_SERVER_AUDIO_PLAYER`
  - computed `db_path`

### Persistence

- [src/music_server/database/store.py](src/music_server/database/store.py)
  - sqlite schema creation
  - track upsert/list/search/get/count (with duration, stable URI, track number)
  - queue enqueue/list/pop/count
  - queue item delete/clear helpers
  - distinct artist/album counters
  - stale-track pruning support

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

### Playback and audio

- [src/music_server/playback/player.py](src/music_server/playback/player.py)
  - queue operations and playback state (`play`, `pause`, `stop`)
  - playlist version tracking for MPD status
  - elapsed playback timeline tracking
  - persistent playback-state save/restore
  - event notifications for MPD idle clients

- [src/music_server/audio/pipeline.py](src/music_server/audio/pipeline.py)
  - native audio playback via soundfile/sounddevice when available
  - configured player command support for compatibility and scripted playback
  - playback lifecycle stop/replace behavior
  - basic position, volume, mute, and pause/resume handling

### MPD protocol

- [src/music_server/mpd/server.py](src/music_server/mpd/server.py)
  - in-process command execution for tests and integration
  - threaded TCP server with MPD banner
  - implemented command set:
    - `ping`, `idle`, `noidle`, `close`, `kill`
    - `status`, `stats`, `outputs`
    - `listall`, `list`, `listallinfo`, `find`, `search`, `playlistinfo`, `playlistfind`, `lsinfo`
    - `command_list_begin`, `command_list_ok_begin`, `command_list_end`
    - `add`, `addid`, `clear`, `deleteid`
    - `play`, `playid`, `next`, `pause`, `stop`, `currentsong`
    - `commands`, `notcommands`

### Tests

- [tests/test_smoke.py](tests/test_smoke.py)
- [tests/test_prototype.py](tests/test_prototype.py)
- [tests/test_mpd.py](tests/test_mpd.py)
- [tests/test_audio.py](tests/test_audio.py)

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
- `mpd-serve --host HOST --port PORT`

All commands are implemented in [src/music_server/app.py](src/music_server/app.py).

## 4. How To Test

### Automated tests

Run from repo root:

```bash
.venv/bin/python -m pytest
```

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
MUSIC_SERVER_AUDIO_PLAYER="mpv --no-video --really-quiet --" \
.venv/bin/python -m music_server.app scan
.venv/bin/python -m music_server.app tracks --limit 20
.venv/bin/python -m music_server.app queue-add 1
.venv/bin/python -m music_server.app queue
.venv/bin/python -m music_server.app play-next
.venv/bin/python -m music_server.app pause 1
.venv/bin/python -m music_server.app pause 0
.venv/bin/python -m music_server.app stop
```

### MPD server runtime check

Start server:

```bash
.venv/bin/python -m music_server.app mpd-serve --host 127.0.0.1 --port 6600
```

Then use any MPD client pointed at `127.0.0.1:6600`.

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

### mopidy-mpd parity

Not implemented:

- full MPD command surface compatibility
- full MPD idle/noidle semantics parity (advanced session behavior still partial)
- authentication and permission model

Current implementation: [src/music_server/mpd/server.py](src/music_server/mpd/server.py)

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
   - surface useful runtime diagnostics when playback or MPD operations fail

3. Playback robustness
   - improve player process monitoring and recovery when the player exits unexpectedly
   - add seek support
   - add volume and mute controls
   - improve transition handling between tracks

4. Persistence and recovery
   - make database writes and migrations safer
   - improve crash-safe queue and playback-state recovery
   - handle missing or changed files gracefully

5. MPD compatibility and client support
   - cover more advanced MPD client commands and edge cases
   - improve idle/session handling for real-world clients

6. Monitoring and resilience
   - add simple monitoring or restart guidance for local unattended use

### Practical definition of “production ready”

For this project, production readiness means all of the following are true:

- local library scanning and playback are reliable on real media collections
- MPD clients can connect and operate without surprising failures
- the server starts cleanly and recovers from common runtime errors
- logs and runtime state are understandable for day-to-day use
- the experience is smooth enough for regular single-user listening

## 7. Recommended Next Implementation Order

1. Add structured logging and better runtime diagnostics.
2. Improve player process monitoring and recovery.
3. Add seek support and volume/mute controls.
4. Expand MPD client compatibility for stricter clients (`listplaylists`, `playlistclear`, `playlistadd`, etc.).
5. Improve idle/noidle behavior for real-world client flows.
6. Harden persistence and recovery around queue and playback state.

## 8. Known Constraints

- Tag extraction depends on file format support in `mutagen`; fallback remains filename parsing.
- Audio output depends on an external player executable (`mpv`, `ffplay`, `cvlc`, or configured command).
- MPD support is practical but partial; some clients may require additional commands.
- Queue/playback behavior is local and pragmatic, not Mopidy-parity complete.

## 9. Context Prompt For Next Chat

Use this prompt to continue quickly in a new `/chat` session:

```text
Use HANDOFF.md as source of truth.
Continue implementation from the current working prototype.
Primary next goal: improve MPD client compatibility and metadata quality for daily usage.
Before each edit, state which files will change and expected behavior.
After edits, run .venv/bin/python -m pytest.
```