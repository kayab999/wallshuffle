import fcntl
import logging
import os
import shutil
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "wallshuffle")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.ini")


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
                dialog.run()
                dialog.destroy()

            GLib.idle_add(_show)  # Use GLib.idle_add to ensure it runs on the main GTK thread

        except Exception as e:
            logging.warning(f"Could not show GUI error dialog: {e}")
            print(f"ERROR: {message}", file=sys.stderr)
    else:
        # Fallback for non-GUI context or if parent is None
        # Try notify-send if DISPLAY is set, otherwise just print to stderr
        if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            try:
                subprocess.run(["notify-send", "WallShuffle Error", message], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except FileNotFoundError:
                print(f"ERROR: {message} (notify-send not found)", file=sys.stderr)
        else:
            print(f"ERROR: {message}", file=sys.stderr)


def log_wallpaper_history(image_path):
    history_file = os.path.join(CONFIG_DIR, "history.log")
    history = []
    try:
        # Open file in append mode first to ensure it exists, but we need read/write for updating
        if not os.path.exists(history_file):
            open(history_file, "a").close()

        with open(history_file, "r+") as f:
            try:
                # Acquire exclusive lock
                fcntl.flock(f, fcntl.LOCK_EX)

                content = f.read()
                history = content.splitlines() if content else []

                if image_path in history:
                    history.remove(image_path)
                history.insert(0, image_path)
                history = history[:20]

                # Rewind and truncate
                f.seek(0)
                f.truncate()
                f.write("\n".join(history))

            finally:
                # Release lock
                fcntl.flock(f, fcntl.LOCK_UN)

    except IOError as e:
        logging.error(f"File I/O error while logging wallpaper history: {e}")
    except Exception as e:
        logging.critical(f"An unhandled error occurred in log_wallpaper_history: {e}", exc_info=True)


def check_systemd_available():
    """
    Check if systemctl --user is functional.
    Fast-failing with timeout to prevent startup hangs.
    """
    try:
        # Check if systemctl exists in PATH or common locations
        systemctl_path = shutil.which("systemctl")
        if not systemctl_path:
            for path in ["/bin/systemctl", "/usr/bin/systemctl"]:
                if os.path.exists(path):
                    systemctl_path = path
                    break

        if not systemctl_path:
            logging.warning("systemctl not found in PATH or standard locations")
            return False

        # Use list-units to check connectivity instead of is-system-running.
        # is-system-running returns non-zero for 'degraded' or 'starting' states, which often
        # causes false negatives even if the service manager is responsive.
        # list-units checks if we can actually talk to the user manager.
        result = subprocess.run(
            [systemctl_path, "--user", "list-units", "--no-pager", "--no-legend", "-n", "1"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

        if result.returncode == 0:
            logging.debug("systemd user session is accessible via list-units")
            return True
        else:
            logging.warning(f"systemd user session verify failed (exit code: {result.returncode}, stderr: {result.stderr.strip()})")
            return False

    except subprocess.TimeoutExpired:
        logging.warning("systemctl --user check timed out after 5 seconds")
        return False
    except Exception as e:
        logging.error(f"Error checking systemd availability: {e}", exc_info=True)
        return False
