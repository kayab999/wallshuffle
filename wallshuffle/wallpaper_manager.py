import hashlib
import json
import logging
import os
import shutil
import subprocess
import threading

import gi
from PIL import Image

gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib
from .constants import GNOME_COMPAT

class WallpaperManager:
    # Desktop environment categories
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

    def cleanup_temp_files(self):
        """Removes temporary files to prevent accumulation."""
        temp_dir = os.path.join(os.path.expanduser("~"), ".config", "wallshuffle", "temp")
        if os.path.exists(temp_dir):
            try:
                # Remove the entire directory and recreate it to ensure it's empty
                shutil.rmtree(temp_dir)
                os.makedirs(temp_dir, exist_ok=True)
                self.logger.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                self.logger.error(f"Failed to clean up temporary directory: {e}")

    def get_desktop_environment(self):
        """Detects the current desktop environment using environment variables and process inspection."""
        xdg_current_desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        desktop_session = os.environ.get("DESKTOP_SESSION", "").lower()

        self.logger.debug(f"Detecting DE: XDG_CURRENT_DESKTOP='{xdg_current_desktop}', DESKTOP_SESSION='{desktop_session}'")

        # 1. Check XDG_CURRENT_DESKTOP
        if xdg_current_desktop:
            for variant in GNOME_COMPAT:
                if variant in xdg_current_desktop:
                    return variant
            if "kde" in xdg_current_desktop:
                return "kde"
            elif "xfce" in xdg_current_desktop:
                return "xfce"

        # 2. Check DESKTOP_SESSION
        if desktop_session:
            for variant in GNOME_COMPAT:
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
                    if subprocess.run(["pgrep", "-x", proc_name], capture_output=True, timeout=2).returncode == 0:
                        return de_name
                except subprocess.CalledProcessError:
                    # Process not running (expected, continue checking)
                    continue
                except subprocess.TimeoutExpired:
                    self.logger.warning(f"DE detection timeout for process '{proc_name}'")
                    continue
                except (FileNotFoundError, PermissionError) as e:
                    self.logger.warning(f"DE detection failed for '{proc_name}': {e}")
                    continue
                except Exception as e:
                    # Unexpected error - log it for debugging
                    self.logger.debug(f"Unexpected error checking process '{proc_name}': {e}")
                    continue
        else:
            self.logger.warning("pgrep not found. Cannot detect DE via process inspection.")

        # If we reach here, we couldn't detect DE via any method
        self.logger.warning("Could not detect desktop environment via any method. Returning 'unknown'.")
        return "unknown"

    def _run_subprocess(self, command, description="", timeout=10):
        """Helper to run shell commands safely."""
        try:
            self.logger.debug(f"Exec: {' '.join(command)} ({description})")
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)
            return True
        except subprocess.TimeoutExpired:
            self.logger.error(f"Failed {description}: Timeout ({timeout}s)")
            return False
        except Exception as e:
            self.logger.error(f"Failed {description}: {e}")
            return False

    def get_monitor_info(self):
        """Returns geometry for all detected monitors (Thread-Safe)."""
        # If we are already on the main thread, run directly
        if threading.current_thread() is threading.main_thread():
            return self._get_monitor_info_main()

        # Otherwise, schedule on main thread and wait
        result_container = {"info": []}
        event = threading.Event()

        def callback():
            try:
                result_container["info"] = self._get_monitor_info_main()
            except Exception as e:
                self.logger.error(f"Error getting monitor info on main thread: {e}")
            finally:
                event.set()
            return False

        GLib.idle_add(callback)
        if not event.wait(timeout=2.0):
            self.logger.warning("Timeout waiting for monitor info from main thread. Falling back to xrandr.")
            return self._get_monitor_info_xrandr()

        return result_container["info"]

    def _get_monitor_info_xrandr(self):
        """Fallback monitor detection via xrandr (works without GLib MainLoop)."""
        monitor_info = []
        if not shutil.which("xrandr"):
            self.logger.warning("xrandr not found, cannot detect monitors in headless mode.")
            return monitor_info

        try:
            import re
            result = subprocess.run(["xrandr", "--query"], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                pattern = re.compile(r" connected (?:primary )?(\d+)x(\d+)\+(\d+)\+(\d+)")
                for idx, line in enumerate(result.stdout.splitlines()):
                    match = pattern.search(line)
                    if match:
                        w, h, x, y = map(int, match.groups())
                        monitor_info.append({
                            "name": f"Monitor-{idx}",
                            "width": w, "height": h,
                            "x": x, "y": y,
                        })
                self.logger.debug(f"xrandr fallback detected monitors: {monitor_info}")
            else:
                self.logger.error(f"xrandr query failed with code {result.returncode}")
        except Exception as e:
            self.logger.error(f"xrandr fallback failed: {e}")

        return monitor_info

    def _get_monitor_info_main(self):
        """Internal method to get monitor info using Gdk (Must run on Main Thread)."""
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

            # Ensure RGB for JPEG
            if composite_img.mode == "RGBA":
                composite_img = composite_img.convert("RGB")

            temp_dir = os.path.join(os.path.expanduser("~"), ".config", "wallshuffle", "temp")
            os.makedirs(temp_dir, exist_ok=True)
            path = os.path.join(temp_dir, "composite_wallpaper.jpg")
            composite_img.save(path)
            return path
        except Exception as e:
            self.logger.error(f"Composite image failed: {e}")
            return image_path

    def create_multi_monitor_composite(self, image_paths, monitor_info, mode="zoom"):
        """
        Creates a single large image by stitching multiple images together
        based on the monitor layout and the selected scaling mode.
        """
        if not monitor_info or not image_paths:
            return image_paths[0] if image_paths else None

        try:
            # Determine canvas size (bounding box)
            min_x = min(m["x"] for m in monitor_info)
            min_y = min(m["y"] for m in monitor_info)
            max_x = max(m["x"] + m["width"] for m in monitor_info)
            max_y = max(m["y"] + m["height"] for m in monitor_info)

            total_width = max_x - min_x
            total_height = max_y - min_y

            # Create blank canvas
            canvas = Image.new("RGB", (total_width, total_height), (0, 0, 0))

            for i, monitor in enumerate(monitor_info):
                # Cycle through images if fewer than monitors
                img_path = image_paths[i % len(image_paths)]

                try:
                    with Image.open(img_path) as img:
                        target_w = monitor["width"]
                        target_h = monitor["height"]

                        img_ratio = img.width / img.height
                        target_ratio = target_w / target_h

                        # Apply scaling based on mode
                        if mode == "zoom":
                            # Zoom/Cover: Resize to fill, crop excess

                            if img_ratio > target_ratio:
                                new_height = target_h
                                new_width = int(new_height * img_ratio)
                                resized = img.resize((new_width, new_height), Image.LANCZOS)
                                left = (new_width - target_w) // 2
                                final_img = resized.crop((left, 0, left + target_w, target_h))
                            else:
                                new_width = target_w
                                new_height = int(new_width / img_ratio)
                                resized = img.resize((new_width, new_height), Image.LANCZOS)
                                top = (new_height - target_h) // 2
                                final_img = resized.crop((0, top, target_w, top + target_h))

                        elif mode == "scaled":
                            # Scaled/Fit: Resize to fit inside, black bars
                            if img_ratio > target_ratio:
                                # Wider than screen: Fit Width
                                new_width = target_w
                                new_height = int(new_width / img_ratio)
                            else:
                                # Taller than screen: Fit Height
                                new_height = target_h
                                new_width = int(new_height * img_ratio)

                            resized = img.resize((new_width, new_height), Image.LANCZOS)

                            # Create black background for this monitor patch
                            bg = Image.new("RGB", (target_w, target_h), (0, 0, 0))
                            # Center the resized image
                            offset_x = (target_w - new_width) // 2
                            offset_y = (target_h - new_height) // 2
                            bg.paste(resized, (offset_x, offset_y))
                            final_img = bg

                        elif mode == "stretched":
                            # Stretched: Resize to exact dimensions (distorted)
                            final_img = img.resize((target_w, target_h), Image.LANCZOS)

                        elif mode == "centered":
                            # Centered: No resizing, just crop or center
                            # Create black background
                            bg = Image.new("RGB", (target_w, target_h), (0, 0, 0))
                            # Calculate offset to center the original image
                            offset_x = (target_w - img.width) // 2
                            offset_y = (target_h - img.height) // 2
                            bg.paste(img, (offset_x, offset_y))
                            final_img = bg # If image is larger, paste creates crop effect naturally?
                            # PIL paste handles larger images by cropping them, but only if we paste onto a canvas
                            # However, if offset is negative (image larger), we need to crop the image first
                            if offset_x < 0 or offset_y < 0:
                                # Logic to crop center of image to fit monitor
                                # But standard "center" usually just shows center pixels.
                                # Let's stick to simple paste, but we might need to crop if image > monitor
                                # Actually `paste` does not crop automatically in a way that centers.
                                # It just pastes top-left at the given coordinate.
                                # If coordinate is negative, it pastes off-canvas.
                                pass
                            # Re-doing Center logic to be robust:
                            bg = Image.new("RGB", (target_w, target_h), (0, 0, 0))

                            # Caclulate crop from source image if it's larger than target
                            if img.width > target_w:
                                left = (img.width - target_w) // 2
                                img_crop_w = img.crop((left, 0, left + target_w, img.height))
                            else:
                                img_crop_w = img

                            if img_crop_w.height > target_h:
                                top = (img_crop_w.height - target_h) // 2
                                final_img_content = img_crop_w.crop((0, top, img_crop_w.width, top + target_h))
                            else:
                                final_img_content = img_crop_w

                            # Calculate paste position for the (potentially cropped) image
                            paste_x = (target_w - final_img_content.width) // 2
                            paste_y = (target_h - final_img_content.height) // 2
                            bg.paste(final_img_content, (paste_x, paste_y))
                            final_img = bg

                        elif mode == "spanned":
                             # Spanned on a per-monitor basis acts like zoom/cover usually
                             final_img = img.resize((target_w, target_h), Image.LANCZOS) # Fallback to stretch/zoom?
                             # Actually spanned usually means one big image across all.
                             # But here we are in "Different image on each monitor" flow.
                             # So "spanned" doesn't make sense per monitor. Treat as zoom.
                             # Reuse Zoom logic (condensed for brevity, or just call it recursively? No, infinite loop risk)
                             # Just duplicate zoom logic or fallthrough to zoom default
                             # Let's fallback to zoom
                             img_ratio = img.width / img.height
                             target_ratio = target_w / target_h
                             if img_ratio > target_ratio:
                                 new_height = target_h
                                 new_width = int(new_height * img_ratio)
                                 resized = img.resize((new_width, new_height), Image.LANCZOS)
                                 left = (new_width - target_w) // 2
                                 final_img = resized.crop((left, 0, left + target_w, target_h))
                             else:
                                 new_width = target_w
                                 new_height = int(new_width / img_ratio)
                                 resized = img.resize((new_width, new_height), Image.LANCZOS)
                                 top = (new_height - target_h) // 2
                                 final_img = resized.crop((0, top, target_w, top + target_h))
                        else:
                            # Default to zoom
                            img_ratio = img.width / img.height
                            target_ratio = target_w / target_h
                            if img_ratio > target_ratio:
                                new_height = target_h
                                new_width = int(new_height * img_ratio)
                                resized = img.resize((new_width, new_height), Image.LANCZOS)
                                left = (new_width - target_w) // 2
                                final_img = resized.crop((left, 0, left + target_w, target_h))
                            else:
                                new_width = target_w
                                new_height = int(new_width / img_ratio)
                                resized = img.resize((new_width, new_height), Image.LANCZOS)
                                top = (new_height - target_h) // 2
                                final_img = resized.crop((0, top, target_w, top + target_h))

                        # Paste into canvas
                        paste_x = monitor["x"] - min_x
                        paste_y = monitor["y"] - min_y
                        canvas.paste(final_img, (paste_x, paste_y))

                except Exception as e:
                    self.logger.error(f"Error processing image {img_path} for monitor {monitor['name']}: {e}")
                    # Continue to next monitor, leaving black hole if failed

            temp_dir = os.path.join(os.path.expanduser("~"), ".config", "wallshuffle", "temp")
            os.makedirs(temp_dir, exist_ok=True)
            path = os.path.join(temp_dir, "stitched_wallpaper.jpg")
            canvas.save(path, quality=95)
            self.logger.info(f"Created stitched wallpaper: {path} ({total_width}x{total_height}) with mode '{mode}'")
            return path

        except Exception as e:
            self.logger.error(f"Stitching failed: {e}")
            return image_paths[0]

    def apply_desktop_settings(self, mode, image_paths=None, background_color=None):
        """Dispatcher for different DE implementations."""
        if not image_paths:
            return False

        if self.desktop_environment in GNOME_COMPAT:
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

        # Determine strict mode or composite
        final_path = image_paths[0]

        # If we have multiple images, we need to stitch them for GNOME
        # unless mode is explicitly spanned and we only have 1 (handled in core.py)
        # Check if we actually need stitching (more than 1 distinct path)
        if len(image_paths) > 1:
            monitor_info = self.get_monitor_info()
            if len(monitor_info) > 1:
                self.logger.info(f"Multiple images and monitors detected for GNOME. Using Virtual Stitching with mode '{mode}'.")
                final_path = self.create_multi_monitor_composite(image_paths, monitor_info, mode)
                mode = "spanned" # Force spanned to display the stitched image correctly

        # Mode & Color
        self._run_subprocess(["gsettings", "set", schema, "picture-options", mode], "set mode")
        if background_color:
            self._run_subprocess(["gsettings", "set", schema, "color-shading-type", "solid"], "set solid shading")
            self._run_subprocess(["gsettings", "set", schema, "primary-color", background_color], "set bg color")

        # Image URI
        # Copy to local cache to ensure accessibility (fixes issues with /mnt/ paths)
        try:
            cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "wallshuffle")
            os.makedirs(cache_dir, exist_ok=True)

            src = final_path
            # Use a hash of the full path + extension to ensure uniqueness
            path_hash = hashlib.sha256(src.encode()).hexdigest()[:12]
            ext = os.path.splitext(src)[1]
            filename = f"wallpaper_{path_hash}{ext}"

            dst = os.path.join(cache_dir, filename)

            # Only copy (or symlink) if source and dest are different
            if os.path.abspath(src) != os.path.abspath(dst):
                # Remove existing cache file/link if it exists
                if os.path.exists(dst) or os.path.islink(dst):
                    os.remove(dst)

                # Create a symbolic link instead of copying to save space (user requested "hyperlink")
                try:
                    os.symlink(src, dst)
                    self.logger.info(f"Created symlink: {dst} -> {src}")
                except OSError as e:
                    self.logger.warning(f"Failed to create symlink ({e}), falling back to copy.")
                    shutil.copy2(src, dst)
                    self.logger.info(f"Cached image (copy) to: {dst}")

                local_path = dst
            else:
                local_path = src
        except Exception as e:
            self.logger.warning(f"Failed to cache image, using original path: {e}")
            local_path = final_path

        uri = f"file://{local_path}"
        self._run_subprocess(["gsettings", "set", schema, "picture-uri", uri], "set uri")
        self._run_subprocess(["gsettings", "set", schema, "picture-uri-dark", uri], "set dark uri")

        return True

    def _generate_kde_script(self, image_paths, mode):
        """Generates the JavaScript payload for KDE Plasma."""
        fill_mode = self.KDE_FILL_MODES.get(mode, 1) # Default to Fit (Scaled)

        # Ensure image_paths is a list
        if isinstance(image_paths, str):
            image_paths = [image_paths]

        # Prepare js array of paths
        # safe_paths = [json.dumps(f"file://{p}") for p in image_paths]
        # But we want to assign them sequentially to desktops.

        # We can embed the paths array in JS and pick by index.
        js_paths_array = "[" + ", ".join([json.dumps(f"file://{p}") for p in image_paths]) + "]"

        return f"""
            var allDesktops = desktops();
            var images = {js_paths_array};
            for (var i=0; i<allDesktops.length; i++) {{
                var d = allDesktops[i];
                d.wallpaperPlugin = 'org.kde.image';
                d.currentConfigGroup = Array('Wallpaper', 'org.kde.image', 'General');

                // Select image based on desktop index (cycle if fewer images)
                var img = images[i % images.length];

                d.writeConfig('Image', img);
                d.writeConfig('FillMode', {fill_mode});
            }}
        """

    def apply_kde_settings(self, mode, image_paths=None, background_color=None):
        if not image_paths:
            return True

        script = self._generate_kde_script(image_paths, mode)
        return self._run_subprocess([
            "dbus-send", "--session", "--dest=org.kde.plasmashell", "--type=method_call",
            "/PlasmaShell", "org.kde.PlasmaShell.evaluateScript", f"string:{script}"
        ], "kde script")

    def apply_xfce_settings(self, mode, image_paths=None, background_color=None):
        if not image_paths:
            return True

        style = self.XFCE_STYLES.get(mode, "5") # Default to Zoomed

        try:
            # Use run directly for query to get output, but with validation
            props_result = subprocess.run(
                ["xfconf-query", "-c", "xfce4-desktop", "-l"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if props_result.returncode != 0:
                self.logger.warning(f"xfconf-query list failed: {props_result.stderr}")
                return False

            props = props_result.stdout.splitlines()

            # Find all last-image properties
            image_props = [p for p in props if "last-image" in p]
            # Find all image-style properties
            style_props = [p for p in props if "image-style" in p]

            # Sort them to hope they match monitor order (Monitor-0, Monitor-1...)
            # Standard generic sort usually handles monitor0, monitor1 fine.
            image_props.sort()

            for i, prop in enumerate(image_props):
                img_path = image_paths[i % len(image_paths)]
                self._run_subprocess(["xfconf-query", "-c", "xfce4-desktop", "-p", prop, "-s", img_path], f"xfce image {i}")

            for prop in style_props:
                 self._run_subprocess(["xfconf-query", "-c", "xfce4-desktop", "-p", prop, "-s", style], "xfce style")

            return True
        except subprocess.TimeoutExpired:
            self.logger.error("XFCE settings failed: Timeout querying xfconf")
            return False
        except Exception as e:
            self.logger.error(f"XFCE settings failed: {e}")
            return False
