# music_server/audio/backend/gstreamer_backend.py

from __future__ import annotations

from typing import Any, Callable

from music_server.audio.backend.base import AudioBackend
from music_server.audio.backend.gstreamer import GStreamer


class GStreamerBackend(AudioBackend):
    """AudioBackend implementation using GStreamer."""

    def __init__(self) -> None:
        self._gst = GStreamer()
        self._player = self._gst.create_playbin()

        self._uri: str | None = None
        self._state = "stopped"
        self._volume = 100
        self._muted = False

        self._source_setup_callback: Callable[[Any], None] | None = None
        self._about_to_finish_callback: Callable[[], None] | None = None

    def set_uri(self, uri: str) -> None:
        self._uri = uri

    def prepare_change(self) -> None:
        self.stop_playback()

    def start_playback(self) -> bool:
        if not self._uri:
            return False

        self._gst.set_uri(
            self._player,
            self._uri,
        )

        # Restore volume/mute state before starting.
        self._gst.set_volume(
            self._player,
            self._volume,
        )

        self._player.set_property(
            "mute",
            self._muted,
        )

        started = self._gst.play(
            self._player,
        )

        if started:
            self._state = "playing"

        return started

    def pause_playback(self) -> bool:
        if self._state == "playing":
            paused = self._gst.pause(
                self._player,
            )

            if paused:
                self._state = "paused"

            return paused

        if self._state == "paused":
            resumed = self._gst.play(
                self._player,
            )

            if resumed:
                self._state = "playing"

            return resumed

        return False

    def stop_playback(self) -> bool:
        stopped = self._gst.stop(
            self._player,
        )

        if stopped:
            self._state = "stopped"

        return stopped

    def get_position(self) -> int:
        return self._gst.get_position(
            self._player,
        )

    def set_position(self, position_ms: int) -> bool:
        return self._gst.seek(
            self._player,
            position_ms,
        )

    def set_volume(self, volume: int) -> bool:
        self._volume = max(0, min(100, volume))

        return self._gst.set_volume(
            self._player,
            self._volume,
        )

    def set_mute(self, muted: bool) -> bool:
        self._muted = muted

        self._player.set_property(
            "mute",
            muted,
        )

        return True

    def get_current_tags(self) -> dict[str, list[Any]]:
        return {}

    def is_playing(self) -> bool:
        return self._state == "playing"

    def set_source_setup_callback(
        self,
        callback: Callable[[Any], None],
    ) -> None:
        self._source_setup_callback = callback

    def set_about_to_finish_callback(
        self,
        callback: Callable[[], None],
    ) -> None:
        self._about_to_finish_callback = callback

    def close(self) -> None:
        self.stop_playback()