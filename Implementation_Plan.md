# Implementation Plan

This document defines the implementation path for turning the current Mopidy-based setup into a single, local-music-server codebase. The goal is not a rewrite from scratch. The goal is to understand the existing architecture, preserve working behavior, and migrate the required pieces in a controlled sequence.

## Current Status Snapshot

The implementation has moved beyond the initial scaffold. The project now supports local library scanning, SQLite-backed queueing, MPD-compatible commands, and a native audio backend path with explicit player-command fallback. The remaining work is focused on robustness, quality-of-life polish, and hardening the experience for everyday local use.

## Goals

Build a lightweight local music server that supports:

- Local music library browsing and search
- Metadata indexing and persistence
- Playlist and queue management
- Audio playback
- MPD protocol support
- Configuration and logging

The resulting project should be easier to understand, easier to maintain, faster to start, and simpler to extend than the current extension-based arrangement.

## Non-Goals

Do not attempt to remove large parts of Mopidy before the replacement is understood and validated.

Do not rewrite the whole system in one pass.

Do not optimize for code deletion over correctness.

Do not change behavior unless the change is explicitly justified and covered by tests.

## Core Principles

1. Start from the current architecture and preserve behavior first.
2. Separate discovery from implementation.
3. Migrate one subsystem at a time.
4. Keep the smallest possible working surface at every stage.
5. Validate each cut with focused tests before moving on.

## Working Agreement

I am the primary code writer for this project.

Before any code edit, I will state which files I am changing and what behavior the change is meant to achieve.

You will review the plan, architecture, and implementation decisions, while I will carry out the code changes and keep the implementation moving.

If a change affects behavior, I will call that out before editing and follow it with a focused validation step.

## Current Architecture Summary

The current setup is split across three main areas:

- Mopidy core, which owns startup, config loading, actor orchestration, and audio/backend wiring
- mopidy-local, which owns the local library database, scanner, URI translation, and storage logic
- mopidy-mpd, which owns the MPD protocol frontend, socket server, session handling, and command dispatch

The current extension system is the main source of indirection. The long-term plan is to replace extension registration and plugin discovery with direct module wiring inside the new repository.

## Target Repository Shape

The target repository should resemble a direct local music server, not a generic plugin host.

Suggested top-level packages:

- core
- library
- playback
- scanner
- database
- audio
- mpd
- config
- utils

This layout is intentionally simple. It keeps the major responsibilities visible and avoids extension-style indirection unless it is still required during migration.

## Implementation Strategy

### Phase 1: Architecture Discovery

Purpose: build a dependable understanding of the current system before moving code.

What to document:

- Startup sequence
- Actor system and event flow
- Backend and frontend registration
- Audio pipeline
- Configuration loading and validation
- Local library storage and query model
- MPD protocol flow and client handling

Deliverables:

- Architecture notes
- Dependency graph
- Subsystem inventory
- Package map

Implementation approach:

- Read the current Mopidy core, mopidy-local, and mopidy-mpd code paths that actually control startup and runtime behavior.
- Trace the concrete flow from CLI entry point to server startup to audio and frontend initialization.
- Identify where each subsystem begins and ends.

Validation:

- Each architectural claim should be backed by a specific module or test file.
- Any ambiguous boundary should be called out explicitly instead of guessed.

### Phase 2: Dependency Analysis

Purpose: determine what is required, optional, and removable.

For every package or subsystem, document:

- Purpose
- Required or optional
- Dependencies
- Who uses it
- Risk if removed
- Replacement strategy

Implementation approach:

- Build a dependency matrix for the current Mopidy core package tree.
- Repeat the same analysis for mopidy-local and mopidy-mpd.
- Separate pure logic from extension glue.

Validation:

- No removal decisions in this phase.
- Every proposed removal must be justified by a clear dependency analysis.

### Phase 3: Define the Minimal Distribution

Purpose: define the smallest useful local music server.

Required capabilities:

- Library scanning
- Metadata database
- Playback
- Playlists and queue management
- MPD protocol support

Likely out of scope for the first cut:

- Extension discovery
- Generic plugin infrastructure
- Extra web frontends
- Third-party extension support
- Unused backends and protocol surfaces

Implementation approach:

- Decide which Mopidy subsystems stay and which can be replaced by direct modules.
- Define the minimum runtime object graph.
- Make sure every required feature has a concrete owner in the new architecture.

Validation:

- The minimal set must be sufficient to support local playback through MPD clients.

### Phase 4: Repository Design

Purpose: design the new codebase before migration begins.

Design decisions to make:

- Package boundaries
- Module responsibilities
- Configuration layout
- Logging setup
- Test layout
- Documentation structure

Implementation approach:

- Preserve clear boundaries between storage, scanning, playback, and protocol handling.
- Keep the initial design direct and explicit.
- Avoid designing abstractions that only make sense if the old extension system still exists.

Validation:

- The design should support incremental migration of mopidy-local first and mopidy-mpd second.

### Phase 5: Merge mopidy-local

Purpose: move local library functionality into the new codebase.

What to bring over:

- Library browsing and search logic
- SQLite schema and migrations
- Storage and indexing logic
- URI translation
- Scanner and mtime discovery logic
- Playlist-related local-library behavior if still needed

Implementation approach:

- Replace extension registration with direct instantiation from the application startup path.
- Keep the existing behavior stable while moving the code.
- Introduce a direct service boundary for the local library stack.
- Preserve the local URI scheme unless there is a concrete reason to change it.

Validation:

- Run the local library tests after every migration step.
- Verify that indexing, lookup, browse, and clear behavior still match the existing implementation.

### Phase 6: Merge mopidy-mpd

Purpose: integrate MPD directly into the new server startup.

What to bring over:

- MPD socket server
- Session handling
- Command dispatch
- Protocol parsing
- Authentication and idle behavior

Implementation approach:

- Remove the extension boundary around MPD startup.
- Instantiate the MPD server directly from the main application startup path.
- Keep the protocol behavior stable while simplifying construction and registration.
- Maintain the existing command semantics until the new repository is stable.

Validation:

- Run the MPD protocol tests after every migration step.
- Verify client connection, command parsing, idle handling, and error responses.

### Phase 7: Remove Extension Infrastructure

Purpose: simplify the architecture after the replacements are proven.

Candidates for removal or reduction:

- Extension discovery
- Plugin registration
- Compatibility layers that exist only to support old boundaries
- Any actor layers that no longer provide real isolation or concurrency value

Implementation approach:

- Remove only after the new direct startup path is stable.
- Keep any actor or listener abstraction that still provides clear value.
- Avoid removing concurrency primitives until their replacement is well understood.

Validation:

- Startup, playback, local library access, and MPD protocol handling must still work end to end.

### Phase 8: Cleanup

Purpose: remove leftovers and tighten the design.

Cleanup tasks:

- Remove dead code
- Remove unused configuration options
- Remove obsolete utilities
- Consolidate duplicate logic
- Improve naming and module boundaries

Implementation approach:

- Keep cleanup separate from functional migration.
- Use tests to ensure no behavior regresses while simplifying.

Validation:

- Only remove code after confirming nothing depends on it.

## Proposed New Code Organization

This is the working package map for the new repository.

### core

Owns application startup and the main service composition.

Responsibilities:

- Bootstrapping
- Dependency wiring
- Lifecycle management
- High-level orchestration

### library

Owns local music browsing and search behavior.

Responsibilities:

- Browse
- Search
- Lookup
- URI mapping
- Library-facing domain logic

### database

Owns persistence and schema management.

Responsibilities:

- SQLite schema
- Migrations
- Query helpers
- Track, album, and artist persistence

### scanner

Owns filesystem scanning and metadata extraction.

Responsibilities:

- Walk local media paths
- Collect mtimes
- Detect changes
- Feed metadata into the database layer

### playback

Owns queue and playback control.

Responsibilities:

- Playback state
- Queue and tracklist logic
- URI resolution for playable media

### audio

Owns the audio pipeline and output integration.

Responsibilities:

- Playback pipeline setup
- Output sink management
- Mixer integration if retained

### mpd

Owns the MPD protocol server.

Responsibilities:

- Socket server
- Client sessions
- Command parsing and dispatch
- Protocol responses

### config

Owns configuration parsing and defaults.

Responsibilities:

- Default configuration
- Runtime validation
- Path handling

### utils

Owns shared helpers that do not belong in the main domain packages.

Responsibilities:

- Generic filesystem helpers
- Formatting helpers
- Shared types or constants

## Migration Order

The implementation order should be:

1. Discover and document the current architecture.
2. Define the dependency matrix and removal candidates.
3. Design the target repository layout.
4. Merge mopidy-local behavior into the new codebase.
5. Merge mopidy-mpd behavior into the new codebase.
6. Remove extension infrastructure only after the direct path is validated.
7. Clean up dead code and simplify further.

This order matters because the local library stack provides the persistence and scanning foundation, while MPD provides the external client-facing contract.

## Validation Plan

Every phase needs a focused validation step.

Recommended validation types:

- Targeted unit tests for the touched subsystem
- Narrow integration tests around startup and protocol handling
- Focused type checks or lint checks when a code path is being moved
- End-to-end smoke tests only after the individual pieces are stable

Validation must be local to the change. If a change touches the library stack, run library tests first. If it touches the MPD stack, run MPD protocol tests first. If it touches startup wiring, validate startup before broadening the check set.

## Rollback Strategy

Each migration step should remain small enough to revert safely.

Rollback rules:

- Keep changes scoped to one subsystem at a time.
- Preserve old behavior until the replacement is verified.
- Do not mix cleanup with behavior changes.
- If a migration step fails, revert only the most recent step and re-evaluate the boundary.

## Open Questions

These should be resolved before implementation begins:

- Should the initial migration preserve Pykka actors everywhere, or should some controller layers be simplified during the merge?
- Should the local URI scheme remain exactly as-is for compatibility, or should it be normalized as part of the repository merge?
- Which parts of Mopidy core should remain as-is during the first merge, and which should be replaced immediately by direct code in the new repository?
- Which optional behaviors, if any, should remain in the first release beyond the minimum local-library and MPD functionality?

## Practical Next Step

The next implementation artifact should be a dependency matrix for Mopidy core, mopidy-local, and mopidy-mpd. That matrix will determine the safe removal candidates and the first concrete cut points for migration.