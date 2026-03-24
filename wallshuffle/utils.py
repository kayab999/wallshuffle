import fcntl
import logging
import os
import shutil
import subprocess

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "wallshuffle")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.ini")



def log_wallpaper_history(image_path):
    history_file = os.path.join(CONFIG_DIR, "history.log")
    history = []
    try:
        # Open file in append mode first to ensure it exists, but we need read/write for updating
        if not os.path.exists(history_file):
            with open(history_file, "a"):
                pass

        with open(history_file, "r+") as f:
            try:
                # Acquire exclusive lock
                fcntl.flock(f, fcntl.LOCK_EX)

                content = f.read()
                history = content.splitlines() if content else []

                # Sanitize path: remove newlines/ctrl chars to prevent corruption
                safe_path = image_path.replace("\n", "").replace("\r", "").strip()

                if safe_path in history:
                    history.remove(safe_path)
                history.insert(0, safe_path)
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


def escape_systemd_path(path):
    """
    Escapes a path for use in a systemd unit file (ExecStart, WorkingDirectory).

    Rules implemented:
    1. Escape backslashes as double backslashes.
    2. Escape double quotes as \" because we wrap the whole string in quotes.
    3. Escape % as %% to prevent systemd specifier expansion.
    4. Escape $ as $$ to prevent variable expansion (though less critical inside quotes, better safe).
    5. Wrap the final result in double quotes.
    """
    if not path:
        return ""

    safe_path = path.replace("\\", "\\\\")
    safe_path = safe_path.replace('"', '\\"')
    safe_path = safe_path.replace("%", "%%")
    safe_path = safe_path.replace("$", "$$")

    return f'"{safe_path}"'
