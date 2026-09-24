import logging

import gi

from ..constants import DisplayMode, ImageEffect, MultiMonitorMode, WallpaperSource
from .handlers.about import AboutHandlersMixin
from .handlers.folders import FolderHandlersMixin
from .handlers.persistence import PersistenceHandlersMixin
from .handlers.polling import PollingHandlersMixin
from .handlers.settings import SettingsHandlersMixin
from .handlers.source import SourceHandlersMixin
from .handlers.wallpaper import WallpaperHandlersMixin
from .panels import WindowPanelsMixin

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk


class WallpaperAppWindow(
    Gtk.ApplicationWindow,
    WindowPanelsMixin,
    PollingHandlersMixin,
    SourceHandlersMixin,
    SettingsHandlersMixin,
    FolderHandlersMixin,
    WallpaperHandlersMixin,
    PersistenceHandlersMixin,
    AboutHandlersMixin,
):
    def __init__(self, *args, **kwargs):
        logging.debug(f"WallpaperAppWindow init started. kwargs keys: {list(kwargs.keys())}")
        self.app = kwargs.pop("app", None)
        self.is_de_supported = kwargs.pop("is_de_supported", False)
        logging.info(f"UI received is_de_supported: {self.is_de_supported}")
        self.is_systemd_available = kwargs.pop("is_systemd_available", False)

        logging.debug("Calling super().__init__")
        super().__init__(*args, **kwargs)
        logging.debug("super().__init__ completed")

        self.set_default_size(700, 700)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_border_width(0) # Removed border width for modern look
        self.set_name("wallshuffle-main-window")
        self.config_manager = self.app.config_manager
        self.config = self.app.config
        self.wallpaper_manager = self.app.wallpaper_manager
        self.theme_engine = getattr(self.app, "theme_engine", None)
        self._polling_in_progress = False

        # Initialize data lists
        self.sources = list(WallpaperSource.ALL)
        self.modes = list(DisplayMode.ALL)
        self.effects = list(ImageEffect.ALL)
        self.multi_monitor_modes = list(MultiMonitorMode.ALL)

        logging.debug("Calling init_ui")
        self.init_ui()
        logging.debug("init_ui completed")

        # Load settings and apply initial state
        logging.debug("Loading settings")
        self.load_settings()
        logging.debug("Updating current wallpaper label")
        self.update_current_wallpaper_label()
        logging.debug("Updating image count")
        self.update_image_count()

        # Start adaptive status polling (5s when focused, 30s when not).
        # One-shot initial poll after 1s; adaptive timer owns the repeat.
        self._poll_timeout_id = None
        self._poll_interval_seconds = 5
        GLib.timeout_add(1000, lambda: (self.poll_timer_status(), False)[1])
        self._start_adaptive_poll()

        self.connect("delete-event", self.on_delete_event)
        self.connect("focus-in-event", self._on_focus_in)
        self.connect("focus-out-event", self._on_focus_out)

        logging.debug("Window initialized (hidden)")

        # Initial visibility check based on source
        # self.on_source_changed(self.combo_source) # Call this after UI is built
        # self.on_multi_monitor_changed(self.combo_multi_monitor)

        logging.info("WallpaperAppWindow initialization successful")

