"""HTTP API server for music-server."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import parse_qs, urlparse

from music_server.core import CoreService
from music_server.database import QueueRecord, TrackRecord


class HttpApiError(Exception):
    """Error raised for request validation or routing failures."""

    def __init__(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        super().__init__(message)
        self.status = int(status)


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """JSON response returned by API handlers."""

    status: int
    payload: dict | list


class HttpApi:
    """Route HTTP requests to core services."""

    def __init__(self, service: CoreService) -> None:
        self.service = service

    def handle(self, method: str, path: str, *, query: str = "", body: dict | None = None) -> HttpResponse:
        """Dispatch one HTTP request and return a JSON response."""

        self.service.bootstrap()
        route = path.rstrip("/") or "/"
        query_params = parse_qs(query, keep_blank_values=False)
        payload = body or {}

        if method == "GET" and route == "/health":
            return HttpResponse(status=HTTPStatus.OK, payload={"status": "ok"})

        if method == "GET" and route == "/api/status":
            tracks, queue_size = self.service.status()
            return HttpResponse(
                status=HTTPStatus.OK,
                payload={
                    "tracks": tracks,
                    "queue": queue_size,
                    "playback": self._now_playing_payload(),
                },
            )

        if method == "POST" and route == "/api/library/scan":
            summary = self.service.scanner.scan()
            return HttpResponse(
                status=HTTPStatus.OK,
                payload={
                    "scanned_files": summary.scanned_files,
                    "indexed_tracks": summary.indexed_tracks,
                    "skipped_files": summary.skipped_files,
                    "removed_tracks": summary.removed_tracks,
                },
            )

        if method == "GET" and route == "/api/tracks":
            limit = self._query_int(query_params, "limit", default=50, minimum=1, maximum=10000)
            search = self._query_str(query_params, "search", default="")
            if search:
                tracks = self.service.library.search_tracks(search, limit=limit)
            else:
                tracks = self.service.library.list_tracks(limit=limit)
            return HttpResponse(status=HTTPStatus.OK, payload={"items": [self._track_payload(t) for t in tracks]})

        if method == "GET" and route.startswith("/api/tracks/"):
            track_id = self._parse_trailing_int(route, prefix="/api/tracks/")
            track = self.service.library.get_track(track_id)
            if track is None:
                raise HttpApiError("track not found", status=HTTPStatus.NOT_FOUND)
            return HttpResponse(status=HTTPStatus.OK, payload=self._track_payload(track))

        if method == "GET" and route == "/api/queue":
            queue = self.service.playback.list_queue()
            return HttpResponse(status=HTTPStatus.OK, payload={"items": [self._queue_payload(i) for i in queue]})

        if method == "POST" and route == "/api/queue":
            track_id = self._payload_int(payload, "track_id", minimum=1)
            added = self.service.playback.enqueue(track_id)
            if not added:
                raise HttpApiError("track not found", status=HTTPStatus.NOT_FOUND)
            return HttpResponse(status=HTTPStatus.CREATED, payload={"queued": True, "track_id": track_id})

        if method == "DELETE" and route == "/api/queue":
            self.service.playback.clear_queue()
            return HttpResponse(status=HTTPStatus.OK, payload={"cleared": True})

        if method == "DELETE" and route.startswith("/api/queue/"):
            queue_id = self._parse_trailing_int(route, prefix="/api/queue/")
            deleted = self.service.playback.delete_queue_id(queue_id)
            if not deleted:
                raise HttpApiError("queue item not found", status=HTTPStatus.NOT_FOUND)
            return HttpResponse(status=HTTPStatus.OK, payload={"deleted": True, "queue_id": queue_id})

        if method == "GET" and route == "/api/now-playing":
            return HttpResponse(status=HTTPStatus.OK, payload=self._now_playing_payload())

        if method == "POST" and route == "/api/playback/play-next":
            track = self.service.play_next()
            if track is None:
                raise HttpApiError("queue is empty", status=HTTPStatus.CONFLICT)
            return HttpResponse(status=HTTPStatus.OK, payload={"track": self._track_payload(track)})

        if method == "POST" and route == "/api/playback/play":
            track_id = self._payload_int(payload, "track_id", minimum=1)
            track = self.service.play_track(track_id)
            if track is None:
                raise HttpApiError("track not found", status=HTTPStatus.NOT_FOUND)
            return HttpResponse(status=HTTPStatus.OK, payload={"track": self._track_payload(track)})

        if method == "POST" and route == "/api/playback/play-position":
            position = self._payload_int(payload, "position", minimum=0)
            track = self.service.play_position(position)
            if track is None:
                raise HttpApiError("position not found in queue", status=HTTPStatus.NOT_FOUND)
            return HttpResponse(status=HTTPStatus.OK, payload={"track": self._track_payload(track)})

        if method == "POST" and route == "/api/playback/play-queue-id":
            queue_id = self._payload_int(payload, "queue_id", minimum=1)
            track = self.service.play_queue_id(queue_id)
            if track is None:
                raise HttpApiError("queue item not found", status=HTTPStatus.NOT_FOUND)
            return HttpResponse(status=HTTPStatus.OK, payload={"track": self._track_payload(track)})

        if method == "POST" and route == "/api/playback/random-queue":
            count = self._payload_int(payload, "count", minimum=1, maximum=100, default=10)
            added = self.service.random_queue(count)
            return HttpResponse(status=HTTPStatus.OK, payload={"random_queue_added": added, "count": count})

        if method == "POST" and route == "/api/playback/pause":
            paused = self._payload_bool(payload, "paused", default=True)
            if not self.service.pause_audio(paused):
                raise HttpApiError("no current track", status=HTTPStatus.CONFLICT)
            return HttpResponse(status=HTTPStatus.OK, payload={"paused": paused})

        if method == "POST" and route == "/api/playback/resume":
            if not self.service.pause_audio(False):
                raise HttpApiError("no current track", status=HTTPStatus.CONFLICT)
            return HttpResponse(status=HTTPStatus.OK, payload={"paused": False})

        if method == "POST" and route == "/api/playback/stop":
            self.service.stop_audio()
            return HttpResponse(status=HTTPStatus.OK, payload={"stopped": True})

        if method == "POST" and route == "/api/playback/seek":
            position = self._payload_float(payload, "position", minimum=0.0)
            if not self.service.seek_audio(position):
                raise HttpApiError("no current track", status=HTTPStatus.CONFLICT)
            return HttpResponse(status=HTTPStatus.OK, payload={"position": position})

        if method == "POST" and route == "/api/playback/volume":
            value = self._payload_int(payload, "value", minimum=0, maximum=100)
            if not self.service.set_audio_volume(value):
                raise HttpApiError("volume change failed", status=HTTPStatus.CONFLICT)
            return HttpResponse(status=HTTPStatus.OK, payload={"volume": value})

        if method == "POST" and route == "/api/playback/mute":
            muted = self._payload_bool(payload, "muted", default=True)
            if not self.service.set_audio_mute(muted):
                raise HttpApiError("mute change failed", status=HTTPStatus.CONFLICT)
            return HttpResponse(status=HTTPStatus.OK, payload={"muted": muted})

        raise HttpApiError("route not found", status=HTTPStatus.NOT_FOUND)

    def _now_playing_payload(self) -> dict:
        current = self.service.playback.current_track()
        return {
            "state": self.service.playback.state(),
            "elapsed": round(self.service.playback.elapsed_seconds(), 3),
            "track": self._track_payload(current) if current is not None else None,
        }

    def _track_payload(self, track: TrackRecord) -> dict:
        return {
            "id": track.id,
            "path": track.path,
            "uri": track.uri,
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "track_no": track.track_no,
            "duration": track.duration,
            "mtime": track.mtime,
        }

    def _queue_payload(self, item: QueueRecord) -> dict:
        return {
            "queue_id": item.queue_id,
            "track": self._track_payload(item.track),
        }

    def _query_str(self, query_params: dict[str, list[str]], key: str, *, default: str) -> str:
        values = query_params.get(key)
        if not values:
            return default
        return values[0]

    def _query_int(
        self,
        query_params: dict[str, list[str]],
        key: str,
        *,
        default: int,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int:
        values = query_params.get(key)
        if not values:
            return default
        try:
            value = int(values[0])
        except ValueError as exc:
            raise HttpApiError(f"{key} must be an integer") from exc
        return self._clamp_int(value, key=key, minimum=minimum, maximum=maximum)

    def _payload_int(
        self,
        payload: dict,
        key: str,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int:
        if key not in payload:
            raise HttpApiError(f"missing field: {key}")
        value = payload[key]
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise HttpApiError(f"{key} must be an integer") from exc
        return self._clamp_int(parsed, key=key, minimum=minimum, maximum=maximum)

    def _payload_float(self, payload: dict, key: str, *, minimum: float | None = None) -> float:
        if key not in payload:
            raise HttpApiError(f"missing field: {key}")
        value = payload[key]
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise HttpApiError(f"{key} must be a number") from exc
        if minimum is not None and parsed < minimum:
            raise HttpApiError(f"{key} must be >= {minimum}")
        return parsed

    def _payload_bool(self, payload: dict, key: str, *, default: bool) -> bool:
        if key not in payload:
            return default
        value = payload[key]
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
        raise HttpApiError(f"{key} must be a boolean")

    def _clamp_int(self, value: int, *, key: str, minimum: int | None, maximum: int | None) -> int:
        if minimum is not None and value < minimum:
            raise HttpApiError(f"{key} must be >= {minimum}")
        if maximum is not None and value > maximum:
            raise HttpApiError(f"{key} must be <= {maximum}")
        return value

    def _parse_trailing_int(self, route: str, *, prefix: str) -> int:
        raw = route.removeprefix(prefix)
        if not raw or "/" in raw:
            raise HttpApiError("route not found", status=HTTPStatus.NOT_FOUND)
        try:
            return int(raw)
        except ValueError as exc:
            raise HttpApiError("id must be an integer") from exc


class HttpServer:
    """Serve JSON APIs for music-server over HTTP."""

    def __init__(self, service: CoreService) -> None:
        self._api = HttpApi(service)

    def serve_forever(self, *, host: str = "127.0.0.1", port: int = 8080) -> None:
        """Start serving HTTP requests until interrupted."""

        api = self._api

        class Handler(BaseHTTPRequestHandler):
            server_version = "music-server-http/0.1"

            def do_GET(self) -> None:  # noqa: N802
                self._handle("GET")

            def do_POST(self) -> None:  # noqa: N802
                self._handle("POST")

            def do_DELETE(self) -> None:  # noqa: N802
                self._handle("DELETE")

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

            def _handle(self, method: str) -> None:
                parsed = urlparse(self.path)
                body: dict | None = None
                if method == "POST":
                    body = self._read_json_body()
                    if body is None:
                        return
                try:
                    response = api.handle(method, parsed.path, query=parsed.query, body=body)
                    self._send_json(response.status, response.payload)
                except HttpApiError as exc:
                    self._send_json(exc.status, {"error": str(exc)})
                except Exception:
                    self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal server error"})

            def _read_json_body(self) -> dict | None:
                length_header = self.headers.get("Content-Length", "0")
                try:
                    length = int(length_header)
                except ValueError:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid content-length"})
                    return None
                raw = self.rfile.read(length) if length > 0 else b"{}"
                if not raw:
                    return {}
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid json body"})
                    return None
                if not isinstance(parsed, dict):
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "json body must be an object"})
                    return None
                return parsed

            def _send_json(self, status: int, payload: dict | list) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(int(status))
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        with ThreadingHTTPServer((host, port), Handler) as server:
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                return