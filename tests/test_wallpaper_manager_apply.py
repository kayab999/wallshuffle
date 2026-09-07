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

    def test_cap_canvas_size_large(self):
        from wallshuffle.constants import MAX_CANVAS_PIXELS

        manager = WallpaperManager()
        # 15360x4320 = 66MP > 33MP cap
        w, h, scale = manager._cap_canvas_size(15360, 4320)
        self.assertLessEqual(w * h, MAX_CANVAS_PIXELS)
        self.assertLess(scale, 1.0)
        self.assertEqual((w, h), (10922, 3072))

    def test_cap_canvas_size_small_no_scaling(self):
        manager = WallpaperManager()
        w, h, scale = manager._cap_canvas_size(3280, 1080)
        self.assertEqual((w, h), (3280, 1080))
        self.assertEqual(scale, 1.0)

    def test_cap_canvas_size_zero(self):
        manager = WallpaperManager()
        w, h, scale = manager._cap_canvas_size(0, 0)
        self.assertEqual(scale, 1.0)

    def test_downscale_for_canvas_bilinear_threshold(self):
        manager = WallpaperManager()
        # Source 8000x6000 > 2*1920x1080 => should downscale via BILINEAR thumbnail
        large = Image.new("RGB", (8000, 6000))
        down = manager._downscale_for_canvas(large, 1920, 1080)
        self.assertLessEqual(max(down.size), 3840)  # 2*1920
        self.assertLess(down.size[0] * down.size[1], large.size[0] * large.size[1])
        # Small source should return same object (no copy)
        small = Image.new("RGB", (1000, 800))
        same = manager._downscale_for_canvas(small, 1920, 1080)
        self.assertIs(same, small)

    @patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "KDE"}, clear=False)
    @patch("wallshuffle.wallpaper_manager.WallpaperManager._run_subprocess")
    def test_apply_kde_settings_invokes_dbus(self, mock_run):
        mock_run.return_value = (True, "")
        manager = WallpaperManager()
        success, _ = manager.apply_kde_settings("zoom", [self.image_path])
        self.assertTrue(success)
        mock_run.assert_called_once()
        self.assertIn("dbus-send", mock_run.call_args[0][0][0])

    def test_resolve_usable_image_path_follows_symlink(self):
        link_path = os.path.join(self.temp_dir, "alias.jpg")
        os.symlink(self.image_path, link_path)
        manager = WallpaperManager()
        resolved = manager._resolve_usable_image_path(link_path)
        self.assertEqual(resolved, os.path.realpath(self.image_path))

    def test_resolve_usable_image_path_rejects_dangling_symlink(self):
        link_path = os.path.join(self.temp_dir, "broken.jpg")
        os.symlink(os.path.join(self.temp_dir, "missing.jpg"), link_path)
        manager = WallpaperManager()
        self.assertIsNone(manager._resolve_usable_image_path(link_path))

    @patch.object(WallpaperManager, "get_desktop_environment", return_value="gnome")
    @patch.object(WallpaperManager, "apply_gnome_settings", return_value=(True, ""))
    def test_apply_desktop_settings_accepts_symlink_to_image(self, mock_gnome, _mock_de):
        link_path = os.path.join(self.temp_dir, "link.jpg")
        os.symlink(self.image_path, link_path)
        manager = WallpaperManager()
        success, error = manager.apply_desktop_settings("zoom", [link_path])
        self.assertTrue(success, error)
        mock_gnome.assert_called_once()
        applied_paths = mock_gnome.call_args[0][1]
        self.assertEqual(applied_paths, [os.path.realpath(self.image_path)])


if __name__ == "__main__":
    unittest.main()

