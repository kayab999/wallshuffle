import os
import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from ...constants import MultiMonitorMode, WallpaperSource
from ...image_discovery import count_images_in_folder
from ...online_sources import OnlineSourceManager


class SourceHandlersMixin:
    def count_local_images(self, path, recursive):
        return count_images_in_folder(path, recursive)

    def update_image_count(self, path_override=None):
        source = self.combo_source.get_active_text()
        if source == WallpaperSource.LOCAL_FOLDER:
            if path_override:
                path = path_override
            else:
                cat_name = self.combo_folders.get_active_text()
                path = self.folder_categories.get(cat_name) if cat_name else None

            recursive = self.check_recursive.get_active()
            if path and os.path.isdir(path):
                # Run in thread to avoid freezing UI on large folders
                def count_thread():
                    count = self.count_local_images(path, recursive)
                    GLib.idle_add(lambda: self.lbl_source_status.set_text(f"✓ {count} images found"))

                threading.Thread(target=count_thread, daemon=True).start()
            else:
                self.lbl_source_status.set_text("⚠ Select a folder category")
        else:
            self.lbl_source_status.set_text("✓ Unsplash Source")

    def on_folder_changed(self, widget):
        # Now widget is a ComboBoxText
        category_name = widget.get_active_text()
        if category_name and category_name in self.folder_categories:
            path = self.folder_categories[category_name]
            if os.path.isdir(path):
                # We can't apply style classes to the combo box entry easily unless we get the child entry
                # But for now let's just update the count.
                self.update_image_count(path_override=path)
                return

        # Explicitly handle empty or invalid
        self.lbl_source_status.set_text("⚠ Select a valid category")

    def validate_api_key(self, widget):
        key = widget.get_text()
        if len(key) < 20 and key != "":  # Arbitrary check for length
            widget.get_style_context().add_class("warning")
        else:
            widget.get_style_context().remove_class("warning")



    def on_multi_monitor_changed(self, combo):
        text = combo.get_active_text()
        is_spanning = text == MultiMonitorMode.SPAN

        # Disable scaling mode if spanning is active, as spanning forces a specific mode
        self.combo_mode.set_sensitive(not is_spanning)
        if is_spanning:
            tooltip = "Disabled because 'Span image across all monitors' overrides scaling settings."
        else:
            tooltip = "Select how the image should be scaled on the screen."
        self.combo_mode.set_tooltip_text(tooltip)

    def on_api_key_visibility_toggle(self, entry, icon_pos, event):
        if icon_pos == Gtk.EntryIconPosition.SECONDARY:
            visible = entry.get_visibility()
            entry.set_visibility(not visible)
            icon_name = "view-conceal-symbolic" if not visible else "view-reveal-symbolic"
            entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, icon_name)

    def on_source_changed(self, combo):
        text = combo.get_active_text()
        if hasattr(self, 'stack_source'):
            child = text if text in self.sources else WallpaperSource.LOCAL_FOLDER
            self.stack_source.set_visible_child_name(child)

            if text == WallpaperSource.LOCAL_FOLDER:
                 self.update_image_count()
            elif text == WallpaperSource.URL:
                url_valid = hasattr(self, "entry_url") and self.entry_url.get_text().startswith("http")
                status_text = "✓ Online image" if url_valid else "⚠ Enter a valid URL"
                self.lbl_source_status.set_text(status_text)
            else:
                 self.lbl_source_status.set_text("✓ Unsplash Source")

    def on_test_unsplash_clicked(self, widget):
        api_key = self.entry_unsplash_api_key.get_text()

        # Show loading cursor or disable button
        self.btn_test_unsplash.set_sensitive(False)
        self.btn_test_unsplash.set_label("Testing...")

        def run_test():
            # Use OnlineSourceManager logic
            source_manager = OnlineSourceManager(self.config_manager, self.config)
            success, message = source_manager.test_api_connection(api_key)

            GLib.idle_add(self._on_test_complete, success, message)

        threading.Thread(target=run_test, daemon=True).start()

    def _on_test_complete(self, success, message):
        # Guard against processing if window is being destroyed/closed
        if not self.get_realized():
            return False

        self.btn_test_unsplash.set_sensitive(True)
        self.btn_test_unsplash.set_label("Test Connection")

        dialog_type = Gtk.MessageType.INFO if success else Gtk.MessageType.ERROR
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=dialog_type,
            buttons=Gtk.ButtonsType.OK,
            text="Connection Test Result",
        )
        dialog.format_secondary_text(message)

        def on_response(d, res):
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show()
