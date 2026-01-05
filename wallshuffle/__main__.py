import argparse
import logging
import os
import sys

from .app import WallpaperApp
from .core import WallpaperUpdateResult, change_wallpaper


def setup_logging():
    """Configure logging with proper log rotation and directory."""
    # Use XDG config directory for logs
    log_dir = os.path.join(os.path.expanduser("~"), ".config", "wallshuffle", "logs")

    # Create directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)

    log_file_path = os.path.join(log_dir, "wallshuffle.log")

    # Clear any existing handlers (in case of module reload)
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Configure FileHandler
    file_handler = logging.FileHandler(log_file_path, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

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
    root_logger.setLevel(logging.DEBUG)

    # Log startup message
    logging.info(f"WallShuffle started - Log file: {log_file_path}")
    logging.debug(f"Python version: {sys.version}")
    logging.debug(f"Platform: {sys.platform}")


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="WallShuffle - A wallpaper changer for Linux desktops."
    )
    parser.add_argument("--change", action="store_true", help="Change the wallpaper and exit.")
    args = parser.parse_args()

    if args.change:
        result = change_wallpaper()
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


if __name__ == "__main__":
    main()
