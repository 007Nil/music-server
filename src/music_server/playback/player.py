"""Playback and queue controller."""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any

from music_server.database import DatabaseStore, QueueRecord, TrackRecord


class PlaybackController:
    """Control queue operations and simulated playback."""

    def __init__(self, store: DatabaseStore, *, state_path: Path | None = None) -> None:
        self.store = store
        self._state_path = state_path
        self._current_track: TrackRecord | None = None
        self._paused = False
        self._playlist_version = 0
        self._started_at: float | None = None
        self._elapsed_at_pause = 0.0
        self._state_loaded = False
        self._listeners: list = []

    def subscribe(self, listener) -> None:
        """Register a callback for playback or playlist changes."""

        self._listeners.append(listener)

    def restore_state(self) -> None:
        """Restore persisted playback state once after DB initialization."""

        if self._state_loaded:
            return
        self._state_loaded = True
        if self._state_path is None or not self._state_path.exists():
            return
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception:
            return

        self._playlist_version = int(payload.get("playlist_version", 0))
        track_id = int(payload.get("current_track_id", 0))
        paused = bool(payload.get("paused", False))
        elapsed = float(payload.get("elapsed", 0.0))
        if track_id <= 0:
            return

        track = self.store.get_track(track_id)
        if track is None:
            return
        if not Path(track.path).exists():
            return

        self._current_track = track
        self._paused = paused
        self._elapsed_at_pause = max(0.0, min(elapsed, track.duration))
        if not paused:
            self._started_at = time.monotonic()
        self._persist_state()

    def _persist_state(self) -> None:
        if self._state_path is None:
            return
        payload = {
            "current_track_id": self._current_track.id if self._current_track is not None else 0,
            "paused": self._paused,
            "elapsed": round(self.elapsed_seconds(), 3),
            "playlist_version": self._playlist_version,
        }
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(json.dumps(payload), encoding="utf-8")
        except Exception:
            return

    def _publish(self, subsystems: set[str]) -> None:
        for listener in list(self._listeners):
            try:
                listener(subsystems)
            except Exception:
                continue

    def enqueue(self, track_id: int) -> bool:
        """Enqueue a track by id."""

        added = self.store.enqueue(track_id)
        if added:
            self._playlist_version += 1
            self._persist_state()
            self._publish({"playlist"})
        return added

    def enqueue_and_get_id(self, track_id: int) -> int | None:
        """Enqueue and return queue id."""

        queue_id = self.store.enqueue_and_get_id(track_id)
        if queue_id is not None:
            self._playlist_version += 1
            self._persist_state()
            self._publish({"playlist"})
        return queue_id

    def list_queue(self) -> list[QueueRecord]:
        """Return the current queue."""

        return self.store.list_queue()

    def play_next(self) -> TrackRecord | None:
        """Pop and return the next queued track."""

        next_track = self.store.pop_next_queue()
        self._current_track = next_track
        self._paused = False
        self._elapsed_at_pause = 0.0
        self._started_at = time.monotonic() if next_track is not None else None
        if next_track is not None:
            self._playlist_version += 1
            self._persist_state()
            self._publish({"player", "playlist"})
        return next_track

    def play_track(self, track_id: int) -> TrackRecord | None:
        """Set the given track as the current track."""

        track = self.store.get_track(track_id)
        self._current_track = track
        self._paused = False
        self._elapsed_at_pause = 0.0
        self._started_at = time.monotonic() if track is not None else None
        if track is not None:
            self._persist_state()
            self._publish({"player"})
        return track

    def play_queue_id(self, queue_id: int) -> TrackRecord | None:
        """Play a track by queue id and remove it from queue."""

        item = self.store.get_queue_item_by_id(queue_id)
        if item is None:
            return None
        deleted = self.store.delete_queue_id(queue_id)
        if deleted:
            self._playlist_version += 1
        self._current_track = item.track
        self._paused = False
        self._elapsed_at_pause = 0.0
        self._started_at = time.monotonic()
        self._persist_state()
        self._publish({"player", "playlist"})
        return item.track

    def play_position(self, position: int) -> TrackRecord | None:
        """Play a track by queue position and remove it from queue."""

        item = self.store.get_queue_item_by_position(position)
        if item is None:
            return None
        deleted = self.store.delete_queue_id(item.queue_id)
        if deleted:
            self._playlist_version += 1
        self._current_track = item.track
        self._paused = False
        self._elapsed_at_pause = 0.0
        self._started_at = time.monotonic()
        self._persist_state()
        self._publish({"player", "playlist"})
        return item.track

    def current_track(self) -> TrackRecord | None:
        """Return the currently playing track."""

        return self._current_track

    def stop(self) -> None:
        """Stop playback state."""

        self._current_track = None
        self._paused = False
        self._elapsed_at_pause = 0.0
        self._started_at = None
        self._persist_state()
        self._publish({"player"})

    def set_position(self, position_seconds: float) -> bool:
        """Seek within the current track if one is active."""

        if self._current_track is None:
            return False
        self._elapsed_at_pause = max(0.0, min(position_seconds, self._current_track.duration))
        self._started_at = time.monotonic() if not self._paused else None
        self._persist_state()
        self._publish({"player"})
        return True

    def pause(self, paused: bool) -> bool:
        """Set pause state if track is active."""

        if self._current_track is None:
            return False
        if paused and not self._paused:
            self._elapsed_at_pause = self.elapsed_seconds()
            self._started_at = None
        if not paused and self._paused:
            self._started_at = time.monotonic()
        self._paused = paused
        self._persist_state()
        self._publish({"player"})
        return True

    def state(self) -> str:
        """Return MPD-like playback state string."""

        if self._current_track is None:
            return "stop"
        if self._paused:
            return "pause"
        return "play"

    def playlist_version(self) -> int:
        """Return monotonically increasing playlist version."""

        return self._playlist_version

    def clear_queue(self) -> None:
        """Clear queue entries."""

        self.store.clear_queue()
        self._playlist_version += 1
        self._persist_state()
        self._publish({"playlist"})

    def delete_queue_id(self, queue_id: int) -> bool:
        """Delete queue entry by queue id."""

        deleted = self.store.delete_queue_id(queue_id)
        if deleted:
            self._playlist_version += 1
            self._persist_state()
            self._publish({"playlist"})
        return deleted

    def count_queue(self) -> int:
        """Return queue size."""

        return self.store.count_queue()

    def elapsed_seconds(self) -> float:
        """Return elapsed playback seconds for current track."""

        if self._current_track is None:
            return 0.0
        if self._paused or self._started_at is None:
            return min(self._elapsed_at_pause, self._current_track.duration)
        elapsed = self._elapsed_at_pause + (time.monotonic() - self._started_at)
        return min(max(elapsed, 0.0), self._current_track.duration)
