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
        logger.info("CoreService initialized with settings: %s", {
            "data_dir": str(settings.data_dir),
            "db_path": str(settings.db_path),
            "music_dir": str(settings.music_dir),
            "playback_state_path": str(settings.playback_state_path)
        })

    def bootstrap(self) -> None:
        """Prepare directories and initialize persistence."""

        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.store.initialize()
        self.playback.restore_state()
        logger.info("Bootstrapped service at %s", self.settings.data_dir)

    def start(self) -> None:
        """Start the application."""

        self.bootstrap()
        logger.info("music-server starting from %s", self.settings.data_dir)
        print(f"music-server starting from {self.settings.data_dir}")

    def status(self) -> tuple[int, int]:
        """Return indexed track count and queue length."""

        self.bootstrap()
        tracks = self.library.count_tracks()
        queue_size = self.playback.count_queue()
        logger.debug("Status check: tracks=%d, queue=%d", tracks, queue_size)
        return (tracks, queue_size)

    def play_next(self):
        """Play the next queued track through the audio pipeline."""

        self.bootstrap()
        logger.info("Playing next track from queue")
        track = self.playback.play_next()
        if track is None:
            logger.warning("No tracks in queue to play")
            return None
        logger.info("Playing track: %s - %s", track.artist, track.title)
        self.audio.play_file(Path(track.path))
        return track

    def play_position(self, position: int):
        """Play and remove a queued track by position."""

        self.bootstrap()
        logger.info("Playing track at position %d", position)
        track = self.playback.play_position(position)
        if track is None:
            logger.warning("Track not found at position %d", position)
            return None
        logger.info("Playing track: %s - %s", track.artist, track.title)
        self.audio.play_file(Path(track.path))
        return track

    def play_track(self, track_id: int):
        """Play a specific track through the audio pipeline."""

        self.bootstrap()
        logger.info("Playing track with ID %d", track_id)
        track = self.playback.play_track(track_id)
        if track is None:
            logger.warning("Track not found with ID %d", track_id)
            return None
        # self.audio.play_file(Path(track.path))
        logger.info("Track prepared for playback: %s - %s", track.artist, track.title)
        return track

    def stop_audio(self) -> None:
        """Stop audio playback."""

        logger.info("Stopping audio playback")
        self.audio.stop()
        self.playback.stop()
        logger.info("Audio playback stopped")

    def seek_audio(self, position_seconds: float) -> bool:
        """Seek within the current track."""

        if self.playback.current_track() is None:
            logger.warning("Seek attempted without active track")
            return False
        logger.debug("Seeking to position %f seconds", position_seconds)
        self.playback.set_position(position_seconds)
        logger.info("Successfully seeked to %f seconds", position_seconds)
        return True

    def set_audio_volume(self, volume: int) -> bool:
        """Set audio volume on the active playback pipeline."""

        logger.debug("Setting audio volume to %d", volume)
        result = self.audio.set_volume(volume)
        if result:
            logger.info("Volume set to %d", volume)
        else:
            logger.error("Failed to set volume to %d", volume)
        return result

    def set_audio_mute(self, muted: bool) -> bool:
        """Mute or unmute audio playback."""

        logger.debug("Setting audio mute to %s", muted)
        result = self.audio.set_mute(muted)
        if result:
            logger.info("Audio %s", "muted" if muted else "unmuted")
        else:
            logger.error("Failed to %s audio", "mute" if muted else "unmute")
        return result

    def pause_audio(self, paused: bool) -> bool:
        """Pause or resume playback state."""

        previous_state = self.playback.state()
        logger.debug("Attempting to %s playback", "pause" if paused else "resume")
        if not self.playback.pause(paused):
            logger.warning("Pause/resume failed: no current track")
            return False

        target_state = "pause" if paused else "play"
        if previous_state != target_state:
            # Best effort: update backend state when transitioning between play/pause.
            logger.debug("Updating backend playback state to %s", "paused" if paused else "playing")
            self.audio.set_paused(paused)
        logger.info("Playback %s", "paused" if paused else "resumed")
        return True
