# Development Guide

This document explains the application flow end to end, including the main modules, the function call chain for each major action, and the runtime path from CLI input to playback or MPD output.

The project is intentionally simple: a single-user, localhost-oriented music server with local file scanning, queue management, playback state, and an MPD-compatible protocol server.

## 1. Architecture overview

The main runtime pieces are:

- [src/music_server/app.py](src/music_server/app.py): CLI entry point
- [src/music_server/core/service.py](src/music_server/core/service.py): top-level orchestration
- [src/music_server/library/service.py](src/music_server/library/service.py): read access to the indexed library
- [src/music_server/playback/player.py](src/music_server/playback/player.py): queue and playback state controller
- [src/music_server/audio/pipeline.py](src/music_server/audio/pipeline.py): thin playback API over the backend
- [src/music_server/audio/backend.py](src/music_server/audio/backend.py): audio backend implementation
- [src/music_server/scanner/scanner.py](src/music_server/scanner/scanner.py): library scan and metadata extraction
- [src/music_server/mpd/server.py](src/music_server/mpd/server.py): MPD-compatible TCP server
- [src/music_server/database/store.py](src/music_server/database/store.py): SQLite persistence
- [src/music_server/config/settings.py](src/music_server/config/settings.py): environment-driven configuration

## 2. Startup and bootstrap flow

The first important path is application startup.

### Flow

```mermaid
flowchart TD
    A[CLI command: start/init-db/status/scan] --> B[app.main]
    B --> C[load_settings]
    B --> D[CoreService(settings)]
    D --> E[DatabaseStore]
    D --> F[LibraryScanner]
    D --> G[LibraryService]
    D --> H[PlaybackController]
    D --> I[AudioPipeline]

    B --> J{command}
    J -->|init-db| K[CoreService.bootstrap]
    J -->|scan| K
    J -->|status| K
    J -->|start| K

    K --> L[settings.data_dir.mkdir]
    K --> M[store.initialize]
    K --> N[playback.restore_state]
```

### Function chain

- app.main
- CoreService.__init__
- CoreService.bootstrap
- DatabaseStore.initialize
- PlaybackController.restore_state

### Notes

- bootstrap creates the data directory, initializes SQLite, and restores the saved playback state if present.
- The app is designed to be restarted safely without losing the basic persistence layer.

## 3. Scan and index a music library

The scan command walks the configured music directory, extracts metadata, and updates the database.

### Flow

```mermaid
flowchart TD
    A[CLI: scan] --> B[app.main]
    B --> C[CoreService.bootstrap]
    C --> D[LibraryScanner.scan]
    D --> E[settings.music_dir.rglob]
    E --> F[SUPPORTED_EXTENSIONS check]
    F --> G[_read_metadata]
    G --> H[MutagenFile]
    G --> I[_parse_artist_title]
    G --> J[_album_for_file]
    D --> K[store.upsert_track]
    D --> L[store.delete_tracks_not_in]
    L --> M[ScanSummary]
```

### Function chain

- app.main
- CoreService.bootstrap
- LibraryScanner.scan
- LibraryScanner._read_metadata
- LibraryScanner._parse_artist_title
- LibraryScanner._album_for_file
- LibraryScanner._stable_uri_for_file
- DatabaseStore.upsert_track
- DatabaseStore.delete_tracks_not_in

### Important detail

The scanner uses Mutagen for metadata extraction and falls back to filename-based values when tags are missing.

## 4. Queue a song

Queueing a song adds it to the SQLite-backed queue.

### Flow

```mermaid
flowchart TD
    A[CLI: queue-add 1] --> B[app.main]
    B --> C[CoreService.bootstrap]
    C --> D[PlaybackController.enqueue]
    D --> E[DatabaseStore.enqueue]
    E --> F[PlaybackController._playlist_version += 1]
    F --> G[PlaybackController._persist_state]
    G --> H[PlaybackController._publish]
```

### Function chain

- app.main
- CoreService.bootstrap
- PlaybackController.enqueue
- DatabaseStore.enqueue
- PlaybackController._persist_state
- PlaybackController._publish

## 5. How playing a song works

This is the central runtime path. It has two layers:

1. the queue/playback state layer
2. the audio backend layer

### Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI as app.main
    participant Core as CoreService
    participant Playback as PlaybackController
    participant Audio as AudioPipeline
    participant Backend as LocalAudioBackend
    participant DB as DatabaseStore

    User->>CLI: play 1
    CLI->>Core: play_track(1)
    Core->>Playback: play_track(1)
    Playback->>DB: get_track(1)
    DB-->>Playback: TrackRecord
    Playback->>Playback: update current track, reset timing
    Playback->>Playback: _persist_state()
    Core->>Audio: play_file(Path(track.path))
    Audio->>Audio: stop()
    Audio->>Backend: set_uri(path)
    Audio->>Backend: prepare_change()
    Audio->>Backend: start_playback()
    Backend->>Backend: choose player or native backend
    Backend-->>Audio: started / failed
```

### Function chain

- app.main
- CoreService.play_track
- PlaybackController.play_track
- DatabaseStore.get_track
- PlaybackController._persist_state
- AudioPipeline.play_file
- AudioPipeline.stop
- LocalAudioBackend.set_uri
- LocalAudioBackend.prepare_change
- LocalAudioBackend.start_playback

### What happens inside the backend

The backend takes one of two paths:

- if a configured player is present, it launches it through subprocess.Popen
- otherwise it tries the native Python audio path using soundfile and sounddevice

The important distinction is that playback control is split between:

- PlaybackController: queue selection and playback state
- AudioPipeline / LocalAudioBackend: actual audio output

## 6. How play-next works

The play-next command uses the queue directly.

### Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI as app.main
    participant Core as CoreService
    participant Playback as PlaybackController
    participant DB as DatabaseStore
    participant Audio as AudioPipeline

    User->>CLI: play-next
    CLI->>Core: play_next()
    Core->>Playback: play_next()
    Playback->>DB: pop_next_queue()
    DB-->>Playback: TrackRecord
    Playback->>Playback: update current track and timing
    Playback->>Playback: _persist_state()
    Core->>Audio: play_file(Path(track.path))
```

### Function chain

- app.main
- CoreService.play_next
- PlaybackController.play_next
- DatabaseStore.pop_next_queue
- PlaybackController._persist_state
- AudioPipeline.play_file

## 7. Pause, seek, volume, and mute

These controls currently operate mostly through playback state rather than the underlying backend.

### Flow

```mermaid
flowchart TD
    A[CLI pause/seek/volume/mute] --> B[app.main]
    B --> C[CoreService.pause_audio / seek_audio / set_audio_volume / set_audio_mute]
    C --> D[PlaybackController.pause / set_position]
    C --> E[AudioPipeline.set_volume / set_mute]
```

### Function chain

- app.main
- CoreService.pause_audio
- PlaybackController.pause
- CoreService.seek_audio
- PlaybackController.set_position
- CoreService.set_audio_volume
- AudioPipeline.set_volume
- CoreService.set_audio_mute
- AudioPipeline.set_mute

### Current behavior note

- pause and seek are currently tracked in PlaybackController.
- start/stop/volume/mute are routed to the audio pipeline and backend.

## 8. Command-family diagrams

The previous sections already covered the main paths, but the same runtime can be grouped by command family for easier reference.

### 8.1 Library commands: init-db, scan, tracks, status

```mermaid
flowchart TD
    A[CLI command] --> B[app.main]
    B --> C[CoreService.bootstrap]
    C --> D[DatabaseStore.initialize]
    C --> E[PlaybackController.restore_state]

    A -->|scan| F[LibraryScanner.scan]
    A -->|tracks| G[LibraryService.list_tracks or search_tracks]
    A -->|status| H[LibraryService.count_tracks + PlaybackController.count_queue]
```

### 8.2 Queue commands: queue-add, queue, queue-clear, deleteid

```mermaid
flowchart TD
    A[CLI command] --> B[app.main]
    B --> C[CoreService.bootstrap]
    C --> D[PlaybackController.enqueue / list_queue / clear_queue / delete_queue_id]
    D --> E[DatabaseStore queue operations]
    D --> F[PlaybackController._persist_state]
    D --> G[PlaybackController._publish]
```

### 8.3 Playback commands: play, play-next, stop

```mermaid
flowchart TD
    A[CLI command] --> B[app.main]
    B --> C[CoreService.play_track / play_next / stop_audio]
    C --> D[PlaybackController.play_track / play_next / stop]
    C --> E[AudioPipeline.play_file / stop]
    E --> F[LocalAudioBackend.set_uri / prepare_change / start_playback]
```

### 8.4 Control commands: pause, seek, volume, mute

```mermaid
flowchart TD
    A[CLI command] --> B[app.main]
    B --> C[CoreService.pause_audio / seek_audio / set_audio_volume / set_audio_mute]
    C --> D[PlaybackController.pause / set_position]
    C --> E[AudioPipeline.set_volume / set_mute]
    E --> F[LocalAudioBackend.set_volume / set_mute]
```

### 8.5 HTTP routes: status, scan, queue, playback, now-playing

```mermaid
flowchart TD
    A[HTTP client] --> B[HttpServer.serve_forever]
    B --> C[HttpApi.handle]
    C --> D[CoreService.bootstrap]
    C --> E[LibraryService and DatabaseStore]
    C --> F[PlaybackController methods]
    C --> G[AudioPipeline controls]
```

## 9. Persistence model

The app persists two concepts:

- tracks: indexed music files and metadata
- queue state: pending queue items and playback state

The state is written to SQLite and to a JSON playback-state file.

### Key persistence points

- DatabaseStore.upsert_track
- DatabaseStore.enqueue
- PlaybackController._persist_state
- PlaybackController.restore_state

## 10. Quick mental model

If you want the shortest possible explanation of the runtime:

1. The CLI parses input in app.main.
2. The CLI delegates to CoreService.
3. CoreService uses PlaybackController for queue and state.
4. CoreService uses AudioPipeline for actual audio output.
5. The HTTP server routes API requests through the same CoreService and PlaybackController path.

That is the backbone of the application.
