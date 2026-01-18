import logging
import os
import unittest
from unittest.mock import MagicMock, patch

from wallshuffle.__main__ import configure_backend
from wallshuffle.config_manager import ConfigManager


class TestRobustness(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)  # Suppress logging during tests

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_config_safe_harbor(self):
        """Test that get_setting returns fallback on error instead of crashing."""
        cm = ConfigManager()

        # Mock config object that raises an error on get()
        mock_config = MagicMock()
        mock_config.has_option.return_value = True
        mock_config.get.side_effect = Exception("Simulated Config Crash")

        # Should not raise exception
        value = cm.get_setting(mock_config, "Settings", "some_key", fallback="default_value")
        self.assertEqual(value, "default_value")

    def test_backend_detection_wayland(self):
        """Test that X11 is forced when Wayland is detected."""
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"}, clear=True):
            if "GDK_BACKEND" in os.environ:
                del os.environ["GDK_BACKEND"]

            configure_backend()
            self.assertEqual(os.environ.get("GDK_BACKEND"), "x11")

    def test_backend_detection_x11(self):
        """Test that backend is NOT changed for X11 sessions."""
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"}, clear=True):
            if "GDK_BACKEND" in os.environ:
                del os.environ["GDK_BACKEND"]

            configure_backend()
            self.assertIsNone(os.environ.get("GDK_BACKEND"))

if __name__ == "__main__":
    unittest.main()
