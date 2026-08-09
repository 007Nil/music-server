"""Core service for application startup and orchestration."""

from __future__ import annotations

import logging
from pathlib import Path

from music_server.audio import AudioPipeline
from music_server.config import Settings
from music_server.database import DatabaseStore
from music_server.library import LibraryService
from music_server.playback import PlaybackController
from music_server.scanner import LibraryScanner

logger = logging.getLogger(__name__)


class CoreService:
    """Manage the top-level application lifecycle."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = DatabaseStore(settings.db_path)
        self.scanner = LibraryScanner(settings=settings, store=self.store)
        self.library = LibraryService(store=self.store)
        self.playback = PlaybackController(store=self.store, state_path=settings.playback_state_path)
        self.audio = AudioPipeline()

    def bootstrap(self) -> None:
        """Prepare directories and initialize persistence."""

        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.store.initialize()
        self.playback.restore_state()
        logger.info("bootstrapped service at %s", self.settings.data_dir)

    def start(self) -> None:
        """Start the application."""

        self.bootstrap()
        print(f"music-server starting from {self.settings.data_dir}")

    def status(self) -> tuple[int, int]:
        """Return indexed track count and queue length."""

        self.bootstrap()
        return (self.library.count_tracks(), self.playback.count_queue())

    def play_next(self):
        """Play the next queued track through the audio pipeline."""

        self.bootstrap()
        track = self.playback.play_next()
        if track is None:
            return None
        self.audio.play_file(Path(track.path))
        return track

    def play_position(self, position: int):
        """Play and remove a queued track by position."""

        self.bootstrap()
        track = self.playback.play_position(position)
        if track is None:
            return None
        self.audio.play_file(Path(track.path))
        return track

    def play_track(self, track_id: int):
        """Play a specific track through the audio pipeline."""

        self.bootstrap()
        track = self.playback.play_track(track_id)
        if track is None:
            return None
        # self.audio.play_file(Path(track.path))
        return track

    def stop_audio(self) -> None:
        """Stop audio playback."""

        self.audio.stop()
        self.playback.stop()

    def seek_audio(self, position_seconds: float) -> bool:
        """Seek within the current track."""

        if self.playback.current_track() is None:
            return False
        self.playback.set_position(position_seconds)
        return True

    def set_audio_volume(self, volume: int) -> bool:
        """Set audio volume on the active playback pipeline."""

        return self.audio.set_volume(volume)

    def set_audio_mute(self, muted: bool) -> bool:
        """Mute or unmute audio playback."""

        return self.audio.set_mute(muted)

    def pause_audio(self, paused: bool) -> bool:
        """Pause or resume playback state."""
        is_playing = self.audio.is_playing()
        print(f"pause_audio: is_playing={is_playing}, paused={paused}")
        return self.playback.pause(paused)
