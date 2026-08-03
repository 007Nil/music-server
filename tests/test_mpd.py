from __future__ import annotations

import sys
import time

from music_server.config import load_settings
from music_server.core import CoreService
from music_server.mpd import MpdServer


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


def test_mpd_status_and_listall(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)
    mpd = MpdServer(service)

    status = mpd.execute_line("status")
    listing = mpd.execute_line("listall")

    assert "state: stop" in status.lines
    assert any(line.startswith("audio: ") for line in status.lines)
    assert status.lines[-1] == "OK"
    assert any(line.startswith("file: ") for line in listing.lines)
    assert listing.lines[-1] == "OK"

    stats = mpd.execute_line("stats")
    assert any(line.startswith("songs: 2") for line in stats.lines)
    assert stats.lines[-1] == "OK"


def test_mpd_find_add_play_currentsong_next(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)
    mpd = MpdServer(service)

    find = mpd.execute_line('find any "Alpha"')
    assert any("Title: First" == line for line in find.lines)

    track = service.library.search_tracks("Alpha", limit=1)[0]
    add = mpd.execute_line(f'add "{track.path}"')
    assert add.lines == ["OK"]

    addid = mpd.execute_line(f'addid "{track.path}"')
    assert addid.lines[0].startswith("Id: ")
    assert addid.lines[-1] == "OK"

    playlist = mpd.execute_line("playlistinfo")
    assert any(line.startswith("Pos: ") for line in playlist.lines)
    assert any(line.startswith("Id: ") for line in playlist.lines)
    assert playlist.lines[-1] == "OK"

    play = mpd.execute_line("play")
    assert play.lines == ["OK"]

    status_after_play = mpd.execute_line("status")
    assert any(line.startswith("elapsed: ") for line in status_after_play.lines)
    assert any(line.startswith("time: ") for line in status_after_play.lines)

    paused = mpd.execute_line("pause 1")
    assert paused.lines == ["OK"]

    resumed = mpd.execute_line("pause 0")
    assert resumed.lines == ["OK"]

    current = mpd.execute_line("currentsong")
    assert any(line == f"Id: {track.id}" for line in current.lines)
    assert current.lines[-1] == "OK"

    stop = mpd.execute_line("stop")
    assert stop.lines == ["OK"]

    next_result = mpd.execute_line("next")
    assert next_result.lines == ["OK"]


def test_mpd_commands_and_playid(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)
    mpd = MpdServer(service)

    track = service.library.search_tracks("Alpha", limit=1)[0]
    addid = mpd.execute_line(f'addid "{track.path}"')
    queue_id = int(addid.lines[0].split(": ", maxsplit=1)[1])

    commands = mpd.execute_line("commands")
    assert any(line == "command: playid" for line in commands.lines)
    assert any(line == "command: outputs" for line in commands.lines)
    assert any(line == "command: command_list_ok_begin" for line in commands.lines)
    assert commands.lines[-1] == "OK"

    idle = mpd.execute_line("idle")
    assert idle.lines == ["changed: player", "OK"]

    noidle = mpd.execute_line("noidle")
    assert noidle.lines == ["OK"]

    outputs = mpd.execute_line("outputs")
    assert any(line == "outputid: 0" for line in outputs.lines)
    assert outputs.lines[-1] == "OK"

    playlistid = mpd.execute_line(f"playlistid {queue_id}")
    assert any(line == f"Id: {queue_id}" for line in playlistid.lines)
    assert playlistid.lines[-1] == "OK"

    playid = mpd.execute_line(f"playid {queue_id}")
    assert playid.lines == ["OK"]


def test_mpd_command_list_ok_mode(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)
    mpd = MpdServer(service)

    response = mpd._execute_command_list(["ping", "status"], send_list_ok=True)
    assert response.lines.count("list_OK") == 2
    assert response.lines[-1] == "OK"


def test_mpd_extended_commands_and_playlist_queries(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)
    mpd = MpdServer(service)

    track = service.library.search_tracks("Alpha", limit=1)[0]
    add = mpd.execute_line(f'add "{track.path}"')
    assert add.lines == ["OK"]

    listing = mpd.execute_line("list artist")
    assert any(line == "Artist: Alpha" for line in listing.lines)
    assert listing.lines[-1] == "OK"

    full_listing = mpd.execute_line("listallinfo")
    assert any(line.startswith("file: ") for line in full_listing.lines)
    assert full_listing.lines[-1] == "OK"

    playlist_query = mpd.execute_line("playlistfind title First")
    assert any(line == "Title: First" for line in playlist_query.lines)
    assert playlist_query.lines[-1] == "OK"

    lsinfo = mpd.execute_line(f'lsinfo "{track.path}"')
    assert any(line.startswith("file: ") for line in lsinfo.lines)
    assert lsinfo.lines[-1] == "OK"


def test_mpd_play_launches_audio_backend(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    music_dir = tmp_path / "music"
    album = music_dir / "Demo"
    album.mkdir(parents=True)

    (album / "Alpha - First.mp3").write_bytes(b"audio")

    monkeypatch.setenv("MUSIC_SERVER_DATA_DIR", str(data_dir))
    monkeypatch.setenv("MUSIC_SERVER_MUSIC_DIR", str(music_dir))

    marker = tmp_path / "player.log"
    player_script = tmp_path / "player.py"
    player_script.write_text(
        "import pathlib, sys\n"
        "pathlib.Path(sys.argv[1]).write_text(sys.argv[2])\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MUSIC_SERVER_AUDIO_PLAYER", f"{sys.executable} {player_script} {marker}")

    service = CoreService(load_settings())
    service.bootstrap()
    service.scanner.scan()
    mpd = MpdServer(service)

    track = service.library.search_tracks("Alpha", limit=1)[0]
    mpd.execute_line(f'add "{track.path}"')
    mpd.execute_line("play")

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if marker.exists():
            break
        time.sleep(0.01)

    assert marker.read_text(encoding="utf-8") == track.path


def test_mpd_unknown_command_returns_ack(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)
    mpd = MpdServer(service)

    response = mpd.execute_line("doesnotexist")
    assert response.lines[0].startswith("ACK")