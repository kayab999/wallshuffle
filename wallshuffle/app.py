import errno
import logging
import os
import shutil
import signal  # For signal handlers
import socket
import sys
import threading
import time

import gi

from .config_manager import get_config_manager
from .constants import GNOME_COMPAT
from .core import WallpaperUpdateResult, change_wallpaper
from .gui_helpers import show_error_dialog
from .online_sources import OnlineSourceManager
from .theme_manager import ThemeManager
from .ui import WallpaperAppWindow
from .utils import CONFIG_DIR, check_systemd_available
from .wallpaper_manager import WallpaperManager

gi.require_version("Gtk", "3.0")

# Flag to track if tray icon support is available
TRAY_SUPPORTED = False
AppIndicator3 = None

try:
    try:
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3 as AppIndicator3
        TRAY_SUPPORTED = True
    except (ValueError, ImportError):
        try:
            gi.require_version("AppIndicator3", "0.1")
            from gi.repository import AppIndicator3
            TRAY_SUPPORTED = True
        except (ValueError, ImportError):
            logging.warning("Neither AyatanaAppIndicator3 nor AppIndicator3 found. Tray icon will be disabled.")
except Exception as e:
    logging.error(f"Unexpected error while checking for tray support: {e}")

from gi.repository import Gio, GLib, Gtk


class WallpaperApp(Gtk.Application):
    def __init__(self, *args: any, **kwargs: any) -> None:
        super().__init__(
            *args,
            application_id="com.wallshuffle.app",
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
            **kwargs,
        )
        self.logger = logging.getLogger(self.__class__.__name__)
        self.win = None
        self.status_icon = None
        self.tray_available = False # Will be set to True on success
        self.paused = False
        self.css_provider = None
        self.server_socket = None
        # Include UID in socket name to support multi-user environments
        self.socket_name = f"\0wallshuffle_{os.getuid()}_lock"

        # Register cleanup handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGHUP, self._signal_handler)

        self.logger.debug("Initializing ThemeManager in WallpaperApp.__init__")
        self.config_manager = get_config_manager()
        self.config = self.config_manager.load_settings()
        self.wallpaper_manager = WallpaperManager()

        # Schedule cache cleanup
        threading.Thread(target=OnlineSourceManager.cleanup_old_cache, daemon=True).start()

        # Perform environment checks immediately in __init__
        # This prevents race conditions where the window is created (using defaults)
        # before do_startup() runs.

        # Quick DE detection
        current_de = self.wallpaper_manager.get_desktop_environment()

        # GNOME-compatible environments list (must match wallpaper_manager.py)
        if current_de in GNOME_COMPAT or current_de in ["kde", "xfce"]:
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

        # Sync local state with systemd timer
        if self.is_systemd_available:
            is_active = self.wallpaper_manager.check_timer_active()
            self.paused = not is_active
            self.logger.info(f"Systemd timer active: {is_active}. Setting paused state to: {self.paused}")
        else:
            self.paused = True

    def _clean_temp_dir(self) -> None:
        """Cleans up temporary files from previous sessions."""
        try:
            temp_dir = os.path.join(CONFIG_DIR, "temp")
            if os.path.exists(temp_dir):
                self.logger.info(f"Cleaning temp directory: {temp_dir}")
                shutil.rmtree(temp_dir)
                os.makedirs(temp_dir, exist_ok=True)
        except Exception as e:
            self.logger.warning(f"Failed to clean temp directory: {e}")

    def _signal_handler(self, signum: int, frame: any) -> None:
        """Handle termination signals gracefully."""
        # Use low-level write to avoid re-entrant logging issues in signal handlers
        msg = f"Received signal {signum}, cleaning up...\n"
        os.write(sys.stderr.fileno(), msg.encode())

        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

        # Handle different signals appropriately
        if signum == signal.SIGTERM:
            GLib.idle_add(self.quit)
        elif signum == signal.SIGINT:
            sys.exit(0)
        elif signum == signal.SIGHUP:
            GLib.idle_add(self.quit)

    def _init_single_instance(self):
        """
        Initialize single instance mechanism using Abstract Unix Domain Socket.
        Returns True if we are the primary instance.
        Returns False if another instance is running (and we notified it).
        """
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            # Bind to abstract namespace (starts with null byte)
            # This is automatically cleaned up by kernel when process dies
            self.server_socket.bind(self.socket_name)
            self.server_socket.listen(1)
            self.logger.info("Socket bound successfully. We are the primary instance.")

            # Start listener thread
            thread = threading.Thread(target=self._socket_listener, daemon=True)
            thread.start()
            return True
        except OSError as e:  # socket.error is alias for OSError
            if e.errno == errno.EADDRINUSE:
                self.logger.info("Another instance is running. Attempting to wake it up.")
                try:
                    client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    client_socket.settimeout(2.0)  # Don't block forever if primary is hung
                    client_socket.connect(self.socket_name)
                    client_socket.sendall(b"WAKEUP")
                    client_socket.close()
                    self.logger.info("Sent WAKEUP signal to primary instance.")
                except Exception as e2:
                    self.logger.error(f"Failed to communicate with primary instance: {e2}")
                return False
            else:
                self.logger.error(f"Unexpected socket error: {e}")
                return False

    def _socket_listener(self):
        """Listens for commands from other instances."""
        while True:
            try:
                conn, _ = self.server_socket.accept()
                data = conn.recv(1024)
                if data == b"WAKEUP":
                    self.logger.info("Received WAKEUP command via socket.")
                    GLib.idle_add(self.do_activate)
                conn.close()
            except Exception as e:
                self.logger.error(f"Socket listener error: {e}")
                # If socket is closed (e.g. on shutdown), break loop
                if self.server_socket.fileno() == -1:
                    break
                # Prevent infinite loop on repeated failure
                time.sleep(1)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.logger.debug("Entering WallpaperApp.do_startup")
        self._clean_temp_dir()
        self.hold()

        # Check if another instance is running using Sockets
        if not self._init_single_instance():
            self.logger.info("Exiting because another instance is running.")
            self.quit()
            return

        # Clean up temp files from previous runs
        self.wallpaper_manager.cleanup_temp_files()

        try:
            self.css_provider = self.theme_manager.get_css_provider()
        except Exception as e:
            self.logger.error(f"Failed to load CSS: {e}", exc_info=True)

        try:
            self.create_status_icon()
        except Exception as e:
            self.logger.error(f"Failed to create tray icon: {e}", exc_info=True)

        # Force window activation on startup if not running in change-only mode
        # This ensures visibility even if the OS doesn't send the 'activate' signal
        GLib.timeout_add(100, self.do_activate)

    def do_activate(self):
        self.logger.debug("do_activate called")

        # If window exists, just bring it to front and return
        if self.win:
            self.logger.info("Window already exists, re-presenting.")
            try:
                self.win.show_all()
                self.win.deiconify()
                self.win.present()
            except Exception as e:
                self.logger.error(f"Error re-presenting window: {e}", exc_info=True)
            return

        if not self.win:
            try:
                self.win = WallpaperAppWindow(
                    application=self,
                    title="WallShuffle",
                    app=self,
                    is_de_supported=self.is_de_supported,
                    is_systemd_available=self.is_systemd_available,
                )
            except Exception as e:
                self.logger.critical(f"Failed to initialize main window: {e}", exc_info=True)
                show_error_dialog(f"Failed to start application UI: {e}", None)
                self.quit()
                return

        # Ensure window is visible and presented
        if self.win:
            try:
                self.win.set_keep_above(True)  # Force on top
                self.win.show_all()
                self.win.deiconify()
                self.win.present()
                self.logger.info(f"Window presented. Visibility: {self.win.get_visible()}")

                # Disable keep-above after a short delay so it doesn't annoy user forever
                GLib.timeout_add(2000, lambda: self.win.set_keep_above(False))
            except Exception as e:
                self.logger.error(f"Error presenting window: {e}", exc_info=True)

    def create_status_icon(self):
        self.logger.debug("create_status_icon called.")

        if not TRAY_SUPPORTED or AppIndicator3 is None:
            self.logger.warning("Tray support is not available. Skipping tray icon creation.")
            self.tray_available = False
            return

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
            init_icon = "image-x-generic"
            if icon_path and os.path.exists(icon_path):
                init_icon = os.path.splitext(os.path.basename(icon_path))[0]

            self.status_icon = AppIndicator3.Indicator.new(indicator_id, init_icon, AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
            self.logger.debug(f"AppIndicator3.Indicator.new called successfully with icon '{init_icon}'.")
            
            # Icon itself is created, so mark as available early
            self.tray_available = True

            if icon_path and os.path.exists(icon_path):
                self.status_icon.set_icon_theme_path(os.path.dirname(icon_path))

            # Create and set menu BEFORE activating
            self.indicator_menu = self._create_indicator_menu()
            self.status_icon.set_menu(self.indicator_menu)
            self.logger.debug("Menu attached to indicator.")

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

            self.logger.debug("create_status_icon finished successfully.")
        except Exception as e:
            self.logger.error(f"Failed to create status icon: {e}", exc_info=True)

    def _create_indicator_menu(self):
        menu = Gtk.Menu()
        self.menu_item_next = Gtk.MenuItem(label="Next Wallpaper")
        pause_label = "Resume" if self.paused else "Pause"
        self.menu_item_pause = Gtk.MenuItem(label=pause_label)
        menu_item_open = Gtk.MenuItem(label="Open WallShuffle")
        menu_item_support = Gtk.MenuItem(label="Support WallShuffle ☕")
        menu_item_about = Gtk.MenuItem(label="About")
        menu_item_quit = Gtk.MenuItem(label="Quit")

        self.menu_item_next.connect("activate", self.on_next_wallpaper_clicked)
        self.menu_item_pause.connect("activate", self.on_pause_resume_clicked)
        menu_item_open.connect("activate", self.on_open_wallshuffle_clicked)
        menu_item_support.connect("activate", self.on_support_clicked)
        menu_item_about.connect("activate", self.on_about_clicked)
        menu_item_quit.connect("activate", self.on_quit_clicked)

        menu.append(self.menu_item_next)
        menu.append(self.menu_item_pause)
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(menu_item_open)
        menu.append(menu_item_support)
        menu.append(menu_item_about)
        menu.append(menu_item_quit)

        menu.show_all()
        return menu

    def _send_notification(self, title: str, body: str) -> None:
        notification = Gio.Notification.new(title)
        notification.set_body(body)
        notification.set_default_action("app.activate")
        self.send_notification("wallshuffle-notification", notification)

    def _handle_change_result(self, result: WallpaperUpdateResult) -> None:
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
        self.logger.debug("Tray: Next Wallpaper clicked")
        def change_and_update():
            try:
                result = change_wallpaper()
                GLib.idle_add(self._handle_change_result, result)
            except Exception as e:
                self.logger.error(f"Error in change_wallpaper thread: {e}", exc_info=True)
                # Ensure we re-enable the menu item even if it crashes
                GLib.idle_add(lambda: self.menu_item_next.set_sensitive(True) if hasattr(self, "menu_item_next") else None)
                GLib.idle_add(self._send_notification, "WallShuffle Error", f"Failed to change wallpaper: {e}")

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
        self.logger.debug("Tray: Pause/Resume clicked")
        current_paused_state = self.paused  # Store current state before attempting change

        def toggle_timer_thread():
            """Background thread function to toggle the timer."""
            command_success = False

            # Proactively reload to ensure systemd sees our .timer file
            self.wallpaper_manager._run_subprocess(["systemctl", "--user", "daemon-reload"], "daemon-reload", timeout=5)

            if current_paused_state:  # App is currently paused, so try to resume (start timer)
                self.logger.info("Attempting to resume wallpaper timer.")
                command_success = self.wallpaper_manager._run_subprocess(
                    ["systemctl", "--user", "enable", "wallpaper-changer.timer"],
                    "enable timer",
                    timeout=5,
                )
                if command_success:
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
                if command_success:
                    self.wallpaper_manager._run_subprocess(
                        ["systemctl", "--user", "disable", "wallpaper-changer.timer"],
                        "disable timer",
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
            
            # Update UI label immediately
            if self.win:
                self.win.poll_timer_status()
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
        self.logger.debug("Tray: Open WallShuffle clicked")
        self.do_activate()

    def on_support_clicked(self, widget):
        self.logger.debug("Tray: Support clicked")
        import subprocess
        donate_url = "https://buymeacoffee.com/wallshuffle"
        try:
            subprocess.Popen(["xdg-open", donate_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self.logger.warning(f"Could not open donation URL: {e}")

    def on_about_clicked(self, widget):
        self.logger.debug("Tray: About clicked")
        if self.win:
            self.win.on_about_clicked(widget)
        else:
            # If window doesn't exist yet, we might need to create it or just ignore
            self.do_activate()
            if self.win:
                self.win.on_about_clicked(widget)

    def on_quit_clicked(self, widget):
        self.logger.debug("Tray: Quit clicked")
        self.quit()
