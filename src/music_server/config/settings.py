"""Configuration settings for music-server."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import sys


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings for the application."""

    data_dir: Path
    music_dir: Path

    @property
    def db_path(self) -> Path:
        """Return the default sqlite database path."""

        return self.data_dir / "library.db"

    @property
    def playback_state_path(self) -> Path:
        """Return persistent playback state file path."""

        return self.data_dir / "playback_state.json"


def load_settings() -> Settings:
    """Load runtime settings from the environment."""
    try:
        data_dir = os.environ.get("MUSIC_SERVER_DATA_DIR")
        music_dir = os.environ.get("MUSIC_SERVER_MUSIC_DIR")
        return Settings(
            data_dir=Path(data_dir).expanduser(),
            music_dir=Path(music_dir).expanduser()
        )
    except Exception or TypeError as e:
        print("MUSIC_SERVER_DATA_DIR or MUSIC_SERVER_MUSIC_DIR env varibale does not exists")
        print("Below env variables are missing")
        print("export MUSIC_SERVER_DATA_DIR='$HOME/.music-server'")
        print("export MUSIC_SERVER_MUSIC_DIR='$HOME/Music'")
        sys.exit(-1)

