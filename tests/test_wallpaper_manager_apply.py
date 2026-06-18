import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from wallshuffle.wallpaper_manager import WallpaperManager


class TestWallpaperManagerApply(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.image_path = os.path.join(self.temp_dir, "wall.jpg")
        Image.new("RGB", (100, 50), color="blue").save(self.image_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_composite_image_scales_to_monitor_bounds(self):
        manager = WallpaperManager()
        monitors = [{"x": 0, "y": 0, "width": 200, "height": 100}]
        output = manager.create_composite_image(self.image_path, monitors)
        self.assertTrue(os.path.exists(output))
        with Image.open(output) as image:
            self.assertEqual(image.size, (200, 100))

    @patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "KDE"}, clear=False)
    @patch("wallshuffle.wallpaper_manager.WallpaperManager._run_subprocess")
    def test_apply_kde_settings_invokes_dbus(self, mock_run):
        mock_run.return_value = (True, "")
        manager = WallpaperManager()
        success, _ = manager.apply_kde_settings("zoom", [self.image_path])
        self.assertTrue(success)
        mock_run.assert_called_once()
        self.assertIn("dbus-send", mock_run.call_args[0][0][0])


if __name__ == "__main__":
    unittest.main()
