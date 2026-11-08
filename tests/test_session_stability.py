"""Long-session stability: bounded temp dir and bounded RSS drift.

Automated evidence only: the apply step is mocked to success so this NOT a
desktop-environment integration test (see scripts/real_desktop_endurance_check.py
for the manual real-DE counterpart). It exercises the full real PIL pipeline
(composite + effect) of core.change_wallpaper() for ~30 consecutive changes and
asserts that neither the temp dir nor process RSS grows over time.
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from wallshuffle.constants import ImageEffect, WallpaperSource
from wallshuffle.core import WallpaperUpdateResult, change_wallpaper

RSS_TOLERANCE_MB = 100


def _vm_field(field_name):
    """RSS in kB from /proc/self/status (Linux)."""
    with open("/proc/self/status", "r") as handle:
        for line in handle:
            if line.startswith(field_name + ":"):
                return int(line.split()[1])
    return None


class TestSessionStability(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, ".config", "wallshuffle")
        os.makedirs(self.config_dir, exist_ok=True)
        self.img_path = os.path.join(self.temp_dir, "wall.jpg")
        Image.new("RGB", (64, 64), color="green").save(self.img_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _successful_change(self):
        mock_cm = MagicMock()
        settings = {
            "source": WallpaperSource.LOCAL_FOLDER,
            "folder": self.img_path,
            "mode": "zoom",
            "effect": ImageEffect.SEPIA,
        }
        mock_cm.load_settings.return_value = {"Settings": settings}
        mock_cm.get_setting.side_effect = lambda config, section, key, default=None, value_type=str: (
            settings.get(key, default)
        )

        with patch("wallshuffle.core.CONFIG_DIR", self.config_dir), \
                patch("wallshuffle.effects.CONFIG_DIR", self.config_dir), \
                patch("wallshuffle.core.get_config_manager", return_value=mock_cm), \
                patch("wallshuffle.core.WallpaperManager") as manager_cls:
            manager_cls.return_value.get_monitor_info.return_value = [
                {"width": 320, "height": 240, "x": 0, "y": 0}
            ]
            manager_cls.return_value.apply_desktop_settings.return_value = (True, "")
            result, message = change_wallpaper()
        self.assertEqual(result, WallpaperUpdateResult.SUCCESS, message)

    def _temp_count(self):
        temp_dir = os.path.join(self.config_dir, "temp")
        if not os.path.isdir(temp_dir):
            return 0
        return len(os.listdir(temp_dir))

    def test_thirty_changes_bound_temp_and_rss(self):
        baseline_rss_kb = _vm_field("VmRSS")
        counts = []

        for _ in range(30):
            self._successful_change()
            counts.append(self._temp_count())

        # Temp dir must stay at the same small set on every single change.
        self.assertLessEqual(counts[0], 2, f"unexpected temp set: {counts[0]}")
        self.assertEqual(counts, [counts[0]] * len(counts), "temp dir grew over the session")

        rss_samples_kb = _vm_field("VmRSS")
        self.assertIsNotNone(baseline_rss_kb)
        drift_mb = (rss_samples_kb - baseline_rss_kb) / 1024.0
        self.assertLess(
            drift_mb, RSS_TOLERANCE_MB,
            f"RSS drifted {drift_mb:.1f} MB over 30 changes (positive = leak)",
        )


if __name__ == "__main__":
    unittest.main()
