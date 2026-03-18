import logging
import os
import shutil
import sys
import threading

import gi

from . import __version__
from .constants import SUPPORTED_EXTENSIONS
from .core import WallpaperUpdateResult, change_wallpaper
from .online_sources import OnlineSourceManager
from .themes import THEMES
from .utils import CONFIG_DIR, escape_systemd_path, show_error_dialog
from .wallpaper_manager import WallpaperManager

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk


def _find_executable_for_systemd():
    """
    Devuelve la ruta estable que systemd debe ejecutar para invocar wallshuffle --change.
    Preferimos: user-installed wrapper (which wallshuffle) -> APPIMAGE wrapper -> sys.executable.
    """
    # 1) Preferir el ejecutable instalable en PATH (editable install o wrapper)
    exe = shutil.which("wallshuffle")
    if exe:
        return exe

    # 2) Si estamos corriendo dentro de AppImage y existe un wrapper instalado, preferirlo.
    appimage_path = os.environ.get("APPIMAGE")
    if appimage_path:
        # Posible ubicación recomendada del AppImage en instalación de usuario
        user_appimage = os.path.expanduser("~/Applications/WallShuffle.AppImage")
        if os.path.isfile(user_appimage) and os.access(user_appimage, os.X_OK):
            return user_appimage
        # Si no, usar APPIMAGE path directo (menos ideal, pero explícito)
        if os.path.isfile(appimage_path) and os.access(appimage_path, os.X_OK):
            return appimage_path

    # 3) Fallback: sys.executable (dev mode)
    return sys.executable


class WallpaperAppWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        logging.debug(f"WallpaperAppWindow init started. kwargs keys: {list(kwargs.keys())}")
        self.app = kwargs.pop("app", None)
        self.is_de_supported = kwargs.pop("is_de_supported", False)
        logging.info(f"UI received is_de_supported: {self.is_de_supported}")
        self.is_systemd_available = kwargs.pop("is_systemd_available", False)

        logging.debug("Calling super().__init__")
        super().__init__(*args, **kwargs)
        logging.debug("super().__init__ completed")

        self.set_default_size(700, 700)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_border_width(0) # Removed border width for modern look
        self.set_name("wallshuffle-main-window")
        self.config_manager = self.app.config_manager
        self.config = self.app.config
        self.wallpaper_manager = WallpaperManager()
        self.theme_manager = self.app.theme_manager

        # Initialize data lists
        self.sources = ["Local Folder", "Unsplash"]
        self.modes = ["zoom", "scaled", "centered", "spanned", "stretched"]
        self.effects = ["None", "Grayscale", "Blur", "Sepia"]
        self.multi_monitor_modes = [
            "Single image on all monitors",
            "Different image on each monitor",
            "Span image across all monitors",
        ]

        logging.debug("Calling init_ui")
        self.init_ui()
        logging.debug("init_ui completed")

        # Load settings and apply initial state
        logging.debug("Loading settings")
        self.load_settings()
        logging.debug("Updating current wallpaper label")
        self.update_current_wallpaper_label()
        logging.debug("Updating image count")
        self.update_image_count()

        self.connect("delete-event", self.on_delete_event)
        self.connect("focus-out-event", self.on_focus_out)

        if self.app.css_provider:
            logging.debug("Applying CSS provider")
            self.get_style_context().add_provider(self.app.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        logging.debug("Window initialized (hidden)")

        # Initial visibility check based on source
        # self.on_source_changed(self.combo_source) # Call this after UI is built
        # self.on_multi_monitor_changed(self.combo_multi_monitor)

        logging.info("WallpaperAppWindow initialization successful")

    def on_delete_event(self, widget, event):
        logging.warning("DELETE EVENT TRIGGERED - Hiding window")
        self.hide()
        return True

    def on_focus_out(self, widget, event):
        logging.warning("FOCUS OUT EVENT TRIGGERED")
        return False  # Propagate event

    def init_ui(self):
        self._build_header_bar()

        # Main Layout: Scrolled Window
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.add(scrolled_window)

        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_vbox.set_margin_top(20)
        main_vbox.set_margin_bottom(20)
        main_vbox.set_margin_start(20)
        main_vbox.set_margin_end(20)
        scrolled_window.add(main_vbox)

        self._build_info_bar(main_vbox)
        self._build_hero_section(main_vbox)
        self._build_source_section(main_vbox)
        self._build_settings_section(main_vbox)

        # Apply restrictions
        if not self.is_de_supported:
            self._apply_de_restrictions()
        if not self.is_systemd_available:
            self._apply_systemd_restrictions()

    def _build_header_bar(self):
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title(f"WallShuffle v{__version__}")
        self.set_titlebar(header)

        self.btn_save = Gtk.Button(label="Save")
        self.btn_save.get_style_context().add_class("suggested-action")
        self.btn_save.connect("clicked", self.on_save_clicked)
        header.pack_end(self.btn_save)

        self.btn_apply_now = Gtk.Button(label="Next Wallpaper")
        self.btn_apply_now.set_image(Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON))
        self.btn_apply_now.connect("clicked", self.on_next_wallpaper_clicked)
        header.pack_start(self.btn_apply_now)

    def _build_info_bar(self, parent):
        self.info_bar_de = Gtk.InfoBar()
        self.info_bar_de.set_message_type(Gtk.MessageType.WARNING)
        self.info_bar_de.set_no_show_all(True)
        content_area = self.info_bar_de.get_content_area()
        content_area.add(Gtk.Label(label="Your desktop environment is not officially supported."))
        self.info_bar_de.set_visible(not self.is_de_supported)
        parent.pack_start(self.info_bar_de, False, False, 0)

    def _build_hero_section(self, parent):
        hero_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        hero_box.set_halign(Gtk.Align.CENTER)
        parent.pack_start(hero_box, False, False, 0)

        self.preview_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hero_box.pack_start(self.preview_box, False, False, 0)

        info_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        info_vbox.set_valign(Gtk.Align.CENTER)
        hero_box.pack_start(info_vbox, False, False, 0)

        self.entry_current_path = Gtk.Entry()
        self.entry_current_path.set_editable(False)
        self.entry_current_path.set_has_frame(False)
        self.entry_current_path.get_style_context().add_class("flat")
        self.entry_current_path.set_placeholder_text("No wallpaper set")
        self.entry_current_path.set_width_chars(30)
        info_vbox.pack_start(self.entry_current_path, False, False, 0)

        self.lbl_next_change = Gtk.Label(label="Next change: --:--")
        self.lbl_next_change.set_halign(Gtk.Align.START)
        self.lbl_next_change.get_style_context().add_class("dim-label")
        info_vbox.pack_start(self.lbl_next_change, False, False, 0)

        self.lbl_source_status = Gtk.Label(label="")
        self.lbl_source_status.set_halign(Gtk.Align.START)
        info_vbox.pack_start(self.lbl_source_status, False, False, 0)

    def _build_source_section(self, parent):
        lbl_section = Gtk.Label(label="Source")
        lbl_section.set_halign(Gtk.Align.START)
        lbl_section.set_markup("<b>Source</b>")
        parent.pack_start(lbl_section, False, False, 0)

        source_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        source_box.set_margin_start(10)
        parent.pack_start(source_box, False, False, 0)

        self.combo_source = Gtk.ComboBoxText()
        for source in self.sources:
            self.combo_source.append_text(source)
        self.combo_source.connect("changed", self.on_source_changed)
        source_box.pack_start(self.combo_source, False, False, 0)

        self.stack_source = Gtk.Stack()
        self.stack_source.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        source_box.pack_start(self.stack_source, False, False, 0)

        # Local Page
        page_local = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        hbox_folder = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        self.combo_folders = Gtk.ComboBoxText()
        self.combo_folders.set_hexpand(True)
        self.combo_folders.connect("changed", self.on_folder_changed)

        self.btn_manage_folders = Gtk.Button(label="Manage Sources...")
        self.btn_manage_folders.connect("clicked", self.on_manage_folders_clicked)

        hbox_folder.pack_start(self.combo_folders, True, True, 0)
        hbox_folder.pack_start(self.btn_manage_folders, False, False, 0)
        self.check_recursive = Gtk.CheckButton(label="Include subfolders")
        self.check_recursive.connect("toggled", lambda w: self.update_image_count())
        page_local.pack_start(hbox_folder, False, False, 0)
        page_local.pack_start(self.check_recursive, False, False, 0)
        self.stack_source.add_named(page_local, "Local Folder")

        # Unsplash Page
        page_unsplash = Gtk.Grid()
        page_unsplash.set_column_spacing(10)
        page_unsplash.set_row_spacing(10)

        self.lbl_api_key = Gtk.Label(label="API Key:")
        self.entry_unsplash_api_key = Gtk.Entry()
        self.entry_unsplash_api_key.set_visibility(False)
        self.entry_unsplash_api_key.set_placeholder_text("Unsplash Access Key")
        self.entry_unsplash_api_key.connect("changed", self.validate_api_key)

        self.lbl_keywords = Gtk.Label(label="Keywords:")
        self.entry_keywords = Gtk.Entry()
        self.entry_keywords.set_placeholder_text("nature, architecture")

        self.btn_test_unsplash = Gtk.Button(label="Test Connection")
        self.btn_test_unsplash.connect("clicked", self.on_test_unsplash_clicked)

        page_unsplash.attach(self.lbl_api_key, 0, 0, 1, 1)
        page_unsplash.attach(self.entry_unsplash_api_key, 1, 0, 1, 1)
        page_unsplash.attach(self.btn_test_unsplash, 2, 0, 1, 1)
        page_unsplash.attach(self.lbl_keywords, 0, 1, 1, 1)
        page_unsplash.attach(self.entry_keywords, 1, 1, 2, 1)
        self.stack_source.add_named(page_unsplash, "Unsplash")

    def _build_settings_section(self, parent):
        lbl_section = Gtk.Label(label="Settings")
        lbl_section.set_halign(Gtk.Align.START)
        lbl_section.set_markup("<b>Settings</b>")
        parent.pack_start(lbl_section, False, False, 0)

        grid = Gtk.Grid()
        grid.set_column_spacing(20)
        grid.set_row_spacing(15)
        grid.set_margin_start(10)
        parent.pack_start(grid, False, False, 0)

        # Mode
        grid.attach(Gtk.Label(label="Scaling:", halign=Gtk.Align.START), 0, 0, 1, 1)
        self.combo_mode = Gtk.ComboBoxText()
        for mode in self.modes:
            self.combo_mode.append_text(mode)
        grid.attach(self.combo_mode, 1, 0, 1, 1)

        # Effect
        grid.attach(Gtk.Label(label="Effect:", halign=Gtk.Align.START), 0, 1, 1, 1)
        self.combo_effect = Gtk.ComboBoxText()
        for effect in self.effects:
            self.combo_effect.append_text(effect)
        grid.attach(self.combo_effect, 1, 1, 1, 1)
        # Background
        grid.attach(Gtk.Label(label="Background:", halign=Gtk.Align.START), 2, 0, 1, 1)
        self.btn_color = Gtk.ColorButton()
        grid.attach(self.btn_color, 3, 0, 1, 1)

        # Theme
        grid.attach(Gtk.Label(label="Theme:", halign=Gtk.Align.START), 2, 1, 1, 1)
        self.combo_theme = Gtk.ComboBoxText()
        for name in THEMES.keys():
            self.combo_theme.append_text(name)

        current_theme = "Ubuntu"
        if self.app and hasattr(self.app, "theme_manager"):
            current_theme = self.app.theme_manager.current_theme_name
        self.combo_theme.set_active(list(THEMES.keys()).index(current_theme) if current_theme in THEMES else 0)
        self.combo_theme.connect("changed", self._on_theme_changed)
        grid.attach(self.combo_theme, 3, 1, 1, 1)

        # Custom Theme Colors (Initally hidden)
        self.box_custom_colors = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.box_custom_colors.pack_start(Gtk.Label(label="Custom Colors:"), False, False, 0)

        self.btn_custom_bg = Gtk.ColorButton()
        self.btn_custom_bg.set_tooltip_text("Background Color")
        self.box_custom_colors.pack_start(self.btn_custom_bg, False, False, 0)

        self.btn_custom_fg = Gtk.ColorButton()
        self.btn_custom_fg.set_tooltip_text("Foreground Color")
        self.box_custom_colors.pack_start(self.btn_custom_fg, False, False, 0)

        self.btn_custom_accent = Gtk.ColorButton()
        self.btn_custom_accent.set_tooltip_text("Accent Color")
        self.box_custom_colors.pack_start(self.btn_custom_accent, False, False, 0)

        parent.pack_start(self.box_custom_colors, False, False, 0)

        # Automation
        grid.attach(Gtk.Label(label="Automation:", halign=Gtk.Align.START), 0, 2, 1, 1)
        hbox_auto = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox_auto.pack_start(Gtk.Label(label="Every"), False, False, 0)
        self.spin_interval = Gtk.SpinButton()
        self.spin_interval.set_adjustment(Gtk.Adjustment(value=30, lower=1, upper=10080, step_increment=1))
        self.spin_interval.set_numeric(True)
        hbox_auto.pack_start(self.spin_interval, False, False, 0)
        hbox_auto.pack_start(Gtk.Label(label="mins"), False, False, 0)
        hbox_auto.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 10)
        self.check_startup = Gtk.CheckButton(label="On Startup")
        hbox_auto.pack_start(self.check_startup, False, False, 0)
        grid.attach(hbox_auto, 1, 2, 3, 1)

        # Monitors
        grid.attach(Gtk.Label(label="Monitors:", halign=Gtk.Align.START), 0, 3, 1, 1)
        self.combo_multi_monitor = Gtk.ComboBoxText()
        for m in self.multi_monitor_modes:
            self.combo_multi_monitor.append_text(m)
        self.combo_multi_monitor.connect("changed", self.on_multi_monitor_changed)
        grid.attach(self.combo_multi_monitor, 1, 3, 3, 1)

    def _apply_de_restrictions(self):
        self.combo_source.set_sensitive(False)
        self.stack_source.set_sensitive(False)
        self.btn_save.set_sensitive(False)
        self.btn_apply_now.set_sensitive(False)

    def _apply_systemd_restrictions(self):
        self.spin_interval.set_sensitive(False)
        self.check_startup.set_sensitive(False)
        self.spin_interval.set_tooltip_text("Disabled: systemd not found.")
        self.check_startup.set_tooltip_text("Disabled: systemd not found.")

    def _on_theme_changed(self, cb):
        theme_name = cb.get_active_text()
        if theme_name and self.app and hasattr(self.app, "theme_manager"):
            self.app.theme_manager.set_theme_name(theme_name)

            # Show/hide custom color pickers
            if theme_name == "Custom":
                self.box_custom_colors.show_all()
            else:
                self.box_custom_colors.hide()

            new_provider = self.app.theme_manager.get_css_provider()
            style_context = self.get_style_context()
            if self.app.css_provider:
                style_context.remove_provider(self.app.css_provider)
            style_context.add_provider(new_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.app.css_provider = new_provider

    def count_local_images(self, path, recursive):
        if not path or not os.path.isdir(path):
            return 0

        count = 0

        if recursive:
            visited_dirs = set()
            for root, dirs, files in os.walk(path, followlinks=True):
                # Detect loops
                try:
                    real_root = os.path.realpath(root)
                    if real_root in visited_dirs:
                        dirs[:] = []  # Don't recurse further
                        continue
                    visited_dirs.add(real_root)
                except OSError:
                    pass

                for f in files:
                    if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS:
                        count += 1
        else:
            try:
                for f in os.listdir(path):
                    if os.path.isfile(os.path.join(path, f)) and os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS:
                        count += 1
            except OSError:
                pass
        return count

    def update_image_count(self, path_override=None):
        source = self.combo_source.get_active_text()
        if source == "Local Folder":
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
        is_spanning = text == "Span image across all monitors"

        # Disable scaling mode if spanning is active, as spanning forces a specific mode
        self.combo_mode.set_sensitive(not is_spanning)
        if is_spanning:
            tooltip = "Disabled because 'Span image across all monitors' overrides scaling settings."
        else:
            tooltip = "Select how the image should be scaled on the screen."
        self.combo_mode.set_tooltip_text(tooltip)

    def on_source_changed(self, combo):
        text = combo.get_active_text()
        if hasattr(self, 'stack_source'):
            child = "Local Folder" if text == "Local Folder" else "Unsplash"
            self.stack_source.set_visible_child_name(child)

            if text == "Local Folder":
                 self.update_image_count()
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

    def load_settings(self):
        # Load Categories first
        self._load_categories_from_config()
        self.update_folder_combo()

        if "Settings" in self.config:
            settings = self.config["Settings"]

            # Ensure valid values and avoid None
            def safe_set_active(combo, value, options):
                if value in options:
                    combo.set_active(options.index(value))
                else:
                    combo.set_active(0)

            source = settings.get("source", "Local Folder")
            safe_set_active(self.combo_source, source, self.sources)

            # Match saved folder path to category
            saved_Folder = settings.get("folder", "")
            found_cat = None
            for name, path in self.folder_categories.items():
                if path == saved_Folder:
                    found_cat = name
                    break

            # Set active using simple iteration as safe_set_active is generic
            if found_cat:
                # find index of found_cat
                idx = 0
                for name in self.folder_categories:
                    if name == found_cat:
                        self.combo_folders.set_active(idx)
                        break
                    idx += 1

            self.check_recursive.set_active(self.config_manager.get_setting(self.config, "Settings", "recursive_search", False, value_type=bool))
            self.entry_keywords.set_text(settings.get("keywords", ""))

            unsplash_api_key = settings.get("unsplash_api_key", "")
            if unsplash_api_key == "YOUR_UNSPLASH_API_KEY":
                unsplash_api_key = ""
            self.entry_unsplash_api_key.set_text(unsplash_api_key)

            mode = settings.get("mode", "zoom")
            safe_set_active(self.combo_mode, mode, self.modes)

            self.spin_interval.set_value(self.config_manager.get_setting(self.config, "Settings", "interval", 30, value_type=int))
            self.check_startup.set_active(self.config_manager.get_setting(self.config, "Settings", "startup", False, value_type=bool))

            effect = settings.get("effect", "None")
            safe_set_active(self.combo_effect, effect, self.effects)

            multi_monitor_mode = settings.get("multi_monitor_mode", "Single image on all monitors")
            safe_set_active(self.combo_multi_monitor, multi_monitor_mode, self.multi_monitor_modes)

            # Theme loading
            theme_name = settings.get("theme", "Ubuntu")
            theme_keys = list(THEMES.keys())
            safe_set_active(self.combo_theme, theme_name, theme_keys)

            # Visibility for custom colors
            if theme_name == "Custom":
                self.box_custom_colors.show_all()

                # Load custom colors
                def parse_and_set(btn, color_str, default="#000000"):
                    c = Gdk.RGBA()
                    if not c.parse(color_str):
                        c.parse(default)
                    btn.set_rgba(c)

                parse_and_set(self.btn_custom_bg, settings.get("custom_background", "#F5F5F5"))
                parse_and_set(self.btn_custom_fg, settings.get("custom_foreground", "#333333"))
                parse_and_set(self.btn_custom_accent, settings.get("custom_accent", "#007ACC"))
            else:
                self.box_custom_colors.hide()

            bg_color_str = settings.get("background_color", "#000000")
            color = Gdk.RGBA()
            if color.parse(bg_color_str):
                self.btn_color.set_rgba(color)

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

    def update_current_wallpaper_label(self):
        history_file = os.path.join(CONFIG_DIR, "history.log")
        paths = []
        if os.path.exists(history_file):
            try:
                with open(history_file, "r") as f:
                    # Read enough lines to cover potential monitors
                    paths = [line.strip() for line in f.readlines()[:10] if line.strip()]
            except IOError:
                pass

        monitor_mode = self.config_manager.get_setting(self.config, "Settings", "multi_monitor_mode", "Single image on all monitors")

        target_count = 1
        if monitor_mode == "Different image on each monitor":
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

        def load_thumbnails(paths_to_load):
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

            GLib.idle_add(self._update_preview_box, pixbufs)

        threading.Thread(target=load_thumbnails, args=(display_paths,), daemon=True).start()

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

    def _handle_change_result(self, result):
        """Handles the result from change_wallpaper on the main GTK thread."""
        if result == WallpaperUpdateResult.SUCCESS:
            self.update_current_wallpaper_label()
        else:
            error_map = {
                WallpaperUpdateResult.NO_SOURCE_CONFIGURED: "No wallpaper source is configured. Please check your settings.",
                WallpaperUpdateResult.NO_IMAGES_FOUND: "No images were found. If using Unsplash, check your API key.",
                WallpaperUpdateResult.NETWORK_ERROR: "Network error. If using Unsplash, check your internet and API key.",
                WallpaperUpdateResult.UNSUPPORTED_DESKTOP: "Your desktop environment is not supported for automatic wallpaper changes.",
                WallpaperUpdateResult.COMMAND_FAILED: "The command to set the wallpaper failed. Check logs for details.",
                WallpaperUpdateResult.CONFIGURATION_ERROR: "Configuration error. Please check your settings.",
                WallpaperUpdateResult.FILE_SYSTEM_ERROR: "A file system error occurred. Check permissions and paths.",
            }
            message = error_map.get(result, "An unknown error occurred.")
            show_error_dialog(message, self)

        # Re-enable the button
        self.btn_apply_now.set_sensitive(True)

    def on_next_wallpaper_clicked(self, widget):
        def change_and_update():
            result = change_wallpaper()
            GLib.idle_add(self._handle_change_result, result)

        try:
            self.btn_apply_now.set_sensitive(False)
            thread = threading.Thread(target=change_and_update, daemon=True)
            thread.start()
        except Exception as e:
            logging.critical(f"Error starting wallpaper change thread from GUI: {e}", exc_info=True)
            self.btn_apply_now.set_sensitive(True)  # Re-enable on thread start failure

    def on_save_clicked(self, widget):
        source = self.combo_source.get_active_text()

        # Get folder path from selected category
        cat_name = self.combo_folders.get_active_text()
        folder = self.folder_categories.get(cat_name, "") if cat_name else ""

        recursive_search = self.check_recursive.get_active()
        keywords = self.entry_keywords.get_text()
        unsplash_api_key = self.entry_unsplash_api_key.get_text()
        mode = self.combo_mode.get_active_text()
        interval = self.spin_interval.get_value_as_int()
        startup = self.check_startup.get_active()
        effect = self.combo_effect.get_active_text()
        multi_monitor_mode = self.combo_multi_monitor.get_active_text()
        theme = self.combo_theme.get_active_text()

        bg_color = self.btn_color.get_rgba()
        hex_color = "#{:02x}{:02x}{:02x}".format(int(bg_color.red * 255), int(bg_color.green * 255), int(bg_color.blue * 255))

        settings_dict = {
            "source": source or "Local Folder",
            "folder": folder,
            "recursive_search": str(recursive_search),
            "keywords": keywords,
            "unsplash_api_key": unsplash_api_key,
            "mode": mode or "zoom",
            "interval": str(interval),
            "startup": str(startup),
            "effect": effect or "None",
            "multi_monitor_mode": multi_monitor_mode or "Single image on all monitors",
            "theme": theme or "Ubuntu",
            "background_color": hex_color,
        }

        # Save custom colors if theme is Custom
        if theme == "Custom":
            def get_hex(btn):
                rgba = btn.get_rgba()
                return "#{:02x}{:02x}{:02x}".format(int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255))
            settings_dict["custom_background"] = get_hex(self.btn_custom_bg)
            settings_dict["custom_foreground"] = get_hex(self.btn_custom_fg)
            settings_dict["custom_accent"] = get_hex(self.btn_custom_accent)

        if not self.config_manager.save_settings(self.config, settings_dict):
            return

        # Run systemd setup in background to avoid blocking UI
        threading.Thread(
            target=self.setup_systemd_timer,
            args=(interval, startup),
            daemon=True
        ).start()

        self.hide()

    def setup_systemd_timer(self, interval, startup):
        if not self.is_systemd_available:
            logging.warning("Systemd is not available, skipping timer setup (this is expected on non-systemd systems).")
            # We do not show an error dialog here anymore, as the UI already informs the user about this limitation.
            return

        systemd_path = os.path.join(os.path.expanduser("~"), ".config", "systemd", "user")
        try:
            os.makedirs(systemd_path, exist_ok=True)

            uid = os.getuid()
            dbus_address = f"unix:path=/run/user/{uid}/bus"

            exec_path = _find_executable_for_systemd()

            if exec_path == sys.executable:
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                # Use escape_systemd_path for robust quoting/escaping of ExecStart
                esc_exec = escape_systemd_path(exec_path)
                exec_start_cmd = f"{esc_exec} -m wallshuffle --change"
                # WorkingDirectory must NOT be quoted - systemd expects raw absolute path
                working_dir = project_root
            else:
                esc_exec = escape_systemd_path(exec_path)
                exec_start_cmd = f"{esc_exec} --change"
                # WorkingDirectory must NOT be quoted - systemd expects raw absolute path
                working_dir = os.path.expanduser("~")

            # Capture critical environment variables for the background job
            env_vars = f'Environment="DBUS_SESSION_BUS_ADDRESS={dbus_address}"\n'

            # GSettings and DE detection rely on these
            if "DISPLAY" in os.environ:
                 env_vars += f'Environment="DISPLAY={os.environ["DISPLAY"]}"\n'
            if "XDG_CURRENT_DESKTOP" in os.environ:
                 env_vars += f'Environment="XDG_CURRENT_DESKTOP={os.environ["XDG_CURRENT_DESKTOP"]}"\n'
            # Also capture DESKTOP_SESSION as backup
            if "DESKTOP_SESSION" in os.environ:
                 env_vars += f'Environment="DESKTOP_SESSION={os.environ["DESKTOP_SESSION"]}"\n'

            service_content = f"""[Unit]
Description=WallShuffle Service

[Service]
Type=oneshot
WorkingDirectory={working_dir}
ExecStart={exec_start_cmd}
{env_vars}
"""
            with open(os.path.join(systemd_path, "wallpaper-changer.service"), "w") as f:
                f.write(service_content)

            timer_content = f"""[Unit]
Description=Run WallShuffle periodically

[Timer]
OnUnitActiveSec={interval}min
OnActiveSec=1s
OnBootSec=2min

[Install]
WantedBy=timers.target
"""
            with open(os.path.join(systemd_path, "wallpaper-changer.timer"), "w") as f:
                f.write(timer_content)
        except (IOError, OSError) as e:
            logging.error(f"File I/O error setting up systemd timer files: {e}")
            GLib.idle_add(show_error_dialog, f"File I/O error setting up systemd timer files: {e}", self)
            return
        except Exception as e:
            logging.critical(f"An unhandled error occurred during systemd file setup: {e}", exc_info=True)
            GLib.idle_add(show_error_dialog, f"An unhandled error occurred during systemd file setup: {e}", self)
            return

        try:
            if not self.wallpaper_manager._run_subprocess(["systemctl", "--user", "daemon-reload"], "daemon-reload", timeout=5):
                GLib.idle_add(show_error_dialog, "Failed to run systemctl daemon-reload. Check logs for details.", self)

            if startup:
                self.wallpaper_manager._run_subprocess(["systemctl", "--user", "enable", "wallpaper-changer.timer"], "enable timer", timeout=5)
                self.wallpaper_manager._run_subprocess(["systemctl", "--user", "start", "wallpaper-changer.timer"], "start timer", timeout=5)
            else:
                self.wallpaper_manager._run_subprocess(["systemctl", "--user", "disable", "wallpaper-changer.timer"], "disable timer", timeout=5)
                self.wallpaper_manager._run_subprocess(["systemctl", "--user", "stop", "wallpaper-changer.timer"], "stop timer", timeout=5)

        except Exception as e:
            logging.error(f"Error executing systemctl commands: {e}")

class ManageFoldersDialog(Gtk.Dialog):
    def __init__(self, parent, categories):
        super().__init__(title="Manage Folder Sources", transient_for=parent, flags=0)
        self.add_buttons(
            Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE
        )
        self.set_default_size(500, 350)
        self.categories = categories # Dict of Name: Path
        self.parent_window = parent

        box = self.get_content_area()
        box.set_spacing(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)

        # List Store: Name, Path
        self.store = Gtk.ListStore(str, str)
        for name, path in self.categories.items():
            self.store.append([name, path])

        # TreeView
        self.tree = Gtk.TreeView(model=self.store)

        renderer_text = Gtk.CellRendererText()
        col_name = Gtk.TreeViewColumn("Name", renderer_text, text=0)
        col_name.set_sort_column_id(0)
        self.tree.append_column(col_name)

        col_path = Gtk.TreeViewColumn("Path", renderer_text, text=1)
        self.tree.append_column(col_path)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.add(self.tree)
        box.pack_start(scroll, True, True, 0)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        btn_add = Gtk.Button(label="Add Folder")
        btn_add.connect("clicked", self.on_add_clicked)
        btn_box.pack_start(btn_add, False, False, 0)

        btn_remove = Gtk.Button(label="Remove")
        btn_remove.connect("clicked", self.on_remove_clicked)
        btn_box.pack_start(btn_remove, False, False, 0)

        box.pack_start(btn_box, False, False, 0)

        self.show_all()

    def on_add_clicked(self, widget):
        dialog = Gtk.FileChooserDialog(
            title="Select Folder",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK,
        )

        if dialog.run() == Gtk.ResponseType.OK:
            path = dialog.get_filename()
            dialog.destroy()

            # Ask for a name
            name_dialog = Gtk.Dialog(title="Category Name", parent=self, flags=0)
            name_dialog.add_buttons(Gtk.STOCK_OK, Gtk.ResponseType.OK, Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
            content = name_dialog.get_content_area()
            entry = Gtk.Entry()
            entry.set_placeholder_text("e.g., Nature, Cars")
            content.pack_start(Gtk.Label(label="Enter a name for this folder check:"), False, False, 10)
            content.pack_start(entry, False, False, 10)
            name_dialog.show_all()

            if name_dialog.run() == Gtk.ResponseType.OK:
                name = entry.get_text().strip()
                if name and name not in self.categories:
                    self.store.append([name, path])
                    self.categories[name] = path
                    self.parent_window.save_folder_categories() # Auto-save
                elif name in self.categories:
                    show_error_dialog("Category name already exists detected.", parent=self)
            name_dialog.destroy()
        else:
            dialog.destroy()

    def on_remove_clicked(self, widget):
        selection = self.tree.get_selection()
        model, iter = selection.get_selected()
        if iter:
            name = model[iter][0]
            del self.categories[name]
            model.remove(iter)
            self.parent_window.save_folder_categories() # Auto-save
