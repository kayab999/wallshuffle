import tempfile
import unittest
from unittest.mock import MagicMock, patch

from wallshuffle.constants import WallpaperSource
from wallshuffle.core import WallpaperUpdateResult, change_wallpaper


class TestCoreUnsplash(unittest.TestCase):
    def setUp(self):
        self.config_dir = tempfile.mkdtemp()

    def _mock_config(self, settings):
        mock_cm = MagicMock()
        mock_cm.load_settings.return_value = {"Settings": settings}

        def get_setting(config, section, key, default=None, value_type=str):
            value = settings.get(key, default)
            if value_type is bool and isinstance(value, str):
                return value.lower() == "true"
            return value

        mock_cm.get_setting.side_effect = get_setting
        return mock_cm

    @patch("wallshuffle.core.CONFIG_DIR")
    @patch("wallshuffle.core.get_config_manager")
    @patch("wallshuffle.core.WallpaperManager")
    @patch("wallshuffle.core.OnlineSourceManager")
    def test_parallel_unsplash_fetch(self, mock_osm_cls, mock_manager_cls, mock_get_cm, _mock_config_dir):
        with patch("wallshuffle.core.CONFIG_DIR", self.config_dir):
            mock_get_cm.return_value = self._mock_config({
                "source": WallpaperSource.UNSPLASH,
                "unsplash_api_key": "valid_key",
                "keywords": "nature",
                "multi_monitor_mode": "Different image on each monitor",
            })
            manager = mock_manager_cls.return_value
            manager.get_monitor_info.return_value = [
                {"width": 1920, "height": 1080, "x": 0, "y": 0},
                {"width": 1920, "height": 1080, "x": 1920, "y": 0},
            ]
            manager.apply_desktop_settings.return_value = (True, "")

            instance = mock_osm_cls.return_value
            instance.fetch_unsplash_wallpaper.side_effect = [
                ("/tmp/img0.jpg", ""),
                ("/tmp/img1.jpg", ""),
            ]

            result, _ = change_wallpaper()
            self.assertEqual(result, WallpaperUpdateResult.SUCCESS)
            self.assertEqual(instance.fetch_unsplash_wallpaper.call_count, 2)


if __name__ == "__main__":
    unittest.main()
