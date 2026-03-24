import logging
import os
import shutil
import sys

from .utils import escape_systemd_path


def _find_executable_for_systemd():
    """
    Returns the stable path that systemd should execute to invoke wallshuffle --change.
    Prefers: user-installed wrapper (which wallshuffle) -> APPIMAGE wrapper -> sys.executable.
    """
    # 1) Prefer installable executable in PATH (editable install or wrapper)
    exe = shutil.which("wallshuffle")
    if exe:
        return exe

    # 2) If running inside AppImage and an installed wrapper exists, prefer it.
    appimage_path = os.environ.get("APPIMAGE")
    if appimage_path:
        # Possible recommended AppImage location in user installation
        user_appimage = os.path.expanduser("~/Applications/WallShuffle.AppImage")
        if os.path.isfile(user_appimage) and os.access(user_appimage, os.X_OK):
            return user_appimage
        # Otherwise, use direct APPIMAGE path (less ideal, but explicit)
        if os.path.isfile(appimage_path) and os.access(appimage_path, os.X_OK):
            return appimage_path

    # 3) Fallback: sys.executable (dev mode)
    return sys.executable

def setup_systemd_timer(interval, startup, is_systemd_available, run_subprocess_func, error_callback=None):
    if not is_systemd_available:
        logging.warning("Systemd is not available, skipping timer setup (this is expected on non-systemd systems).")
        return

    systemd_path = os.path.join(os.path.expanduser("~"), ".config", "systemd", "user")
    try:
        os.makedirs(systemd_path, exist_ok=True)

        uid = os.getuid()
        dbus_address = f"unix:path=/run/user/{uid}/bus"

        exec_path = _find_executable_for_systemd()

        if exec_path == sys.executable:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            esc_exec = escape_systemd_path(exec_path)
            exec_start_cmd = f"{esc_exec} -m wallshuffle --change"
            working_dir = project_root
        else:
            esc_exec = escape_systemd_path(exec_path)
            exec_start_cmd = f"{esc_exec} --change"
            working_dir = os.path.expanduser("~")

        env_vars = f'Environment="DBUS_SESSION_BUS_ADDRESS={dbus_address}"\n'
        if "DISPLAY" in os.environ:
             env_vars += f'Environment="DISPLAY={os.environ["DISPLAY"]}"\n'
        if "XDG_CURRENT_DESKTOP" in os.environ:
             env_vars += f'Environment="XDG_CURRENT_DESKTOP={os.environ["XDG_CURRENT_DESKTOP"]}"\n'
        if "DESKTOP_SESSION" in os.environ:
             env_vars += f'Environment="DESKTOP_SESSION={os.environ["DESKTOP_SESSION"]}"\n'

        service_content = f"""[Unit]
Description=WallShuffle Service

[Service]
Type=oneshot
WorkingDirectory={working_dir}
ExecStart={exec_start_cmd}
{env_vars}
"""
        with open(os.path.join(systemd_path, "wallpaper-changer.service"), "w") as f:
            f.write(service_content)

        timer_content = f"""[Unit]
Description=Run WallShuffle periodically

[Timer]
OnUnitActiveSec={interval}min
OnActiveSec=1s
OnBootSec=2min

[Install]
WantedBy=timers.target
"""
        with open(os.path.join(systemd_path, "wallpaper-changer.timer"), "w") as f:
            f.write(timer_content)
    except (IOError, OSError) as e:
        msg = f"File I/O error setting up systemd timer files: {e}"
        logging.error(msg)
        if error_callback:
            error_callback(msg)
        return
    except Exception as e:
        msg = f"An unhandled error occurred during systemd file setup: {e}"
        logging.critical(msg, exc_info=True)
        if error_callback:
            error_callback(msg)
        return

    try:
        if not run_subprocess_func(["systemctl", "--user", "daemon-reload"], "daemon-reload", timeout=5):
            if error_callback:
                error_callback("Failed to run systemctl daemon-reload. Check logs for details.")

        if startup:
            run_subprocess_func(["systemctl", "--user", "enable", "wallpaper-changer.timer"], "enable timer", timeout=5)
            run_subprocess_func(["systemctl", "--user", "start", "wallpaper-changer.timer"], "start timer", timeout=5)
        else:
            run_subprocess_func(["systemctl", "--user", "disable", "wallpaper-changer.timer"], "disable timer", timeout=5)
            run_subprocess_func(["systemctl", "--user", "stop", "wallpaper-changer.timer"], "stop timer", timeout=5)

    except Exception as e:
        logging.error(f"Error executing systemctl commands: {e}")
