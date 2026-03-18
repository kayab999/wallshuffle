import argparse
import logging
import logging.handlers
import os
import sys


def configure_backend():
    """
    Detects the session type and forces X11 backend for GTK3 if running on Wayland.
    This fixes invisibility/positioning bugs on modern GNOME/KDE.
    """
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if "wayland" in session_type:
        # Check if we are forcing a specific backend via CLI args first
        if "GDK_BACKEND" not in os.environ:
            print("Wayland detected. Forcing X11 backend for GTK3 stability.", file=sys.stderr)
            os.environ["GDK_BACKEND"] = "x11"


# Call this BEFORE importing any GTK/GDK modules
configure_backend()

try:
    from .app import WallpaperApp
    from .core import WallpaperUpdateResult, change_wallpaper
except ImportError as e:
    logging.critical(f"Failed to import application modules: {e}", exc_info=True)
    sys.exit(1)
except Exception as e:
    logging.critical(f"Unexpected error during imports: {e}", exc_info=True)
    sys.exit(1)

from . import __version__


def setup_logging():
    """Configure logging with proper log rotation and directory."""
    try:
        # Use XDG config directory for logs
        log_dir = os.path.join(os.path.expanduser("~"), ".config", "wallshuffle", "logs")

        # Create directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)

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


def main():
    try:
        setup_logging()

        parser = argparse.ArgumentParser(description=f"WallShuffle v{__version__} - A wallpaper changer for Linux desktops.")
        parser.add_argument("--change", action="store_true", help="Change the wallpaper and exit.")
        parser.add_argument("--version", action="version", version=f"WallShuffle {__version__}")
        args = parser.parse_args()

        if args.change:
            # Debugging for keybinding/CLI issues
            if os.environ.get("WALLSHUFFLE_DEBUG_CLI") == "1":
                 logging.info(
                     f"CLI Env: DISPLAY={os.environ.get('DISPLAY')}, "
                     f"DBUS={os.environ.get('DBUS_SESSION_BUS_ADDRESS')}, "
                     f"XDG={os.environ.get('XDG_CURRENT_DESKTOP')}"
                 )

            result = change_wallpaper()

            # Flush logs to ensure they are written immediately
            for handler in logging.getLogger().handlers:
                handler.flush()

            if result != WallpaperUpdateResult.SUCCESS:
                logging.error(f"CLI wallpaper change failed with status: {result.name}")
                sys.exit(1)
            else:
                logging.info("CLI wallpaper change finished successfully.")
                sys.exit(0)

        else:
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
