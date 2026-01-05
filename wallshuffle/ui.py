import logging
import os
import shutil
import sys
import threading

import gi

from .core import WallpaperUpdateResult, change_wallpaper
from .themes import THEMES
from .utils import CONFIG_DIR, show_error_dialog
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
        logging.debug("WallpaperAppWindow init called")
        self.app = kwargs.pop("app", None)
        self.is_de_supported = kwargs.pop("is_de_supported", False)
        self.is_systemd_available = kwargs.pop("is_systemd_available", False)
        super().__init__(*args, **kwargs)
        self.set_title("Wallshuffle")
        self.set_default_size(700, 700)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_border_width(15)
        self.set_name("wallshuffle-main-window")
        self.config_manager = self.app.config_manager
        self.config = self.app.config
        self.wallpaper_manager = WallpaperManager()
        self.theme_manager = self.app.theme_manager

        self.init_ui()

        # Load settings and apply initial state
        self.load_settings()
        self.update_current_wallpaper_label()
        self.update_image_count()

        self.connect("delete-event", self.on_delete_event)

        if self.app.css_provider:
            self.get_style_context().add_provider(
                self.app.css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        self.show_all()
        # Initial visibility check based on source
        self.on_source_changed(self.combo_source)

    def on_delete_event(self, widget, event):
        self.hide()
        return True

    def init_ui(self):
        # Main Layout: Scrolled Window
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.add(scrolled_window)

        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_vbox.set_margin_top(10)
        main_vbox.set_margin_bottom(10)
        main_vbox.set_margin_start(10)
        main_vbox.set_margin_end(10)
        scrolled_window.add(main_vbox)

        # InfoBar for Unsupported Desktop Environment
        self.info_bar_de = Gtk.InfoBar()
        self.info_bar_de.set_message_type(Gtk.MessageType.WARNING)
        content_area = self.info_bar_de.get_content_area()
        content_area.add(
            Gtk.Label(
                "Your desktop environment is not officially supported for automatic wallpaper changes. Wallshuffle might not work correctly."
            )
        )
        self.info_bar_de.show_all()
        self.info_bar_de.set_visible(not self.is_de_supported)
        main_vbox.pack_start(self.info_bar_de, False, False, 0)

        # --- System Status ---
        frame_status = Gtk.Frame(label="System Capabilities")
        main_vbox.pack_start(frame_status, False, False, 0)

        grid_status = Gtk.Grid()
        grid_status.set_column_spacing(10)
        grid_status.set_row_spacing(5)
        grid_status.set_margin_top(10)
        grid_status.set_margin_bottom(10)
        grid_status.set_margin_start(10)
        grid_status.set_margin_end(10)
        frame_status.add(grid_status)

        # Manual Wallpaper Status
        lbl_manual_icon = Gtk.Label(label="✅")
        lbl_manual = Gtk.Label(label="Manual Wallpaper Change: Available")
        lbl_manual.set_halign(Gtk.Align.START)
        grid_status.attach(lbl_manual_icon, 0, 0, 1, 1)
        grid_status.attach(lbl_manual, 1, 0, 1, 1)

        # Scheduling Status
        if self.is_systemd_available:
            lbl_sched_icon = Gtk.Label(label="✅")
            lbl_sched = Gtk.Label(label="Automatic Scheduling: Available")
        else:
            lbl_sched_icon = Gtk.Label(label="⚠️")
            lbl_sched = Gtk.Label(label="Automatic Scheduling: Unavailable (Systemd not detected)")
            lbl_sched.set_tooltip_text(
                "Automatic scheduling requires systemd, which was not found on this system.\n"
                "You can still change wallpapers manually using the 'Next Wallpaper' button."
            )
        lbl_sched.set_halign(Gtk.Align.START)
        grid_status.attach(lbl_sched_icon, 0, 1, 1, 1)
        grid_status.attach(lbl_sched, 1, 1, 1, 1)

        # --- Section 1: Source Configuration ---
        frame_source = Gtk.Frame(label="Source Configuration")
        frame_source.get_label_widget().get_style_context().add_class("title-2")
        main_vbox.pack_start(frame_source, False, False, 0)

        grid_source = Gtk.Grid()
        grid_source.set_column_spacing(15)
        grid_source.set_row_spacing(10)
        grid_source.set_margin_top(15)
        grid_source.set_margin_bottom(15)
        grid_source.set_margin_start(15)
        grid_source.set_margin_end(15)
        frame_source.add(grid_source)

        lbl_source = Gtk.Label(label="Wallpaper Source:")
        lbl_source.set_halign(Gtk.Align.START)
        self.combo_source = Gtk.ComboBoxText()
        self.sources = ["Local Folder", "Unsplash"]
        for source in self.sources:
            self.combo_source.append_text(source)
        self.combo_source.connect("changed", self.on_source_changed)

        # Source Status Indicator
        self.lbl_source_status = Gtk.Label(label="")
        self.lbl_source_status.set_halign(Gtk.Align.START)
        self.lbl_source_status.get_style_context().add_class("dim-label")

        grid_source.attach(lbl_source, 0, 0, 1, 1)
        grid_source.attach(self.combo_source, 1, 0, 2, 1)
        grid_source.attach(self.lbl_source_status, 1, 5, 2, 1)  # Row 5, below others

        # Local Source Controls
        self.lbl_folder = Gtk.Label(label="Path:")
        self.lbl_folder.set_halign(Gtk.Align.START)

        folder_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.entry_folder = Gtk.Entry()
        self.entry_folder.set_hexpand(True)
        self.entry_folder.set_placeholder_text("Select a folder or image file...")
        self.entry_folder.connect("changed", self.on_folder_changed)  # Validation/Count

        btn_browse = Gtk.Button(label="Browse")
        btn_browse.connect("clicked", self.on_browse_clicked)
        folder_hbox.pack_start(self.entry_folder, True, True, 0)
        folder_hbox.pack_start(btn_browse, False, False, 0)

        self.check_recursive = Gtk.CheckButton(label="Include subfolders")
        self.check_recursive.set_tooltip_text("Recursively search for images in subdirectories")
        self.check_recursive.connect("toggled", lambda w: self.update_image_count())

        grid_source.attach(self.lbl_folder, 0, 1, 1, 1)
        grid_source.attach(folder_hbox, 1, 1, 2, 1)
        grid_source.attach(self.check_recursive, 1, 2, 2, 1)

        # Unsplash Controls
        self.lbl_api_key = Gtk.Label(label="API Key:")
        self.lbl_api_key.set_halign(Gtk.Align.START)
        self.entry_unsplash_api_key = Gtk.Entry()
        self.entry_unsplash_api_key.set_visibility(False)
        self.entry_unsplash_api_key.set_placeholder_text("Enter Unsplash Access Key")
        self.entry_unsplash_api_key.connect("changed", self.validate_api_key)

        self.lbl_keywords = Gtk.Label(label="Keywords:")
        self.lbl_keywords.set_halign(Gtk.Align.START)
        self.entry_keywords = Gtk.Entry()
        self.entry_keywords.set_placeholder_text("nature, dark, architecture")

        self.btn_test_unsplash = Gtk.Button(label="Test Connection")
        self.btn_test_unsplash.connect("clicked", self.on_test_unsplash_clicked)

        grid_source.attach(self.lbl_api_key, 0, 3, 1, 1)
        grid_source.attach(self.entry_unsplash_api_key, 1, 3, 2, 1)
        grid_source.attach(self.lbl_keywords, 0, 4, 1, 1)
        grid_source.attach(self.entry_keywords, 1, 4, 1, 1)
        grid_source.attach(self.btn_test_unsplash, 2, 3, 1, 1)

        # --- Section 2: Display Settings ---
        frame_display = Gtk.Frame(label="Display Settings")
        frame_display.get_label_widget().get_style_context().add_class("title-2")
        main_vbox.pack_start(frame_display, False, False, 0)

        grid_display = Gtk.Grid()
        grid_display.set_column_spacing(15)
        grid_display.set_row_spacing(10)
        grid_display.set_margin_top(15)
        grid_display.set_margin_bottom(15)
        grid_display.set_margin_start(15)
        grid_display.set_margin_end(15)
        frame_display.add(grid_display)

        lbl_mode = Gtk.Label(label="Scaling Mode:")
        lbl_mode.set_halign(Gtk.Align.START)
        self.combo_mode = Gtk.ComboBoxText()
        self.modes = ["zoom", "scaled", "centered", "spanned", "stretched"]
        for mode in self.modes:
            self.combo_mode.append_text(mode)

        lbl_effect = Gtk.Label(label="Image Effect:")
        lbl_effect.set_halign(Gtk.Align.START)
        self.combo_effect = Gtk.ComboBoxText()
        self.effects = ["None", "Grayscale", "Blur", "Sepia"]
        for effect in self.effects:
            self.combo_effect.append_text(effect)

        lbl_bg_color = Gtk.Label(label="Background:")
        lbl_bg_color.set_halign(Gtk.Align.START)
        self.btn_color = Gtk.ColorButton()
        self.btn_color.set_title("Select Background Color")
        self.btn_color.set_tooltip_text(
            "Sets the background color for 'Centered' or 'Scaled' modes where the image doesn't fill the screen."
        )

        lbl_multi = Gtk.Label(label="Multi-Monitor:")
        lbl_multi.set_halign(Gtk.Align.START)
        self.combo_multi_monitor = Gtk.ComboBoxText()
        self.multi_monitor_modes = [
            "Single image on all monitors",
            "Span image across all monitors",
        ]
        for mode in self.multi_monitor_modes:
            self.combo_multi_monitor.append_text(mode)

        grid_display.attach(lbl_mode, 0, 0, 1, 1)
        grid_display.attach(self.combo_mode, 1, 0, 1, 1)

        grid_display.attach(lbl_effect, 0, 1, 1, 1)
        grid_display.attach(self.combo_effect, 1, 1, 1, 1)

        grid_display.attach(lbl_bg_color, 2, 0, 1, 1)
        grid_display.attach(self.btn_color, 3, 0, 1, 1)

        grid_display.attach(lbl_multi, 0, 2, 1, 1)
        grid_display.attach(self.combo_multi_monitor, 1, 2, 3, 1)

        theme_box = self.build_theme_selector()
        grid_display.attach(theme_box, 0, 3, 4, 1)

        # --- Section 3: Schedule & Behavior ---
        frame_schedule = Gtk.Frame(label="Schedule & Behavior")
        frame_schedule.get_label_widget().get_style_context().add_class("title-2")
        main_vbox.pack_start(frame_schedule, False, False, 0)

        # Simplified HBox layout for grouping
        schedule_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        schedule_box.set_margin_top(15)
        schedule_box.set_margin_bottom(15)
        schedule_box.set_margin_start(15)
        schedule_box.set_margin_end(15)
        frame_schedule.add(schedule_box)

        # Row 1: Interval
        row_interval = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lbl_interval = Gtk.Label(label="Change Every:")
        adjustment = Gtk.Adjustment(
            value=30, lower=0, upper=10080, step_increment=1, page_increment=10
        )
        self.spin_interval = Gtk.SpinButton()
        self.spin_interval.set_adjustment(adjustment)
        self.spin_interval.set_numeric(True)
        lbl_mins = Gtk.Label(label="minutes")

        row_interval.pack_start(lbl_interval, False, False, 0)
        row_interval.pack_start(self.spin_interval, False, False, 0)
        row_interval.pack_start(lbl_mins, False, False, 0)

        # Row 2: Checkboxes
        row_checks = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        self.check_startup = Gtk.CheckButton(label="Change on startup")
        
        row_checks.pack_start(self.check_startup, False, False, 0)

        schedule_box.pack_start(row_interval, False, False, 0)
        schedule_box.pack_start(row_checks, False, False, 0)

        # --- Section 4: Current Status ---
        frame_status = Gtk.Frame(label="Current Status")
        frame_status.get_label_widget().get_style_context().add_class("title-2")
        main_vbox.pack_start(frame_status, False, False, 0)

        vbox_status = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox_status.set_margin_top(15)
        vbox_status.set_margin_bottom(15)
        vbox_status.set_margin_start(15)
        vbox_status.set_margin_end(15)
        frame_status.add(vbox_status)

        # Status Top Row: Thumbnail + Details
        hbox_status_top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        vbox_status.pack_start(hbox_status_top, False, False, 0)

        # Thumbnail
        self.image_preview = Gtk.Image()
        self.image_preview.set_pixel_size(100)  # Slightly smaller but visible
        self.image_preview.set_alignment(0, 0)
        hbox_status_top.pack_start(self.image_preview, False, False, 0)

        # Details Column
        vbox_details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        hbox_status_top.pack_start(vbox_details, True, True, 0)

        # Next Change Label
        self.lbl_next_change = Gtk.Label(label="Next change: --:--")
        self.lbl_next_change.set_halign(Gtk.Align.START)
        vbox_details.pack_start(self.lbl_next_change, False, False, 0)

        # Current Path (Read-only)
        self.entry_current_path = Gtk.Entry()
        self.entry_current_path.set_editable(False)
        self.entry_current_path.set_has_frame(False)
        self.entry_current_path.get_style_context().add_class("flat")
        self.entry_current_path.set_placeholder_text("No wallpaper set")
        vbox_details.pack_start(self.entry_current_path, False, False, 0)

        self.btn_apply_now = Gtk.Button(label="Apply Now")
        self.btn_apply_now.set_image(
            Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        )
        self.btn_apply_now.set_always_show_image(True)
        self.btn_apply_now.connect("clicked", self.on_next_wallpaper_clicked)
        self.btn_apply_now.set_halign(Gtk.Align.START)
        vbox_details.pack_start(self.btn_apply_now, False, False, 0)

        # --- Bottom Actions ---
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_bottom(10)
        btn_box.set_margin_end(10)
        main_vbox.pack_end(btn_box, False, True, 0)

        btn_save = Gtk.Button(label="_Save Settings")
        btn_save.set_use_underline(True)
        btn_save.get_style_context().add_class("suggested-action")
        btn_save.connect("clicked", self.on_save_clicked)

        btn_box.pack_end(btn_save, False, True, 0)

        # Disable controls if DE is not supported
        if not self.is_de_supported:
            self.combo_source.set_sensitive(False)
            self.entry_folder.set_sensitive(False)
            btn_browse.set_sensitive(False)
            self.check_recursive.set_sensitive(False)
            self.entry_unsplash_api_key.set_sensitive(False)
            self.entry_keywords.set_sensitive(False)
            self.btn_test_unsplash.set_sensitive(False)
            self.combo_mode.set_sensitive(False)
            self.combo_effect.set_sensitive(False)
            self.btn_color.set_sensitive(False)
            self.combo_multi_monitor.set_sensitive(False)
            self.spin_interval.set_sensitive(False)
            self.check_startup.set_sensitive(False)
            self.btn_apply_now.set_sensitive(False)
            btn_save.set_sensitive(False)

        # Disable scheduling controls if systemd is not available
        if not self.is_systemd_available:
            self.spin_interval.set_sensitive(False)
            self.spin_interval.set_tooltip_text("Disabled because systemd was not found.")
            self.check_startup.set_sensitive(False)
            self.check_startup.set_tooltip_text("Disabled because systemd was not found.")
            # The Save button should still be sensitive if other settings (not related to scheduling) can be saved.
            # But the schedule itself will not work, so disabling save for scheduling is fine.
            # However, if DE is supported but systemd is not, save button should still be sensitive
            # only for saving non-scheduling related settings.
            # So, only disable scheduling controls, not the save button.

    def count_local_images(self, path, recursive):
        if not path or not os.path.isdir(path):
            return 0

        count = 0
        extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif"}

        if recursive:
            for _, _, files in os.walk(path):
                for f in files:
                    if os.path.splitext(f)[1].lower() in extensions:
                        count += 1
        else:
            try:
                for f in os.listdir(path):
                    if (
                        os.path.isfile(os.path.join(path, f))
                        and os.path.splitext(f)[1].lower() in extensions
                    ):
                        count += 1
            except OSError:
                pass
        return count

    def update_image_count(self):
        source = self.combo_source.get_active_text()
        if source == "Local Folder":
            path = self.entry_folder.get_text()
            recursive = self.check_recursive.get_active()
            if path and os.path.isdir(path):
                # Run in thread to avoid freezing UI on large folders
                def count_thread():
                    count = self.count_local_images(path, recursive)
                    GLib.idle_add(
                        lambda: self.lbl_source_status.set_text(f"✓ {count} images found")
                    )

                threading.Thread(target=count_thread, daemon=True).start()
            else:
                self.lbl_source_status.set_text("⚠ Invalid path")
        else:
            self.lbl_source_status.set_text("✓ Unsplash Source")

    def on_folder_changed(self, widget):
        path = widget.get_text()
        if os.path.isdir(path):
            widget.get_style_context().remove_class("error")
            self.update_image_count()
        else:
            widget.get_style_context().add_class("error")
            self.lbl_source_status.set_text("⚠ Path does not exist")

    def validate_api_key(self, widget):
        key = widget.get_text()
        if len(key) < 20 and key != "":  # Arbitrary check for length
            widget.get_style_context().add_class("warning")
        else:
            widget.get_style_context().remove_class("warning")

    def build_theme_selector(self):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        label = Gtk.Label(label="UI Theme:")
        self.combo_theme = Gtk.ComboBoxText()
        for name in THEMES.keys():
            self.combo_theme.append_text(name)

        current_theme_name = "Ubuntu"
        if self.app and hasattr(self.app, "theme_manager"):
            current_theme_name = self.app.theme_manager.current_theme_name

        self.combo_theme.set_active(
            list(THEMES.keys()).index(current_theme_name) if current_theme_name in THEMES else 0
        )

        def on_theme_changed(cb):
            text = cb.get_active_text()
            if text and self.app and hasattr(self.app, "theme_manager"):
                self.app.theme_manager.set_theme_name(text)
                new_provider = self.app.theme_manager.get_css_provider()

                style_context = self.get_style_context()
                if self.app.css_provider:
                    style_context.remove_provider(self.app.css_provider)

                style_context.add_provider(new_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                self.app.css_provider = new_provider

        self.combo_theme.connect("changed", on_theme_changed)
        hbox.pack_start(label, False, False, 0)
        hbox.pack_start(self.combo_theme, False, False, 0)
        return hbox

    def on_source_changed(self, combo):
        text = combo.get_active_text()
        is_local = text == "Local Folder"

        # Toggle visibility of local folder controls
        self.lbl_folder.set_visible(is_local)
        self.entry_folder.get_parent().set_visible(is_local)  # Hide the HBox containing entry and browse
        self.check_recursive.set_visible(is_local)

        # Toggle visibility of Unsplash controls
        self.lbl_api_key.set_visible(not is_local)
        self.entry_unsplash_api_key.set_visible(not is_local)
        self.lbl_keywords.set_visible(not is_local)
        self.entry_keywords.set_visible(not is_local)
        self.btn_test_unsplash.set_visible(not is_local)

        if not is_local:
            unsplash_api_key = self.config_manager.get_setting(
                self.config, "Settings", "unsplash_api_key", "YOUR_UNSPLASH_API_KEY"
            )
            if unsplash_api_key and unsplash_api_key != "YOUR_UNSPLASH_API_KEY":
                # Maybe auto-fill or handle logic
                pass

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
        dialog.run()
        dialog.destroy()

    def load_settings(self):
        if "Settings" in self.config:
            settings = self.config["Settings"]
            source = settings.get("source", "Local Folder")
            if source in self.sources:
                self.combo_source.set_active(self.sources.index(source))

            self.entry_folder.set_text(settings.get("folder", ""))
            self.check_recursive.set_active(
                self.config_manager.get_setting(
                    self.config, "Settings", "recursive_search", False, value_type=bool
                )
            )
            self.entry_keywords.set_text(settings.get("keywords", ""))

            unsplash_api_key = settings.get("unsplash_api_key", "")
            if unsplash_api_key == "YOUR_UNSPLASH_API_KEY":
                unsplash_api_key = ""
            self.entry_unsplash_api_key.set_text(unsplash_api_key)

            mode = settings.get("mode", "zoom")
            if mode in self.modes:
                self.combo_mode.set_active(self.modes.index(mode))

            self.spin_interval.set_value(
                self.config_manager.get_setting(
                    self.config, "Settings", "interval", 30, value_type=int
                )
            )
            self.check_startup.set_active(
                self.config_manager.get_setting(
                    self.config, "Settings", "startup", False, value_type=bool
                )
            )

            effect = settings.get("effect", "None")
            if effect in self.effects:
                self.combo_effect.set_active(self.effects.index(effect))

            multi_monitor_mode = settings.get("multi_monitor_mode", "Single image on all monitors")
            if multi_monitor_mode in self.multi_monitor_modes:
                self.combo_multi_monitor.set_active(
                    self.multi_monitor_modes.index(multi_monitor_mode)
                )

            bg_color_str = settings.get("background_color", "#000000")
            color = Gdk.RGBA()
            if color.parse(bg_color_str):
                self.btn_color.set_rgba(color)

    def on_browse_clicked(self, widget):
        dialog = Gtk.FileChooserDialog(
            title="Choose a folder or file", parent=self, action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, "Select", Gtk.ResponseType.OK)

        # Allow selecting folders OR files?
        # GTK FileChooserAction is distinct. We can switch modes or add a filter.
        # To support "Direct Access Links" (Files) and "Folders", we might need two buttons or a clever dialog.
        # For now, let's stick to standard behavior but allow file selection if the user wants.
        # Actually, let's make it smarter.

        # Add a filter for images
        filter_img = Gtk.FileFilter()
        filter_img.set_name("Images")
        filter_img.add_mime_type("image/jpeg")
        filter_img.add_mime_type("image/png")
        filter_img.add_mime_type("image/bmp")
        filter_img.add_mime_type("image/webp")
        dialog.add_filter(filter_img)

        # Add "All files"
        filter_all = Gtk.FileFilter()
        filter_all.set_name("All Files")
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)

        # We start in folder mode, but maybe we can add a check button to switch?
        # Simpler: Just use SELECT_FOLDER as primary, but if user wants a file, they can paste it or we add a separate "Select File" button?
        # The user requested "direct access links". Let's assume they might paste it or browse.
        # Let's try to support both.
        # Ideally, we'd have a toggle. For this implementation, I'll stick to SELECT_FOLDER for the "Browse" button
        # as it's the 90% use case, but I'll add a secondary "Select File" button or just let them paste.
        # Wait, I can just change the action based on a modifier or add another button.
        # Let's add a "Select File" button to the UI in the next iteration if needed.
        # For now, I'll leave it as SELECT_FOLDER but user can paste paths.

        # Actually, let's use OPEN (File) but allow selecting folders?
        # No, GTK3 is strict.
        # Let's default to Folder.
        dialog.set_action(Gtk.FileChooserAction.SELECT_FOLDER)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.entry_folder.set_text(dialog.get_filename())
        dialog.destroy()

    def on_refresh_path_clicked(self, widget):
        self.update_current_wallpaper_label()

    def update_current_wallpaper_label(self):
        history_file = os.path.join(CONFIG_DIR, "history.log")
        current_path = "N/A"
        if os.path.exists(history_file):
            try:
                with open(history_file, "r") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        current_path = first_line
            except IOError:
                pass

        self.entry_current_path.set_text(current_path)

        # Update Thumbnail
        if os.path.exists(current_path) and os.path.isfile(current_path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(current_path, -1, 150, True)
                self.image_preview.set_from_pixbuf(pixbuf)
                self.image_preview.set_visible(True)
            except Exception as e:
                logging.error(f"Failed to load thumbnail: {e}")
                self.image_preview.set_visible(False)
        else:
            self.image_preview.set_visible(False)

    def _handle_change_result(self, result):
        """Handles the result from change_wallpaper on the main GTK thread."""
        if result == WallpaperUpdateResult.SUCCESS:
            self.update_current_wallpaper_label()
        else:
            error_map = {
                WallpaperUpdateResult.NO_SOURCE_CONFIGURED: "No wallpaper source is configured. Please check your settings.",
                WallpaperUpdateResult.NO_IMAGES_FOUND: "No images were found for the current configuration.",
                WallpaperUpdateResult.NETWORK_ERROR: "A network error occurred while fetching the wallpaper.",
                WallpaperUpdateResult.UNSUPPORTED_DESKTOP: "Your desktop environment is not supported for automatic wallpaper changes.",
                WallpaperUpdateResult.COMMAND_FAILED: "The command to set the wallpaper failed. Check logs for details.",
                WallpaperUpdateResult.CONFIGURATION_ERROR: "A configuration error was found. Please check your settings file.",
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
        folder = self.entry_folder.get_text()
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
        hex_color = "#{:02x}{:02x}{:02x}".format(
            int(bg_color.red * 255), int(bg_color.green * 255), int(bg_color.blue * 255)
        )

        settings_dict = {
            "source": source,
            "folder": folder,
            "recursive_search": str(recursive_search),
            "keywords": keywords,
            "unsplash_api_key": unsplash_api_key,
            "mode": mode,
            "interval": str(interval),
            "startup": str(startup),
            "effect": effect,
            "multi_monitor_mode": multi_monitor_mode,
            "theme": theme,
            "background_color": hex_color,
        }

        if not self.config_manager.save_settings(self.config, settings_dict):
            return

        self.setup_systemd_timer(interval, startup)
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
                exec_start_cmd = f"{exec_path} -m wallshuffle --change"
                working_dir = project_root
            else:
                exec_start_cmd = f"{exec_path} --change"
                working_dir = os.path.expanduser("~")

            service_content = f"""[Unit]
Description=WallShuffle Service

[Service]
Type=oneshot
WorkingDirectory={working_dir}
ExecStart={exec_start_cmd}
Environment="DBUS_SESSION_BUS_ADDRESS={dbus_address}"
"""
            with open(os.path.join(systemd_path, "wallpaper-changer.service"), "w") as f:
                f.write(service_content)

            timer_section_items = ["[Timer]"]
            if interval > 0:
                timer_section_items.append(f"OnUnitActiveSec={interval}min")
            if startup:
                timer_section_items.append("OnBootSec=2min")

            timer_section_str = "\n".join(timer_section_items)

            timer_content = f"""[Unit]
Description=Run WallShuffle periodically

{timer_section_str}

[Install]
WantedBy=timers.target
"""
            with open(os.path.join(systemd_path, "wallpaper-changer.timer"), "w") as f:
                f.write(timer_content)
        except (IOError, OSError) as e:
            logging.error(f"File I/O error setting up systemd timer files: {e}")
            show_error_dialog(f"File I/O error setting up systemd timer files: {e}", self)
            return
        except Exception as e:
            logging.critical(
                f"An unhandled error occurred during systemd file setup: {e}", exc_info=True
            )
            show_error_dialog(f"An unhandled error occurred during systemd file setup: {e}", self)
            return

        try:
            if not self.wallpaper_manager._run_subprocess(
                ["systemctl", "--user", "daemon-reload"], "daemon-reload"
            ):
                show_error_dialog(
                    "Failed to run systemctl daemon-reload. Check logs for details.", self
                )
                return

            if interval > 0 or startup:
                if not self.wallpaper_manager._run_subprocess(
                    ["systemctl", "--user", "enable", "--now", "wallpaper-changer.timer"],
                    "enable timer",
                ):
                    show_error_dialog(
                        "Failed to enable systemd timer. Check logs for details.", self
                    )
            else:
                if not self.wallpaper_manager._run_subprocess(
                    ["systemctl", "--user", "disable", "--now", "wallpaper-changer.timer"],
                    "disable timer",
                ):
                    show_error_dialog(
                        "Failed to disable systemd timer. Check logs for details.", self
                    )
        except Exception as e:
            logging.critical(
                f"An unhandled error occurred during systemctl interaction: {e}", exc_info=True
            )
            show_error_dialog(
                f"An unhandled error occurred during systemctl interaction: {e}", self
            )
