"""Library queries backed by the sqlite store."""

from __future__ import annotations

from music_server.database import DatabaseStore, TrackRecord


class LibraryService:
    """Read-focused service for indexed library data."""

    def __init__(self, store: DatabaseStore) -> None:
        self.store = store

    def list_tracks(self, *, limit: int = 50) -> list[TrackRecord]:
        """Return a limited track list."""

        return self.store.list_tracks(limit=limit)

    def search_tracks(self, query: str, *, limit: int = 50) -> list[TrackRecord]:
        """Search tracks by text query."""

        return self.store.search_tracks(query=query, limit=limit)

    def get_track(self, track_id: int) -> TrackRecord | None:
        """Return track details by id."""

        return self.store.get_track(track_id)

    def count_tracks(self) -> int:
        """Return indexed track count."""

        return self.store.count_tracks()
