import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk

from ...constants import DisplayMode, ImageEffect, MultiMonitorMode, WallpaperSource


class SettingsHandlersMixin:
    def load_settings(self):
        # Load Categories first
        self._load_categories_from_config()
        self.update_folder_combo()

        if "Settings" in self.config:
            settings = self.config["Settings"]

            # Ensure valid values and avoid None
            def safe_set_active(combo, value, options):
                if value in options:
                    combo.set_active(options.index(value))
                else:
                    combo.set_active(0)

            source = settings.get("source", WallpaperSource.LOCAL_FOLDER)
            safe_set_active(self.combo_source, source, self.sources)

            # Match saved folder path to category
            saved_Folder = settings.get("folder", "")
            found_cat = None
            for name, path in self.folder_categories.items():
                if path == saved_Folder:
                    found_cat = name
                    break

            # Set active using simple iteration as safe_set_active is generic
            if found_cat:
                # find index of found_cat
                idx = 0
                for name in self.folder_categories:
                    if name == found_cat:
                        self.combo_folders.set_active(idx)
                        break
                    idx += 1

            self.check_recursive.set_active(self.config_manager.get_setting(self.config, "Settings", "recursive_search", False, value_type=bool))
            self.entry_keywords.set_text(settings.get("keywords", ""))

            unsplash_api_key = settings.get("unsplash_api_key", "")
            if unsplash_api_key == "YOUR_UNSPLASH_API_KEY":
                unsplash_api_key = ""
            self.entry_unsplash_api_key.set_text(unsplash_api_key)

            mode = settings.get("mode", DisplayMode.ZOOM)
            safe_set_active(self.combo_mode, mode, self.modes)

            self.spin_interval.set_value(self.config_manager.get_setting(self.config, "Settings", "interval", 30, value_type=int))
            self.check_startup.set_active(self.config_manager.get_setting(self.config, "Settings", "startup", False, value_type=bool))
            self.check_random_order.set_active(self.config_manager.get_setting(self.config, "Settings", "random_order", True, value_type=bool))

            effect = settings.get("effect", ImageEffect.NONE)
            safe_set_active(self.combo_effect, effect, self.effects)

            multi_monitor_mode = settings.get("multi_monitor_mode", MultiMonitorMode.SINGLE)
            safe_set_active(self.combo_multi_monitor, multi_monitor_mode, self.multi_monitor_modes)

            url = settings.get("hyperlink_url", "")
            if hasattr(self, 'entry_url'):
                self.entry_url.set_text(url)

            # Theme loading
            theme_name = settings.get("theme", "Ubuntu")
            if self.theme_engine:
                theme_keys = list(self.theme_engine.store.get_all_presets().keys())
                safe_set_active(self.combo_theme, theme_name, theme_keys)
            else:
                safe_set_active(self.combo_theme, theme_name, ["Ubuntu"])

            # Visibility for custom colors
            if theme_name == "Custom":
                self.box_custom_colors.show_all()

                # Load custom colors
                def parse_and_set(btn, color_str, default="#000000"):
                    c = Gdk.RGBA()
                    if not c.parse(color_str):
                        c.parse(default)
                    btn.set_rgba(c)

                parse_and_set(self.btn_custom_bg, settings.get("custom_background", "#F5F5F5"))
                parse_and_set(self.btn_custom_fg, settings.get("custom_foreground", "#333333"))
                parse_and_set(self.btn_custom_accent, settings.get("custom_accent", "#007ACC"))
            else:
                self.box_custom_colors.hide()

            # Proactively reload theme if engine exists
            if self.theme_engine:
                try:
                    self.theme_engine.config = self.config
                    self.theme_engine.resolver.config = self.config
                    self.theme_engine.set_theme(theme_name, save=False)
                    logging.info(f"Theme '{theme_name}' applied successfully.")
                except Exception as e:
                    logging.error(f"Failed to reload theme: {e}")

            bg_color_str = settings.get("background_color", "#000000")
            color = Gdk.RGBA()
            if color.parse(bg_color_str):
                self.btn_color.set_rgba(color)
