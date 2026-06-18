import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from wallshuffle.constants import ImageEffect, MultiMonitorMode, WallpaperSource
from wallshuffle.core import WallpaperUpdateResult, change_wallpaper


class TestCoreSources(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, ".config", "wallshuffle")
        os.makedirs(self.config_dir, exist_ok=True)
        self.img_path = os.path.join(self.temp_dir, "wall.jpg")
        Image.new("RGB", (64, 64), color="green").save(self.img_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _mock_config(self, settings):
        mock_cm = MagicMock()
        mock_cm.load_settings.return_value = {"Settings": settings}

        def get_setting(config, section, key, default=None, value_type=str):
            value = settings.get(key, default)
            if value_type is bool and isinstance(value, str):
                return value.lower() == "true"
            if value_type is int and isinstance(value, str):
                return int(value)
            return value

        mock_cm.get_setting.side_effect = get_setting
        return mock_cm

    @patch("wallshuffle.core.CONFIG_DIR")
    @patch("wallshuffle.core.get_config_manager")
    @patch("wallshuffle.core.WallpaperManager")
    def test_local_single_file_source(self, mock_manager_cls, mock_get_cm, mock_config_dir):
        mock_config_dir.__str__ = lambda self: self.config_dir  # type: ignore[method-assign]
        with patch("wallshuffle.core.CONFIG_DIR", self.config_dir):
            mock_get_cm.return_value = self._mock_config({
                "source": WallpaperSource.LOCAL_FOLDER,
                "folder": self.img_path,
                "mode": "zoom",
            })
            mock_manager_cls.return_value.get_monitor_info.return_value = [{"width": 1920, "height": 1080}]
            mock_manager_cls.return_value.apply_desktop_settings.return_value = (True, "")

            result, _ = change_wallpaper()
            self.assertEqual(result, WallpaperUpdateResult.SUCCESS)

    @patch("wallshuffle.core.CONFIG_DIR")
    @patch("wallshuffle.core.get_config_manager")
    @patch("wallshuffle.core.WallpaperManager")
    def test_missing_folder_returns_error(self, mock_manager_cls, mock_get_cm, mock_config_dir):
        with patch("wallshuffle.core.CONFIG_DIR", self.config_dir):
            mock_get_cm.return_value = self._mock_config({
                "source": WallpaperSource.LOCAL_FOLDER,
                "folder": "",
            })
            mock_manager_cls.return_value.get_monitor_info.return_value = []

            result, message = change_wallpaper()
            self.assertEqual(result, WallpaperUpdateResult.NO_SOURCE_CONFIGURED)
            self.assertIn("folder", message.lower())

    @patch("wallshuffle.core.CONFIG_DIR")
    @patch("wallshuffle.core.get_config_manager")
    @patch("wallshuffle.core.WallpaperManager")
    @patch("wallshuffle.core.requests.get")
    def test_url_source_download(self, mock_get, mock_manager_cls, mock_get_cm, mock_config_dir):
        with patch("wallshuffle.core.CONFIG_DIR", self.config_dir):
            mock_get_cm.return_value = self._mock_config({
                "source": WallpaperSource.URL,
                "hyperlink_url": "https://example.com/wall.jpg",
                "mode": "zoom",
            })
            mock_manager_cls.return_value.get_monitor_info.return_value = [{"width": 1920, "height": 1080}]
            mock_manager_cls.return_value.apply_desktop_settings.return_value = (True, "")

            response = MagicMock()
            response.headers = {"Content-Length": str(os.path.getsize(self.img_path))}
            response.iter_content.return_value = [open(self.img_path, "rb").read()]
            response.raise_for_status.return_value = None
            mock_get.return_value = response

            result, _ = change_wallpaper()
            self.assertEqual(result, WallpaperUpdateResult.SUCCESS)

    @patch("wallshuffle.core.CONFIG_DIR")
    @patch("wallshuffle.core.get_config_manager")
    @patch("wallshuffle.core.WallpaperManager")
    def test_span_mode_composites(self, mock_manager_cls, mock_get_cm, mock_config_dir):
        with patch("wallshuffle.core.CONFIG_DIR", self.config_dir):
            mock_get_cm.return_value = self._mock_config({
                "source": WallpaperSource.LOCAL_FOLDER,
                "folder": self.img_path,
                "multi_monitor_mode": MultiMonitorMode.SPAN,
                "mode": "zoom",
            })
            manager = mock_manager_cls.return_value
            manager.get_monitor_info.return_value = [
                {"width": 1920, "height": 1080, "x": 0, "y": 0},
                {"width": 1920, "height": 1080, "x": 1920, "y": 0},
            ]
            manager.create_composite_image.return_value = self.img_path
            manager.apply_desktop_settings.return_value = (True, "")

            result, _ = change_wallpaper()
            self.assertEqual(result, WallpaperUpdateResult.SUCCESS)
            manager.create_composite_image.assert_called_once()

    @patch("wallshuffle.core.CONFIG_DIR")
    @patch("wallshuffle.core.get_config_manager")
    @patch("wallshuffle.core.WallpaperManager")
    def test_grayscale_effect_applied(self, mock_manager_cls, mock_get_cm, mock_config_dir):
        with patch("wallshuffle.core.CONFIG_DIR", self.config_dir):
            mock_get_cm.return_value = self._mock_config({
                "source": WallpaperSource.LOCAL_FOLDER,
                "folder": self.img_path,
                "effect": ImageEffect.GRAYSCALE,
                "mode": "zoom",
            })
            mock_manager_cls.return_value.get_monitor_info.return_value = [{"width": 1920, "height": 1080}]
            mock_manager_cls.return_value.apply_desktop_settings.return_value = (True, "")

            result, _ = change_wallpaper()
            self.assertEqual(result, WallpaperUpdateResult.SUCCESS)


if __name__ == "__main__":
    unittest.main()
