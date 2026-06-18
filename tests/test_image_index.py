import os
import tempfile
import unittest
from unittest.mock import patch

from wallshuffle.image_discovery import find_images_in_folder
from wallshuffle.image_index import (
    invalidate_folder_cache,
    load_cached_images,
    store_cached_images,
)


class TestImageIndex(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name
        self.cache_dir = os.path.join(self.temp_dir.name, "cache", "folder_index")
        os.makedirs(self.root, exist_ok=True)
        for name in ("a.jpg", "b.png"):
            path = os.path.join(self.root, name)
            with open(path, "w") as handle:
                handle.write("x")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_store_and_load_cache(self):
        with patch("wallshuffle.image_index.INDEX_CACHE_DIR", self.cache_dir):
            images = [os.path.join(self.root, "a.jpg")]
            store_cached_images(self.root, False, images)
            cached = load_cached_images(self.root, False)
            self.assertEqual(cached, images)

    def test_cache_invalidates_on_new_file(self):
        with patch("wallshuffle.image_index.INDEX_CACHE_DIR", self.cache_dir):
            images = [os.path.join(self.root, "a.jpg")]
            store_cached_images(self.root, False, images)
            with open(os.path.join(self.root, "c.webp"), "w") as handle:
                handle.write("new")
            self.assertIsNone(load_cached_images(self.root, False))

    def test_invalidate_folder_cache(self):
        with patch("wallshuffle.image_index.INDEX_CACHE_DIR", self.cache_dir):
            store_cached_images(self.root, False, ["a"])
            invalidate_folder_cache(self.root, False)
            self.assertIsNone(load_cached_images(self.root, False))

    def test_find_images_uses_cache_on_second_scan(self):
        with patch("wallshuffle.image_index.INDEX_CACHE_DIR", self.cache_dir):
            first = find_images_in_folder(self.root, False)
            with patch("os.walk") as mock_walk:
                second = find_images_in_folder(self.root, False)
                mock_walk.assert_not_called()
            self.assertEqual(len(first), 2)
            self.assertEqual(len(second), 2)


if __name__ == "__main__":
    unittest.main()
