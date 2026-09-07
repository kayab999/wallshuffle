import os
import tempfile
import unittest
from unittest.mock import patch

from wallshuffle.utils import escape_systemd_path, escape_systemd_working_dir, log_wallpaper_history


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

    def test_escape_systemd_working_dir_never_quotes(self):
        escaped = escape_systemd_working_dir("/home/user/My%Docs")
        self.assertFalse(escaped.startswith('"'))
        self.assertFalse(escaped.endswith('"'))
        self.assertEqual(escaped, "/home/user/My%%Docs")

    def test_escape_systemd_working_dir_plain_path_unchanged(self):
        self.assertEqual(escape_systemd_working_dir("/home/user"), "/home/user")

    def test_escape_systemd_working_dir_empty(self):
        self.assertEqual(escape_systemd_working_dir(""), "")

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

    def test_log_wallpaper_history_concurrent_timeout(self):
        """Fase 1: history lock con timeout 5s monotónico — no bloquea indefinido y no trunca."""
        import fcntl
        import time

        with patch("wallshuffle.utils.CONFIG_DIR", self.config_dir):
            history_file = os.path.join(self.config_dir, "history.log")
            # ensure file exists
            with open(history_file, "w") as f:
                f.write("/tmp/old.jpg\n")
            orig_size = os.path.getsize(history_file)
            holder = open(history_file, "r+")
            fcntl.flock(holder, fcntl.LOCK_EX)
            try:
                start = time.monotonic()
                log_wallpaper_history("/tmp/new.jpg")
                elapsed = time.monotonic() - start
                self.assertGreaterEqual(elapsed, 4.5)
                self.assertLess(elapsed, 6.5)
                # File must not be truncated to 0
                self.assertGreater(os.path.getsize(history_file), 0)
                # Ensure old content still there (skip)
                with open(history_file, "r") as h:
                    content = h.read()
                self.assertIn("/tmp/old.jpg", content)
            finally:
                fcntl.flock(holder, fcntl.LOCK_UN)
                holder.close()


if __name__ == "__main__":
    unittest.main()
