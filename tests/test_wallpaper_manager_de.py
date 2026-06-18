import unittest
from unittest.mock import MagicMock, patch

from wallshuffle.wallpaper_manager import WallpaperManager


class TestWallpaperManagerDE(unittest.TestCase):
    @patch("wallshuffle.wallpaper_manager.shutil.which", return_value=None)
    @patch("os.path.isfile", return_value=True)
    @patch("os.path.abspath", side_effect=lambda path: path)
    def test_unknown_desktop_returns_error(self, _abspath, _isfile, _mock_which):
        manager = WallpaperManager()
        manager.desktop_environment = "unknown"
        success, message = manager.apply_desktop_settings("zoom", ["/tmp/fake.jpg"])
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
        with patch("os.path.isfile", return_value=True), patch("os.path.abspath", side_effect=lambda p: p):
            with patch.object(manager, "get_monitor_info", return_value=[]):
                success, _ = manager.apply_gnome_settings("zoom", ["/tmp/test.jpg"])
        self.assertTrue(success)


if __name__ == "__main__":
    unittest.main()
