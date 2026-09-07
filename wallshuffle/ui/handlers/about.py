import logging
import os
import subprocess

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ... import __version__
from ...gui_helpers import wire_dialog_default


class AboutHandlersMixin:
    def on_about_clicked(self, widget):
        dialog = Gtk.Dialog(
            title="About WallShuffle",
            transient_for=self,
            modal=True,
            destroy_with_parent=True,
        )
        dialog.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        dialog.set_default_size(650, 560)

        content_area = dialog.get_content_area()
        content_area.set_spacing(0)

        # ── Header Section ──
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        header_box.set_margin_top(18)
        header_box.set_margin_bottom(12)
        header_box.set_margin_start(20)
        header_box.set_margin_end(20)

        lbl_title = Gtk.Label()
        lbl_title.set_markup(f"<span size='xx-large' weight='bold'>WallShuffle</span>  <span size='small' alpha='60%'>v{__version__}</span>")
        lbl_title.set_halign(Gtk.Align.CENTER)
        header_box.pack_start(lbl_title, False, False, 0)

        lbl_tagline = Gtk.Label()
        lbl_tagline.set_markup("<span alpha='70%'>A lightweight, privacy-first wallpaper manager for Linux desktops.</span>")
        lbl_tagline.set_halign(Gtk.Align.CENTER)
        header_box.pack_start(lbl_tagline, False, False, 0)

        content_area.pack_start(header_box, False, False, 0)

        # ── Separator ──
        content_area.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        # ── README Body ──
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_hexpand(True)
        scrolled_window.set_vexpand(True)
        scrolled_window.set_margin_top(8)
        scrolled_window.set_margin_bottom(8)
        scrolled_window.set_margin_start(16)
        scrolled_window.set_margin_end(16)

        textview = Gtk.TextView()
        textview.set_editable(False)
        textview.set_wrap_mode(Gtk.WrapMode.WORD)
        textview.set_cursor_visible(False)
        textview.set_left_margin(8)
        textview.set_right_margin(8)
        textview.set_top_margin(8)
        textview.set_bottom_margin(8)

        # handlers/ -> ui/ -> wallshuffle/ -> package README, then project root
        candidates = [
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "README.md")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "README.md")),
        ]
        readme_content = None
        for readme_path in candidates:
            try:
                with open(readme_path, "r", encoding="utf-8") as f:
                    readme_content = f.read()
                break
            except OSError:
                continue
        if readme_content is None:
            readme_content = (
                f"WallShuffle v{__version__}\n\n"
                "A lightweight, privacy-first wallpaper manager for Linux.\n\n"
                "Use wallshuffle --change for hotkeys and timers.\n"
                "See https://github.com/kayab999/wallshuffle for full documentation."
            )
        textview.get_buffer().set_text(readme_content)

        scrolled_window.add(textview)
        content_area.pack_start(scrolled_window, True, True, 0)

        # ── Footer: Privacy Badge + Donate Button ──
        content_area.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        footer_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        footer_box.set_margin_top(10)
        footer_box.set_margin_bottom(6)
        footer_box.set_margin_start(16)
        footer_box.set_margin_end(16)

        # Privacy badge
        privacy_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        privacy_icon = Gtk.Image.new_from_icon_name("security-high-symbolic", Gtk.IconSize.SMALL_TOOLBAR)
        privacy_box.pack_start(privacy_icon, False, False, 0)
        lbl_privacy = Gtk.Label()
        lbl_privacy.set_markup("<span size='small' alpha='60%'>Privacy-First · Local Processing · No Telemetry</span>")
        privacy_box.pack_start(lbl_privacy, False, False, 0)
        footer_box.pack_start(privacy_box, True, False, 0)

        # Donate button
        btn_donate = Gtk.Button()
        btn_donate_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_donate_icon = Gtk.Image.new_from_icon_name("emblem-favorite-symbolic", Gtk.IconSize.BUTTON)
        btn_donate_box.pack_start(btn_donate_icon, False, False, 0)
        btn_donate_box.pack_start(Gtk.Label(label="Support Development ☕"), False, False, 0)
        btn_donate.add(btn_donate_box)
        btn_donate.get_style_context().add_class("suggested-action")
        btn_donate.set_tooltip_text("Buy me a coffee to support WallShuffle development!")
        btn_donate.connect("clicked", self._on_donate_clicked)
        footer_box.pack_end(btn_donate, False, False, 0)

        content_area.pack_start(footer_box, False, False, 0)

        dialog.show_all()
        wire_dialog_default(dialog, Gtk.ResponseType.CLOSE)
        dialog.run()
        dialog.destroy()

    def _on_donate_clicked(self, widget):
        donate_url = "https://buymeacoffee.com/kayabsoftware"
        try:
            subprocess.Popen(["xdg-open", donate_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logging.warning(f"Could not open donation URL: {e}")
