import os
import unittest
from unittest.mock import patch

from wallshuffle.gui_helpers import show_error_dialog, wire_dialog_default


class TestGuiHelpers(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_headless_error_prints_to_stderr(self):
        with patch("builtins.print") as mock_print:
            show_error_dialog("Something failed", parent=None)
        mock_print.assert_called()

    def test_wire_dialog_default_sets_entry_and_button(self):
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            self.skipTest("requires a display for Gtk widgets")

        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        Gtk.init([])
        dialog = Gtk.Dialog(title="t", modal=True)
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        entry = Gtk.Entry()
        dialog.get_content_area().pack_start(entry, False, False, 0)
        dialog.show_all()

        button = wire_dialog_default(dialog, Gtk.ResponseType.OK, entry=entry)
        self.assertIsNotNone(button)
        self.assertTrue(button.get_can_default())
        self.assertTrue(entry.get_activates_default())
        self.assertIs(dialog.get_default_widget(), button)
        dialog.destroy()


if __name__ == "__main__":
    unittest.main()
