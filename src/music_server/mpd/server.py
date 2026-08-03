"""Minimal MPD protocol server."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex
import socketserver
import threading

from music_server.core import CoreService
from music_server.database import TrackRecord


class MpdCommandError(Exception):
    """Error raised for invalid MPD commands."""

    def __init__(self, message: str, *, code: int = 5) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class MpdResponse:
    """A protocol response."""

    lines: list[str]
    close_connection: bool = False


class MpdServer:
    """Handle a small, useful subset of the MPD protocol."""

    banner = "OK MPD 0.23.5"

    def __init__(self, service: CoreService) -> None:
        self.service = service
        self._events = threading.Condition()
        self._event_version = 0
        self._changed_subsystems: set[str] = set()
        self.service.playback.subscribe(self._on_playback_event)

    def _on_playback_event(self, subsystems: set[str]) -> None:
        with self._events:
            self._event_version += 1
            self._changed_subsystems.update(subsystems)
            self._events.notify_all()

    def _wait_for_idle_events(
        self,
        *,
        last_version: int,
        subsystems: set[str],
    ) -> tuple[int, list[str]]:
        with self._events:
            while self._event_version <= last_version:
                self._events.wait()
            changed = self._changed_subsystems.intersection(subsystems) if subsystems else self._changed_subsystems
            if not changed:
                changed = {"player"}
            return self._event_version, sorted(changed)

    def serve_forever(self, *, host: str = "127.0.0.1", port: int = 6600) -> None:
        """Run a threaded MPD TCP server."""

        self.service.bootstrap()

        outer = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self) -> None:  # noqa: D401
                self.wfile.write(f"{outer.banner}\n".encode("utf-8"))
                self.wfile.flush()

                command_list_mode: str | None = None
                command_list_buffer: list[str] = []
                session_event_version = outer._event_version

                while True:
                    raw = self.rfile.readline()
                    if not raw:
                        break
                    line = raw.decode("utf-8", errors="replace").strip()

                    if command_list_mode is not None:
                        if line.lower() == "command_list_end":
                            response = outer._execute_command_list(
                                command_list_buffer,
                                send_list_ok=(command_list_mode == "ok"),
                            )
                            command_list_mode = None
                            command_list_buffer = []
                            for out_line in response.lines:
                                self.wfile.write(f"{out_line}\n".encode("utf-8"))
                            self.wfile.flush()
                            if response.close_connection:
                                break
                            continue
                        command_list_buffer.append(line)
                        continue

                    lower = line.lower()
                    if lower == "command_list_ok_begin":
                        command_list_mode = "ok"
                        command_list_buffer = []
                        continue
                    if lower == "command_list_begin":
                        command_list_mode = "plain"
                        command_list_buffer = []
                        continue
                    if lower.startswith("idle"):
                        parts = shlex.split(line)
                        requested = set(parts[1:] or ["player", "playlist", "database", "output"])
                        session_event_version, changed = outer._wait_for_idle_events(
                            last_version=session_event_version,
                            subsystems=requested,
                        )
                        for subsystem in changed:
                            self.wfile.write(f"changed: {subsystem}\n".encode("utf-8"))
                        self.wfile.write(b"OK\n")
                        self.wfile.flush()
                        continue

                    response = outer.execute_line(line)
                    for out_line in response.lines:
                        self.wfile.write(f"{out_line}\n".encode("utf-8"))
                    self.wfile.flush()
                    if response.close_connection:
                        break

        with socketserver.ThreadingTCPServer((host, port), Handler) as server:
            server.serve_forever()

    def execute_line(self, line: str) -> MpdResponse:
        """Parse and execute one MPD command line."""

        try:
            return self._execute(line)
        except MpdCommandError as exc:
            ack = f"ACK [{exc.code}@0] {{{line.split(' ', maxsplit=1)[0] or 'command'}}} {exc}"
            return MpdResponse(lines=[ack])

    def _execute(self, line: str) -> MpdResponse:
        self.service.bootstrap()

        if not line:
            return MpdResponse(lines=["OK"])

        parts = shlex.split(line)
        if not parts:
            return MpdResponse(lines=["OK"])

        command = parts[0].lower()
        args = parts[1:]

        if command == "ping":
            return MpdResponse(lines=["OK"])

        if command == "idle":
            subsystem = args[0] if args else "player"
            return MpdResponse(lines=[f"changed: {subsystem}", "OK"])

        if command == "noidle":
            return MpdResponse(lines=["OK"])

        if command in {"command_list_ok_begin", "command_list_begin", "command_list_end"}:
            raise MpdCommandError("Command list mode requires a TCP session", code=5)

        if command in {"close", "kill"}:
            return MpdResponse(lines=["OK"], close_connection=True)

        if command == "status":
            return MpdResponse(lines=[*self._status_lines(), "OK"])

        if command == "stats":
            return MpdResponse(lines=[*self._stats_lines(), "OK"])

        if command == "listall":
            return MpdResponse(lines=[*self._listall_lines(), "OK"])

        if command == "playlistinfo":
            return MpdResponse(lines=[*self._playlistinfo_lines(), "OK"])

        if command == "list":
            if len(args) != 1:
                raise MpdCommandError("list requires one tag")
            return MpdResponse(lines=[*self._list_lines(args[0]), "OK"])

        if command == "listallinfo":
            return MpdResponse(lines=[*self._listallinfo_lines(), "OK"])

        if command == "playlistfind":
            if len(args) < 2:
                raise MpdCommandError("playlistfind requires field and query")
            field = args[0].lower()
            query = " ".join(args[1:])
            return MpdResponse(lines=[*self._playlistfind_lines(field=field, query=query), "OK"])

        if command == "lsinfo":
            if len(args) > 1:
                raise MpdCommandError("lsinfo accepts at most one path")
            return MpdResponse(lines=[*self._lsinfo_lines(args[0] if args else None), "OK"])

        if command == "playlistid":
            if not args:
                return MpdResponse(lines=[*self._playlistinfo_lines(), "OK"])
            if len(args) != 1:
                raise MpdCommandError("playlistid accepts at most one id")
            queue = self.service.playback.list_queue()
            item = next((entry for entry in queue if entry.queue_id == int(args[0])), None)
            if item is None:
                return MpdResponse(lines=["OK"])
            position = next(i for i, entry in enumerate(queue) if entry.queue_id == item.queue_id)
            return MpdResponse(
                lines=[
                    *self._track_lines(item.track),
                    f"Pos: {position}",
                    f"Id: {item.queue_id}",
                    "OK",
                ]
            )

        if command in {"find", "search"}:
            if len(args) < 2:
                raise MpdCommandError("find/search requires field and query")
            field = args[0].lower()
            query = " ".join(args[1:])
            return MpdResponse(lines=[*self._search_lines(field=field, query=query), "OK"])

        if command == "add":
            if len(args) != 1:
                raise MpdCommandError("add requires a track path")
            self._add_by_path(args[0])
            return MpdResponse(lines=["OK"])

        if command == "addid":
            if len(args) != 1:
                raise MpdCommandError("addid requires a track path")
            queue_id = self._add_by_path(args[0])
            return MpdResponse(lines=[f"Id: {queue_id}", "OK"])

        if command == "clear":
            self.service.playback.clear_queue()
            return MpdResponse(lines=["OK"])

        if command == "deleteid":
            if len(args) != 1:
                raise MpdCommandError("deleteid requires a queue id")
            deleted = self.service.playback.delete_queue_id(int(args[0]))
            if not deleted:
                raise MpdCommandError("No such song")
            return MpdResponse(lines=["OK"])

        if command == "play":
            if args:
                track = self.service.play_position(int(args[0]))
            else:
                track = self.service.play_next()
            if track is None:
                raise MpdCommandError("No such song")
            self.service.audio.play_file(Path(track.path))
            return MpdResponse(lines=["OK"])

        if command == "playid":
            if len(args) != 1:
                raise MpdCommandError("playid requires a queue id")
            track = self.service.playback.play_queue_id(int(args[0]))
            if track is None:
                raise MpdCommandError("No such song")
            self.service.audio.play_file(Path(track.path))
            return MpdResponse(lines=["OK"])

        if command == "stop":
            self.service.stop_audio()
            return MpdResponse(lines=["OK"])

        if command == "seek":
            if len(args) != 1:
                raise MpdCommandError("seek requires a position")
            self.service.seek_audio(float(args[0]))
            return MpdResponse(lines=["OK"])

        if command == "volume":
            if len(args) != 1:
                raise MpdCommandError("volume requires a value")
            self.service.set_audio_volume(int(args[0]))
            return MpdResponse(lines=["OK"])

        if command == "pause":
            if len(args) > 1:
                raise MpdCommandError("pause accepts at most one argument")
            paused = True
            if args:
                paused = args[0] != "0"
            if not self.service.pause_audio(paused):
                raise MpdCommandError("No current song")
            return MpdResponse(lines=["OK"])

        if command == "next":
            track = self.service.play_next()
            if track is None:
                raise MpdCommandError("No more songs in queue")
            return MpdResponse(lines=["OK"])

        if command == "previous":
            track = self.service.playback.current_track()
            if track is None:
                raise MpdCommandError("No current song")
            return MpdResponse(lines=["OK"])

        if command == "clearerror":
            return MpdResponse(lines=["OK"])

        if command == "commands":
            return MpdResponse(lines=[*self._commands_lines(), "OK"])

        if command == "notcommands":
            return MpdResponse(lines=["OK"])

        if command == "outputs":
            return MpdResponse(
                lines=[
                    "outputid: 0",
                    "outputname: Local Audio Output",
                    "outputenabled: 1",
                    "OK",
                ]
            )

        if command == "currentsong":
            track = self.service.playback.current_track()
            if track is None:
                return MpdResponse(lines=["OK"])
            return MpdResponse(lines=[*self._track_lines(track), f"Id: {track.id}", "OK"])

        raise MpdCommandError("Unknown command")

    def _status_lines(self) -> list[str]:
        playback = self.service.playback
        current = playback.current_track()
        queue_len = self.service.playback.count_queue()
        state = playback.state()
        elapsed = playback.elapsed_seconds()
        lines = [
            "volume: -1",
            "repeat: 0",
            "random: 0",
            "single: 0",
            "consume: 0",
            f"playlist: {playback.playlist_version()}",
            f"playlistlength: {queue_len}",
            f"state: {state}",
            "audio: 0:0:0",
            "bitrate: 0",
        ]
        if current is not None:
            duration = max(current.duration, 0.0)
            lines.extend(
                [
                    "song: 0",
                    f"songid: {current.id}",
                    f"elapsed: {elapsed:.3f}",
                    f"duration: {duration:.3f}",
                    f"time: {int(elapsed)}:{int(duration)}",
                ]
            )
        return lines

    def _stats_lines(self) -> list[str]:
        store = self.service.store
        return [
            f"artists: {store.count_artists()}",
            f"albums: {store.count_albums()}",
            f"songs: {store.count_tracks()}",
            "uptime: 0",
            "playtime: 0",
            "db_playtime: 0",
            "db_update: 0",
        ]

    def _listall_lines(self) -> list[str]:
        tracks = self.service.library.list_tracks(limit=10000)
        return [f"file: {self._display_path(track)}" for track in tracks]

    def _playlistinfo_lines(self) -> list[str]:
        queue = self.service.playback.list_queue()
        lines: list[str] = []
        for position, item in enumerate(queue):
            lines.extend(self._track_lines(item.track))
            lines.append(f"Pos: {position}")
            lines.append(f"Id: {item.queue_id}")
        return lines

    def _list_lines(self, field: str) -> list[str]:
        normalized = field.lower()
        if normalized not in {"artist", "album", "title", "file", "track"}:
            raise MpdCommandError("Unsupported list field")

        tracks = self.service.library.list_tracks(limit=10000)
        values: set[str] = set()
        for track in tracks:
            if normalized == "artist":
                values.add(track.artist)
            elif normalized == "album":
                values.add(track.album)
            elif normalized == "title":
                values.add(track.title)
            elif normalized == "file":
                values.add(self._display_path(track))
            else:
                values.add(str(track.track_no))

        label = normalized.capitalize()
        return [f"{label}: {value}" for value in sorted(values)]

    def _listallinfo_lines(self) -> list[str]:
        tracks = self.service.library.list_tracks(limit=10000)
        lines: list[str] = []
        for track in tracks:
            lines.extend(self._track_lines(track))
        return lines

    def _playlistfind_lines(self, *, field: str, query: str) -> list[str]:
        if field not in {"any", "title", "artist", "album", "file"}:
            raise MpdCommandError("Unsupported playlistfind field")

        queue = self.service.playback.list_queue()
        if field == "any":
            filtered = [item.track for item in queue]
        elif field == "file":
            filtered = [item.track for item in queue if query.lower() in self._display_path(item.track).lower()]
        elif field == "title":
            filtered = [item.track for item in queue if query.lower() in item.track.title.lower()]
        elif field == "artist":
            filtered = [item.track for item in queue if query.lower() in item.track.artist.lower()]
        else:
            filtered = [item.track for item in queue if query.lower() in item.track.album.lower()]

        lines: list[str] = []
        for track in filtered:
            lines.extend(self._track_lines(track))
        return lines

    def _lsinfo_lines(self, path: str | None) -> list[str]:
        if path is None:
            return []
        resolved = self._resolve_track_path(path)
        tracks = self.service.library.list_tracks(limit=10000)
        track = next((item for item in tracks if item.path == resolved), None)
        if track is None:
            return []
        return self._track_lines(track)

    def _search_lines(self, *, field: str, query: str) -> list[str]:
        matched = self.service.library.search_tracks(query, limit=10000)
        if field not in {"any", "title", "artist", "album", "file"}:
            raise MpdCommandError("Unsupported search field")

        if field == "any":
            filtered = matched
        elif field == "file":
            filtered = [track for track in matched if query.lower() in track.path.lower()]
        elif field == "title":
            filtered = [track for track in matched if query.lower() in track.title.lower()]
        elif field == "artist":
            filtered = [track for track in matched if query.lower() in track.artist.lower()]
        else:
            filtered = [track for track in matched if query.lower() in track.album.lower()]

        lines: list[str] = []
        for track in filtered:
            lines.extend(self._track_lines(track))
        return lines

    def _add_by_path(self, path: str) -> int:
        resolved = self._resolve_track_path(path)
        tracks = self.service.library.list_tracks(limit=10000)
        track = next((item for item in tracks if item.path == resolved), None)
        if track is None:
            raise MpdCommandError("No such song")
        queue_id = self.service.playback.enqueue_and_get_id(track.id)
        if queue_id is None:
            raise MpdCommandError("Could not enqueue track")
        return queue_id

    def _resolve_track_path(self, path: str) -> str:
        if path.startswith("/"):
            return path
        return str(self.service.settings.music_dir / path)

    def _display_path(self, track: TrackRecord) -> str:
        if track.uri:
            return track.uri
        music_root = self.service.settings.music_dir
        track_path = Path(track.path)
        try:
            return str(track_path.relative_to(music_root))
        except ValueError:
            return str(track_path)

    def _execute_command_list(self, commands: list[str], *, send_list_ok: bool) -> MpdResponse:
        output: list[str] = []
        should_close = False
        for command_line in commands:
            response = self.execute_line(command_line)
            if response.lines and response.lines[0].startswith("ACK"):
                return MpdResponse(lines=[*output, response.lines[0]], close_connection=response.close_connection)
            lines_without_ok = [line for line in response.lines if line != "OK"]
            output.extend(lines_without_ok)
            if send_list_ok:
                output.append("list_OK")
            if response.close_connection:
                should_close = True
                break
        output.append("OK")
        return MpdResponse(lines=output, close_connection=should_close)

    def _commands_lines(self) -> list[str]:
        return [
            "command: ping",
            "command: idle",
            "command: noidle",
            "command: status",
            "command: stats",
            "command: listall",
            "command: find",
            "command: search",
            "command: playlistinfo",
            "command: list",
            "command: listallinfo",
            "command: playlistfind",
            "command: lsinfo",
            "command: playlistid",
            "command: add",
            "command: addid",
            "command: clear",
            "command: deleteid",
            "command: play",
            "command: playid",
            "command: stop",
            "command: pause",
            "command: next",
            "command: currentsong",
            "command: commands",
            "command: notcommands",
            "command: outputs",
            "command: command_list_ok_begin",
            "command: command_list_begin",
            "command: command_list_end",
            "command: close",
            "command: kill",
        ]

    def _track_lines(self, track: TrackRecord) -> list[str]:
        return [
            f"file: {self._display_path(track)}",
            f"Artist: {track.artist}",
            f"Album: {track.album}",
            f"Title: {track.title}",
            f"Track: {track.track_no}",
            f"Time: {int(track.duration)}",
        ]
