import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import requests

from wallshuffle.online_sources import OnlineSourceManager


class TestOnlineSourcesFetch(unittest.TestCase):
    def setUp(self):
        OnlineSourceManager._consecutive_failures = 0
        OnlineSourceManager._last_failure_time = None
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_config_manager = MagicMock()
        self.mock_config = {"Settings": {"unsplash_api_key": "valid_key"}}
        self.mock_config_manager.get_setting.side_effect = lambda config, section, option, fallback, vtype=None: {
            "unsplash_api_key": "valid_key",
            "circuit_breaker_failures": 3,
            "circuit_breaker_cooldown": 15,
            "max_cache_size_mb": 500,
        }.get(option, fallback)
        self.manager = OnlineSourceManager(self.mock_config_manager, self.mock_config)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fetch_uses_cache_when_available(self):
        cached_path = os.path.join(self.temp_dir.name, "cached.jpg")
        with open(cached_path, "w") as handle:
            handle.write("cached")

        with patch.object(self.manager, "_get_cached_image", return_value=cached_path):
            path, error = self.manager.fetch_unsplash_wallpaper("nature", index=0)
        self.assertEqual(path, cached_path)
        self.assertEqual(error, "")

    def test_fetch_records_http_failure(self):
        self.manager.session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500")
        mock_response.json.return_value = {}
        self.manager.session.get.return_value = mock_response

        path, error = self.manager.fetch_unsplash_wallpaper("nature", index=0)
        self.assertIsNone(path)
        self.assertIn("HTTP error", error)

    def test_cleanup_old_cache_removes_expired(self):
        cache_dir = os.path.join(self.temp_dir.name, "cache")
        os.makedirs(cache_dir, exist_ok=True)
        old_file = os.path.join(cache_dir, "old.jpg")
        with open(old_file, "w") as handle:
            handle.write("x")
        old_time = 0
        os.utime(old_file, (old_time, old_time))

        with patch("wallshuffle.online_sources.CACHE_DIR", cache_dir), \
                patch("wallshuffle.online_sources.CACHE_EXPIRATION_HOURS", 1), \
                patch("wallshuffle.image_index.INDEX_CACHE_DIR",
                      os.path.join(self.temp_dir.name, "folder_index")):
            OnlineSourceManager.cleanup_old_cache(max_size_mb=500)

        self.assertFalse(os.path.exists(old_file))

    def test_cleanup_old_cache_purges_stale_tmp_wall_files(self):
        """Crash leftovers of atomic cache writes are purged; live writes not."""
        cache_dir = os.path.join(self.temp_dir.name, "cache2")
        os.makedirs(cache_dir, exist_ok=True)
        stale_tmp = os.path.join(cache_dir, ".tmp_wall_stale.jpg")
        fresh_tmp = os.path.join(cache_dir, ".tmp_wall_fresh.jpg")
        keep = os.path.join(cache_dir, "cached_key.jpg")
        for path in (stale_tmp, fresh_tmp, keep):
            with open(path, "w") as handle:
                handle.write("x")
        old_time = time.time() - 7200
        os.utime(stale_tmp, (old_time, old_time))

        idx_dir = os.path.join(self.temp_dir.name, "folder_index2")
        with patch("wallshuffle.online_sources.CACHE_DIR", cache_dir), \
                patch("wallshuffle.image_index.INDEX_CACHE_DIR", idx_dir):
            OnlineSourceManager.cleanup_old_cache(max_size_mb=500)

        self.assertFalse(os.path.exists(stale_tmp), "stale .tmp_wall_ crash leftover")
        self.assertTrue(os.path.exists(fresh_tmp), "in-progress write < 1 h must survive")
        self.assertTrue(os.path.exists(keep))

    def test_test_api_connection_unauthorized(self):
        self.manager.session = MagicMock()
        response = MagicMock()
        response.status_code = 401
        self.manager.session.get.return_value = response
        success, message = self.manager.test_api_connection("bad-key")
        self.assertFalse(success)
        self.assertIn("Unauthorized", message)


if __name__ == "__main__":
    unittest.main()
