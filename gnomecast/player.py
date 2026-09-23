import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import pychromecast
from pychromecast.error import ChromecastConnectionError

from .utils import start_thread

__all__ = [
    "ACTIVE_STATES",
    "CastPlayer",
    "ChromecastConnectionError",
    "cast_from_host",
    "discover_casts",
]

ACTIVE_STATES = ("BUFFERING", "PLAYING", "PAUSED")


def discover_casts() -> list[pychromecast.Chromecast]:
    chromecasts, _ = pychromecast.get_chromecasts()
    return chromecasts


def cast_from_host(host: str) -> pychromecast.Chromecast:
    """
    Connect to a Chromecast by IP address or hostname.

    Raises pychromecast.error.ChromecastConnectionError if unreachable.
    """
    return pychromecast.get_chromecast_from_host((host, 8009, uuid.uuid4(), None, host))


def _try_cast_command(command, *args) -> None:
    try:
        command(*args)
    except pychromecast.error.PyChromecastError as e:
        print("cast command failed (ignored):", e)


class CastPlayer:
    """
    Controls playback on the selected Chromecast and polls its status.

    Callbacks are invoked from the monitor thread, not the GUI thread:
    - on_state_changed(state): the player state changed
    - on_tick(): called every poll where the player state didn't change
    - on_position(seconds): estimated playback position while playing
    - on_finished(): playback went from PLAYING to IDLE
    """

    def __init__(
        self,
        on_state_changed: Callable[[str | None], None],
        on_tick: Callable[[], None],
        on_position: Callable[[float], None],
        on_finished: Callable[[], None],
    ):
        self.on_state_changed = on_state_changed
        self.on_tick = on_tick
        self.on_position = on_position
        self.on_finished = on_finished
        self.cast: pychromecast.Chromecast | None = None
        self.last_known_player_state: str | None = None
        self.last_known_current_time: float | None = None
        self.last_time_current_time: float | None = None
        self.last_known_volume_level: float | None = None
        self.seeking = False
        self.seek_confirmed_after: datetime | None = None

    def start(self) -> None:
        start_thread(self._monitor, daemon=True)

    @property
    def state(self) -> str | None:
        if not self.cast:
            return None
        return str(self.cast.media_controller.status.player_state)

    @property
    def is_active(self) -> bool:
        return self.state in ACTIVE_STATES

    @property
    def volume_level(self) -> float | None:
        if not self.cast:
            return None
        return float(self.cast.media_controller.status.volume_level)

    def select(self, cast: pychromecast.Chromecast | None) -> None:
        self.cast = cast
        if cast:
            self.last_known_volume_level = cast.media_controller.status.volume_level
        self.last_known_player_state = None

    def play(
        self,
        url: str,
        content_type: str,
        subtitles_url: str | None = None,
        current_time: float | None = None,
    ) -> None:
        """
        Load new media on the cast, replacing whatever app is running.
        """
        if not self.cast:
            return
        cast = self.cast
        cast.wait()
        _try_cast_command(cast.quit_app)
        mc = cast.media_controller
        mc.play_media(
            url,
            content_type,
            subtitles=subtitles_url,
            current_time=current_time,
            stream_type=pychromecast.STREAM_TYPE_BUFFERED,
        )
        print(cast.status)
        print(mc.status)

    def toggle_pause(self) -> None:
        if not self.cast:
            return
        mc = self.cast.media_controller
        if mc.status.player_state == "PLAYING":
            mc.pause()
        elif mc.status.player_state == "PAUSED":
            mc.play()

    def stop(self) -> None:
        if not self.cast:
            return
        _try_cast_command(self.cast.media_controller.stop)

    def wait(self) -> None:
        if self.cast:
            self.cast.wait()

    def begin_seek(self) -> None:
        """
        Suspend position updates, e.g. while the user drags the scrubber.
        """
        self.seeking = True

    def seek(self, seconds: float) -> None:
        if not self.cast:
            return
        self.seeking = True
        self.seek_confirmed_after = datetime.now(UTC)
        self.cast.media_controller.seek(seconds)

    def seek_delta(self, delta: float) -> float | None:
        """
        Seek relative to the estimated current position; returns the target.
        """
        if not self.cast or self.last_time_current_time is None:
            return None
        mc = self.cast.media_controller
        seconds = float(
            mc.status.current_time + time.time() - self.last_time_current_time + delta
        )
        self.last_time_current_time = time.time()
        mc.status.current_time = seconds
        self.seek(seconds)
        return seconds

    def set_volume(self, volume: float) -> None:
        if not self.cast:
            return
        if self.last_known_volume_level != volume:
            self.last_known_volume_level = volume
            self.cast.set_volume(volume)
            print("setting volume", volume)

    def set_playback_rate(self, rate: float) -> None:
        if not self.cast:
            return
        mc = self.cast.media_controller
        if mc.status is None or mc.status.media_session_id is None:  # ty: ignore[redundant-condition-strict]
            return
        mc.send_message(
            {
                "type": "SET_PLAYBACK_RATE",
                "mediaSessionId": mc.status.media_session_id,
                "playbackRate": rate,
            },
            inc_session_id=True,
        )

    def _monitor(self) -> None:
        while True:
            time.sleep(1)
            if not self.cast:
                continue
            mc = self.cast.media_controller
            if (
                self.seeking
                and self.seek_confirmed_after is not None
                and mc.status.last_updated is not None
                and mc.status.last_updated > self.seek_confirmed_after
            ):
                # Confirms via last_updated instead of a BUFFERING->PLAYING
                # transition, which short seeks often skip entirely.
                self.seeking = False
            seeking = self.seeking
            state = mc.status.player_state
            if state != self.last_known_player_state:
                if state == "IDLE" and self.last_known_player_state == "PLAYING":
                    self.on_finished()
                self.last_known_player_state = state
                self.on_state_changed(state)
            else:
                self.on_tick()
            if self.last_known_current_time != mc.status.current_time:
                self.last_known_current_time = mc.status.current_time
                self.last_time_current_time = time.time()
            if (
                not seeking
                and state == "PLAYING"
                and self.last_time_current_time is not None
            ):
                self.on_position(
                    mc.status.current_time + time.time() - self.last_time_current_time
                )
