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
            # Cache only stores when the list matches the full folder signature.
            images = sorted(
                os.path.join(self.root, name) for name in ("a.jpg", "b.png")
            )
            store_cached_images(self.root, False, images)
            cached = load_cached_images(self.root, False)
            self.assertEqual(sorted(cached or []), images)

    def test_store_skips_partial_image_list(self):
        with patch("wallshuffle.image_index.INDEX_CACHE_DIR", self.cache_dir):
            partial = [os.path.join(self.root, "a.jpg")]
            store_cached_images(self.root, False, partial)
            self.assertIsNone(load_cached_images(self.root, False))

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

    def test_hard_break_cap_10k(self):
        """Fase 1: _scan_folder_once hace hard break tras MAX_CACHED_IMAGES sin stat extra."""
        from wallshuffle import constants as const_mod
        from wallshuffle.image_index import _scan_folder_once

        orig = const_mod.MAX_CACHED_IMAGES
        try:
            const_mod.MAX_CACHED_IMAGES = 5
            # need to patch the imported constant inside image_index as well (from import)
            import wallshuffle.image_index as idx_mod

            old_idx = idx_mod.MAX_CACHED_IMAGES
            idx_mod.MAX_CACHED_IMAGES = 5
            # create 12 files
            for i in range(10):
                path = os.path.join(self.root, f"extra_{i}.bmp")
                with open(path, "w") as h:
                    h.write("x")
            # count stat calls
            import os as _os

            orig_stat = _os.stat
            cnt = {"n": 0}

            def counting_stat(p):
                cnt["n"] += 1
                return orig_stat(p)

            with patch("wallshuffle.image_index.os.stat", side_effect=counting_stat):
                with patch("wallshuffle.image_index._is_usable_image_path", return_value=True):
                    # Need _is_usable to return True to hit stat path; but we patch it
                    images, count, _ = _scan_folder_once(self.root, False)
                    # With hard break, count==5 and images 5, stat calls ~15 (3 per file) not 36 (12*3)
                    self.assertEqual(len(images), 5)
                    self.assertEqual(count, 5)
                    # _is_usable mocked, so stat only in outer loop (1 per file) => 5 calls
                    self.assertLessEqual(cnt["n"], 7)
            idx_mod.MAX_CACHED_IMAGES = old_idx
        finally:
            const_mod.MAX_CACHED_IMAGES = orig
            # cleanup extra files
            for i in range(10):
                try:
                    os.remove(os.path.join(self.root, f"extra_{i}.bmp"))
                except OSError:
                    pass


if __name__ == "__main__":
    unittest.main()
