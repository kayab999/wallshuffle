import argparse
import logging
import logging.handlers
import os
import sys


def configure_backend():
    """
    Detects the session type and forces X11 backend for GTK3 if running on Wayland.
    This fixes invisibility/positioning bugs on modern GNOME/KDE.
    Can be overridden by setting WALLSHUFFLE_FORCE_WAYLAND=1.

    Only needed for the GUI. Headless --change must not force GDK_BACKEND.
    """
    if os.environ.get("WALLSHUFFLE_FORCE_WAYLAND") == "1":
        print("WALLSHUFFLE_FORCE_WAYLAND=1 detected. Not forcing X11 backend.", file=sys.stderr)
        return

    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if "wayland" in session_type:
        if "GDK_BACKEND" not in os.environ:
            print("Wayland detected. Forcing X11 backend for GTK3 stability.", file=sys.stderr)
            os.environ["GDK_BACKEND"] = "x11"


from . import __version__


def setup_logging():
    """Configure logging with proper log rotation and directory."""
    try:
        # Use XDG config directory for logs
        log_dir = os.path.join(os.path.expanduser("~"), ".config", "wallshuffle", "logs")

        # Create directory if it doesn't exist
        os.makedirs(log_dir, mode=0o700, exist_ok=True)

        log_file_path = os.path.join(log_dir, "wallshuffle.log")

        # Clear any existing handlers (e.g. the emergency one)
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Configure RotatingFileHandler: 5MB max, 3 backups
        file_handler = logging.handlers.RotatingFileHandler(log_file_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")

        # Check for debug environment variable
        debug_mode = os.environ.get("WALLSHUFFLE_DEBUG") == "1"
        log_level = logging.DEBUG if debug_mode else logging.INFO

        file_handler.setLevel(log_level)

        # Configure format
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)

        # Console handler for warnings and errors only (to avoid spamming stdout)
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(formatter)

        # Add handlers to root logger
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        root_logger.setLevel(log_level)

        # Log startup message
        logging.info(f"WallShuffle v{__version__} started - Log file: {log_file_path}")
        logging.debug(f"Python version: {sys.version}")
        logging.debug(f"Platform: {sys.platform}")
    except Exception as e:
        # Fallback to stderr if file logging fails
        sys.stderr.write(f"ERROR: Failed to setup file logging: {e}\n")
        # Re-enable basic logging if it was cleared
        logging.getLogger().handlers = []
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
        logging.error("Failed to setup file logging", exc_info=True)


def _run_change_wallpaper() -> int:
    """Headless one-shot used by hotkeys, systemd timer, and CLI --change."""
    logging.info(
        "CLI --change requested (hotkey/timer/manual). "
        f"DISPLAY={os.environ.get('DISPLAY')!r} "
        f"WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY')!r} "
        f"DBUS_SESSION_BUS_ADDRESS={'set' if os.environ.get('DBUS_SESSION_BUS_ADDRESS') else 'unset'} "
        f"XDG_CURRENT_DESKTOP={os.environ.get('XDG_CURRENT_DESKTOP')!r}"
    )

    try:
        from .core import WallpaperUpdateResult, change_wallpaper
    except ImportError as e:
        logging.critical(f"Failed to import core modules: {e}", exc_info=True)
        return 1

    result = change_wallpaper()

    for handler in logging.getLogger().handlers:
        handler.flush()

    if result[0] != WallpaperUpdateResult.SUCCESS:
        logging.error(f"CLI wallpaper change failed with status: {result[0].name}: {result[1]}")
        return 1

    logging.info("CLI wallpaper change finished successfully.")
    return 0


def main():
    try:
        # Parse early so --change never forces GDK_BACKEND / GUI bootstrap.
        parser = argparse.ArgumentParser(description=f"WallShuffle v{__version__} - A wallpaper changer for Linux desktops.")
        parser.add_argument(
            "--change",
            action="store_true",
            help="Change the wallpaper once and exit (for system hotkeys and systemd timers).",
        )
        parser.add_argument("--version", action="version", version=f"WallShuffle {__version__}")
        args = parser.parse_args()

        setup_logging()

        if args.change:
            exit_code = _run_change_wallpaper()
            logging.shutdown()
            sys.exit(exit_code)

        # GUI path only: force X11 on Wayland for GTK3 stability
        configure_backend()

        # Preliminary check for a valid graphical environment
        display = os.environ.get("DISPLAY")
        dbus = os.environ.get("DBUS_SESSION_BUS_ADDRESS")

        if not display:
            logging.error("DISPLAY environment variable is not set. GUI cannot start.")
            print("ERROR: DISPLAY is not set. Use 'wallshuffle --change' for headless mode.", file=sys.stderr)
            sys.exit(1)
        try:
            import gi
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk

            if not Gtk.init_check()[0]:
                raise RuntimeError("Gtk.init_check() failed. Cannot connect to display.")

            logging.debug(f"Preliminary GTK display check successful (DISPLAY={display}).")
        except Exception as e:
            logging.error(
                f"Failed to connect to graphical display (GTK initialization failed: {e}). "
                f"Context: DISPLAY={display}, DBUS={dbus}. "
                "Use 'wallshuffle --change' for headless wallpaper changes."
            )
            print(
                f"ERROR: Failed to connect to graphical display ({e}).\n"
                "Tip: Ensure your DISPLAY environment variable is set correctly, "
                "or use 'wallshuffle --change' to change wallpaper without a GUI.",
                file=sys.stderr
            )
            sys.exit(1)

        try:
            from .app import WallpaperApp
        except ImportError as e:
            logging.critical(f"Failed to import GUI modules: {e}", exc_info=True)
            sys.exit(1)

        app = WallpaperApp()
        exit_code = app.run(sys.argv)
        logging.shutdown()
        sys.exit(exit_code)
    except Exception as e:
        logging.critical("Unhandled exception in main application loop", exc_info=True)
        sys.stderr.write(f"CRITICAL ERROR: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
