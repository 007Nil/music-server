"""Mopidy-style audio backend interface and a simple local implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
import shlex
import shutil
import subprocess
from typing import Any

try:
    import sounddevice as sd
except OSError:
    sd = None

import soundfile as sf


class AudioBackend(ABC):
    """Abstract playback backend used by the audio service."""

    @abstractmethod
    def set_uri(self, uri: str) -> None:
        """Load a track URI for playback."""

    @abstractmethod
    def prepare_change(self) -> None:
        """Prepare for a state transition such as switching tracks."""

    @abstractmethod
    def start_playback(self) -> bool:
        """Start playback."""

    @abstractmethod
    def pause_playback(self) -> bool:
        """Pause playback."""

    @abstractmethod
    def stop_playback(self) -> bool:
        """Stop playback."""

    @abstractmethod
    def get_position(self) -> int:
        """Return playback position in milliseconds."""

    @abstractmethod
    def set_position(self, position_ms: int) -> bool:
        """Seek to a given position in milliseconds."""

    @abstractmethod
    def get_current_tags(self) -> dict[str, list[Any]]:
        """Return current metadata tags."""

    @abstractmethod
    def is_playing(self) -> bool:
        """Return True when playback is active."""

    @abstractmethod
    def set_source_setup_callback(self, callback: Callable[[Any], None]) -> None:
        """Register a callback for source setup."""

    @abstractmethod
    def set_about_to_finish_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback for about-to-finish events."""


class LocalAudioBackend(AudioBackend):
    """Native backend that decodes and plays local audio files directly."""

    DEFAULT_PLAYER_CANDIDATES: tuple[list[str], ...] = (
        ["mpv", "--no-video", "--really-quiet", "--"],
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
        ["cvlc", "--play-and-exit", "--intf", "dummy"],
    )

    def __init__(
        self,
        *,
        configured_player: str = "",
        popen_factory: Callable[..., subprocess.Popen[bytes]] | None = None,
        which_func: Callable[[str], str | None] | None = None,
    ) -> None:
        self.configured_player = configured_player.strip()
        self._popen_factory = popen_factory or subprocess.Popen
        self._which = which_func or shutil.which
        self._current_uri: str | None = None
        self._state = "stopped"
        self._position_ms = 0
        self._tags: dict[str, list[Any]] = {}
        self._source_setup_callback: Callable[[Any], None] | None = None
        self._about_to_finish_callback: Callable[[], None] | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._stream: Any | None = None
        self._audio_data: Any | None = None
        self._sample_rate = 0
        self._frames = 0
        self._playback_started = False
        self.volume = 100
        self.muted = False

    def set_uri(self, uri: str) -> None:
        self._current_uri = uri
        self._position_ms = 0
        self._tags = {}

    def prepare_change(self) -> None:
        self.stop_playback()
        self._state = "stopped"

    def start_playback(self) -> bool:
        if not self._current_uri:
            return False
        self.stop_playback()
        if self.configured_player:
            command = self._build_command(Path(self._current_uri))
            self._process = self._popen_factory(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._state = "playing"
            return True

        file_path = Path(self._current_uri)
        if not file_path.exists():
            return False
        try:
            audio_data, sample_rate = sf.read(str(file_path), always_2d=True)
        except Exception:
            return False

        self._audio_data = audio_data
        self._sample_rate = int(sample_rate)
        self._frames = 0
        self._playback_started = False

        def callback(outdata: Any, frames: int, time_info: Any, status: Any) -> None:
            if self._audio_data is None:
                outdata.fill(0)
                raise sd.CallbackStop
            start = self._frames
            end = start + frames
            chunk = self._audio_data[start:end]
            if len(chunk) < frames:
                chunk = self._audio_data[start:]
                if len(chunk) == 0:
                    outdata.fill(0)
                    raise sd.CallbackStop
                outdata[:len(chunk)] = chunk
                outdata[len(chunk):] = 0
                self._frames = len(self._audio_data)
            else:
                outdata[:] = chunk
                self._frames = end
            if self.muted:
                outdata.fill(0)
            else:
                gain = self.volume / 100.0
                outdata *= gain
            self._position_ms = int(self._frames / max(self._sample_rate, 1) * 1000)

        if sd is None:
            self._stream = None
            return False

        try:
            self._stream = sd.OutputStream(
                samplerate=self._sample_rate,
                channels=self._audio_data.shape[1] if self._audio_data.ndim > 1 else 1,
                callback=callback,
                dtype="float32",
            )
            self._stream.start()
        except Exception:
            self._stream = None
            return False

        self._playback_started = True
        self._state = "playing"
        return True

    def pause_playback(self) -> bool:
        if self._state == "playing" and self._stream is not None:
            self._stream.stop()
            self._state = "paused"
            return True
        if self._state == "paused" and self._stream is not None:
            self._stream.start()
            self._state = "playing"
            return True
        return False

    def stop_playback(self) -> bool:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._audio_data = None
        self._process = None
        self._state = "stopped"
        self._position_ms = 0
        self._playback_started = False
        return True

    def get_position(self) -> int:
        return self._position_ms

    def set_position(self, position_ms: int) -> bool:
        if self._audio_data is None:
            self._position_ms = max(0, position_ms)
            return True
        frame_index = int(max(0, position_ms) / 1000 * max(self._sample_rate, 1))
        self._frames = min(max(frame_index, 0), len(self._audio_data) - 1)
        self._position_ms = max(0, position_ms)
        return True

    def set_volume(self, volume: int) -> bool:
        self.volume = max(0, min(100, volume))
        if self._stream is not None:
            self._stream.stop()
            self._stream.start()
        return True

    def set_mute(self, muted: bool) -> bool:
        self.muted = muted
        return True

    def get_current_tags(self) -> dict[str, list[Any]]:
        return self._tags

    def is_playing(self) -> bool:
        return self._state == "playing" and self._stream is not None

    def set_source_setup_callback(self, callback: Callable[[Any], None]) -> None:
        self._source_setup_callback = callback

    def set_about_to_finish_callback(self, callback: Callable[[], None]) -> None:
        self._about_to_finish_callback = callback

    def _build_command(self, file_path: Path) -> list[str]:
        if self.configured_player:
            command = shlex.split(self.configured_player, posix=True)
            if not command:
                raise RuntimeError("Configured audio player command is empty")
            return [*command, str(file_path)]

        for candidate in self.DEFAULT_PLAYER_CANDIDATES:
            if self._which(candidate[0]) is not None:
                return [*candidate, str(file_path)]

        raise RuntimeError(
            "No supported audio player found. Set MUSIC_SERVER_AUDIO_PLAYER to a valid command."
        )
