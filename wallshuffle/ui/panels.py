"""GTK panel builders for the main settings window."""


import gi

from .. import __version__
from ..constants import WallpaperSource

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class WindowPanelsMixin:
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

        self.btn_refresh = Gtk.Button()
        self.btn_refresh.set_image(Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON))
        self.btn_refresh.set_tooltip_text("Refresh Status")
        self.btn_refresh.connect("clicked", lambda w: self.poll_timer_status())
        header.pack_end(self.btn_refresh)

        self.btn_about = Gtk.Button()
        self.btn_about.get_style_context().add_class("secondary-button")
        self.btn_about.set_image(Gtk.Image.new_from_icon_name("help-about-symbolic", Gtk.IconSize.BUTTON))
        self.btn_about.set_tooltip_text("General Information")
        self.btn_about.connect("clicked", self.on_about_clicked)
        header.pack_end(self.btn_about)

        self.btn_apply_now = Gtk.Button(label="Next Wallpaper")
        self.btn_apply_now.get_style_context().add_class("primary-button")
        self.btn_apply_now.set_image(Gtk.Image.new_from_icon_name("media-skip-forward-symbolic", Gtk.IconSize.BUTTON))
        self.btn_apply_now.connect("clicked", self.on_next_wallpaper_clicked)
        header.pack_start(self.btn_apply_now)

    def _build_info_bar(self, parent):
        self.info_bar_de = Gtk.InfoBar()
        self.info_bar_de.set_message_type(Gtk.MessageType.WARNING)
        self.info_bar_de.set_no_show_all(True)
        content_area = self.info_bar_de.get_content_area()
        lbl = Gtk.Label(label="Your desktop environment is not officially supported. Automatic changes may fail. Check the README for details.")
        lbl.set_line_wrap(True)
        content_area.add(lbl)
        self.info_bar_de.set_visible(not self.is_de_supported)
        parent.pack_start(self.info_bar_de, False, False, 0)

        # Theme failure warning
        self.info_bar_theme = Gtk.InfoBar()
        self.info_bar_theme.set_message_type(Gtk.MessageType.WARNING)
        self.info_bar_theme.set_no_show_all(True)
        content_area_theme = self.info_bar_theme.get_content_area()
        lbl_theme = Gtk.Label(label="Theme could not be loaded. The app may look different than expected. Check logs for details.")
        lbl_theme.set_line_wrap(True)
        content_area_theme.add(lbl_theme)
        self.info_bar_theme.set_visible(self.theme_engine is None)
        parent.pack_start(self.info_bar_theme, False, False, 0)

    def _build_hero_section(self, parent):
        frame = Gtk.Frame()
        frame.get_style_context().add_class("card")
        parent.pack_start(frame, False, False, 0)

        hero_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        hero_box.set_halign(Gtk.Align.CENTER)
        frame.add(hero_box)

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
        frame = Gtk.Frame()
        frame.get_style_context().add_class("card")
        parent.pack_start(frame, False, False, 0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        frame.add(vbox)

        lbl_section = Gtk.Label(label="Source")
        lbl_section.set_halign(Gtk.Align.START)
        lbl_section.set_markup("<span size='large' weight='bold'>Source</span>")
        vbox.pack_start(lbl_section, False, False, 0)

        source_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        source_box.set_margin_start(10)
        vbox.pack_start(source_box, False, False, 0)

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
        self.btn_manage_folders.get_style_context().add_class("secondary-button")
        self.btn_manage_folders.connect("clicked", self.on_manage_folders_clicked)

        hbox_folder.pack_start(self.combo_folders, True, True, 0)
        hbox_folder.pack_start(self.btn_manage_folders, False, False, 0)
        self.check_recursive = Gtk.CheckButton(label="Include subfolders")
        self.check_recursive.connect("toggled", lambda w: self.update_image_count())
        page_local.pack_start(hbox_folder, False, False, 0)
        page_local.pack_start(self.check_recursive, False, False, 0)
        self.stack_source.add_named(page_local, WallpaperSource.LOCAL_FOLDER)

        # Unsplash Page
        page_unsplash = Gtk.Grid()
        page_unsplash.set_column_spacing(10)
        page_unsplash.set_row_spacing(10)

        self.lbl_api_key = Gtk.Label(label="API Key:")
        self.entry_unsplash_api_key = Gtk.Entry()
        self.entry_unsplash_api_key.set_visibility(False)
        self.entry_unsplash_api_key.set_placeholder_text("Unsplash Access Key")
        self.entry_unsplash_api_key.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "view-reveal-symbolic")
        self.entry_unsplash_api_key.connect("icon-press", self.on_api_key_visibility_toggle)
        self.entry_unsplash_api_key.connect("changed", self.validate_api_key)

        self.lbl_keywords = Gtk.Label(label="Keywords:")
        self.entry_keywords = Gtk.Entry()
        self.entry_keywords.set_placeholder_text("nature, architecture")

        self.btn_test_unsplash = Gtk.Button(label="Test Connection")
        self.btn_test_unsplash.get_style_context().add_class("secondary-button")
        self.btn_test_unsplash.connect("clicked", self.on_test_unsplash_clicked)

        page_unsplash.attach(self.lbl_api_key, 0, 0, 1, 1)
        page_unsplash.attach(self.entry_unsplash_api_key, 1, 0, 1, 1)
        page_unsplash.attach(self.btn_test_unsplash, 2, 0, 1, 1)
        page_unsplash.attach(self.lbl_keywords, 0, 1, 1, 1)
        page_unsplash.attach(self.entry_keywords, 1, 1, 2, 1)
        self.stack_source.add_named(page_unsplash, WallpaperSource.UNSPLASH)

        # URL Page
        page_url = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.entry_url = Gtk.Entry()
        self.entry_url.set_placeholder_text("https://example.com/wallpaper.jpg")
        self.entry_url.set_hexpand(True)
        lbl_url = Gtk.Label(label="Image URL:")
        lbl_url.set_halign(Gtk.Align.START)
        def on_url_changed(widget):
            self.lbl_source_status.set_text("✓ Online image" if widget.get_text().startswith("http") else "⚠ Enter a valid URL")
        self.entry_url.connect("changed", on_url_changed)
        page_url.pack_start(lbl_url, False, False, 0)
        page_url.pack_start(self.entry_url, False, False, 0)
        self.stack_source.add_named(page_url, WallpaperSource.URL)

    def _build_settings_section(self, parent):
        frame = Gtk.Frame()
        frame.get_style_context().add_class("card")
        parent.pack_start(frame, False, False, 0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        frame.add(vbox)

        lbl_section = Gtk.Label(label="Settings")
        lbl_section.set_halign(Gtk.Align.START)
        lbl_section.set_markup("<span size='large' weight='bold'>Settings</span>")
        vbox.pack_start(lbl_section, False, False, 0)

        grid = Gtk.Grid()
        grid.set_column_spacing(20)
        grid.set_row_spacing(15)
        grid.set_margin_start(10)
        vbox.pack_start(grid, False, False, 0)

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
        if self.theme_engine:
            presets = self.theme_engine.store.get_all_presets()
            for name in presets.keys():
                self.combo_theme.append_text(name)

            current_theme = self.theme_engine.get_current_theme_name()
            self.combo_theme.set_active(list(presets.keys()).index(current_theme) if current_theme in presets else 0)
        else:
            self.combo_theme.append_text("Ubuntu")
            self.combo_theme.set_active(0)

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

        # Random Order (Moved out of Automation for visibility)
        grid.attach(Gtk.Label(label="Sequence:", halign=Gtk.Align.START), 0, 4, 1, 1)
        self.check_random_order = Gtk.CheckButton(label="Random Order")
        grid.attach(self.check_random_order, 1, 4, 1, 1)

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

    def _on_theme_event(self, spec):
        """Handle theme change event from the ThemeEngine."""
        self.logger.info(f"UI received theme change event: {spec.id}")

        # Show/hide custom color pickers based on the spec ID
        if spec.id == "Custom":
            if hasattr(self, "box_custom_colors"):
                self.box_custom_colors.show_all()
        else:
            if hasattr(self, "box_custom_colors"):
                self.box_custom_colors.hide()

    def _on_theme_changed(self, cb):
        theme_name = cb.get_active_text()
        if theme_name and self.theme_engine:
            self.theme_engine.set_theme(theme_name)

