import os
import shutil
import tempfile
import unittest

from PIL import Image

from wallshuffle.constants import MAX_EFFECT_DIMENSION, ImageEffect
from wallshuffle.effects import _maybe_downscale, apply_image_effect


class TestEffects(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.small_path = os.path.join(self.temp_dir, "small.jpg")
        self.large_path = os.path.join(self.temp_dir, "large.jpg")
        Image.new("RGB", (200, 200), color="blue").save(self.small_path)
        Image.new("RGB", (MAX_EFFECT_DIMENSION + 500, 1000), color="red").save(self.large_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_none_effect_returns_original(self):
        self.assertEqual(apply_image_effect(self.small_path, ImageEffect.NONE), self.small_path)

    def test_grayscale_creates_processed_file(self):
        result = apply_image_effect(self.small_path, ImageEffect.GRAYSCALE)
        self.assertNotEqual(result, self.small_path)
        self.assertTrue(os.path.exists(result))
        with Image.open(result) as image:
            self.assertEqual(image.mode, "RGB")

    def test_blur_creates_processed_file(self):
        result = apply_image_effect(self.small_path, ImageEffect.BLUR)
        self.assertTrue(os.path.exists(result))

    def test_sepia_creates_processed_file(self):
        result = apply_image_effect(self.small_path, ImageEffect.SEPIA)
        self.assertTrue(os.path.exists(result))

    def test_downscale_large_image(self):
        with Image.open(self.large_path) as image:
            scaled = _maybe_downscale(image)
            self.assertLessEqual(max(scaled.size), MAX_EFFECT_DIMENSION)

    def test_missing_file_returns_original(self):
        missing = os.path.join(self.temp_dir, "missing.jpg")
        self.assertEqual(apply_image_effect(missing, ImageEffect.GRAYSCALE), missing)


if __name__ == "__main__":
    unittest.main()
