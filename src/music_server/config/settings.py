"""Configuration settings for music-server."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings for the application."""

    data_dir: Path
    music_dir: Path
    audio_player: str

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

    data_dir = os.environ.get("MUSIC_SERVER_DATA_DIR", ".music-server")
    music_dir = os.environ.get("MUSIC_SERVER_MUSIC_DIR", "~/Music")
    audio_player = os.environ.get("MUSIC_SERVER_AUDIO_PLAYER", "")
    return Settings(
        data_dir=Path(data_dir).expanduser(),
        music_dir=Path(music_dir).expanduser(),
        audio_player=audio_player,
    )
