from pathlib import Path

from music_server.app import main
from music_server.config import load_settings
from music_server.core import CoreService


def test_main_smoke(capsys) -> None:
    main()
    captured = capsys.readouterr()
    assert "music-server starting" in captured.out


def test_load_settings_uses_default_data_dir() -> None:
    settings = load_settings()
    assert settings.data_dir == Path(".music-server")


def test_core_service_start_uses_settings(capsys) -> None:
    settings = load_settings()
    service = CoreService(settings)

    service.start()

    captured = capsys.readouterr()
    assert str(settings.data_dir) in captured.out
