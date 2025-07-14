import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib


def show_error_dialog(window, title: str, message: str) -> None:
    def inner() -> None:
        dialog = Gtk.MessageDialog(
            window,
            0,
            Gtk.MessageType.ERROR,
            Gtk.ButtonsType.CLOSE,
            title,
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    GLib.idle_add(inner)
