import logging
import os
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk


def wire_dialog_default(dialog, response_id, entry=None):
    """
    Make Enter activate a dialog response reliably.

    set_default_response alone is not enough when focus is in a Gtk.Entry:
    the target button must be can-default and the dialog default widget, and
    the entry must set_activates_default(True). Also connect Entry "activate"
    as a fallback so Enter always emits the intended response.
    """
    dialog.set_default_response(response_id)
    button = dialog.get_widget_for_response(response_id)
    if button is not None:
        button.set_can_default(True)
        dialog.set_default(button)

    if entry is not None:
        entry.set_activates_default(True)

        def _on_entry_activate(_widget):
            dialog.response(response_id)

        entry.connect("activate", _on_entry_activate)

    return button


def show_error_dialog(message, parent=None):
    logging.error(f"Error: {message}")

    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    if parent and has_display:
        try:
            if GLib.main_depth() <= 0:
                print(f"ERROR: {message}", file=sys.stderr)
                return

            def _show():
                dialog = Gtk.MessageDialog(
                    transient_for=parent,
                    modal=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="WallShuffle Error",
                )
                dialog.format_secondary_text(message)
                dialog.show_all()
                wire_dialog_default(dialog, Gtk.ResponseType.OK)

                def on_response(d, res):
                    d.destroy()

                dialog.connect("response", on_response)

            GLib.idle_add(_show)

        except Exception as e:
            logging.warning(f"Could not show GUI error dialog: {e}")
            print(f"ERROR: {message}", file=sys.stderr)
    else:
        if has_display:
            try:
                subprocess.run(["notify-send", "WallShuffle Error", message], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            except FileNotFoundError:
                print(f"ERROR: {message} (notify-send not found)", file=sys.stderr)
        else:
            print(f"ERROR: {message}", file=sys.stderr)
