"""Tests for CLI --change (hotkey / timer entrypoint)."""

import unittest
from unittest.mock import patch

from wallshuffle import __main__ as main_mod
from wallshuffle.core import WallpaperUpdateResult


class TestCliChange(unittest.TestCase):
    def test_run_change_wallpaper_success_exit_code(self):
        with patch("wallshuffle.core.change_wallpaper") as mock_change:
            mock_change.return_value = (WallpaperUpdateResult.SUCCESS, "")
            code = main_mod._run_change_wallpaper()
            self.assertEqual(code, 0)
            mock_change.assert_called_once()

    def test_run_change_wallpaper_failure_exit_code(self):
        with patch("wallshuffle.core.change_wallpaper") as mock_change:
            mock_change.return_value = (
                WallpaperUpdateResult.NO_IMAGES_FOUND,
                "none",
            )
            code = main_mod._run_change_wallpaper()
            self.assertEqual(code, 1)

    def test_configure_backend_not_called_for_change(self):
        """GUI-only backend force must not run when argv is --change."""
        with patch.object(main_mod, "configure_backend") as mock_backend:
            with patch.object(main_mod, "setup_logging"):
                with patch.object(main_mod, "_run_change_wallpaper", return_value=0) as mock_run:
                    with patch("sys.argv", ["wallshuffle", "--change"]):
                        with self.assertRaises(SystemExit) as cm:
                            main_mod.main()
                    self.assertEqual(cm.exception.code, 0)
                    mock_run.assert_called_once()
                    mock_backend.assert_not_called()


if __name__ == "__main__":
    unittest.main()
