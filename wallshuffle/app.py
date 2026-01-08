import atexit  # For cleanup registration
import errno  # For EWOULDBLOCK
import fcntl  # For file locking
import logging
import os
import signal  # For signal handlers
import sys
import threading
import time

import gi

from .config_manager import ConfigManager
from .core import WallpaperUpdateResult, change_wallpaper
from .theme_manager import ThemeManager
from .ui import WallpaperAppWindow
from .utils import CONFIG_DIR, check_systemd_available, show_error_dialog
from .wallpaper_manager import WallpaperManager

gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3
from gi.repository import Gio, GLib, Gtk


class WallpaperApp(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            application_id="com.wallshuffle.app",
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
            **kwargs,
        )
        self.logger = logging.getLogger(self.__class__.__name__)
        self.win = None
        self.status_icon = None
        self.paused = False
        self.css_provider = None
        self.lock_file_fd = None  # File descriptor for the lock file
        self.lock_file_path = None  # Path to lock file for cleanup

        # Register cleanup handlers
        atexit.register(self._release_lock)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGHUP, self._signal_handler)
        signal.signal(signal.SIGUSR1, self._handle_sigusr1)

        self.logger.debug("Initializing ThemeManager in WallpaperApp.__init__")
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_settings()
        self.wallpaper_manager = WallpaperManager()

        # Perform environment checks immediately in __init__
        # This prevents race conditions where the window is created (using defaults)
        # before do_startup() runs.

        # Quick DE detection with retry logic for robustness on startup
        current_de = "unknown"
        for attempt in range(5):
            current_de = self.wallpaper_manager.get_desktop_environment()
            if current_de != "unknown":
                break
            self.logger.warning(f"DE detection failed (attempt {attempt + 1}/5). Retrying in 2s...")
            time.sleep(2)

        # GNOME-compatible environments list (must match wallpaper_manager.py)
        gnome_compat = ["gnome", "unity", "ubuntu", "cinnamon", "budgie", "mate", "pantheon", "pop"]

        if current_de in gnome_compat or current_de in ["kde", "xfce"]:
            self.is_de_supported = True
            self.logger.info(f"Desktop Environment: {current_de} (Supported)")
        else:
            self.is_de_supported = False
            self.logger.warning(f"Desktop Environment: '{current_de}' (Unsupported). Wallpaper functionality may not work correctly.")

        self.is_systemd_available = check_systemd_available()

        self.logger.info(f"DE Supported: {self.is_de_supported}")
        self.logger.info(f"Systemd Available: {self.is_systemd_available}")

        self.theme_manager = ThemeManager(self.config_manager, self.config)
        self.logger.debug("ThemeManager initialized")

    def _signal_handler(self, signum, frame):
        """Handle termination signals gracefully."""
        signal_names = {signal.SIGTERM: "SIGTERM", signal.SIGINT: "SIGINT", signal.SIGHUP: "SIGHUP"}
        signal_name = signal_names.get(signum, f"Signal {signum}")
        self.logger.info(f"Received {signal_name}, cleaning up...")
        self._release_lock()

        # Handle different signals appropriately
        if signum == signal.SIGTERM:
            self.quit()
        elif signum == signal.SIGINT:
            sys.exit(0)
        elif signum == signal.SIGHUP:
            # Hangup signal - typically from terminal closure
            self.quit()

    def _handle_sigusr1(self, signum, frame):
        """Handle SIGUSR1 to activate/show the window."""
        self.logger.info("Received SIGUSR1, activating window...")
        GLib.idle_add(self.do_activate)

    def _is_lock_stale(self, lock_path, max_age_hours=1):
        """
        Check if lock file is stale (older than max_age_hours).
        Returns True if lock should be removed.
        Validates that the PID in the lockfile is not a running process.
        """
        if not os.path.exists(lock_path):
            return False

        try:
            # Read the PID from the lock file
            with open(lock_path, "r") as f:
                pid_str = f.read().strip()
                if pid_str:
                    try:
                        pid = int(pid_str)
                        # Check if process is still running
                        try:
                            # Send signal 0 to check if process exists (doesn't actually send signal)
                            os.kill(pid, 0)
                            # Process exists, lock is NOT stale
                            self.logger.info(f"Lock file contains running process PID {pid}, not stale")
                            return False
                        except ProcessLookupError:
                            # Process doesn't exist, lock is stale
                            self.logger.warning(f"Lock file contains dead process PID {pid}, treating as stale")
                            return True
                        except PermissionError:
                            # Process exists but we don't have permission to signal it
                            # This means it's a real running process
                            self.logger.info(f"Lock file contains process PID {pid} (permission denied), not stale")
                            return False
                    except ValueError:
                        # Invalid PID in lock file, check by age
                        self.logger.warning(f"Lock file contains invalid PID: {pid_str}")

            # Check file age as fallback
            stat_info = os.stat(lock_path)
            age_seconds = time.time() - stat_info.st_mtime
            age_hours = age_seconds / 3600

            if age_hours > max_age_hours:
                self.logger.warning(f"Lock file is {age_hours:.1f}h old (threshold: {max_age_hours}h), treating as stale")
                return True
        except OSError as e:
            self.logger.error(f"Error checking lock file age: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error checking lock staleness: {e}", exc_info=True)

        return False

    def _check_single_instance(self):
        """
        Acquire exclusive application lock with stale lock recovery.
        """
        self.lock_file_path = os.path.join(CONFIG_DIR, "wallshuffle.lock")

        # Ensure config directory exists
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
        except OSError as e:
            self.logger.error(f"Cannot create config directory: {e}")
            return False

        # Check for stale lock
        if self._is_lock_stale(self.lock_file_path):
            self.logger.info("Removing stale lock file")
            try:
                os.unlink(self.lock_file_path)
            except OSError as e:
                self.logger.error(f"Failed to remove stale lock: {e}")
                # Continue anyway - flock will fail if process still running

        try:
            # Open lock file
            self.lock_file_fd = os.open(
                self.lock_file_path,
                os.O_CREAT | os.O_RDWR | os.O_CLOEXEC,  # Prevent inheritance by child processes
            )

            # Write PID for debugging
            try:
                os.ftruncate(self.lock_file_fd, 0)
                pid_str = f"{os.getpid()}\n"
                os.write(self.lock_file_fd, pid_str.encode())
            except OSError as e:
                self.logger.warning(f"Cannot write PID to lock file: {e}")

            # Acquire exclusive lock (non-blocking)
            fcntl.flock(self.lock_file_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

            self.logger.info(f"Acquired lock: {self.lock_file_path} (PID {os.getpid()})")
            return True

        except OSError as e:
            if e.errno == errno.EAGAIN or e.errno == errno.EWOULDBLOCK:
                # Lock already held by another process
                existing_pid = "unknown"
                try:
                    if self.lock_file_fd is not None:
                        os.lseek(self.lock_file_fd, 0, os.SEEK_SET)
                        existing_pid = os.read(self.lock_file_fd, 32).decode().strip()
                except Exception:
                    pass

                self.logger.warning(f"Another instance is running (PID {existing_pid}). Sending SIGUSR1 to activate it.")

                # Send signal to existing process to wake it up
                if existing_pid and existing_pid.isdigit():
                    try:
                        os.kill(int(existing_pid), signal.SIGUSR1)
                        self.logger.info(f"Sent SIGUSR1 to process {existing_pid}")
                    except OSError as e:
                        self.logger.error(f"Failed to signal existing process {existing_pid}: {e}")

                # Clean up fd
                if self.lock_file_fd is not None:
                    try:
                        os.close(self.lock_file_fd)
                    except Exception:
                        pass
                    self.lock_file_fd = None

                # Return False to exit this instance (but don't show error dialog)
                return False
            else:
                self.logger.error(f"Error acquiring lock: {e}", exc_info=True)
                show_error_dialog(f"Error acquiring lock: {e}", self.win)
                return False

        except Exception as e:
            self.logger.critical(f"Unexpected error in lock acquisition: {e}", exc_info=True)
            show_error_dialog(f"Critical startup error: {e}", self.win)
            return False

    def _release_lock(self):
        """
        Release lock file and delete it.
        Safe to call multiple times via atexit.
        """
        if self.lock_file_fd is not None:
            try:
                fcntl.flock(self.lock_file_fd, fcntl.LOCK_UN)
                os.close(self.lock_file_fd)
                self.logger.info("Released lock file descriptor")
            except Exception as e:
                self.logger.warning(f"Error releasing lock fd: {e}")
            finally:
                self.lock_file_fd = None

        # Remove lock file
        if self.lock_file_path and os.path.exists(self.lock_file_path):
            try:
                os.unlink(self.lock_file_path)
                self.logger.info(f"Deleted lock file: {self.lock_file_path}")
            except Exception as e:
                self.logger.warning(f"Error deleting lock file: {e}")

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.logger.debug("Entering WallpaperApp.do_startup")
        self.hold()

        # Check if another instance is running
        if not self._check_single_instance():
            self.quit()
            return

        # Environment checks moved to __init__ to avoid race conditions

        self.css_provider = self.theme_manager.get_css_provider()
        self.create_status_icon()

        # Force window activation on startup if not running in change-only mode
        # This ensures visibility even if the OS doesn't send the 'activate' signal
        GLib.timeout_add(100, self.do_activate)

    def do_activate(self):
        self.logger.debug("do_activate called")
        if not self.win:
            self.win = WallpaperAppWindow(
                application=self,
                title="WallShuffle",
                app=self,
                is_de_supported=self.is_de_supported,
                is_systemd_available=self.is_systemd_available,
            )
            if self.win:
                self.win.present()

        # Ensure window is visible and presented
        if self.win:
            self.win.show_all()
            self.win.deiconify()  # Unminimize if minimized
            self.win.present()
            self.win.present_with_time(Gtk.get_current_event_time())

    def create_status_icon(self):
        self.logger.debug("create_status_icon called.")
        indicator_id = "wallshuffle-indicator"

        # Determine icon path using absolute paths
        icon_path = None

        # Check for AppImage environment
        appimage_path = os.environ.get("APPIMAGE")
        appdir_path = os.environ.get("APPDIR")

        if appimage_path or appdir_path:
            # Running as AppImage
            self.logger.debug(f"AppImage detected - APPIMAGE={appimage_path}, APPDIR={appdir_path}")
            if appdir_path:
                # Check in APPDIR for icon
                appdir_icon = os.path.join(appdir_path, "icon.png")
                if os.path.exists(appdir_icon):
                    icon_path = appdir_icon
                    self.logger.info(f"Found icon in APPDIR: {icon_path}")
                else:
                    # Also check usr/share locations within AppImage
                    appimage_search_paths = [
                        os.path.join(appdir_path, "usr", "share", "pixmaps", "wallshuffle.png"),
                        os.path.join(appdir_path, "usr", "share", "wallshuffle", "icon.png"),
                        os.path.join(appdir_path, ".DirIcon"),  # AppImage default icon
                    ]
                    for path in appimage_search_paths:
                        if os.path.exists(path):
                            icon_path = path
                            self.logger.info(f"Found icon in AppImage: {icon_path}")
                            break

        elif getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            # Running in a PyInstaller bundle
            self.logger.debug("PyInstaller bundle detected")
            bundle_dir = sys._MEIPASS
            pyinstaller_icon = os.path.join(bundle_dir, "icon.png")
            if os.path.exists(pyinstaller_icon):
                icon_path = pyinstaller_icon
                self.logger.info(f"Found icon in PyInstaller bundle: {icon_path}")

        # If not found in bundled environment, search standard locations
        if not icon_path:
            # Running as package or from source - try multiple locations
            module_dir = os.path.dirname(os.path.abspath(__file__))

            search_paths = [
                os.path.join(module_dir, "..", "icon.png"),  # Source tree
                "/usr/share/pixmaps/wallshuffle.png",  # Debian/Ubuntu install
                "/usr/share/wallshuffle/icon.png",  # Alternative location
                "/usr/local/share/pixmaps/wallshuffle.png",  # Local install
                os.path.join(module_dir, "icon.png"),  # Package internal
                os.path.expanduser("~/.local/share/icons/hicolor/scalable/apps/wallshuffle.png"),  # User install
            ]

            self.logger.debug(f"Searching for icon in {len(search_paths)} locations...")
            for path in search_paths:
                abs_path = os.path.abspath(path)
                if os.path.exists(abs_path):
                    icon_path = abs_path
                    self.logger.info(f"Found icon at: {abs_path}")
                    break

            if not icon_path:
                self.logger.warning(f"Icon file not found in any of {len(search_paths)} search paths")
                self.logger.debug(f"Searched: {', '.join(search_paths)}")

        try:
            self.status_icon = AppIndicator3.Indicator.new(indicator_id, "wallshuffle", AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
            self.logger.debug("AppIndicator3.Indicator.new called successfully.")

            self.status_icon.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            self.logger.debug("set_status(ACTIVE) called.")

            if icon_path and os.path.exists(icon_path):
                self.status_icon.set_icon_full(icon_path, "WallShuffle")
                self.logger.info(f"Icon set successfully: {icon_path}")
            else:
                # Try theme icons as fallback
                for theme_icon in ["wallshuffle", "image-x-generic", "applications-graphics"]:
                    try:
                        self.status_icon.set_icon_full(theme_icon, "WallShuffle")
                        self.logger.info(f"Using theme icon: {theme_icon}")
                        break
                    except Exception as e:
                        self.logger.debug(f"Theme icon '{theme_icon}' not available: {e}")
                        continue

            self.indicator_menu = self._create_indicator_menu()
            self.status_icon.set_menu(self.indicator_menu)
            self.logger.debug("create_status_icon finished successfully.")
        except Exception as e:
            self.logger.error(f"Failed to create status icon: {e}", exc_info=True)

    def _create_indicator_menu(self):
        menu = Gtk.Menu()
        self.menu_item_next = Gtk.MenuItem(label="Next Wallpaper")
        self.menu_item_pause = Gtk.MenuItem(label="Pause/Resume")
        menu_item_open = Gtk.MenuItem(label="Open WallShuffle")
        menu_item_quit = Gtk.MenuItem(label="Quit")

        self.menu_item_next.connect("activate", self.on_next_wallpaper_clicked)
        self.menu_item_pause.connect("activate", self.on_pause_resume_clicked)
        menu_item_open.connect("activate", self.on_open_wallshuffle_clicked)
        menu_item_quit.connect("activate", self.on_quit_clicked)

        menu.append(self.menu_item_next)
        menu.append(self.menu_item_pause)
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(menu_item_open)
        menu.append(menu_item_quit)

        menu.show_all()
        return menu

    def _send_notification(self, title, body):
        notification = Gio.Notification.new(title)
        notification.set_body(body)
        notification.set_default_action("app.activate")
        self.send_notification("wallshuffle-notification", notification)

    def _handle_change_result(self, result):
        """Handles the result from change_wallpaper on the main GTK thread."""
        if result == WallpaperUpdateResult.SUCCESS:
            if self.win:
                self.win.update_current_wallpaper_label()
        else:
            error_map = {
                WallpaperUpdateResult.NO_SOURCE_CONFIGURED: "No wallpaper source is configured.",
                WallpaperUpdateResult.NO_IMAGES_FOUND: "No images were found for the current configuration.",
                WallpaperUpdateResult.NETWORK_ERROR: "A network error occurred while fetching wallpaper.",
                WallpaperUpdateResult.UNSUPPORTED_DESKTOP: "Your desktop environment is not supported.",
                WallpaperUpdateResult.COMMAND_FAILED: "The command to set the wallpaper failed.",
                WallpaperUpdateResult.CONFIGURATION_ERROR: "A configuration error was found.",
                WallpaperUpdateResult.FILE_SYSTEM_ERROR: "A file system error occurred.",
            }
            message = error_map.get(result, "An unknown error occurred while changing wallpaper.")
            self._send_notification("Wallshuffle Error", message)

        # Re-enable the menu item
        if hasattr(self, "menu_item_next"):
            self.menu_item_next.set_sensitive(True)

    def on_next_wallpaper_clicked(self, widget):
        def change_and_update():
            result = change_wallpaper()
            GLib.idle_add(self._handle_change_result, result)

        try:
            # Disable button to prevent rapid clicks
            if hasattr(self, "menu_item_next"):
                self.menu_item_next.set_sensitive(False)

            thread = threading.Thread(target=change_and_update, daemon=True)
            thread.start()
        except Exception as e:
            self.logger.critical(f"Error starting wallpaper change thread from indicator: {e}", exc_info=True)
            if hasattr(self, "menu_item_next"):
                self.menu_item_next.set_sensitive(True)  # Re-enable on thread start failure

    def on_pause_resume_clicked(self, widget):
        """Handle pause/resume button click with non-blocking systemctl calls."""
        current_paused_state = self.paused  # Store current state before attempting change

        def toggle_timer_thread():
            """Background thread function to toggle the timer."""
            command_success = False
            if current_paused_state:  # App is currently paused, so try to resume (start timer)
                self.logger.info("Attempting to resume wallpaper timer.")
                command_success = self.wallpaper_manager._run_subprocess(
                    ["systemctl", "--user", "start", "wallpaper-changer.timer"],
                    "start timer",
                    timeout=5,
                )
            else:  # App is currently running, so try to pause (stop timer)
                self.logger.info("Attempting to pause wallpaper timer.")
                command_success = self.wallpaper_manager._run_subprocess(
                    ["systemctl", "--user", "stop", "wallpaper-changer.timer"],
                    "stop timer",
                    timeout=5,
                )

            # Update UI on main thread
            GLib.idle_add(self._handle_timer_toggle_result, command_success, current_paused_state)

        try:
            # Disable button to prevent rapid clicks
            if hasattr(self, "menu_item_pause"):
                self.menu_item_pause.set_sensitive(False)

            thread = threading.Thread(target=toggle_timer_thread, daemon=True)
            thread.start()
        except Exception as e:
            self.logger.critical(f"Error starting pause/resume thread: {e}", exc_info=True)
            if hasattr(self, "menu_item_pause"):
                self.menu_item_pause.set_sensitive(True)

    def _handle_timer_toggle_result(self, command_success, previous_paused_state):
        """Handle the result of timer toggle on the main GTK thread."""
        if command_success:
            self.paused = not previous_paused_state  # Only toggle if command succeeded
            self.logger.info(f"Wallpaper timer {'paused' if self.paused else 'resumed'}.")
            # Update menu item label to reflect new state
            if self.paused:
                self.menu_item_pause.set_label("Resume")
            else:
                self.menu_item_pause.set_label("Pause")
        else:
            self.logger.error("Failed to change systemd timer state.")
            show_error_dialog(
                "Failed to change systemd timer state. Ensure systemd is running and you have permissions.",
                self.win,  # Pass window for transient dialog
            )

        # Re-enable the menu item
        if hasattr(self, "menu_item_pause"):
            self.menu_item_pause.set_sensitive(True)

    def on_open_wallshuffle_clicked(self, widget):
        self.do_activate()

    def on_quit_clicked(self, widget):
        self.quit()
