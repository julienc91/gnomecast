import gi

gi.require_version("Gtk", "3.0")

from gi.repository import GLib, Gtk


def show_error_dialog(window: Gtk.Window, title: str, message: str) -> None:
    def inner() -> None:
        dialog = Gtk.MessageDialog(
            transient_for=window,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text=title,
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    GLib.idle_add(inner)
