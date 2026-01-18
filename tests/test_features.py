
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from wallshuffle.core import WallpaperUpdateResult, change_wallpaper
from wallshuffle.wallpaper_manager import WallpaperManager


class TestWallShuffleFeatures(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.test_dir, ".config", "wallshuffle")
        os.makedirs(self.config_dir, exist_ok=True)

        # Create dummy images
        self.img1_path = os.path.join(self.test_dir, "img1.jpg")
        self.img2_path = os.path.join(self.test_dir, "img2.jpg")
        Image.new('RGB', (100, 100), color='red').save(self.img1_path)
        Image.new('RGB', (100, 100), color='blue').save(self.img2_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_symlink_loop_detection(self):
        # Create Loop: dirA -> linkToB -> dirB -> linkToA
        dirA = os.path.join(self.test_dir, "dirA")
        dirB = os.path.join(self.test_dir, "dirB")
        os.makedirs(dirA)
        os.makedirs(dirB)

        os.symlink(dirB, os.path.join(dirA, "linkToB"))
        os.symlink(dirA, os.path.join(dirB, "linkToA"))

        # Place image in dirB
        shutil.copy(self.img1_path, os.path.join(dirB, "target.jpg"))

        # Mock Config
        mock_config = {
            "Settings": {
                "source": "Local Folder",
                "folder": dirA,
                "recursive_search": "True",
                "mode": "zoom"
            }
        }

        with patch('wallshuffle.core.ConfigManager') as MockConfigManager:
            # Setup the mock instance
            mock_instance = MockConfigManager.return_value
            mock_instance.load_settings.return_value = mock_config

            # Setup get_setting side effects
            def get_setting_side_effect(config, section, key, default=None, value_type=str):
                # Retrieve from our mock_config
                val = mock_config.get(section, {}).get(key, default)
                if value_type is bool:
                    return str(val).lower() == "true"
                return val

            mock_instance.get_setting.side_effect = get_setting_side_effect

            with patch('wallshuffle.core.WallpaperManager'):
                # Run
                # It should not hang or crash
                res = change_wallpaper()
                # Verify we found the image (or at least didn't crash)
                # Since we mock Manager, apply_desktop_settings is successful unless we fail finding images
                self.assertEqual(res, WallpaperUpdateResult.SUCCESS)

    def test_gnome_stitching(self):
        manager = WallpaperManager()

        # Monitors: 2 side-by-side 1920x1080
        monitor_info = [
            {"name": "M1", "x": 0, "y": 0, "width": 1920, "height": 1080},
            {"name": "M2", "x": 1920, "y": 0, "width": 1920, "height": 1080}
        ]

        images = [self.img1_path, self.img2_path]

        result_path = manager.create_multi_monitor_composite(images, monitor_info)

        self.assertTrue(os.path.exists(result_path))
        with Image.open(result_path) as res_img:
            self.assertEqual(res_img.width, 3840)
            self.assertEqual(res_img.height, 1080)
            # Verify pixels? Maybe too detailed, verifying size is good enough for logic check.

if __name__ == '__main__':
    unittest.main()
