import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from wallshuffle.wallpaper_manager import WallpaperManager


class TestWallpaperManagerDE(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.image_path = os.path.join(self.temp_dir.name, "test.jpg")
        Image.new("RGB", (32, 32), color="green").save(self.image_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("wallshuffle.wallpaper_manager.shutil.which", return_value=None)
    def test_unknown_desktop_returns_error(self, _mock_which):
        manager = WallpaperManager()
        manager.desktop_environment = "unknown"
        success, message = manager.apply_desktop_settings("zoom", [self.image_path])
        self.assertFalse(success)
        self.assertIn("not supported", message.lower())

    @patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "GNOME"}, clear=False)
    @patch("wallshuffle.wallpaper_manager.WallpaperManager._run_subprocess")
    @patch("wallshuffle.wallpaper_manager.subprocess.run")
    def test_gnome_settings_validates_schema(self, mock_run, mock_subprocess_helper):
        schema_result = MagicMock()
        schema_result.returncode = 0
        mock_run.return_value = schema_result
        mock_subprocess_helper.return_value = (True, "")

        manager = WallpaperManager()
        with patch.object(manager, "get_monitor_info", return_value=[]):
            success, _ = manager.apply_gnome_settings("zoom", [self.image_path])
        self.assertTrue(success)

    @patch("wallshuffle.wallpaper_manager.WallpaperManager._run_subprocess")
    @patch("wallshuffle.wallpaper_manager.subprocess.run")
    def test_mate_uses_picture_filename(self, mock_run, mock_subprocess_helper):
        schema_result = MagicMock()
        schema_result.returncode = 0
        mock_run.return_value = schema_result
        mock_subprocess_helper.return_value = (True, "")

        manager = WallpaperManager()
        manager.desktop_environment = "mate"
        with patch.object(manager, "get_monitor_info", return_value=[]):
            success, _ = manager.apply_gnome_settings("zoom", [self.image_path])
        self.assertTrue(success)
        filename_calls = [
            c for c in mock_subprocess_helper.call_args_list
            if c.args and "picture-filename" in c.args[0]
        ]
        self.assertTrue(filename_calls, "MATE should set picture-filename")
        uri_calls = [
            c for c in mock_subprocess_helper.call_args_list
            if c.args and "picture-uri" in c.args[0]
        ]
        self.assertFalse(uri_calls, "MATE must not set picture-uri")

    @patch("wallshuffle.wallpaper_manager.subprocess.run")
    def test_xfce_fails_when_no_last_image_props(self, mock_run):
        result = MagicMock()
        result.returncode = 0
        result.stdout = "/backdrop/screen0/monitor0/workspace0/color-style\n"
        mock_run.return_value = result
        manager = WallpaperManager()
        manager.desktop_environment = "xfce"
        success, message = manager.apply_xfce_settings("zoom", [self.image_path])
        self.assertFalse(success)
        self.assertIn("last-image", message.lower())


if __name__ == "__main__":
    unittest.main()

