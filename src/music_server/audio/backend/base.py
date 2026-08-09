from abc import ABC, abstractmethod
from typing import Any


class AudioBackend(ABC):

    @abstractmethod
    def set_uri(self, uri: str) -> None:
        ...

    @abstractmethod
    def prepare_change(self) -> None:
        ...

    @abstractmethod
    def start_playback(self) -> bool:
        ...

    @abstractmethod
    def pause_playback(self) -> bool:
        ...

    @abstractmethod
    def stop_playback(self) -> bool:
        ...

    @abstractmethod
    def get_position(self) -> int:
        ...

    @abstractmethod
    def set_position(self, position_ms: int) -> bool:
        ...

    @abstractmethod
    def set_volume(self, volume: int) -> bool:
        ...

    @abstractmethod
    def set_mute(self, muted: bool) -> bool:
        ...

    @abstractmethod
    def get_current_tags(self) -> dict[str, list[Any]]:
        ...

    @abstractmethod
    def is_playing(self) -> bool:
        ...