"""MAX_INPUT_PIXELS guard: oversized sources are rejected BEFORE decode."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from wallshuffle.constants import ImageEffect
from wallshuffle.effects import apply_image_effect
from wallshuffle.wallpaper_manager import WallpaperManager

RED = (255, 0, 0)


class TestInputLimitComposite(unittest.TestCase):
    "create_composite_image / create_multi_monitor_composite guards."

    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="ws_input_home_")
        self.env = patch.dict("os.environ", {"HOME": self.home})
        self.env.start()
        self.manager = WallpaperManager()
        self.tracked = []

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.home, ignore_errors=True)

    def _temp_dir(self):
        return os.path.join(self.home, ".config", "wallshuffle", "temp")

    def test_create_composite_image_rejects_oversize_source(self):
        source = os.path.join(self.home, "src.jpg")
        Image.new("RGB", (32, 32), color="green").save(source)
        monitor = [{"x": 0, "y": 0, "width": 100, "height": 100}]

        # 32x32 = 1024 px > cap 100 -> must return the ORIGINAL path untouched
        # (policy: skip processing instead of decoding ~300 MB).
        with patch("wallshuffle.wallpaper_manager.MAX_INPUT_PIXELS", 100):
            result = self.manager.create_composite_image(source, monitor)

        self.assertEqual(result, source)
        os.makedirs(self._temp_dir(), exist_ok=True)
        self.assertEqual(os.listdir(self._temp_dir()), [])

    def test_multi_monitor_composite_skips_oversize_monitor(self):
        small = os.path.join(self.home, "small.jpg")
        big = os.path.join(self.home, "big.jpg")
        Image.new("RGB", (4, 4), color="red").save(small)     # 16 px
        Image.new("RGB", (6, 6), color="blue").save(big)      # 36 px
        monitors = [
            {"name": "m0", "x": 0, "y": 0, "width": 100, "height": 100},
            {"name": "m1", "x": 100, "y": 0, "width": 100, "height": 100},
        ]

        with patch("wallshuffle.wallpaper_manager.MAX_INPUT_PIXELS", 20):
            result = self.manager.create_multi_monitor_composite([small, big], monitors, "zoom")

        self.assertTrue(os.path.isfile(result))
        self.tracked.append(result)
        with Image.open(result) as canvas:
            # Canvas spans both monitors; the oversized one keeps the black bg.
            self.assertEqual(canvas.size, (200, 100))
            self.assertLess(sum(abs(c - r) for c, r in zip(canvas.getpixel((50, 50)), RED, strict=True)), 10)
            self.assertEqual(canvas.getpixel((150, 50)), (0, 0, 0))

    def test_multi_monitor_composite_rejects_all_oversize(self):
        big = os.path.join(self.home, "big.jpg")
        Image.new("RGB", (6, 6), color="blue").save(big)
        monitors = [{"name": "m0", "x": 0, "y": 0, "width": 100, "height": 100}]

        with patch("wallshuffle.wallpaper_manager.MAX_INPUT_PIXELS", 20):
            result = self.manager.create_multi_monitor_composite([big], monitors, "zoom")

        self.assertTrue(os.path.isfile(result))
        self.tracked.append(result)
        with Image.open(result) as canvas:
            self.assertEqual(canvas.size, (100, 100))
            self.assertEqual(canvas.getpixel((50, 50)), (0, 0, 0))


class TestInputLimitEffects(unittest.TestCase):
    "effects.apply_image_effect guard (input cap, not canvas cap)."

    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="ws_fx_home_")
        self.config = patch("wallshuffle.effects.CONFIG_DIR", self.home)
        self.config.start()

    def tearDown(self):
        self.config.stop()
        shutil.rmtree(self.home, ignore_errors=True)

    def test_oversize_source_skips_effect(self):
        source = os.path.join(self.home, "src.jpg")
        Image.new("RGB", (6, 6), color="green").save(source)  # 36 px

        with patch("wallshuffle.effects.MAX_INPUT_PIXELS", 20):
            result = apply_image_effect(source, ImageEffect.GRAYSCALE)

        self.assertEqual(result, source)
        fx_dir = os.path.join(self.home, "temp")
        self.assertFalse(os.path.exists(fx_dir) and os.listdir(fx_dir))

    def test_normal_source_still_processed(self):
        source = os.path.join(self.home, "src.jpg")
        Image.new("RGB", (6, 6), color="green").save(source)

        result = apply_image_effect(source, ImageEffect.GRAYSCALE)

        self.assertNotEqual(result, source)
        self.assertTrue(os.path.isfile(result))
        os.remove(result)


if __name__ == "__main__":
    unittest.main()
