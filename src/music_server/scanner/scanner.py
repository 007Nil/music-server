"""Filesystem scanner for local music files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from mutagen import File as MutagenFile

from music_server.config import Settings
from music_server.database import DatabaseStore


SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".ogg", ".m4a", ".wav"}


@dataclass(frozen=True, slots=True)
class ScanSummary:
    """Summary of a scan run."""

    scanned_files: int
    indexed_tracks: int
    skipped_files: int
    removed_tracks: int


class LibraryScanner:
    """Scan local files and index simple metadata."""

    def __init__(self, settings: Settings, store: DatabaseStore) -> None:
        self.settings = settings
        self.store = store

    def scan(self) -> ScanSummary:
        """Scan the configured music directory and update the database."""

        if not self.settings.music_dir.exists():
            return ScanSummary(
                scanned_files=0,
                indexed_tracks=0,
                skipped_files=0,
                removed_tracks=0,
            )

        scanned_files = 0
        indexed_tracks = 0
        skipped_files = 0
        indexed_paths: set[str] = set()

        for file_path in self.settings.music_dir.rglob("*"):
            if not file_path.is_file():
                continue
            scanned_files += 1
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                skipped_files += 1
                continue

            artist, title = self._parse_artist_title(file_path)
            album = self._album_for_file(file_path)
            tag_artist, tag_album, tag_title, tag_track_no, duration = self._read_metadata(file_path)
            stat = file_path.stat()

            normalized_artist = self._normalize_text(tag_artist or artist)
            normalized_album = self._normalize_text(tag_album or album)
            normalized_title = self._normalize_text(tag_title or title)
            uri = self._stable_uri_for_file(file_path)

            self.store.upsert_track(
                path=str(file_path),
                uri=uri,
                title=normalized_title,
                artist=normalized_artist,
                album=normalized_album,
                track_no=tag_track_no,
                duration=duration,
                mtime=stat.st_mtime,
            )
            indexed_paths.add(str(file_path))
            indexed_tracks += 1

        removed_tracks = self.store.delete_tracks_not_in(indexed_paths)

        return ScanSummary(
            scanned_files=scanned_files,
            indexed_tracks=indexed_tracks,
            skipped_files=skipped_files,
            removed_tracks=removed_tracks,
        )

    def _parse_artist_title(self, file_path: Path) -> tuple[str, str]:
        stem = file_path.stem
        if " - " in stem:
            artist, title = stem.split(" - ", maxsplit=1)
            return artist.strip(), title.strip()
        return "Unknown Artist", stem.strip()

    def _album_for_file(self, file_path: Path) -> str:
        parent = file_path.parent
        if parent == self.settings.music_dir:
            return "Unknown Album"
        return parent.name

    def _stable_uri_for_file(self, file_path: Path) -> str:
        try:
            return file_path.relative_to(self.settings.music_dir).as_posix()
        except ValueError:
            return file_path.as_posix()

    def _read_metadata(self, file_path: Path) -> tuple[str, str, str, int, float]:
        artist = ""
        album = ""
        title = ""
        track_no = 0
        duration = 0.0
        try:
            audio = MutagenFile(file_path, easy=True)
        except Exception:
            return artist, album, title, track_no, duration
        if audio is None:
            return artist, album, title, track_no, duration

        tags = audio.tags or {}
        if "artist" in tags and tags["artist"]:
            artist = self._normalize_artist_values(tags["artist"])
        if "album" in tags and tags["album"]:
            album = str(tags["album"][0])
        if "title" in tags and tags["title"]:
            title = str(tags["title"][0])
        if "tracknumber" in tags and tags["tracknumber"]:
            track_no = self._parse_track_number(str(tags["tracknumber"][0]))
        if audio.info is not None and getattr(audio.info, "length", None) is not None:
            duration = float(audio.info.length)
        return artist, album, title, track_no, duration

    def _normalize_artist_values(self, values: object) -> str:
        if not isinstance(values, list):
            return self._normalize_text(str(values))
        cleaned = [self._normalize_text(str(item)) for item in values if str(item).strip()]
        if len(cleaned) == 1:
            # Keep common feature separators predictable for consistent search matches.
            return self._normalize_text(cleaned[0].replace(";", " / "))
        return " / ".join(cleaned)

    def _parse_track_number(self, value: str) -> int:
        match = re.match(r"\s*(\d+)", value)
        if match is None:
            return 0
        return int(match.group(1))

    def _normalize_text(self, value: str) -> str:
        normalized = " ".join(value.strip().split())
        return normalized or "Unknown"
