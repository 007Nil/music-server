"""Application entry point for music-server."""

from __future__ import annotations

import argparse
import logging
import sys

from music_server.config import load_settings
from music_server.core import CoreService
from music_server.mpd import MpdServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(prog="music-server")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("start")
    sub.add_parser("init-db")
    sub.add_parser("status")
    sub.add_parser("scan")

    tracks = sub.add_parser("tracks")
    tracks.add_argument("--limit", type=int, default=50)
    tracks.add_argument("--search", type=str, default="")

    queue_add = sub.add_parser("queue-add")
    queue_add.add_argument("track_id", type=int)

    sub.add_parser("queue")
    sub.add_parser("queue-clear")
    sub.add_parser("play-next")
    play_cmd = sub.add_parser("play")
    play_cmd.add_argument("track_id", type=int)
    pause_cmd = sub.add_parser("pause")
    pause_cmd.add_argument("value", type=int, nargs="?", default=1)

    seek_cmd = sub.add_parser("seek")
    seek_cmd.add_argument("position", type=float)
    volume_cmd = sub.add_parser("volume")
    volume_cmd.add_argument("value", type=int)
    mute_cmd = sub.add_parser("mute")
    mute_cmd.add_argument("value", type=int, nargs="?", default=1)
    sub.add_parser("stop")

    mpd_serve = sub.add_parser("mpd-serve")
    mpd_serve.add_argument("--host", type=str, default="127.0.0.1")
    mpd_serve.add_argument("--port", type=int, default=6600)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the application CLI."""

    parser = build_parser()
    args = parser.parse_args([] if argv is None else argv)

    settings = load_settings()
    service = CoreService(settings)

    command = args.command or "start"
    if command == "start":
        service.start()
        return 0

    if command == "init-db":
        service.bootstrap()
        print(f"database initialized at {settings.db_path}")
        return 0

    if command == "status":
        tracks, queue_size = service.status()
        print(f"tracks={tracks} queue={queue_size}")
        return 0

    if command == "scan":
        service.bootstrap()
        summary = service.scanner.scan()
        print(
            "scan complete: "
            f"scanned={summary.scanned_files} "
            f"indexed={summary.indexed_tracks} "
            f"skipped={summary.skipped_files} "
            f"removed={summary.removed_tracks}"
        )
        return 0

    if command == "tracks":
        service.bootstrap()
        if args.search:
            tracks = service.library.search_tracks(args.search, limit=args.limit)
        else:
            tracks = service.library.list_tracks(limit=args.limit)
        if not tracks:
            print("no tracks indexed")
            return 0
        for track in tracks:
            print(
                f"{track.id}: {track.artist} - {track.title} "
                f"[{track.album}] {track.path}"
            )
        return 0

    if command == "queue-add":
        service.bootstrap()
        added = service.playback.enqueue(args.track_id)
        if not added:
            print(f"track not found: {args.track_id}")
            return 1
        print(f"queued track {args.track_id}")
        return 0

    if command == "queue":
        service.bootstrap()
        queue_items = service.playback.list_queue()
        if not queue_items:
            print("queue is empty")
            return 0
        for item in queue_items:
            track = item.track
            print(f"{item.queue_id}: {track.artist} - {track.title} (id={track.id})")
        return 0

    if command == "queue-clear":
        service.bootstrap()
        service.playback.clear_queue()
        print("queue cleared")
        return 0

    if command == "play-next":
        track = service.play_next()
        if track is None:
            print("queue is empty")
            return 0
        print(f"playing: {track.artist} - {track.title} [{track.album}]")
        return 0

    if command == "play":
        track = service.play_track(args.track_id)
        if track is None:
            print(f"track not found: {args.track_id}")
            return 1
        print(f"playing: {track.artist} - {track.title} [{track.album}]")
        return 0

    if command == "stop":
        service.stop_audio()
        print("stopped")
        return 0

    if command == "seek":
        if not service.seek_audio(args.position):
            print("no current track")
            return 1
        print(f"seeked to {args.position}s")
        return 0

    if command == "volume":
        if not service.set_audio_volume(args.value):
            print("volume change failed")
            return 1
        print(f"volume set to {args.value}")
        return 0

    if command == "mute":
        muted = args.value != 0
        if not service.set_audio_mute(muted):
            print("mute change failed")
            return 1
        print("muted" if muted else "unmuted")
        return 0

    if command == "pause":
        paused = args.value != 0
        if not service.pause_audio(paused):
            print("no current track")
            return 1
        print("paused" if paused else "resumed")
        return 0

    if command == "mpd-serve":
        server = MpdServer(service)
        print(f"mpd server listening on {args.host}:{args.port}")
        server.serve_forever(host=args.host, port=args.port)
        return 0

    parser.error(f"Unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
