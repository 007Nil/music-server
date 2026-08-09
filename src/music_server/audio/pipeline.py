from pathlib import Path

from music_server.audio.backend.base import AudioBackend
from music_server.audio.factory import create_audio_backend


class AudioPipeline:

    def __init__(
        self,
        *,
        backend: AudioBackend | None = None,
        backend_name: str = "gstreamer",
    ) -> None:

        self._backend = (
            backend
            if backend is not None
            else create_audio_backend(backend_name)
        )

        self._current_file: Path | None = None

    def play_file(self, file_path: Path) -> None:
        self.stop()

        self._current_file = file_path

        self._backend.set_uri(
            str(file_path)
        )

        self._backend.prepare_change()

        self._backend.start_playback()

    def stop(self) -> None:
        self._backend.stop_playback()
        self._current_file = None

    def is_playing(self) -> bool:
        return self._backend.is_playing()

    def get_position(self) -> int:
        return self._backend.get_position()

    def set_position(self, position_ms: int) -> bool:
        return self._backend.set_position(
            position_ms
        )

    def set_volume(self, volume: int) -> bool:
        return self._backend.set_volume(volume)

    def set_mute(self, muted: bool) -> bool:
        return self._backend.set_mute(muted)