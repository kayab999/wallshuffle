import datetime
import logging

import gi

from .themes import THEMES  # ruff: noqa: E402

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # ruff: noqa: E402


class ThemeManager:
    def __init__(self, config_manager, config):
        version_id = "DEBUG_v1.0_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        logging.debug(f"ThemeManager.__init__ called - Version/ID: {version_id}")
        self.config_manager = config_manager
        self.config = config

        # Try to load the theme from config
        saved_theme = self.config_manager.get_setting(self.config, "Settings", "theme")

        if saved_theme and saved_theme in THEMES:
            self.current_theme_name = saved_theme
        else:
            # If no theme is saved (first run) or saved theme is invalid, detect distro
            distro_name = self.detect_distro()
            # Match detected distro name (e.g., "ubuntu") with theme key (e.g., "Ubuntu")
            theme_key = next((k for k in THEMES.keys() if k.lower() == distro_name), "Default")
            self.current_theme_name = theme_key
            # Save the auto-detected theme so it persists
            self.set_theme_name(self.current_theme_name)

    def detect_distro(self):
        """Detects the Linux distribution from /etc/os-release."""
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("ID="):
                        # Returns the ID value, e.g., "ubuntu", "fedora", "arch"
                        return line.split("=")[1].strip().strip('"')
        except FileNotFoundError:
            logging.warning("/etc/os-release not found. Cannot detect distribution.")
        except Exception as e:
            logging.error(f"Error reading /etc/os-release: {e}")
        return None

    def set_theme_name(self, name):
        """Changes the theme and saves it to the config."""
        if name not in THEMES:
            name = "Ubuntu"  # safe fallback

        self.current_theme_name = name
        self.config_manager.save_settings(self.config, {"theme": name})

    def get_css_provider(self):
        """Builds and returns a Gtk.CssProvider for the active theme."""
        theme = THEMES.get(self.current_theme_name, THEMES["Ubuntu"])

        css = f"""
#wallshuffle-main-window {{
    background-color: {theme["background"]};
    color: {theme["foreground"]};
}}

#wallshuffle-main-window GtkLabel {{
    color: {theme["foreground"]};
}}

#wallshuffle-main-window GtkButton {{
    background-color: {theme["accent"]};
    color: {theme["foreground"]};
    border-radius: 6px;
    padding: 4px 8px;
}}

#wallshuffle-main-window GtkButton:hover {{
    box-shadow: 0 0 6px {theme["hover"]};
}}

#wallshuffle-main-window GtkEntry {{
    background-color: {theme["background"]};
    color: {theme["foreground"]};
    border: 1px solid {theme["accent"]};
}}

#wallshuffle-main-window GtkComboBox GtkEntry {{
    background-color: {theme["background"]};
    color: {theme["foreground"]};
}}
"""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css.encode("utf-8"))
        return css_provider
