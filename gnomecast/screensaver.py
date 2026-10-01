import logging
from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import dbus as _dbus

try:
    import dbus
except ImportError:
    dbus = None

logger = logging.getLogger(__name__)


class ScreenSaverInhibitor:
    def __init__(self) -> None:
        self._inhibit_cookie = None

    @cached_property
    def screen_saver_interface(self) -> "_dbus.Interface | None":
        if dbus is None:
            logger.warning("DBus is not available, screen saver won't be inhibited")
            return None

        bus = dbus.SessionBus()
        for path, name in [
            ("org.freedesktop.ScreenSaver", "/ScreenSaver"),
            ("org.mate.ScreenSaver", "/ScreenSaver"),
        ]:
            try:
                saver = bus.get_object(path, name)
                return dbus.Interface(saver, dbus_interface=path)
            except dbus.exceptions.DBusException:
                pass
        logger.warning(
            "No screen saver interface found, screen saver won't be inhibited"
        )
        return None

    def start(self) -> None:
        interface = self.screen_saver_interface
        if interface is None:
            return

        self._inhibit_cookie = interface.Inhibit("Gnomecast", "Player is playing...")

    def stop(self) -> None:
        interface = self.screen_saver_interface
        if interface is None or self._inhibit_cookie is None:
            return

        interface.UnInhibit(self._inhibit_cookie)
        self._inhibit_cookie = None
