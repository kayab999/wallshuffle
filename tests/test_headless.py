import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from wallshuffle.core import WallpaperUpdateResult, change_wallpaper


class TestHeadlessMode(unittest.TestCase):
    """Tests the application behavior in headless environments."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.folder = self.temp_dir.name
        self.image_path = os.path.join(self.folder, "img1.jpg")
        Image.new("RGB", (64, 64), color="red").save(self.image_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("wallshuffle.wallpaper_manager.subprocess.run")
    @patch("wallshuffle.config_manager.ConfigManager.load_settings")
    @patch("wallshuffle.wallpaper_manager.shutil.which")
    def test_change_wallpaper_headless(self, mock_which, mock_load_settings, mock_run):
        """
        Tests that change_wallpaper succeeds even if no DISPLAY is set,
        using the xrandr fallback and avoiding Gdk crashes.
        """
        env_patch = {
            "DISPLAY": "",
            "WAYLAND_DISPLAY": "",
            "XDG_CURRENT_DESKTOP": "gnome",
        }

        mock_config = MagicMock()
        settings_data = {
            "source": "Local Folder",
            "folder": self.folder,
            "mode": "zoom",
            "effect": "None",
            "multi_monitor_mode": "Single image on all monitors",
            "recursive_search": "False",
            "random_order": "True",
        }
        mock_config.__contains__.side_effect = lambda key: key in ["Settings", "FolderCategories"]
        mock_config.__getitem__.side_effect = lambda key: settings_data if key == "Settings" else {}
        mock_config.has_option.side_effect = lambda section, option: option in settings_data
        mock_config.get.side_effect = lambda section, option, **kwargs: settings_data.get(option)
        mock_config.getboolean.side_effect = lambda section, option: str(
            settings_data.get(option, False)
        ).lower() == "true"
        mock_load_settings.return_value = mock_config

        def side_effect_which(tool):
            if tool in ["xrandr", "gsettings"]:
                return f"/usr/bin/{tool}"
            return None

        mock_which.side_effect = side_effect_which
        mock_run.return_value = MagicMock(returncode=0, stdout="connected 1920x1080+0+0")

        with patch.dict(os.environ, env_patch, clear=False):
            # Avoid Gdk path when DISPLAY is empty: force headless monitor detection
            with patch(
                "wallshuffle.wallpaper_manager.WallpaperManager.get_monitor_info",
                return_value=[{"name": "eDP-1", "x": 0, "y": 0, "width": 1920, "height": 1080}],
            ):
                result, error_msg = change_wallpaper()

        self.assertEqual(result, WallpaperUpdateResult.SUCCESS, error_msg)

        gsettings_calls = [
            call for call in mock_run.call_args_list if call.args and "gsettings" in call.args[0]
        ]
        self.assertTrue(len(gsettings_calls) > 0, "gsettings should have been called to set wallpaper")


if __name__ == "__main__":
    unittest.main()
