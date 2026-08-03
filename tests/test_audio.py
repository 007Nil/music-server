from __future__ import annotations

import json
from pathlib import Path

from music_server.audio import AudioPipeline
from music_server.audio.backend import AudioBackend
from music_server.database import DatabaseStore
from music_server.playback import PlaybackController


class _DummyBackend(AudioBackend):
    def __init__(self) -> None:
        self.uris: list[str] = []
        self.started = False
        self.stopped = False
        self.position_ms = 0
        self.tags: dict[str, list[str]] = {}
        self._source_setup_callback = None
        self._about_to_finish_callback = None

    def set_uri(self, uri: str) -> None:
        self.uris.append(uri)

    def prepare_change(self) -> None:
        self.started = False

    def start_playback(self) -> bool:
        self.started = True
        return True

    def pause_playback(self) -> bool:
        return True

    def stop_playback(self) -> bool:
        self.stopped = True
        self.started = False
        return True

    def get_position(self) -> int:
        return self.position_ms

    def set_position(self, position_ms: int) -> bool:
        self.position_ms = position_ms
        return True

    def set_volume(self, volume: int) -> bool:
        self.volume = volume
        return True

    def set_mute(self, muted: bool) -> bool:
        self.muted = muted
        return True

    def get_current_tags(self) -> dict[str, list[str]]:
        return self.tags

    def is_playing(self) -> bool:
        return self.started

    def set_source_setup_callback(self, callback) -> None:
        self._source_setup_callback = callback

    def set_about_to_finish_callback(self, callback) -> None:
        self._about_to_finish_callback = callback


def test_audio_pipeline_uses_backend_for_playback() -> None:
    backend = _DummyBackend()
    pipeline = AudioPipeline()
    pipeline.set_backend(backend)
    pipeline.play_file(Path("/tmp/example.mp3"))

    assert backend.uris == ["/tmp/example.mp3"]
    assert backend.started is True


def test_audio_pipeline_stops_previous_playback() -> None:
    backend = _DummyBackend()
    pipeline = AudioPipeline()
    pipeline.set_backend(backend)
    pipeline.play_file(Path("/tmp/one.mp3"))
    pipeline.play_file(Path("/tmp/two.mp3"))

    assert backend.uris == ["/tmp/one.mp3", "/tmp/two.mp3"]
    assert backend.stopped is True


def test_audio_pipeline_can_report_current_state() -> None:
    backend = _DummyBackend()
    pipeline = AudioPipeline()
    pipeline.set_backend(backend)
    pipeline.play_file(Path("/tmp/example.mp3"))

    assert pipeline.get_position() == 0
    assert pipeline.get_current_tags() == {}
    pipeline.stop()
    assert backend.stopped is True


def test_audio_pipeline_supports_seek_and_volume_controls() -> None:
    backend = _DummyBackend()
    pipeline = AudioPipeline()
    pipeline.set_backend(backend)
    pipeline.play_file(Path("/tmp/example.mp3"))

    assert pipeline.set_position(2500) is True
    assert pipeline.set_volume(35) is True
    assert pipeline.set_mute(True) is True

    assert backend.position_ms == 2500
    assert backend.volume == 35
    assert backend.muted is True


def test_playback_controller_ignores_missing_tracks_on_restore(tmp_path: Path) -> None:
    store = DatabaseStore(tmp_path / "library.db")
    store.initialize()
    track_id = None
    with store._connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tracks(path, uri, title, artist, album, track_no, duration, mtime)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("/tmp/missing-example.mp3", "file:///tmp/missing-example.mp3", "Track", "Artist", "Album", 1, 120.0, 1.0),
        )
        track_id = int(cursor.lastrowid)

    state_path = tmp_path / "playback_state.json"
    state_path.write_text(
        json.dumps({"current_track_id": track_id, "paused": False, "elapsed": 10.0, "playlist_version": 1}),
        encoding="utf-8",
    )

    controller = PlaybackController(store=store, state_path=state_path)
    controller.restore_state()

    assert controller.current_track() is None