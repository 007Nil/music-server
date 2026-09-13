import logging
from pathlib import Path
from typing import List, Optional

from music_server.audio.backend.base import AudioBackend
from music_server.audio.factory import create_audio_backend, get_available_backends

logger = logging.getLogger(__name__)

class AudioPipeline:
    """Manage audio playback with support for multiple backends and fallbacks."""

    def __init__(
        self,
        *,
        backend_name: str = "gstreamer",
        fallback_backends: List[str] = None,
        backend: AudioBackend | None = None,
    ) -> None:
        """
        Initialize the audio pipeline.
        
        Args:
            backend_name: Primary backend name to use
            fallback_backends: List of fallback backend names (in order of preference)
            backend: Direct backend instance to use (bypasses creation)
        """
        self._backend_name = backend_name
        self._fallback_backends = fallback_backends or []
        self._backend = None
        self._current_file: Path | None = None
        self._paused = False
        self._is_initialized = False
        
        # Initialize backend
        self._initialize_backend(backend)

    def _initialize_backend(self, backend: AudioBackend | None = None) -> None:
        """Initialize the audio backend, either from provided instance or creating one."""
        if backend is not None:
            self._backend = backend
        else:
            try:
                self._backend = create_audio_backend(
                    name=self._backend_name,
                    fallbacks=self._fallback_backends
                )
            except Exception as e:
                logger.error("Failed to initialize audio backend: %s", str(e))
                raise
                
        self._is_initialized = True
        logger.info("Audio pipeline initialized with backend: %s", self._backend_name)

    def play_file(self, file_path: Path) -> None:
        """Play a file using the current backend."""
        if not self._is_initialized:
            logger.error("Audio pipeline not initialized")
            return
            
        self.stop()
        
        self._current_file = file_path
        
        try:
            self._backend.set_uri(str(file_path))
            self._backend.prepare_change()
            started = self._backend.start_playback()
            
            if not started:
                logger.warning("Failed to start playback for: %s", file_path)
                self._current_file = None
                return
                
            self._paused = False
            logger.info("Successfully started playback for: %s", file_path)
        except Exception as e:
            logger.error("Playback failed for %s: %s", file_path, str(e))
            self._current_file = None
            raise

    def set_backend(self, backend: AudioBackend) -> None:
        """Replace the active backend."""
        self._backend = backend
        self._current_file = None
        self._paused = False
        self._is_initialized = True
        logger.info("Backend replaced successfully")

    def stop(self) -> None:
        """Stop current playback."""
        if not self._is_initialized:
            return
            
        try:
            if self._backend is not None:
                self._backend.stop_playback()
            self._current_file = None
            self._paused = False
            logger.info("Playback stopped")
        except Exception as e:
            logger.error("Error stopping playback: %s", str(e))

    def set_paused(self, paused: bool) -> bool:
        """Pause or resume playback when the requested state changes."""
        if not self._is_initialized or self._current_file is None:
            return False
            
        try:
            if self._paused == paused:
                return True
                
            changed = self._backend.pause_playback()
            if changed:
                self._paused = paused
                logger.info("Playback %s", "paused" if paused else "resumed")
            return changed
        except Exception as e:
            logger.error("Error during pause/resume: %s", str(e))
            return False

    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        if not self._is_initialized or self._backend is None:
            return False
        try:
            return self._backend.is_playing()
        except Exception as e:
            logger.error("Error checking playback status: %s", str(e))
            return False

    def get_position(self) -> int:
        """Get current playback position in milliseconds."""
        if not self._is_initialized or self._backend is None:
            return 0
        try:
            return self._backend.get_position()
        except Exception as e:
            logger.error("Error getting position: %s", str(e))
            return 0

    def set_position(self, position_ms: int) -> bool:
        """Set playback position in milliseconds."""
        if not self._is_initialized or self._current_file is None:
            return False
        try:
            result = self._backend.set_position(position_ms)
            if result:
                logger.debug("Position set to %d ms", position_ms)
            else:
                logger.warning("Failed to set position to %d ms", position_ms)
            return result
        except Exception as e:
            logger.error("Error setting position: %s", str(e))
            return False

    def set_volume(self, volume: int) -> bool:
        """Set audio volume (0-100)."""
        if not self._is_initialized or self._backend is None:
            return False
        try:
            result = self._backend.set_volume(volume)
            if result:
                logger.debug("Volume set to %d", volume)
            else:
                logger.warning("Failed to set volume to %d", volume)
            return result
        except Exception as e:
            logger.error("Error setting volume: %s", str(e))
            return False

    def set_mute(self, muted: bool) -> bool:
        """Mute or unmute audio."""
        if not self._is_initialized or self._backend is None:
            return False
        try:
            result = self._backend.set_mute(muted)
            if result:
                logger.debug("Audio %s", "muted" if muted else "unmuted")
            else:
                logger.warning("Failed to %s audio", "mute" if muted else "unmute")
            return result
        except Exception as e:
            logger.error("Error setting mute: %s", str(e))
            return False

    def get_current_tags(self) -> dict:
        """Get current audio tags."""
        if not self._is_initialized or self._backend is None:
            return {}
        try:
            return self._backend.get_current_tags()
        except Exception as e:
            logger.error("Error getting current tags: %s", str(e))
            return {}

    def get_backend_info(self) -> dict:
        """Get information about the current backend."""
        return {
            "name": self._backend_name,
            "available_backends": get_available_backends(),
            "fallback_backends": self._fallback_backends,
        }

    def health_check(self) -> bool:
        """Perform a health check on the current backend."""
        try:
            if not self._is_initialized or self._backend is None:
                return False
            # Simple health check - just see if we can make a basic call
            return self.is_playing() is not None
        except Exception as e:
            logger.warning("Backend health check failed: %s", str(e))
            return False