from music_server.audio.backend.base import AudioBackend
from music_server.audio.backend.gstreamer_backend import (
    GStreamerBackend,
)


def create_audio_backend(name: str = "gstreamer") -> AudioBackend:
    if name == "gstreamer":
        return GStreamerBackend()

    raise ValueError(
        f"Unknown audio backend: {name}"
    )