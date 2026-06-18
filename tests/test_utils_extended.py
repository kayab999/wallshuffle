import os
import tempfile
import unittest
from unittest.mock import patch

from wallshuffle.utils import escape_systemd_path, log_wallpaper_history


class TestUtilsExtended(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_dir = os.path.join(self.temp_dir.name, "config")
        os.makedirs(self.config_dir, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_escape_systemd_path_quotes_special_chars(self):
        escaped = escape_systemd_path('/home/user/My%Docs/$wallpaper')
        self.assertTrue(escaped.startswith('"'))
        self.assertIn("%%", escaped)
        self.assertIn("$$", escaped)

    @patch("wallshuffle.utils.CONFIG_DIR")
    def test_log_wallpaper_history_deduplicates(self, mock_config_dir):
        with patch("wallshuffle.utils.CONFIG_DIR", self.config_dir):
            log_wallpaper_history("/tmp/a.jpg")
            log_wallpaper_history("/tmp/b.jpg")
            log_wallpaper_history("/tmp/a.jpg")
            history_file = os.path.join(self.config_dir, "history.log")
            with open(history_file, "r") as handle:
                lines = [line.strip() for line in handle.readlines() if line.strip()]
            self.assertEqual(lines[0], "/tmp/a.jpg")
            self.assertEqual(lines[1], "/tmp/b.jpg")
            self.assertEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main()
