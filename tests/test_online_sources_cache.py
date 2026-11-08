import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from wallshuffle.online_sources import OnlineSourceManager


class TestOnlineSourcesCache(unittest.TestCase):
    def setUp(self):
        self.mock_config = {"Settings": {}}
        self.mock_config_manager = MagicMock()
        self.mock_config_manager.get_setting.side_effect = lambda config, section, option, fallback, vtype=None: {
            "circuit_breaker_failures": 3,
            "circuit_breaker_cooldown": 15,
            "max_cache_size_mb": 500,
        }.get(option, fallback)
        self.manager = OnlineSourceManager(self.mock_config_manager, self.mock_config)

    def test_cache_keys_differ_by_index(self):
        key_a = self.manager._get_cache_key("nature", index=0)
        key_b = self.manager._get_cache_key("nature", index=1)
        self.assertNotEqual(key_a, key_b)

    def test_cache_keys_encode_keywords_consistently(self):
        key_a = self.manager._get_cache_key("nature city", index=0)
        key_b = self.manager._get_cache_key("nature city", index=0)
        self.assertEqual(key_a, key_b)

    @patch("wallshuffle.online_sources.CACHE_DIR")
    def test_cache_hit_refreshes_mtime(self, mock_cache_dir):
        """LRU real: reusar una imagen refresca su mtime (hallazgo 4)."""
        with tempfile.TemporaryDirectory() as cache_dir:
            cached_path = os.path.join(cache_dir, self.manager._get_cache_key("nature", index=0))
            with open(cached_path, "wb") as handle:
                handle.write(b"x")
            old_time = time.time() - 3600
            os.utime(cached_path, (old_time, old_time))

            with patch("wallshuffle.online_sources.CACHE_DIR", cache_dir):
                path = self.manager._get_cached_image("nature", index=0)

            self.assertEqual(path, cached_path)
            self.assertGreater(os.path.getmtime(cached_path), old_time)

    def test_save_image_to_cache_atomic(self):
        """Escritura atómica: un solo archivo visible, sin restos .tmp (hallazgo 8)."""
        with tempfile.TemporaryDirectory() as cache_dir:
            with patch("wallshuffle.online_sources.CACHE_DIR", cache_dir):
                self.manager._save_image_to_cache(b"payload", "nature", index=0)

            names = sorted(os.listdir(cache_dir))
            self.assertEqual(len(names), 1)
            self.assertFalse(names[0].startswith(".tmp_wall_"))
            self.assertEqual(names[0], self.manager._get_cache_key("nature", index=0))
            with open(os.path.join(cache_dir, names[0]), "rb") as handle:
                self.assertEqual(handle.read(), b"payload")

    def test_save_image_file_to_cache_atomic(self):
        with tempfile.TemporaryDirectory() as dirs:
            src = os.path.join(dirs, "download.jpg")
            with open(src, "wb") as handle:
                handle.write(b"wallpaper")
            cache_dir = os.path.join(dirs, "cache")
            os.makedirs(cache_dir)
            with patch("wallshuffle.online_sources.CACHE_DIR", cache_dir):
                self.manager._save_image_file_to_cache(src, "nature", index=0)

            names = [n for n in os.listdir(cache_dir) if not n.startswith(".tmp_wall_")]
            self.assertEqual(len(names), 1)
            with open(os.path.join(cache_dir, names[0]), "rb") as handle:
                self.assertEqual(handle.read(), b"wallpaper")


if __name__ == "__main__":
    unittest.main()
