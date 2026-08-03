from __future__ import annotations

from pathlib import Path

from music_server.config import load_settings
from music_server.core import CoreService


def test_scan_indexes_audio_files(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    music_dir = tmp_path / "music"
    album_dir = music_dir / "Album One"
    album_dir.mkdir(parents=True)

    (album_dir / "Alice - First Song.mp3").write_bytes(b"audio")
    (album_dir / "Bob - Second Song.flac").write_bytes(b"audio")
    (album_dir / "ignore.txt").write_text("not audio")

    monkeypatch.setenv("MUSIC_SERVER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("MUSIC_SERVER_MUSIC_DIR", str(music_dir))
    monkeypatch.setenv("MUSIC_SERVER_AUDIO_PLAYER", "true")

    settings = load_settings()
    service = CoreService(settings)
    service.bootstrap()

    summary = service.scanner.scan()

    assert summary.scanned_files == 3
    assert summary.indexed_tracks == 2
    assert summary.skipped_files == 1
    assert service.library.count_tracks() == 2

    tracks = service.library.list_tracks(limit=10)
    assert len(tracks) == 2
    assert tracks[0].album == "Album One"
    assert all(track.uri for track in tracks)


def test_queue_and_play_next(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    music_dir = tmp_path / "music"
    music_dir.mkdir(parents=True)

    (music_dir / "Artist - Queue Song.mp3").write_bytes(b"audio")

    monkeypatch.setenv("MUSIC_SERVER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("MUSIC_SERVER_MUSIC_DIR", str(music_dir))
    monkeypatch.setenv("MUSIC_SERVER_AUDIO_PLAYER", "true")

    settings = load_settings()
    service = CoreService(settings)
    service.bootstrap()
    service.scanner.scan()

    track = service.library.list_tracks(limit=1)[0]
    assert service.playback.enqueue(track.id)

    queue_items = service.playback.list_queue()
    assert len(queue_items) == 1
    assert queue_items[0].track.id == track.id

    next_track = service.playback.play_next()
    assert next_track is not None
    assert next_track.id == track.id
    assert service.playback.count_queue() == 0


def test_scan_removes_deleted_tracks(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    music_dir = tmp_path / "music"
    music_dir.mkdir(parents=True)

    keep = music_dir / "Artist - Keep.mp3"
    drop = music_dir / "Artist - Drop.mp3"
    keep.write_bytes(b"audio")
    drop.write_bytes(b"audio")

    monkeypatch.setenv("MUSIC_SERVER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("MUSIC_SERVER_MUSIC_DIR", str(music_dir))
    monkeypatch.setenv("MUSIC_SERVER_AUDIO_PLAYER", "true")

    settings = load_settings()
    service = CoreService(settings)
    service.bootstrap()

    first = service.scanner.scan()
    assert first.indexed_tracks == 2
    assert service.library.count_tracks() == 2

    drop.unlink()
    second = service.scanner.scan()
    assert second.removed_tracks == 1
    assert service.library.count_tracks() == 1


def test_status_command_output(tmp_path, monkeypatch, capsys) -> None:
    data_dir = tmp_path / "data"
    music_dir = tmp_path / "music"
    music_dir.mkdir(parents=True)

    (music_dir / "Artist - One.mp3").write_bytes(b"audio")

    monkeypatch.setenv("MUSIC_SERVER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("MUSIC_SERVER_MUSIC_DIR", str(music_dir))
    monkeypatch.setenv("MUSIC_SERVER_AUDIO_PLAYER", "true")

    from music_server.app import main

    assert main(["init-db"]) == 0
    assert main(["scan"]) == 0
    assert main(["status"]) == 0

    captured = capsys.readouterr()
    assert "tracks=1 queue=0" in captured.out
    assert Path(data_dir / "library.db").exists()


def test_cli_play_and_stop(tmp_path, monkeypatch, capsys) -> None:
    data_dir = tmp_path / "data"
    music_dir = tmp_path / "music"
    music_dir.mkdir(parents=True)

    (music_dir / "Artist - One.mp3").write_bytes(b"audio")

    monkeypatch.setenv("MUSIC_SERVER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("MUSIC_SERVER_MUSIC_DIR", str(music_dir))
    monkeypatch.setenv("MUSIC_SERVER_AUDIO_PLAYER", "true")

    from music_server.app import main

    assert main(["scan"]) == 0
    assert main(["play", "1"]) == 0
    assert main(["stop"]) == 0

    captured = capsys.readouterr()
    assert "playing: Artist - One" in captured.out
    assert "stopped" in captured.out


def test_playback_state_persists_across_service_restart(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    music_dir = tmp_path / "music"
    music_dir.mkdir(parents=True)

    (music_dir / "Artist - One.mp3").write_bytes(b"audio")

    monkeypatch.setenv("MUSIC_SERVER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("MUSIC_SERVER_MUSIC_DIR", str(music_dir))
    monkeypatch.setenv("MUSIC_SERVER_AUDIO_PLAYER", "true")

    settings = load_settings()
    service = CoreService(settings)
    service.bootstrap()
    service.scanner.scan()
    service.play_track(1)
    assert service.pause_audio(True)

    restarted = CoreService(settings)
    restarted.bootstrap()
    current = restarted.playback.current_track()
    assert current is not None
    assert current.id == 1
    assert restarted.playback.state() == "pause"