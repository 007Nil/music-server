# Project: Build a Minimal Mopidy Distribution

## Overview

I want to create a lightweight, maintainable fork of Mopidy that contains only the functionality required for a local music server.

This is **not** a rewrite from scratch.

The goal is to understand the existing architecture, extract only the required components, simplify them, and produce a clean, single-codebase version that is easy to maintain and extend.

The final project should feel like a purpose-built local music server rather than a generic plugin-based media framework.

The current implementation already supports local library scanning, SQLite-backed queueing, MPD-compatible commands, and a native Python audio backend path with explicit player-command fallback for scripted testing and compatibility.

---

# Background

Mopidy is built around an extension system where most functionality lives in separate packages.

My current setup only uses:

* Mopidy Core
* mopidy-local
* mopidy-mpd

I do **not** use:

* Spotify
* YouTube
* SoundCloud
* TuneIn
* Podcasts
* Internet radio
* Mopidy-Iris
* HTTP browsing
* Mobile clients
* Web frontends
* Any third-party extensions

The plugin architecture is unnecessary for my use case and adds complexity that I would like to eliminate.

---

# Project Goal

Create a new project that contains only the components necessary for:

* Local music library
* Metadata indexing
* Playlist support
* Queue management
* Audio playback
* MPD protocol support
* Configuration
* Logging

Everything else should be evaluated for removal.

The result should be:

* Smaller
* Easier to understand
* Easier to maintain
* Faster to start
* Easier to debug
* Easier to extend

---

# Important Constraints

This project is **not** about deleting code as quickly as possible.

It is about understanding the architecture before making changes.

Every removal must be justified.

Never remove code without first identifying:

* what it does
* who depends on it
* why it exists
* whether it can safely disappear

---

# Development Philosophy

This is a collaborative engineering project.

The AI is **not** the primary developer.

The AI acts as:

* Software Architect
* Technical Lead
* Reviewer
* Documentation writer
* Refactoring planner

I am the developer.

I will implement the business logic.

---

# AI Responsibilities

You should:

* Study the Mopidy architecture.
* Read the source code.
* Explain how each subsystem works.
* Produce dependency graphs.
* Identify removable modules.
* Identify critical modules.
* Design cleaner architectures.
* Suggest improvements.
* Generate boilerplate code.
* Generate interfaces.
* Generate package structures.
* Produce TODOs.
* Produce migration plans.
* Review my implementations.
* Suggest refactoring opportunities.

Do **not** automatically rewrite thousands of lines of code.

---

# My Responsibilities

I will:

* Write implementation logic.
* Perform refactoring.
* Make architectural decisions.
* Review generated plans.
* Test functionality.
* Decide whether proposed changes are accepted.

---

# Expected Collaboration

For every task:

1. Analyze
2. Explain
3. Design
4. Generate skeleton code
5. Wait for my implementation
6. Review my implementation
7. Continue

Never skip directly to implementation.

---

# Target Repository Structure

The final project should resemble something like:

```text
music-server/

    core/
    library/
    playback/
    scanner/
    database/
    audio/
    mpd/
    config/
    utils/
```

There should be no separate repositories for:

* mopidy-local
* mopidy-mpd

Everything should live in one clean repository.

---

# Long-Term Architecture Goals

The extension system should eventually disappear.

Instead of:

Core
↓

Extension Manager
↓

Plugin
↓

Backend
↓

Service

I want:

Core
↓

Library
↓

Playback
↓

MPD

Simple.

Direct.

Easy to understand.

---

# Migration Strategy

The project should proceed in phases.

## Phase 1 — Architecture Discovery

Study:

* startup sequence
* actor system
* event system
* playback pipeline
* backend architecture
* extension loading
* configuration
* audio pipeline
* MPD server

Deliverables:

* architecture diagrams
* dependency graph
* subsystem overview
* package map

---

## Phase 2 — Dependency Analysis

For every package explain:

Purpose

Required?

Dependencies

Can it be removed?

Risk level

Replacement strategy

Nothing should be removed yet.

---

## Phase 3 — Define the Minimal Distribution

Identify the minimum components required to support:

* local scanning
* metadata database
* playback
* playlists
* MPD protocol

Everything else becomes optional.

---

## Phase 4 — Repository Design

Design the new repository.

Recommend:

* package layout
* module boundaries
* configuration layout
* testing layout
* documentation structure

Explain every decision.

---

## Phase 5 — Merge mopidy-local

Move the functionality from mopidy-local into the new repository.

Replace extension boundaries with direct service calls.

Simplify APIs.

Keep functionality unchanged.

---

## Phase 6 — Merge mopidy-mpd

Integrate MPD directly.

Simplify startup.

Simplify initialization.

Remove unnecessary registration code.

---

## Phase 7 — Remove Extension Infrastructure

Only after everything works.

Evaluate removing:

* extension discovery
* plugin registration
* unnecessary Pykka actors
* compatibility layers
* obsolete interfaces

Never remove abstractions until the replacement is proven.

---

## Phase 8 — Cleanup

Remove:

* dead code
* unused configuration
* obsolete utilities
* duplicate logic
* unnecessary abstractions

Improve:

* readability
* startup time
* memory usage
* maintainability

---

# Code Generation Rules

Generate:

* interfaces
* package structures
* placeholder implementations
* TODO comments
* documentation

Do NOT generate entire implementations unless I explicitly request them.

Use placeholders like:

```python
class LocalLibrary:
    """
    TODO:
        Implement local library management.
        Port logic from mopidy-local.
    """
```

or

```python
def scan_library():
    """
    TODO:
        Implement scanner.
        Preserve current Mopidy behavior.
    """
```

---

# Refactoring Rules

Every refactoring must include:

Why this change is needed.

Advantages.

Disadvantages.

Files affected.

Dependencies.

Migration steps.

Validation steps.

Rollback strategy.

---

# Documentation Requirements

Every major subsystem should have documentation explaining:

Purpose

Responsibilities

Dependencies

Lifecycle

Extension points (if any remain)

Future improvements

---

# Code Quality Expectations

Prefer:

* readable code
* explicit dependencies
* composition over unnecessary abstractions
* simple APIs
* small modules
* good naming
* clear documentation

Avoid:

* clever code
* unnecessary inheritance
* premature optimization
* overengineering

---

# Communication Style

Assume I am an experienced software engineer.

Do not explain basic Python concepts.

Focus on:

* architecture
* software engineering
* dependency management
* maintainability
* trade-offs
* performance
* clean design

If multiple approaches exist:

Compare them.

Recommend one.

Explain why.

Challenge my assumptions if a better design exists.

---

# Success Criteria

The project is successful if the final product:

* preserves the stability of Mopidy
* supports local music playback
* supports MPD clients
* has significantly less code
* has significantly fewer dependencies
* is easier to understand
* is easier to contribute to
* has a clean architecture
* starts quickly
* is easy to package
* is enjoyable to develop

The goal is not to build another media framework.

The goal is to build the cleanest possible local music server based on the proven foundation provided by Mopidy.
