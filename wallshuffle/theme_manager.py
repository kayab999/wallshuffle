# ruff: noqa: E402
import datetime
import logging
import os

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
            logging.info(f"Loaded saved theme: {self.current_theme_name}")
        else:
            # If no theme is saved (first run) or saved theme is invalid, detect distro
            distro_id, distro_like = self.detect_distro()

            # Smart mapping logic
            theme_key = "Default"
            possible_ids = [distro_id, distro_like] if distro_like else [distro_id]

            for d_id in filter(None, possible_ids):
                d_id = d_id.lower()
                # Direct match or alias
                found_key = next((k for k in THEMES.keys() if k.lower() == d_id or (d_id == "linuxmint" and k == "LinuxMint")), None)
                if found_key:
                    theme_key = found_key
                    break

            self.current_theme_name = theme_key
            logging.info(f"Auto-detected theme: {self.current_theme_name} (ID: {distro_id}, LIKE: {distro_like})")
            # Save the auto-detected theme so it persists
            self.set_theme_name(self.current_theme_name)

    def detect_distro(self):
        """Detects the Linux distribution ID and ID_LIKE from /etc/os-release."""
        distro_id = None
        distro_like = None
        try:
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release") as f:
                    for line in f:
                        if line.startswith("ID="):
                            distro_id = line.split("=")[1].strip().strip('"')
                        elif line.startswith("ID_LIKE="):
                            distro_like = line.split("=")[1].strip().strip('"')
            return distro_id, distro_like
        except Exception as e:
            logging.error(f"Error reading /etc/os-release: {e}")
        return None, None

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
* {{
    transition: background 200ms ease-in-out, border-color 200ms ease-in-out, box-shadow 200ms ease-in-out;
}}

#wallshuffle-main-window {{
    background-color: {theme["background"]};
    color: {theme["foreground"]};
    font-family: sans-serif;
}}

/* Titles */
#wallshuffle-main-window .title-2 {{
    font-weight: bold;
    font-size: 1.3em;
    margin-bottom: 12px;
    color: {theme["accent"]};
}}

/* Dim Labels */
#wallshuffle-main-window .dim-label {{
    opacity: 0.65;
    font-size: 0.9em;
}}

/* Cards (Gtk.Frame) */
#wallshuffle-main-window frame, #wallshuffle-main-window .card {{
    background-color: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
}}

#wallshuffle-main-window frame > border {{
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
}}

/* Flat Entries */
#wallshuffle-main-window entry.flat {{
    min-height: 0;
    padding: 4px;
    background-color: transparent;
    border: none;
    box-shadow: none;
    font-weight: bold;
}}

/* Standard Widgets */
#wallshuffle-main-window GtkLabel {{
    color: {theme["foreground"]};
}}

/* Button System */
#wallshuffle-main-window GtkButton, #wallshuffle-main-window button {{
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
    transition: all 200ms ease-in-out;
}}

#wallshuffle-main-window .primary-button,
#wallshuffle-main-window .suggested-action {{
    background-color: {theme["accent"]};
    color: {theme.get("button_text", "#FFFFFF")};
    border: none;
    font-weight: bold;
}}

#wallshuffle-main-window .primary-button:hover,
#wallshuffle-main-window .suggested-action:hover {{
    background-color: {theme.get("hover", theme["accent"])};
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
}}

#wallshuffle-main-window .primary-button:active,
#wallshuffle-main-window .suggested-action:active {{
    opacity: 0.8;
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}}

#wallshuffle-main-window .secondary-button {{
    background-color: rgba(255, 255, 255, 0.1);
    color: {theme["foreground"]};
    border: 1px solid rgba(255, 255, 255, 0.2);
}}

#wallshuffle-main-window .secondary-button:hover {{
    background-color: rgba(255, 255, 255, 0.15);
}}

#wallshuffle-main-window .danger-button {{
    background-color: #e53935;
    color: #ffffff;
    border: none;
}}

#wallshuffle-main-window .danger-button:hover {{
    background-color: #d32f2f;
}}

#wallshuffle-main-window GtkEntry {{
    background-color: rgba(0, 0, 0, 0.2);
    color: {theme["foreground"]};
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 6px;
}}

#wallshuffle-main-window GtkEntry:focus {{
    border-color: {theme["accent"]};
}}

#wallshuffle-main-window GtkComboBox GtkEntry {{
    background-color: transparent;
    border: none;
}}
"""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css.encode("utf-8"))
        return css_provider
