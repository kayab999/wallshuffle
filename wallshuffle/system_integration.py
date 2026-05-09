import logging
import os
import shutil
import sys

from .utils import escape_systemd_path


def _find_executable_for_timer():
    """
    Returns the stable path that systemd or cron should execute to invoke wallshuffle --change.
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

def setup_cron_fallback(interval, startup, run_subprocess_func):
    """
    Fallback for systems without systemd. Manages a crontab entry.
    """
    import subprocess
    
    tag = "# WALLSHUFFLE_TIMER"
    exec_path = _find_executable_for_timer()
    
    # Prepare environment context for CRON with shell escaping to prevent command injection
    import shlex
    uid = os.getuid()
    dbus_address = shlex.quote(os.environ.get("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{uid}/bus"))
    display = shlex.quote(os.environ.get("DISPLAY", ":0"))
    xdg = shlex.quote(os.environ.get("XDG_CURRENT_DESKTOP", ""))
    
    if exec_path == sys.executable:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        # working_dir doesn't need quote if it's from project_root, but safer
        safe_root = shlex.quote(project_root)
        command = f"cd {safe_root} && {exec_path} -m wallshuffle --change"
    else:
        command = f"{exec_path} --change"

    # Wrap with environment variables. shlex.quote already adds quotes if needed.
    full_cmd = f"DBUS_SESSION_BUS_ADDRESS={dbus_address} DISPLAY={display} XDG_CURRENT_DESKTOP={xdg} {command} {tag}"
    
    # Cron interval: */X * * * *
    cron_entry = f"*/{interval} * * * * {full_cmd}"

    try:
        # Get existing crontab
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False, timeout=5)
        lines = result.stdout.splitlines() if result.returncode == 0 else []
        
        # Filter out existing entries
        new_lines = [l for l in lines if tag not in l and l.strip()]
        
        if startup:
            new_lines.append(cron_entry)
            logging.info(f"Adding cron entry: {cron_entry}")
        else:
            logging.info("Removing cron entry.")

        # Write back
        new_crontab = "\n".join(new_lines) + "\n"
        subprocess.run(["crontab", "-"], input=new_crontab, text=True, check=True, timeout=5)
        return True
    except Exception as e:
        logging.error(f"Failed to setup cron fallback: {e}")
        return False

def setup_systemd_timer(interval, startup, is_systemd_available, run_subprocess_func, error_callback=None):
    if not is_systemd_available:
        logging.warning("Systemd is not available, falling back to Cron.")
        success = setup_cron_fallback(interval, startup, run_subprocess_func)
        if not success and error_callback:
            error_callback("Failed to setup Cron fallback.")
        return

    systemd_path = os.path.join(os.path.expanduser("~"), ".config", "systemd", "user")
    try:
        os.makedirs(systemd_path, mode=0o700, exist_ok=True)

        # Usar especificadores de systemd para que sea independiente de la sesión actual
        # %U = UID del usuario, %t = XDG_RUNTIME_DIR (/run/user/%U)
        dbus_address = "unix:path=/run/user/%U/bus"

        exec_path = _find_executable_for_timer()

        if exec_path == sys.executable:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            esc_exec = escape_systemd_path(exec_path)
            exec_start_cmd = f"{esc_exec} -m wallshuffle --change"
            working_dir = project_root
        else:
            esc_exec = escape_systemd_path(exec_path)
            exec_start_cmd = f"{esc_exec} --change"
            working_dir = os.path.expanduser("~")

        # No capturamos DISPLAY de forma estática. En su lugar, confiamos en que 
        # el entorno de systemd --user tenga las variables necesarias, o las
        # importamos dinámicamente si es necesario.
        env_vars = f'Environment="DBUS_SESSION_BUS_ADDRESS={dbus_address}"\n'
        # Podríamos añadir un script de detección de DISPLAY si fuera necesario,
        # pero para la mayoría de entornos modernos con DBUS funcional basta.

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

        # Proactivamente importar el entorno actual al gestor de systemd user
        # Esto ayuda a que el timer funcione inmediatamente en la sesión actual.
        import_cmd = ["systemctl", "--user", "import-environment", "DISPLAY", "XDG_CURRENT_DESKTOP", "XDG_SESSION_TYPE", "DBUS_SESSION_BUS_ADDRESS"]
        run_subprocess_func(import_cmd, "import-environment", timeout=5)

        if startup:
            run_subprocess_func(["systemctl", "--user", "enable", "wallpaper-changer.timer"], "enable timer", timeout=5)
            run_subprocess_func(["systemctl", "--user", "start", "wallpaper-changer.timer"], "start timer", timeout=5)
        else:
            run_subprocess_func(["systemctl", "--user", "disable", "wallpaper-changer.timer"], "disable timer", timeout=5)
            run_subprocess_func(["systemctl", "--user", "stop", "wallpaper-changer.timer"], "stop timer", timeout=5)

    except Exception as e:
        logging.error(f"Error executing systemctl commands: {e}")
