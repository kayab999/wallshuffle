import logging
import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib


class PollingHandlersMixin:
    def on_delete_event(self, widget, event):
        if self.app and not self.app.tray_available:
            logging.info("Tray icon not available. Quitting application instead of hiding.")
            self.app.quit()
            return False

        logging.warning("DELETE EVENT TRIGGERED - Hiding window")
        self.hide()
        return True

    def poll_timer_status(self):
        """Polls the systemd timer status and updates the UI."""
        if not self.is_systemd_available:
            self.lbl_next_change.set_text("systemd not available")
            return False # Stop polling

        if self._polling_in_progress:
            logging.debug("Status poll already in progress. Skipping to avoid thread exhaustion.")
            return True

        self._polling_in_progress = True

        def update():
            try:
                next_run = self.wallpaper_manager.get_timer_next_run()
                GLib.idle_add(self._on_poll_complete, next_run)
            except Exception as e:
                logging.error(f"Error polling timer status: {e}")
                GLib.idle_add(self._on_poll_complete, "Error")

        threading.Thread(target=update, daemon=True).start()
        return True # Keep polling

    def _on_poll_complete(self, next_run):
        """Callback to update UI and release polling lock."""
        if self.get_realized():
            self.lbl_next_change.set_text(f"Next change: {next_run}")
        self._polling_in_progress = False

    def _on_focus_out(self, widget, event):
        logging.debug("Window lost focus. Slowing down polling.")
        self._poll_interval_seconds = 30
        self._start_adaptive_poll()
        return False  # Propagate event

    def _start_adaptive_poll(self):
        """Restarts the adaptive poll with the current interval."""
        if hasattr(self, "_poll_timeout_id") and self._poll_timeout_id:
            GLib.source_remove(self._poll_timeout_id)

        self._poll_timeout_id = GLib.timeout_add_seconds(
            self._poll_interval_seconds,
            self._adaptive_poll
        )

    def _adaptive_poll(self):
        """Adaptive polling logic called by GLib.timeout."""
        if not self.get_visible():
            return True # Keep repeating but window is hidden

        self.poll_timer_status()
        return True # Repeat timer

    def _on_focus_in(self, widget, event):
        """Immediately refresh status when window regains focus and speed up polling."""
        logging.debug("Window focused. Speeding up polling.")
        self.poll_timer_status()
        self._poll_interval_seconds = 5
        self._start_adaptive_poll()
        return False
