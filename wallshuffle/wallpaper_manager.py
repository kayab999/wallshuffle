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

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.desktop_environment = self.get_desktop_environment()
        self._check_system_dependencies()

    def _check_system_dependencies(self):
        """
        Verifies that critical system executables are available.
        Logs warnings if they are missing.
        """
        required_tools = {
            "gnome": ["gsettings"],
            "unity": ["gsettings"],
            "cinnamon": ["gsettings"],
            "mate": ["gsettings"],
            "budgie": ["gsettings"],
            "kde": ["dbus-send"],
            "xfce": ["xfconf-query"],
        }

        # Check tools relevant to current DE
        tools_to_check = required_tools.get(self.desktop_environment, [])
        
        # Always check for systemd integration tools if possible
        if shutil.which("systemctl"):
             self.logger.debug("systemctl found.")
        else:
             self.logger.warning("systemctl not found. Scheduling features will not work.")

        for tool in tools_to_check:
            if not shutil.which(tool):
                self.logger.critical(
                    f"CRITICAL: Required system tool '{tool}' not found! "
                    f"Wallpaper changing will likely fail on {self.desktop_environment}."
                )
            else:
                self.logger.debug(f"Found required tool: {tool}")

    def get_desktop_environment(self):
        """Detects the current desktop environment."""
        xdg_current_desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        desktop_session = os.environ.get("DESKTOP_SESSION", "").lower()

        self.logger.debug("Attempting to detect Desktop Environment:")
        self.logger.debug(f"  XDG_CURRENT_DESKTOP: '{xdg_current_desktop}'")
        self.logger.debug(f"  DESKTOP_SESSION: '{desktop_session}'")

        if xdg_current_desktop:
            for variant in self.GNOME_COMPAT:
                if variant in xdg_current_desktop:
                    self.logger.debug(f"  Detected '{variant}' from XDG_CURRENT_DESKTOP.")
                    return variant
            if "kde" in xdg_current_desktop:
                self.logger.debug("  Detected 'kde' from XDG_CURRENT_DESKTOP.")
                return "kde"
            elif "xfce" in xdg_current_desktop:
                self.logger.debug("  Detected 'xfce' from XDG_CURRENT_DESKTOP.")
                return "xfce"

        if desktop_session:
            for variant in self.GNOME_COMPAT:
                if variant in desktop_session:
                    self.logger.debug(f"  Detected '{variant}' from DESKTOP_SESSION.")
                    return variant
            if "kde" in desktop_session:
                self.logger.debug("  Detected 'kde' from DESKTOP_SESSION.")
                return "kde"
            elif "xfce" in desktop_session:
                self.logger.debug("  Detected 'xfce' from DESKTOP_SESSION.")
                return "xfce"

        # Fallback: Check running processes
        self.logger.debug("Environment variables failed. Checking running processes...")
        try:
            # simple `ps -A` check or iterating /proc. `pgrep` is safer if available.
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
                    res = subprocess.run(["pgrep", "-x", proc_name], capture_output=True)
                    if res.returncode == 0:
                        self.logger.debug(f"  Detected '{de_name}' via process '{proc_name}'.")
                        return de_name
        except Exception as e:
            self.logger.warning(f"Process detection failed: {e}")

        self.logger.info(
            f"Could not detect a supported Desktop Environment. XDG_CURRENT_DESKTOP='{xdg_current_desktop}', DESKTOP_SESSION='{desktop_session}'. Returning 'unknown'."
        )
        return "unknown"

    def _run_subprocess(self, command, description="", timeout=10):
        """
        Run a subprocess command with timeout.

        Args:
            command: List of command arguments
            description: Human-readable description for logging
            timeout: Maximum time in seconds to wait (default: 10)

        Returns:
            True if command succeeded, False otherwise
        """
        try:
            self.logger.debug(
                f"Running command: {' '.join(command)} (Description: {description}, Timeout: {timeout}s)"
            )
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)
            return True
        except subprocess.TimeoutExpired:
            self.logger.error(
                f"Command timed out after {timeout}s ({description}): {' '.join(command)}"
            )
            return False
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error {description}: {e.stderr}")
            return False
        except FileNotFoundError:
            self.logger.error(
                f"Error: Command not found: {command[0]} (Description: {description})"
            )
            return False
        except Exception as e:
            self.logger.critical(
                f"An unhandled error occurred in _run_subprocess for {description}: {e}",
                exc_info=True,
            )
            return False

    def get_monitor_info(self):
        """
        Get monitor geometry using Gdk (Wayland/X11 compatible).
        Replaces legacy xrandr parsing.
        """
        monitor_info = []
        try:
            display = Gdk.Display.get_default()
            if not display:
                # If running headless or purely CLI without session, try to open default
                try:
                    display = Gdk.Display.open_default_libgtk_only()
                except Exception:
                    pass
            
            if not display:
                self.logger.warning("Could not connect to Gdk Display. Monitor info unavailable.")
                return monitor_info

            num_monitors = display.get_n_monitors()
            self.logger.debug(f"Gdk detected {num_monitors} monitors.")

            for i in range(num_monitors):
                monitor = display.get_monitor(i)
                geometry = monitor.get_geometry()
                # Gdk 3.0 monitors don't easily expose names like 'DP-1', but we use index-based ID
                # which is sufficient for geometry calculations.
                monitor_info.append({
                    "name": f"Monitor-{i}",
                    "width": geometry.width,
                    "height": geometry.height,
                    "x": geometry.x,
                    "y": geometry.y,
                })
        except Exception as e:
            self.logger.error(f"Error getting monitor info via Gdk: {e}", exc_info=True)
            
        return monitor_info

    def create_composite_image(self, image_path, monitor_info):
        if not monitor_info:
            self.logger.warning(
                "No monitor info provided for composite image creation. Returning original image path."
            )
            return image_path

        # Calculate total canvas size
        max_x = 0
        max_y = 0
        for m in monitor_info:
            max_x = max(max_x, m["x"] + m["width"])
            max_y = max(max_y, m["y"] + m["height"])

        if max_x == 0 or max_y == 0:
            self.logger.error(
                "Could not determine a valid composite canvas size from monitor info."
            )
            return image_path

        composite_img = Image.new("RGB", (max_x, max_y), (0, 0, 0))  # Black background

        try:
            original_img = Image.open(image_path)

            # Crop the image to the aspect ratio of the target canvas to avoid distortion
            target_aspect = max_x / max_y
            original_aspect = original_img.width / original_img.height

            if original_aspect > target_aspect:
                # Original is wider than target: crop width
                new_width = int(target_aspect * original_img.height)
                offset = (original_img.width - new_width) // 2
                img_cropped = original_img.crop(
                    (offset, 0, offset + new_width, original_img.height)
                )
            else:
                # Original is taller than target: crop height
                new_height = int(original_img.width / target_aspect)
                offset = (original_img.height - new_height) // 2
                img_cropped = original_img.crop(
                    (0, offset, original_img.width, offset + new_height)
                )

            # Resize and paste the cropped image
            resized_img = img_cropped.resize((max_x, max_y), Image.LANCZOS)
            composite_img.paste(resized_img, (0, 0))

            temp_dir = os.path.join(os.path.expanduser("~"), ".config", "wallshuffle", "temp")
            os.makedirs(temp_dir, exist_ok=True)
            composite_image_path = os.path.join(temp_dir, "composite_wallpaper.jpg")
            composite_img.save(composite_image_path)
            return composite_image_path
        except FileNotFoundError:
            self.logger.error(f"Image file not found for composite image creation: {image_path}")
            return image_path
        except UnidentifiedImageError:
            self.logger.error(
                f"Cannot identify image file for composite image creation: {image_path}"
            )
            return image_path
        except IOError as e:
            self.logger.error(f"File I/O error while creating composite image: {e}")
            return image_path
        except Exception as e:
            self.logger.critical(
                f"An unhandled error occurred in create_composite_image: {e}", exc_info=True
            )
            return image_path

    def apply_desktop_settings(self, mode, image_paths=None, background_color=None):
        if self.desktop_environment in self.GNOME_COMPAT:
            return self.apply_gnome_settings(mode, image_paths, background_color)
        elif self.desktop_environment == "kde":
            return self.apply_kde_settings(mode, image_paths, background_color)
        elif self.desktop_environment == "xfce":
            return self.apply_xfce_settings(mode, image_paths, background_color)
        else:
            self.logger.warning(
                f"Desktop environment '{self.desktop_environment}' not supported for applying settings."
            )
            return False

    def apply_gnome_settings(self, mode, image_paths=None, background_color=None):
        ok = self._run_subprocess(
            ["gsettings", "set", "org.gnome.desktop.background", "picture-options", mode]
        )
        if not ok:
            return False

        if background_color:
            ok = self._run_subprocess(
                [
                    "gsettings",
                    "set",
                    "org.gnome.desktop.background",
                    "primary-color",
                    background_color,
                ]
            )
        else:
            ok = self._run_subprocess(
                ["gsettings", "set", "org.gnome.desktop.background", "primary-color", "#000000"]
            )
        if not ok:
            return False

        if image_paths:
            ok = self._run_subprocess(
                [
                    "gsettings",
                    "set",
                    "org.gnome.desktop.background",
                    "picture-uri",
                    f"file://{image_paths[0]}",
                ]
            )
            if not ok:
                return False
            ok = self._run_subprocess(
                [
                    "gsettings",
                    "set",
                    "org.gnome.desktop.background",
                    "picture-uri-dark",
                    f"file://{image_paths[0]}",
                ]
            )
            if not ok:
                return False

        return True

    def _generate_kde_script(self, image_path, mode):
        """
        Generates the JavaScript payload for KDE Plasma.
        """
        fill_mode_map = '{"zoom": 6, "scaled": 2, "centered": 1, "spanned": 4, "stretched": 0}'
        safe_image_path = shlex.quote(f"file://{image_path}")
        
        script = f"""
            var allDesktops = desktops();
            for (var i=0; i<allDesktops.length; i++) {{
                var d = allDesktops[i];
                d.wallpaperPlugin = 'org.kde.image';
                d.currentConfigGroup = Array('Wallpaper', 'org.kde.image', 'General');
                d.writeConfig('Image', {safe_image_path});
                d.writeConfig('FillMode', {fill_mode_map}["{mode}"]);
            }}
            """
        return script

    def apply_kde_settings(self, mode, image_paths=None, background_color=None):
        # This method is complex and returns True for now. Proper implementation would check dbus-send results.
        allowed_modes = ["zoom", "scaled", "centered", "spanned", "stretched"]
        if mode not in allowed_modes:
            self.logger.error(f"Invalid mode '{mode}' provided for KDE settings. Aborting.")
            return False

        if image_paths:
            script = self._generate_kde_script(image_paths[0], mode)
            return self._run_subprocess(
                [
                    "dbus-send",
                    "--session",
                    "--dest=org.kde.plasmashell",
                    "--type=method_call",
                    "/PlasmaShell",
                    "org.kde.PlasmaShell.evaluateScript",
                    script,
                ]
            )
        return True

    def apply_xfce_settings(self, mode, image_paths=None, background_color=None):
        style_map = {"centered": "1", "stretched": "3", "scaled": "4", "zoom": "5", "spanned": "5"}
        xfce_style = style_map.get(mode, "5")

        if not image_paths:
            return True

        # Getting all properties at once is fragile if one command fails.
        # We query for the specific property we need.
        try:
            properties_output = subprocess.run(
                ["xfconf-query", "-c", "xfce4-desktop", "-l"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

        if properties_output:
            for prop in properties_output.splitlines():
                if "last-image" in prop:
                    if not self._run_subprocess(
                        ["xfconf-query", "-c", "xfce4-desktop", "-p", prop, "-s", image_paths[0]]
                    ):
                        return False
                if "image-style" in prop:
                    if not self._run_subprocess(
                        ["xfconf-query", "-c", "xfce4-desktop", "-p", prop, "-s", xfce_style]
                    ):
                        return False
        return True