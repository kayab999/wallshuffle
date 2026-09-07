import os

import gi

from ..gui_helpers import show_error_dialog, wire_dialog_default

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class ManageFoldersDialog(Gtk.Dialog):
    def __init__(self, parent, categories):
        super().__init__(
            title="Manage Folder Sources",
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self.add_buttons(
            Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE
        )
        self.set_default_size(550, 400)
        self.categories = categories  # Dict of Name: Path
        self.parent_window = parent

        box = self.get_content_area()
        box.set_spacing(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # Header label
        lbl_header = Gtk.Label()
        lbl_header.set_markup("<b>Wallpaper Source Folders</b>")
        lbl_header.set_halign(Gtk.Align.START)
        box.pack_start(lbl_header, False, False, 0)

        # Scrollable ListBox
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.get_style_context().add_class("rich-list")
        scroll.add(self.listbox)

        # Frame around the list for a polished border
        frame = Gtk.Frame()
        frame.add(scroll)
        box.pack_start(frame, True, True, 0)

        # Populate existing categories
        for name, path in self.categories.items():
            self._add_row(name, path)

        # Placeholder when empty
        self.listbox.set_placeholder(Gtk.Label(label="No folders added yet. Click 'Add Folder' below."))

        # Add button
        btn_add = Gtk.Button(label="Add Folder")
        btn_add.set_image(Gtk.Image.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON))
        btn_add.set_always_show_image(True)
        btn_add.set_halign(Gtk.Align.START)
        btn_add.connect("clicked", self.on_add_clicked)
        box.pack_start(btn_add, False, False, 0)

        self.show_all()
        # Enter / Space on Close; Escape also ends run() via DELETE_EVENT
        wire_dialog_default(self, Gtk.ResponseType.CLOSE)

    def _add_row(self, name, path):
        row = Gtk.ListBoxRow()
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hbox.set_margin_top(8)
        hbox.set_margin_bottom(8)
        hbox.set_margin_start(12)
        hbox.set_margin_end(8)

        # Icon
        icon = Gtk.Image.new_from_icon_name("folder-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
        hbox.pack_start(icon, False, False, 0)

        # Name + Path stacked vertically
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lbl_name = Gtk.Label(label=name)
        lbl_name.set_halign(Gtk.Align.START)
        lbl_name.get_style_context().add_class("heading")
        vbox.pack_start(lbl_name, False, False, 0)

        lbl_path = Gtk.Label(label=path)
        lbl_path.set_halign(Gtk.Align.START)
        lbl_path.set_ellipsize(3)  # Pango.EllipsizeMode.END
        lbl_path.get_style_context().add_class("dim-label")
        vbox.pack_start(lbl_path, False, False, 0)
        hbox.pack_start(vbox, True, True, 0)

        # Per-row remove button
        btn_remove = Gtk.Button()
        btn_remove.set_image(Gtk.Image.new_from_icon_name("edit-delete-symbolic", Gtk.IconSize.BUTTON))
        btn_remove.set_tooltip_text(f"Remove '{name}'")
        btn_remove.get_style_context().add_class("flat")
        btn_remove.set_valign(Gtk.Align.CENTER)
        btn_remove.connect("clicked", self.on_remove_row_clicked, row, name)
        hbox.pack_end(btn_remove, False, False, 0)

        row.add(hbox)
        row.show_all()
        self.listbox.add(row)

    def _choose_folder_path(self):
        """Open a modal folder chooser. Returns selected path, or None if cancelled."""
        dialog = Gtk.FileChooserDialog(
            title="Select Folder",
            transient_for=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            modal=True,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )
        wire_dialog_default(dialog, Gtk.ResponseType.OK)
        try:
            response = dialog.run()
            if response != Gtk.ResponseType.OK:
                return None
            return dialog.get_filename()
        finally:
            dialog.destroy()

    def _ask_category_name(self, folder_path):
        """
        Prompt for a display name for the selected folder.

        Returns:
            str: stripped name when the user confirms
            None: when the user cancels
        """
        name_dialog = Gtk.Dialog(
            title="Category Name",
            transient_for=self,
            modal=True,
            destroy_with_parent=True,
        )
        name_dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )

        content = name_dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(10)
        content.set_margin_bottom(10)
        content.set_margin_start(10)
        content.set_margin_end(10)

        prompt = Gtk.Label(label="Enter a name for this folder:")
        prompt.set_halign(Gtk.Align.START)
        content.pack_start(prompt, False, False, 0)

        entry = Gtk.Entry()
        entry.set_placeholder_text("e.g., Nature, Cars")
        suggested = os.path.basename(folder_path.rstrip(os.sep)) or folder_path
        entry.set_text(suggested)
        entry.select_region(0, -1)
        content.pack_start(entry, False, False, 0)

        name_dialog.show_all()
        # Enter confirms (via default button + Entry activate fallback); Escape cancels.
        wire_dialog_default(name_dialog, Gtk.ResponseType.OK, entry=entry)
        entry.grab_focus()

        try:
            response = name_dialog.run()
            if response != Gtk.ResponseType.OK:
                return None
            return entry.get_text().strip()
        finally:
            name_dialog.destroy()

    def on_add_clicked(self, widget):
        path = self._choose_folder_path()
        if not path:
            return

        name = self._ask_category_name(path)
        if name is None:
            return

        if not name:
            show_error_dialog("Please enter a name for this folder.", parent=self)
            return

        if name in self.categories:
            show_error_dialog("A folder with that name already exists.", parent=self)
            return

        self.categories[name] = path
        self._add_row(name, path)
        self.parent_window.save_folder_categories()

    def on_remove_row_clicked(self, button, row, name):
        if name in self.categories:
            del self.categories[name]
        self.listbox.remove(row)
        self.parent_window.save_folder_categories()
