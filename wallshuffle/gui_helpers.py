import logging
import os
import subprocess
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib

def show_error_dialog(message, parent=None):
    logging.error(f"Error: {message}")

    # Only try to show a GTK dialog if a parent window is provided and we are in a graphical session.
    if parent and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        try:
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk

            def _show():
                dialog = Gtk.MessageDialog(
                    parent=parent,
                    flags=0,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="WallShuffle Error",
                )
                dialog.format_secondary_text(message)

                def on_response(d, res):
                    d.destroy()

                dialog.connect("response", on_response)
                dialog.show()

            GLib.idle_add(_show)  # Use GLib.idle_add to ensure it runs on the main GTK thread

        except Exception as e:
            logging.warning(f"Could not show GUI error dialog: {e}")
            print(f"ERROR: {message}", file=sys.stderr)
    else:
        # Fallback for non-GUI context or if parent is None
        # Try notify-send if DISPLAY is set, otherwise just print to stderr
        if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            try:
                subprocess.run(["notify-send", "WallShuffle Error", message], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            except FileNotFoundError:
                print(f"ERROR: {message} (notify-send not found)", file=sys.stderr)
        else:
            print(f"ERROR: {message}", file=sys.stderr)
