from __future__ import annotations

from music_server.config import load_settings
from music_server.core import CoreService
from music_server.http import HttpApi, HttpApiError


def _build_service(tmp_path, monkeypatch) -> CoreService:
    data_dir = tmp_path / "data"
    music_dir = tmp_path / "music"
    album = music_dir / "Demo"
    album.mkdir(parents=True)

    (album / "Alpha - First.mp3").write_bytes(b"audio")
    (album / "Beta - Second.flac").write_bytes(b"audio")

    monkeypatch.setenv("MUSIC_SERVER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("MUSIC_SERVER_MUSIC_DIR", str(music_dir))
    monkeypatch.setenv("MUSIC_SERVER_AUDIO_PLAYER", "true")

    service = CoreService(load_settings())
    service.bootstrap()
    service.scanner.scan()
    return service


def test_http_status_tracks_and_now_playing(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)
    api = HttpApi(service)

    status = api.handle("GET", "/api/status")
    assert status.status == 200
    assert status.payload["tracks"] == 2
    assert status.payload["queue"] == 0
    assert status.payload["playback"]["state"] == "stop"

    tracks = api.handle("GET", "/api/tracks", query="search=Alpha&limit=10")
    assert tracks.status == 200
    assert len(tracks.payload["items"]) == 1
    assert tracks.payload["items"][0]["title"] == "First"

    now = api.handle("GET", "/api/now-playing")
    assert now.status == 200
    assert now.payload["track"] is None


def test_http_queue_and_playback_controls(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)
    api = HttpApi(service)

    added = api.handle("POST", "/api/queue", body={"track_id": 1})
    assert added.status == 201

    queue = api.handle("GET", "/api/queue")
    assert queue.status == 200
    assert len(queue.payload["items"]) == 1

    play_next = api.handle("POST", "/api/playback/play-next")
    assert play_next.status == 200
    assert play_next.payload["track"]["id"] == 1

    paused = api.handle("POST", "/api/playback/pause", body={"paused": True})
    assert paused.status == 200
    assert paused.payload["paused"] is True

    resumed = api.handle("POST", "/api/playback/resume", body={})
    assert resumed.status == 200
    assert resumed.payload["paused"] is False

    stopped = api.handle("POST", "/api/playback/stop", body={})
    assert stopped.status == 200
    assert stopped.payload["stopped"] is True


def test_http_scan_and_error_paths(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)
    api = HttpApi(service)

    created = service.settings.music_dir / "Demo" / "Gamma - Third.mp3"
    created.write_bytes(b"audio")

    scan = api.handle("POST", "/api/library/scan", body={})
    assert scan.status == 200
    assert scan.payload["indexed_tracks"] == 3

    track = api.handle("GET", "/api/tracks/3")
    assert track.status == 200
    assert track.payload["title"] == "Third"

    try:
        api.handle("POST", "/api/queue", body={"track_id": 999})
        assert False, "expected not-found error"
    except HttpApiError as exc:
        assert exc.status == 404
        assert "track not found" in str(exc)
