from functools import cached_property

try:
    import dbus
except ImportError:
    dbus = None
    print("DBus is not available. Screen saver inhibition will not work.")


class ScreenSaverInhibitor:
    def __init__(self) -> None:
        self._inhibit_cookie = None

    @cached_property
    def screen_saver_interface(self) -> "dbus.Interface | None":
        if dbus is None:
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
        print("No screen saver interface found. Screen saver inhibition will not work.")
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
