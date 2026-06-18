import tempfile
import unittest
from unittest.mock import patch

from wallshuffle.core import WallpaperUpdateResult, change_wallpaper


class TestCoreConfig(unittest.TestCase):
    def setUp(self):
        self.config_dir = tempfile.mkdtemp()

    @patch("wallshuffle.core.CONFIG_DIR")
    @patch("wallshuffle.core.get_config_manager")
    def test_missing_settings_section(self, mock_get_cm, _mock_config_dir):
        with patch("wallshuffle.core.CONFIG_DIR", self.config_dir):
            mock_get_cm.return_value.load_settings.return_value = {}
            result, message = change_wallpaper()
            self.assertEqual(result, WallpaperUpdateResult.CONFIGURATION_ERROR)
            self.assertIn("Settings", message)


if __name__ == "__main__":
    unittest.main()
