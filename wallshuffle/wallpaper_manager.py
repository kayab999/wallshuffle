import logging
import os
import shlex
import shutil
import subprocess

import gi
from PIL import Image, UnidentifiedImageError

gi.require_version("Gdk", "3.0")
from gi.repository import Gdk


class WallpaperManager:
    # Desktop environment categories
    GNOME_COMPAT = [
        "gnome",
        "unity",
        "ubuntu",
        "cinnamon",
        "budgie",
        "mate",
        "pantheon",
        "pop",
    ]

    # Mappings for scaling modes per DE
    # GNOME modes: 'none', 'wallpaper', 'centered', 'scaled', 'stretched', 'zoom', 'spanned'
    # KDE FillMode: 0:Stretch, 1:Fit, 2:Zoom, 3:Tile, 4:Spanned, 5:Centered
    # XFCE Style: 0:None, 1:Centered, 2:Tiled, 3:Stretched, 4:Scaled, 5:Zoomed, 6:Spanning

    KDE_FILL_MODES = {
        "zoom": 2,
        "scaled": 1,
        "centered": 5,
        "spanned": 4,
        "stretched": 0,
    }

    XFCE_STYLES = {
        "centered": "1",
        "stretched": "3",
        "scaled": "4",
        "zoom": "5",
        "spanned": "6",
    }

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.desktop_environment = self.get_desktop_environment()
        self._check_system_dependencies()

    def _check_system_dependencies(self):
        """Verifies that critical system executables are available."""
        required_tools = {
            "gnome": ["gsettings"],
            "unity": ["gsettings"],
            "cinnamon": ["gsettings"],
            "mate": ["gsettings"],
            "budgie": ["gsettings"],
            "kde": ["dbus-send"],
            "xfce": ["xfconf-query"],
        }

        tools_to_check = required_tools.get(self.desktop_environment, [])

        if shutil.which("systemctl"):
            self.logger.debug("systemctl found.")
        else:
            self.logger.warning("systemctl not found. Scheduling features will not work.")

        for tool in tools_to_check:
            if not shutil.which(tool):
                self.logger.critical(f"CRITICAL: Required system tool '{tool}' not found! Wallpaper changing will likely fail.")
            else:
                self.logger.debug(f"Found required tool: {tool}")

    def get_desktop_environment(self):
        """Detects the current desktop environment using environment variables and process inspection."""
        xdg_current_desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        desktop_session = os.environ.get("DESKTOP_SESSION", "").lower()

        self.logger.debug(f"Detecting DE: XDG_CURRENT_DESKTOP='{xdg_current_desktop}', DESKTOP_SESSION='{desktop_session}'")

        # 1. Check XDG_CURRENT_DESKTOP
        if xdg_current_desktop:
            for variant in self.GNOME_COMPAT:
                if variant in xdg_current_desktop:
                    return variant
            if "kde" in xdg_current_desktop:
                return "kde"
            elif "xfce" in xdg_current_desktop:
                return "xfce"

        # 2. Check DESKTOP_SESSION
        if desktop_session:
            for variant in self.GNOME_COMPAT:
                if variant in desktop_session:
                    return variant
            if "kde" in desktop_session:
                return "kde"
            elif "xfce" in desktop_session:
                return "xfce"

        # 3. Fallback: Check running processes
        if shutil.which("pgrep"):
            process_map = {
                "gnome-shell": "gnome",
                "plasmashell": "kde",
                "xfce4-session": "xfce",
                "mate-session": "mate",
                "cinnamon-session": "cinnamon",
                "budgie-wm": "budgie",
            }
            for proc_name, de_name in process_map.items():
                try:
                    if subprocess.run(["pgrep", "-x", proc_name], capture_output=True).returncode == 0:
                        return de_name
                except Exception:
                    continue

        return "unknown"

    def _run_subprocess(self, command, description="", timeout=10):
        """Helper to run shell commands safely."""
        try:
            self.logger.debug(f"Exec: {' '.join(command)} ({description})")
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)
            return True
        except Exception as e:
            self.logger.error(f"Failed {description}: {e}")
            return False

    def get_monitor_info(self):
        """Returns geometry for all detected monitors."""
        monitor_info = []
        try:
            display = Gdk.Display.get_default()
            if not display:
                display = Gdk.Display.open_default_libgtk_only()
            
            if not display:
                return monitor_info

            for i in range(display.get_n_monitors()):
                geom = display.get_monitor(i).get_geometry()
                monitor_info.append({
                    "name": f"Monitor-{i}",
                    "width": geom.width, "height": geom.height,
                    "x": geom.x, "y": geom.y,
                })
        except Exception as e:
            self.logger.error(f"Gdk monitor detection failed: {e}")
        return monitor_info

    def create_composite_image(self, image_path, monitor_info):
        """Creates a single large image spanning all monitors."""
        if not monitor_info:
            return image_path

        max_x = max(m["x"] + m["width"] for m in monitor_info)
        max_y = max(m["y"] + m["height"] for m in monitor_info)

        if max_x == 0 or max_y == 0:
            return image_path

        try:
            original_img = Image.open(image_path)
            target_aspect = max_x / max_y
            original_aspect = original_img.width / original_img.height

            if original_aspect > target_aspect:
                new_width = int(target_aspect * original_img.height)
                offset = (original_img.width - new_width) // 2
                img_cropped = original_img.crop((offset, 0, offset + new_width, original_img.height))
            else:
                new_height = int(original_img.width / target_aspect)
                offset = (original_img.height - new_height) // 2
                img_cropped = original_img.crop((0, offset, original_img.width, offset + new_height))

            composite_img = img_cropped.resize((max_x, max_y), Image.LANCZOS)
            
            temp_dir = os.path.join(os.path.expanduser("~"), ".config", "wallshuffle", "temp")
            os.makedirs(temp_dir, exist_ok=True)
            path = os.path.join(temp_dir, "composite_wallpaper.jpg")
            composite_img.save(path)
            return path
        except Exception as e:
            self.logger.error(f"Composite image failed: {e}")
            return image_path

    def apply_desktop_settings(self, mode, image_paths=None, background_color=None):
        """Dispatcher for different DE implementations."""
        if self.desktop_environment in self.GNOME_COMPAT:
            return self.apply_gnome_settings(mode, image_paths, background_color)
        elif self.desktop_environment == "kde":
            return self.apply_kde_settings(mode, image_paths, background_color)
        elif self.desktop_environment == "xfce":
            return self.apply_xfce_settings(mode, image_paths, background_color)
        
        self.logger.warning(f"DE '{self.desktop_environment}' not supported.")
        return False

    def _get_gnome_schema(self):
        """Returns the appropriate GSettings schema for the current DE."""
        if self.desktop_environment == "mate":
            return "org.mate.background"
        if self.desktop_environment == "cinnamon":
            return "org.cinnamon.desktop.background"
        return "org.gnome.desktop.background"

    def apply_gnome_settings(self, mode, image_paths=None, background_color=None):
        schema = self._get_gnome_schema()
        
        # Mode & Color
        self._run_subprocess(["gsettings", "set", schema, "picture-options", mode], "set mode")
        if background_color:
            self._run_subprocess(["gsettings", "set", schema, "color-shading-type", "solid"], "set solid shading")
            self._run_subprocess(["gsettings", "set", schema, "primary-color", background_color], "set bg color")
        
        # Image URI
        if image_paths:
            uri = f"file://{image_paths[0]}"
            self._run_subprocess(["gsettings", "set", schema, "picture-uri", uri], "set uri")
            self._run_subprocess(["gsettings", "set", schema, "picture-uri-dark", uri], "set dark uri")
        
        return True

    def apply_kde_settings(self, mode, image_paths=None, background_color=None):
        if not image_paths:
            return True
            
        fill_mode = self.KDE_FILL_MODES.get(mode, 1) # Default to Fit (Scaled)
        safe_path = shlex.quote(f"file://{image_paths[0]}")

        script = f"""
            var allDesktops = desktops();
            for (var i=0; i<allDesktops.length; i++) {{
                var d = allDesktops[i];
                d.wallpaperPlugin = 'org.kde.image';
                d.currentConfigGroup = Array('Wallpaper', 'org.kde.image', 'General');
                d.writeConfig('Image', {safe_path});
                d.writeConfig('FillMode', {fill_mode});
            }}
        """
        return self._run_subprocess([
            "dbus-send", "--session", "--dest=org.kde.plasmashell", "--type=method_call",
            "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript", script
        ], "kde script")

    def apply_xfce_settings(self, mode, image_paths=None, background_color=None):
        if not image_paths:
            return True

        style = self.XFCE_STYLES.get(mode, "5") # Default to Zoomed
        
        try:
            props = subprocess.run(["xfconf-query", "-c", "xfce4-desktop", "-l"], 
                                 capture_output=True, text=True, check=True).stdout
            for prop in props.splitlines():
                if "last-image" in prop:
                    self._run_subprocess(["xfconf-query", "-c", "xfce4-desktop", "-p", prop, "-s", image_paths[0]], "xfce image")
                if "image-style" in prop:
                    self._run_subprocess(["xfconf-query", "-c", "xfce4-desktop", "-p", prop, "-s", style], "xfce style")
            return True
        except Exception as e:
            self.logger.error(f"XFCE settings failed: {e}")
            return False