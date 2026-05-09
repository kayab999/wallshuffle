import configparser
import unittest
from unittest.mock import patch, MagicMock
import os
import shutil
import tempfile

from wallshuffle.core import WallpaperUpdateResult, change_wallpaper

class TestGuiErrors(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.test_dir, ".config", "wallshuffle")
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_file = os.path.join(self.config_dir, "config.ini")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_unsplash_api_key_missing_fallback(self):
        # Ensure the config file exists but doesn't have the API key set
        config = configparser.ConfigParser()
        config["Settings"] = {"source": "Unsplash", "keywords": "test"}
        with open(self.config_file, "w") as f:
            config.write(f)

        def get_setting_side_effect(config, section, option, default=None, value_type=str):
            if option == "source":
                return "Unsplash"
            if option == "unsplash_api_key":
                return "YOUR_UNSPLASH_API_KEY"
            if option == "folder":
                return "" # Fallback to local folder with no folder
            return default

        with patch("wallshuffle.config_manager.CONFIG_DIR", self.config_dir), \
             patch("wallshuffle.config_manager.CONFIG_FILE", self.config_file), \
             patch("wallshuffle.core.get_config_manager") as mock_get_cm, \
             patch("wallshuffle.wallpaper_manager.WallpaperManager.get_desktop_environment", return_value="gnome"):
            
            mock_instance = mock_get_cm.return_value
            mock_instance.get_setting.side_effect = get_setting_side_effect
            mock_instance.load_settings.return_value = config

            result, error_msg = change_wallpaper()

        # Assert that it returned NO_SOURCE_CONFIGURED (because of the fallback to empty local folder)
        self.assertEqual(result, WallpaperUpdateResult.NO_SOURCE_CONFIGURED)

if __name__ == "__main__":
    unittest.main()
