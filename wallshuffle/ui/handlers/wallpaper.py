import logging
import os
import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GdkPixbuf, GLib, Gtk

from ...constants import WALLPAPER_CHANGE_TIMEOUT_SEC, MultiMonitorMode
from ...core import WallpaperUpdateResult, change_wallpaper
from ...gui_helpers import show_error_dialog
from ...utils import CONFIG_DIR


class WallpaperHandlersMixin:
    def update_current_wallpaper_label(self):
        import fcntl
        import time as _time

        history_file = os.path.join(CONFIG_DIR, "history.log")
        paths = []
        if os.path.exists(history_file):
            try:
                with open(history_file, "r") as f:
                    # Shared lock with timeout: writer holds LOCK_EX 5s (utils.py).
                    # Prevents torn reads when timer + Next race.
                    start = _time.monotonic()
                    acquired = False
                    while _time.monotonic() - start < 5.0:
                        try:
                            fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
                            acquired = True
                            break
                        except (IOError, BlockingIOError, OSError):
                            _time.sleep(0.05)
                    try:
                        # Read enough lines to cover potential monitors
                        paths = [line.strip() for line in f.readlines()[:10] if line.strip()]
                    finally:
                        if acquired:
                            try:
                                fcntl.flock(f, fcntl.LOCK_UN)
                            except OSError:
                                pass
            except IOError:
                pass

        monitor_mode = self.config_manager.get_setting(self.config, "Settings", "multi_monitor_mode", MultiMonitorMode.SINGLE)

        target_count = 1
        if monitor_mode == MultiMonitorMode.DIFFERENT:
            monitor_info = self.wallpaper_manager.get_monitor_info()
            target_count = len(monitor_info) if monitor_info else 1

        display_paths = paths[:target_count]

        # Update text entry
        if not display_paths:
             self.entry_current_path.set_text("No wallpaper set")
        elif len(display_paths) == 1:
             self.entry_current_path.set_text(display_paths[0])
        else:
             self.entry_current_path.set_text(f"{len(display_paths)} images set (Multi-Monitor)")

        # Clear existing thumbnails immediately to indicate refresh
        self.preview_box.foreach(lambda w: self.preview_box.remove(w))

        if not display_paths:
            return

        def load_thumbnails(paths_to_load, generation):
            pixbufs = []
            for p in paths_to_load:
                try:
                    if os.path.exists(p) and os.path.isfile(p):
                        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(p, -1, 150, True)
                        pixbufs.append(pb)
                    else:
                        pixbufs.append(None)
                except Exception as e:
                    logging.error(f"Failed to load thumbnail for {p}: {e}")
                    pixbufs.append(None)

            def _apply():
                # Drop stale generations from rapid Next clicks.
                if getattr(self, "_thumb_generation", 0) != generation:
                    return False
                self._update_preview_box(pixbufs)
                return False

            GLib.idle_add(_apply)

        # Generation guard: only latest thumbnail batch may update the preview.
        self._thumb_generation = getattr(self, "_thumb_generation", 0) + 1
        threading.Thread(target=load_thumbnails, args=(display_paths, self._thumb_generation), daemon=True).start()

    def _update_preview_box(self, pixbufs):
        # Clear again to be safe
        self.preview_box.foreach(lambda w: self.preview_box.remove(w))

        for pb in pixbufs:
            img = Gtk.Image()
            if pb:
                img.set_from_pixbuf(pb)
            else:
                img.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)
                img.set_pixel_size(100)

            img.set_visible(True)
            self.preview_box.pack_start(img, False, False, 0)

        self.preview_box.show_all()

    def _handle_change_result(self, result: WallpaperUpdateResult, error_message: str):
        """Handles the result from change_wallpaper on the main GTK thread."""
        if result == WallpaperUpdateResult.SUCCESS:
            self.update_current_wallpaper_label()
        else:
            # Use the specific error message if provided, otherwise fall back to generic
            message = error_message if error_message else "An unknown error occurred."

            error_map = {
                WallpaperUpdateResult.NO_SOURCE_CONFIGURED: "No wallpaper source is configured. Please check your settings.",
                WallpaperUpdateResult.NO_IMAGES_FOUND: "No images were found. If using Unsplash, check your API key.",
                WallpaperUpdateResult.NETWORK_ERROR: "Network error. If using Unsplash, check your internet and API key.",
                WallpaperUpdateResult.UNSUPPORTED_DESKTOP: "Your desktop environment is not supported for automatic wallpaper changes.",
                WallpaperUpdateResult.COMMAND_FAILED: "The command to set the wallpaper failed. Check logs for details.",
                WallpaperUpdateResult.CONFIGURATION_ERROR: "Configuration error. Please check your settings.",
                WallpaperUpdateResult.FILE_SYSTEM_ERROR: "A file system error occurred. Check permissions and paths.",
                WallpaperUpdateResult.DESKTOP_ENVIRONMENT_ERROR: "Failed to apply wallpaper settings to your desktop environment.",
            }
            # If a specific error message was not provided by core.py, use the generic one from the map
            if not error_message:
                message = error_map.get(result, message)

            show_error_dialog(message, self)

        # Re-enable the button
        self.btn_apply_now.set_sensitive(True)

    def on_next_wallpaper_clicked(self, widget):
        # Auto-save current settings before refreshing so it uses the latest UI state
        self.on_save_clicked(widget, hide_window=False, skip_timer_setup=True)

        def change_and_update():
            try:
                result, error_msg = change_wallpaper()
                GLib.idle_add(self._handle_change_result, result, error_msg)
            except Exception as e:
                logging.error(f"Error in change_and_update: {e}", exc_info=True)
                GLib.idle_add(self._handle_change_result, WallpaperUpdateResult.FILE_SYSTEM_ERROR, str(e))

        try:
            self.btn_apply_now.set_sensitive(False)
            thread = threading.Thread(target=change_and_update, daemon=True)
            thread.start()

            # Fase 1: watchdog via constante; re-enable y notifica
            def _watchdog():
                if thread.is_alive():
                    logging.error(
                        f"Watchdog after {WALLPAPER_CHANGE_TIMEOUT_SEC}s — thread hung (network/heavy image)."
                    )
                    GLib.idle_add(
                        lambda: self.btn_apply_now.set_sensitive(True)
                        if hasattr(self, "btn_apply_now")
                        else None
                    )
                    try:
                        from ...gui_helpers import show_error_dialog as _show

                        GLib.idle_add(
                            _show,
                            f"Wallpaper change timed out after {WALLPAPER_CHANGE_TIMEOUT_SEC}s. Check network/folder.",
                            self,
                        )
                    except Exception:
                        pass
                return False  # one-shot

            GLib.timeout_add_seconds(WALLPAPER_CHANGE_TIMEOUT_SEC, _watchdog)
        except Exception as e:
            logging.critical(f"Error starting wallpaper change thread from GUI: {e}", exc_info=True)
            self.btn_apply_now.set_sensitive(True)  # Re-enable on thread start failure
