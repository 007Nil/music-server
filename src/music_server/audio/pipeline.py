"""Audio output integration using a Mopidy-style playback lifecycle."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from music_server.audio.backend import AudioBackend, LocalAudioBackend

logger = logging.getLogger(__name__)


class AudioPipeline:
    """A thin audio API that routes playback through a pluggable backend."""

    def __init__(self, *, configured_player: str = "") -> None:
        self._backend: AudioBackend = LocalAudioBackend(configured_player=configured_player)
        self._current_file: Path | None = None

    def play_file(self, file_path: Path) -> None:
        """Play a file path through the configured backend."""

        self.stop()
        self._current_file = file_path
        logger.info("starting playback for %s", file_path)
        self._backend.set_uri(str(file_path))
        self._backend.prepare_change()
        started = self._backend.start_playback()
        if not started:
            logger.warning("playback start reported failure for %s", file_path)

    def stop(self) -> None:
        """Stop current playback if active."""

        logger.info("stopping playback")
        self._backend.stop_playback()
        self._current_file = None

    def is_playing(self) -> bool:
        """Return True if the backend is currently playing."""

        return self._backend.is_playing()

    def set_backend(self, backend: AudioBackend) -> None:
        """Swap in a different backend implementation."""

        self._backend = backend

    def get_backend(self) -> AudioBackend:
        """Return the active backend."""

        return self._backend

    def get_position(self) -> int:
        """Return playback position in milliseconds."""

        return self._backend.get_position()

    def set_position(self, position_ms: int) -> bool:
        """Seek to a position in milliseconds."""

        return self._backend.set_position(position_ms)

    def set_volume(self, volume: int) -> bool:
        """Set volume on the backend in the range 0-100."""

        return self._backend.set_volume(volume)

    def set_mute(self, muted: bool) -> bool:
        """Mute or unmute the backend."""

        return self._backend.set_mute(muted)

    def get_current_tags(self) -> dict[str, list[Any]]:
        """Return current metadata tags."""

        return self._backend.get_current_tags()
