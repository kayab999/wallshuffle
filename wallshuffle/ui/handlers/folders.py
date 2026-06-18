import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ..dialogs import ManageFoldersDialog


class FolderHandlersMixin:
    def on_browse_clicked(self, widget):
        logging.debug("on_browse_clicked triggered")
        dialog = None
        try:
            dialog = Gtk.FileChooserNative(
                title="Choose a folder",
                parent=self,
                action=Gtk.FileChooserAction.SELECT_FOLDER
            )
            logging.debug(f"FileChooserNative created: {dialog}")
        except Exception as e:
            logging.warning(f"Gtk.FileChooserNative failed, falling back to Gtk.FileChooserDialog: {e}")
            dialog = Gtk.FileChooserDialog(
                title="Choose a folder",
                parent=self,
                action=Gtk.FileChooserAction.SELECT_FOLDER
            )
            dialog.add_buttons(
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT
            )

        if not dialog:
            logging.error("Failed to create any folder chooser dialog.")
            return

        dialog.set_modal(True)

        def on_response(native, response_id):
            logging.debug(f"Folder chooser response: {response_id}")
            if response_id == Gtk.ResponseType.ACCEPT:
                filename = native.get_filename()
                logging.info(f"Folder selected: {filename}")
                self.entry_folder.set_text(filename)
            native.destroy()

        dialog.connect("response", on_response)
        logging.debug("Showing folder chooser dialog")
        dialog.show()

    def on_refresh_path_clicked(self, widget):
        self.update_current_wallpaper_label()

    def save_folder_categories(self):
        """Saves current folder categories to config."""
        # Update local config object for immediate consistency (though not strictly needed if we reload)
        if not self.config.has_section("FolderCategories"):
            self.config.add_section("FolderCategories")
        self.config.remove_section("FolderCategories") # Clear old
        self.config.add_section("FolderCategories")
        for name, path in self.folder_categories.items():
            self.config.set("FolderCategories", name, path)

        # Persist using ConfigManager
        self.config_manager.save_categories(self.folder_categories)
        self.update_folder_combo()

    def update_folder_combo(self):
        """Refreshes the combo box from self.folder_categories."""
        active_id = self.combo_folders.get_active_text()
        self.combo_folders.remove_all()

        for name in self.folder_categories:
            self.combo_folders.append_text(name)

        if active_id in self.folder_categories:
            # Setting active by text is tricky in simple combo
            # We iterate to find index
            idx = 0
            found = False
            for name in self.folder_categories:
                if name == active_id:
                    self.combo_folders.set_active(idx)
                    found = True
                    break
                idx += 1
            if not found and self.folder_categories:
                 self.combo_folders.set_active(0)
        elif self.folder_categories:
            self.combo_folders.set_active(0)

    def on_manage_folders_clicked(self, widget):
        dialog = ManageFoldersDialog(self, self.folder_categories)
        dialog.run()
        dialog.destroy()

    def _load_categories_from_config(self):
        """Loads categories into self.folder_categories dict."""
        self.folder_categories = {}
        if self.config.has_section("FolderCategories"):
            for name, path in self.config.items("FolderCategories"):
                self.folder_categories[name] = path

        # If empty, add Default
        if not self.folder_categories:
             # Try to recover legacy folder setting if not already migrated?
             # (Migration logic is in ConfigManager, so it should be there)
             pass
