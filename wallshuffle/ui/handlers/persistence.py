import logging
import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib

from ...constants import DisplayMode, ImageEffect, MultiMonitorMode, WallpaperSource
from ...gui_helpers import show_error_dialog
from ...system_integration import setup_systemd_timer


class PersistenceHandlersMixin:
    def on_save_clicked(self, widget, hide_window=True, skip_timer_setup=False):
        source = self.combo_source.get_active_text()

        # Get folder path from selected category
        cat_name = self.combo_folders.get_active_text()
        folder = self.folder_categories.get(cat_name, "") if cat_name else ""

        recursive_search = self.check_recursive.get_active()
        keywords = self.entry_keywords.get_text()
        unsplash_api_key = self.entry_unsplash_api_key.get_text()
        hyperlink_url = self.entry_url.get_text() if hasattr(self, 'entry_url') else ""
        mode = self.combo_mode.get_active_text()
        interval = self.spin_interval.get_value_as_int()
        startup = self.check_startup.get_active()
        random_order = self.check_random_order.get_active()
        effect = self.combo_effect.get_active_text()
        multi_monitor_mode = self.combo_multi_monitor.get_active_text()
        theme = self.combo_theme.get_active_text()

        bg_color = self.btn_color.get_rgba()
        hex_color = "#{:02x}{:02x}{:02x}".format(int(bg_color.red * 255), int(bg_color.green * 255), int(bg_color.blue * 255))

        settings_dict = {
            "source": source or WallpaperSource.LOCAL_FOLDER,
            "folder": folder,
            "recursive_search": str(recursive_search),
            "keywords": keywords,
            "unsplash_api_key": unsplash_api_key,
            "hyperlink_url": hyperlink_url,
            "mode": mode or DisplayMode.ZOOM,
            "interval": str(interval),
            "startup": str(startup),
            "random_order": str(random_order),
            "effect": effect or ImageEffect.NONE,
            "multi_monitor_mode": multi_monitor_mode or MultiMonitorMode.SINGLE,
            "theme": theme or "Ubuntu",
            "background_color": hex_color,
        }

        # Save custom colors if theme is Custom
        if theme == "Custom":
            def get_hex(btn):
                rgba = btn.get_rgba()
                return "#{:02x}{:02x}{:02x}".format(int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255))
            settings_dict["custom_background"] = get_hex(self.btn_custom_bg)
            settings_dict["custom_foreground"] = get_hex(self.btn_custom_fg)
            settings_dict["custom_accent"] = get_hex(self.btn_custom_accent)

        if not self.config_manager.save_settings(self.config, settings_dict):
            show_error_dialog(
                "Could not save settings to disk. Check permissions on ~/.config/wallshuffle.",
                parent=self,
            )
            return

        # Refresh UI components after saving
        try:
            self.load_settings()
        except TimeoutError as e:
            # Fase 1: lock timeout — muestra dialog en vez de silencioso
            logging.error(f"Config reload timeout after save: {e}")
            show_error_dialog(f"Settings saved but config reload failed (file locked). Try again.\n\nDetails: {e}", parent=self)
        self.poll_timer_status()

        # Only run systemd setup when explicitly saving (not during auto-save for Next Wallpaper)
        if not skip_timer_setup:
            def _on_systemd_error(msg):
                GLib.idle_add(show_error_dialog, msg, self)

            # Run systemd setup in background to avoid blocking UI
            threading.Thread(
                target=setup_systemd_timer,
                args=(interval, startup, self.is_systemd_available, self.wallpaper_manager._run_subprocess, _on_systemd_error),
                daemon=True
            ).start()

        if hide_window:
            if self.app and not self.app.tray_available:
                 logging.info("Tray icon not available. Keeping window visible after save.")
            else:
                self.hide()
