# Reference Repositories

These repositories are the standing source material for the music-server project. Use them as the primary reference when checking Mopidy architecture, behavior, or migration details.

## Core Mopidy

- Path: `/home/nil/Project/Personal/mopidy_custom`
- Use for: startup flow, actor model, core controllers, audio pipeline, config loading, extension loading, built-in backends, and general Mopidy architecture.
- Most relevant areas:
  - `src/mopidy/_app/`
  - `src/mopidy/core/`
  - `src/mopidy/audio/`
  - `src/mopidy/backend/`
  - `src/mopidy/ext/`
  - `src/mopidy/_exts/`
  - `docs/reference/architecture.md`

## mopidy-local

- Path: `/home/nil/Project/Personal/mopidy-local`
- Use for: local library indexing, SQLite schema, storage, scanning, URI translation, and local playback integration.
- Most relevant areas:
  - `src/mopidy_local/actor.py`
  - `src/mopidy_local/library.py`
  - `src/mopidy_local/storage.py`
  - `src/mopidy_local/schema.py`
  - `src/mopidy_local/playback.py`
  - `src/mopidy_local/translator.py`
  - `src/mopidy_local/mtimes.py`
  - `src/mopidy_local/commands.py`
  - `tests/`

## mopidy-mpd

- Path: `/home/nil/Project/Personal/mopidy-mpd`
- Use for: MPD protocol behavior, socket server setup, session handling, dispatcher logic, context wiring, and command semantics.
- Most relevant areas:
  - `src/mopidy_mpd/__init__.py`
  - `src/mopidy_mpd/actor.py`
  - `src/mopidy_mpd/network.py`
  - `src/mopidy_mpd/session.py`
  - `src/mopidy_mpd/dispatcher.py`
  - `src/mopidy_mpd/context.py`
  - `src/mopidy_mpd/protocol/`
  - `tests/`

## Working Rule

When architectural questions arise, check these repositories first before making design decisions in the new codebase.

When migrating a subsystem, use the corresponding repository as the behavioral reference and port only the parts that are required for the minimal local music server.

For the current implementation, the most important practical distinction is that the new codebase is not a full Mopidy clone. It is a simpler local-first music server with an MPD-style protocol layer and a direct playback pipeline that can use native Python audio when available, while still allowing an explicit external player command for compatibility and smoke testing.