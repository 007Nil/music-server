"""Database persistence for tracks and queue state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True, slots=True)
class TrackRecord:
    """A single indexed music track."""

    id: int
    path: str
    uri: str
    title: str
    artist: str
    album: str
    track_no: int
    duration: float
    mtime: float


@dataclass(frozen=True, slots=True)
class QueueRecord:
    """A queue item joined to a track."""

    queue_id: int
    track: TrackRecord


class DatabaseStore:
    """Manage sqlite schema and queries for music-server."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def initialize(self) -> None:
        """Create database schema if it does not exist."""

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    uri TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    album TEXT NOT NULL,
                    track_no INTEGER NOT NULL DEFAULT 0,
                    duration REAL NOT NULL DEFAULT 0,
                    mtime REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE
                );
                """
            )
            columns = conn.execute("PRAGMA table_info(tracks)").fetchall()
            column_names = {str(row["name"]) for row in columns}
            if "uri" not in column_names:
                conn.execute("ALTER TABLE tracks ADD COLUMN uri TEXT NOT NULL DEFAULT ''")
            if "track_no" not in column_names:
                conn.execute("ALTER TABLE tracks ADD COLUMN track_no INTEGER NOT NULL DEFAULT 0")
            if "duration" not in column_names:
                conn.execute("ALTER TABLE tracks ADD COLUMN duration REAL NOT NULL DEFAULT 0")
            conn.execute("UPDATE tracks SET uri = path WHERE uri = ''")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tracks_uri ON tracks(uri)")

    def upsert_track(
        self,
        *,
        path: str,
        uri: str,
        title: str,
        artist: str,
        album: str,
        track_no: int,
        duration: float,
        mtime: float,
    ) -> None:
        """Insert or update a track by file path."""

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tracks(path, uri, title, artist, album, track_no, duration, mtime)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    uri = excluded.uri,
                    title = excluded.title,
                    artist = excluded.artist,
                    album = excluded.album,
                    track_no = excluded.track_no,
                    duration = excluded.duration,
                    mtime = excluded.mtime
                """,
                (path, uri, title, artist, album, track_no, duration, mtime),
            )

    def list_tracks(self, *, limit: int = 50) -> list[TrackRecord]:
        """List tracks ordered by artist/title."""

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, path, uri, title, artist, album, track_no, duration, mtime
                FROM tracks
                ORDER BY artist, album, title
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._track_from_row(row) for row in rows]

    def search_tracks(self, query: str, *, limit: int = 50) -> list[TrackRecord]:
        """Search tracks by title, artist, or album."""

        pattern = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, path, uri, title, artist, album, track_no, duration, mtime
                FROM tracks
                WHERE title LIKE ? OR artist LIKE ? OR album LIKE ?
                ORDER BY artist, album, title
                LIMIT ?
                """,
                (pattern, pattern, pattern, limit),
            ).fetchall()
        return [self._track_from_row(row) for row in rows]

    def get_track(self, track_id: int) -> TrackRecord | None:
        """Return a track by id."""

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, path, uri, title, artist, album, track_no, duration, mtime
                FROM tracks
                WHERE id = ?
                """,
                (track_id,),
            ).fetchone()
        if row is None:
            return None
        return self._track_from_row(row)

    def count_tracks(self) -> int:
        """Count indexed tracks."""

        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM tracks").fetchone()
        if row is None:
            return 0
        return int(row["count"])

    def enqueue(self, track_id: int) -> bool:
        """Enqueue a track id if it exists."""

        return self.enqueue_and_get_id(track_id) is not None

    def enqueue_and_get_id(self, track_id: int) -> int | None:
        """Enqueue a track and return queue id."""

        if self.get_track(track_id) is None:
            return None
        with self._connect() as conn:
            cursor = conn.execute("INSERT INTO queue(track_id) VALUES(?)", (track_id,))
            return int(cursor.lastrowid)

    def list_queue(self) -> list[QueueRecord]:
        """List queued tracks in insertion order."""

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    q.id AS queue_id,
                    t.id AS track_id,
                    t.path,
                    t.uri,
                    t.title,
                    t.artist,
                    t.album,
                    t.track_no,
                    t.duration,
                    t.mtime
                FROM queue q
                JOIN tracks t ON t.id = q.track_id
                ORDER BY q.id
                """
            ).fetchall()
        return [
            QueueRecord(
                queue_id=int(row["queue_id"]),
                track=TrackRecord(
                    id=int(row["track_id"]),
                    path=str(row["path"]),
                    uri=str(row["uri"]),
                    title=str(row["title"]),
                    artist=str(row["artist"]),
                    album=str(row["album"]),
                    track_no=int(row["track_no"]),
                    duration=float(row["duration"]),
                    mtime=float(row["mtime"]),
                ),
            )
            for row in rows
        ]

    def random_track_ids(self, limit: int = 10) -> list[int]:
        """Return a list of random track ids."""

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id
                FROM tracks
                ORDER BY RANDOM()
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            print(rows)
        return [int(row["id"]) for row in rows]

    def pop_next_queue(self) -> TrackRecord | None:
        """Pop the next queued track and return it."""

        queue_items = self.list_queue()
        if not queue_items:
            return None
        next_item = queue_items[0]
        with self._connect() as conn:
            conn.execute("DELETE FROM queue WHERE id = ?", (next_item.queue_id,))
        return next_item.track

    def clear_queue(self) -> None:
        """Remove all queue entries."""

        with self._connect() as conn:
            conn.execute("DELETE FROM queue")

    def delete_queue_id(self, queue_id: int) -> bool:
        """Delete one queue entry by queue id."""

        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM queue WHERE id = ?", (queue_id,))
            return cursor.rowcount > 0

    def get_queue_item_by_id(self, queue_id: int) -> QueueRecord | None:
        """Return a queue entry by queue id."""

        queue_items = self.list_queue()
        return next((item for item in queue_items if item.queue_id == queue_id), None)

    def get_queue_item_by_position(self, position: int) -> QueueRecord | None:
        """Return a queue entry by position."""

        queue_items = self.list_queue()
        if position < 0 or position >= len(queue_items):
            return None
        return queue_items[position]

    def count_queue(self) -> int:
        """Count queue entries."""

        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM queue").fetchone()
        if row is None:
            return 0
        return int(row["count"])

    def count_artists(self) -> int:
        """Count distinct artists."""

        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(DISTINCT artist) AS count FROM tracks").fetchone()
        if row is None:
            return 0
        return int(row["count"])

    def count_albums(self) -> int:
        """Count distinct albums."""

        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(DISTINCT album) AS count FROM tracks").fetchone()
        if row is None:
            return 0
        return int(row["count"])

    def delete_tracks_not_in(self, existing_paths: set[str]) -> int:
        """Delete tracks not present in existing_paths and return count."""

        with self._connect() as conn:
            if not existing_paths:
                cursor = conn.execute("DELETE FROM tracks")
                return cursor.rowcount

            placeholders = ",".join(["?"] * len(existing_paths))
            cursor = conn.execute(
                f"DELETE FROM tracks WHERE path NOT IN ({placeholders})",
                tuple(existing_paths),
            )
            return cursor.rowcount

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _track_from_row(row: sqlite3.Row) -> TrackRecord:
        return TrackRecord(
            id=int(row["id"]),
            path=str(row["path"]),
            uri=str(row["uri"]),
            title=str(row["title"]),
            artist=str(row["artist"]),
            album=str(row["album"]),
            track_no=int(row["track_no"]),
            duration=float(row["duration"]),
            mtime=float(row["mtime"]),
        )
