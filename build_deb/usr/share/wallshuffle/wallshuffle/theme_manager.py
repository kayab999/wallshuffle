# ruff: noqa: E402
import datetime
import logging

import gi

from .themes import THEMES

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


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

        # If theme is Custom, override values with those from config
        if self.current_theme_name == "Custom":
            theme = theme.copy() # Don't mutate the original dictionary
            theme["background"] = self.config_manager.get_setting(self.config, "Settings", "custom_background", theme["background"])
            theme["foreground"] = self.config_manager.get_setting(self.config, "Settings", "custom_foreground", theme["foreground"])
            theme["accent"] = self.config_manager.get_setting(self.config, "Settings", "custom_accent", theme["accent"])
            theme["button_text"] = self.config_manager.get_setting(self.config, "Settings", "custom_button_text", theme.get("button_text", "#FFFFFF"))

        css = f"""
#wallshuffle-main-window {{
    background-color: {theme["background"]};
    color: {theme["foreground"]};
}}

/* Titles */
.title-2 {{
    font-weight: bold;
    font-size: 1.2em;
    margin-bottom: 10px;
    color: {theme["accent"]};
}}

/* Dim Labels */
.dim-label {{
    opacity: 0.7;
    font-size: 0.9em;
}}

/* Flat Entries */
entry.flat {{
    min-height: 0;
    padding: 2px;
    background-color: transparent;
    border: none;
    box-shadow: none;
    font-weight: bold;
}}

/* Standard Widgets */
#wallshuffle-main-window GtkLabel {{
    color: {theme["foreground"]};
}}

#wallshuffle-main-window GtkButton {{
    background-color: {theme["accent"]};
    color: {theme.get("button_text", theme["foreground"])};
    border-radius: 6px;
    padding: 4px 12px;
    border: none;
    font-weight: bold;
}}

#wallshuffle-main-window GtkButton:hover {{
    opacity: 0.9;
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}}

#wallshuffle-main-window GtkButton:active {{
    opacity: 0.8;
}}

/* Suggested Action Button (Save) */
.suggested-action {{
    background-color: {theme.get("accent_secondary", theme["accent"])};
    color: #ffffff;
}}

#wallshuffle-main-window GtkEntry {{
    background-color: rgba(255, 255, 255, 0.05);
    color: {theme["foreground"]};
    border: 1px solid {theme["accent"]};
    border-radius: 4px;
    padding: 4px;
}}

#wallshuffle-main-window GtkComboBox GtkEntry {{
    background-color: transparent;
    border: none;
}}

/* Hero Section Preview Box styling (if we could target it by ID or class) */
/* Assuming we didn't add a specific class to the box itself, ensuring generic polish */

"""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css.encode("utf-8"))
        return css_provider
