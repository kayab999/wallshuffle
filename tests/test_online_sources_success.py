import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from wallshuffle.online_sources import OnlineSourceManager


class TestOnlineSourcesSuccess(unittest.TestCase):
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

    @patch("wallshuffle.online_sources.CONFIG_DIR")
    @patch("wallshuffle.online_sources.CACHE_DIR")
    def test_fetch_downloads_and_returns_path(self, mock_cache_dir, mock_config_dir):
        mock_config_dir.__str__ = lambda self: self.temp_dir.name  # type: ignore[method-assign]
        with patch("wallshuffle.online_sources.CONFIG_DIR", self.temp_dir.name), patch(
            "wallshuffle.online_sources.CACHE_DIR", os.path.join(self.temp_dir.name, "cache")
        ):
            self.manager.session = MagicMock()
            api_response = MagicMock()
            api_response.raise_for_status.return_value = None
            api_response.json.return_value = {"urls": {"full": "https://images.example/full.jpg"}}

            image_response = MagicMock()
            image_response.raise_for_status.return_value = None
            image_response.iter_content.return_value = [b"fake-image-bytes"]

            self.manager.session.get.side_effect = [api_response, image_response]

            with patch.object(self.manager, "_get_cached_image", return_value=None):
                path, error = self.manager.fetch_unsplash_wallpaper("nature", index=1)

            self.assertIsNotNone(path)
            self.assertEqual(error, "")
            self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
