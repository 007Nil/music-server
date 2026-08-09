import gi

gi.require_version("Gst", "1.0")

from gi.repository import Gst


class GStreamer:

    def __init__(self) -> None:
        Gst.init(None)

    def create_playbin(self) -> Gst.Element:
        player = Gst.ElementFactory.make(
            "playbin",
            "music-player",
        )

        if player is None:
            raise RuntimeError(
                "Failed to create GStreamer playbin"
            )

        return player

    def set_uri(
        self,
        player: Gst.Element,
        path: str,
    ) -> None:
        uri = Gst.filename_to_uri(path)
        player.set_property("uri", uri)

    def play(self, player: Gst.Element) -> bool:
        result = player.set_state(Gst.State.PLAYING)

        return result != Gst.StateChangeReturn.FAILURE

    def pause(self, player: Gst.Element) -> bool:
        result = player.set_state(Gst.State.PAUSED)

        return result != Gst.StateChangeReturn.FAILURE

    def stop(self, player: Gst.Element) -> bool:
        result = player.set_state(Gst.State.NULL)

        return result != Gst.StateChangeReturn.FAILURE

    def seek(
        self,
        player: Gst.Element,
        position_ms: int,
    ) -> bool:
        return player.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH
            | Gst.SeekFlags.KEY_UNIT,
            position_ms * Gst.MSECOND,
        )

    def get_position(
        self,
        player: Gst.Element,
    ) -> int:
        success, position = player.query_position(
            Gst.Format.TIME
        )

        if not success:
            return 0

        return position // Gst.MSECOND

    def set_volume(
        self,
        player: Gst.Element,
        volume: int,
    ) -> bool:
        volume = max(0, min(100, volume))

        player.set_property(
            "volume",
            volume / 100.0,
        )

        return True