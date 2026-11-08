"""Transactional temp-dir sweep + reference-journal retention (pre-commit audit)."""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from wallshuffle.constants import ImageEffect, WallpaperSource
from wallshuffle.core import (
    WallpaperUpdateResult,
    _snapshot_temp_dir,
    _sweep_temp_files,
    change_wallpaper,
)
from wallshuffle.wallpaper_manager import (
    REFERENCES_FILE,
    REFERENCES_FILE_TMP,
    WallpaperManager,
)

XFCE_P0 = "/backdrop/screen0/monitor0/workspace0/last-image"
XFCE_P1 = "/backdrop/screen0/monitor1/workspace0/last-image"


class TestSweepTempFiles(unittest.TestCase):
    """Sweep semantics over references.json (unit level)."""

    def setUp(self):
        self.temp_root = tempfile.mkdtemp(prefix="ws_temp_test_")
        self.pre: dict = {}

    def tearDown(self):
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def _file(self, name, *, mtime=None):
        path = os.path.join(self.temp_root, name)
        with open(path, "wb") as handle:
            handle.write(b"x")
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return os.path.abspath(path)

    def _write_journal(self, slots):
        with open(os.path.join(self.temp_root, REFERENCES_FILE), "w") as handle:
            json.dump({"slots": slots}, handle)

    def _snapshot(self):
        self.pre = _snapshot_temp_dir(self.temp_root)
        return self.pre

    def test_sweep_failure_keeps_active_refs_and_attempt_files(self):
        live = self._file("live.jpg")
        self._write_journal({"xfce:/prop0": [live]})
        self._snapshot()
        attempt = self._file("attempt.jpg")

        _sweep_temp_files(self.temp_root, self.pre, None)

        self.assertTrue(os.path.exists(live))
        self.assertTrue(os.path.exists(attempt))

    def test_sweep_failure_deletes_unreferenced_orphans(self):
        live = self._file("live.jpg")
        orphan = self._file("orphan.jpg")
        self._write_journal({"xfce:/prop0": [live]})
        self._snapshot()

        _sweep_temp_files(self.temp_root, self.pre, None)

        self.assertTrue(os.path.exists(live))
        self.assertFalse(os.path.exists(orphan))

    def test_sweep_failure_missing_journal_fail_safe(self):
        first = self._file("first.jpg")
        second = self._file("second.jpg")
        self._snapshot()
        new = self._file("new.jpg")

        _sweep_temp_files(self.temp_root, self.pre, None)

        # Without the journal we cannot know which file the DE still shows:
        # nothing pre-existing is deleted by a failing attempt.
        self.assertTrue(all(os.path.exists(p) for p in (first, second, new)))

    def test_sweep_failure_corrupt_journal_fail_safe(self):
        pre_existing = self._file("first.jpg")
        with open(os.path.join(self.temp_root, REFERENCES_FILE), "w") as handle:
            handle.write("{not json")
        self._snapshot()
        new = self._file("new.jpg")

        _sweep_temp_files(self.temp_root, self.pre, None)

        self.assertTrue(os.path.exists(pre_existing))
        self.assertTrue(os.path.exists(new))

    def test_sweep_success_keeps_only_applied(self):
        stale = self._file("stale.jpg")
        self._write_journal({"xfce:/prop0": [stale]})
        self._snapshot()
        applied = self._file("applied.jpg")

        _sweep_temp_files(self.temp_root, self.pre, {applied})

        self.assertFalse(os.path.exists(stale))
        self.assertTrue(os.path.exists(applied))
        # The sweep never touches the journal itself (apply layer writes it).
        self.assertTrue(os.path.exists(os.path.join(self.temp_root, REFERENCES_FILE)))

    def test_sweep_failure_treats_overwrite_as_attempt_new(self):
        overwritten = self._file("composite.jpg", mtime=1_000_000_000)
        self._snapshot()
        os.utime(overwritten)

        _sweep_temp_files(self.temp_root, self.pre, None)

        self.assertTrue(os.path.exists(overwritten))

    def test_sweep_ignores_journal_paths_outside_temp(self):
        live = self._file("live.jpg")
        other = self._file("other.jpg")
        self._write_journal(
            {"xfce:/prop0": [live], "uri": ["/nonexistent/missing.jpg", other]}
        )
        self._snapshot()

        _sweep_temp_files(self.temp_root, self.pre, None)

        self.assertTrue(os.path.exists(live))
        self.assertTrue(os.path.exists(other))

    def test_sweep_purges_stale_journal_tmp(self):
        keeper = self._file("keeper.jpg")
        self._write_journal({"xfce:/prop0": [keeper]})
        self._snapshot()
        stale_tmp = os.path.join(self.temp_root, REFERENCES_FILE_TMP)
        with open(stale_tmp, "w") as handle:
            handle.write("{}")

        _sweep_temp_files(self.temp_root, self.pre, None)

        self.assertFalse(os.path.exists(stale_tmp))
        self.assertTrue(os.path.exists(keeper))

    def test_sweep_noop_when_empty(self):
        self._snapshot()
        _sweep_temp_files(self.temp_root, self.pre, None)  # must not raise


class TestXfcePartialApplyRetention(unittest.TestCase):
    """User scenario S/A/B/C: a partial XFCE failure must never delete the
    wallpapers still displayed (per-output journal slots)."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="ws_xfce_journal_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_file(self, name):
        path = os.path.join(self.temp_dir, name)
        Image.new("RGB", (8, 8), color="green").save(path)
        return os.path.abspath(path)

    def _apply(self, fail_prop, monitor0, monitor1):
        """Runs the real apply_xfce_settings: monitor0->paths[0], monitor1->paths[1]."""
        manager = WallpaperManager()
        manager.desktop_environment = "xfce"
        props = MagicMock()
        props.returncode = 0
        props.stdout = f"{XFCE_P0}\n{XFCE_P1}\n"

        def fake_write(cmd, label):
            if fail_prop and cmd[4] == fail_prop:
                return False, f"xfconf write failed: {cmd[4]}"
            return True, ""

        with (
            patch("wallshuffle.wallpaper_manager.subprocess.run", return_value=props),
            patch.object(WallpaperManager, "_run_subprocess", side_effect=fake_write),
            patch("wallshuffle.wallpaper_manager._temp_dir_path", return_value=self.temp_dir),
        ):
            return manager.apply_xfce_settings("zoom", [monitor0, monitor1])

    def _slots(self):
        with open(os.path.join(self.temp_dir, REFERENCES_FILE), "r") as handle:
            return json.load(handle)["slots"]

    def _jpgs(self):
        return sorted(
            f for f in os.listdir(self.temp_dir) if f.endswith(".jpg")
        )

    def test_two_consecutive_partial_failures_keep_live_wallpapers(self):
        # Round 0: full success — both properties point at S.
        s_path = self._write_file("s.jpg")
        ok, error = self._apply(None, s_path, s_path)
        self.assertTrue(ok, error)
        self.assertEqual(self._slots(), {XFCE_P0: [s_path], XFCE_P1: [s_path]})

        pre = _snapshot_temp_dir(self.temp_dir)

        # Attempt A: monitor0 -> A succeeds, monitor1 write fails.
        a_path = self._write_file("a.jpg")
        ok, _ = self._apply(XFCE_P1, a_path, a_path)
        self.assertFalse(ok)
        self.assertEqual(self._slots(), {XFCE_P0: [a_path], XFCE_P1: [s_path]})
        _sweep_temp_files(self.temp_dir, pre, None)
        self.assertTrue(os.path.exists(a_path), "monitor 0 shows A: must survive")
        self.assertTrue(os.path.exists(s_path))

        pre = _snapshot_temp_dir(self.temp_dir)

        # Attempt B: fails at monitor0 before updating any property.
        b_path = self._write_file("b.jpg")
        ok, _ = self._apply(XFCE_P0, b_path, b_path)
        self.assertFalse(ok)
        self.assertEqual(self._slots(), {XFCE_P0: [a_path], XFCE_P1: [s_path]})
        _sweep_temp_files(self.temp_dir, pre, None)
        self.assertTrue(all(os.path.exists(p) for p in (a_path, s_path, b_path)))

        pre = _snapshot_temp_dir(self.temp_dir)

        # Attempt C: monitor0 -> C succeeds; monitor1 fails again.
        c_path = self._write_file("c.jpg")
        ok, _ = self._apply(XFCE_P1, c_path, c_path)
        self.assertFalse(ok)
        self.assertEqual(self._slots(), {XFCE_P0: [c_path], XFCE_P1: [s_path]})
        _sweep_temp_files(self.temp_dir, pre, None)
        self.assertTrue(os.path.exists(c_path) and os.path.exists(s_path))
        self.assertFalse(os.path.exists(a_path), "A was replaced at monitor0: swept")
        self.assertFalse(os.path.exists(b_path), "B was never referenced: swept")

    def test_repeated_partial_failures_stay_bounded(self):
        s_path = self._write_file("s.jpg")
        ok, _ = self._apply(None, s_path, s_path)
        self.assertTrue(ok)
        pre = _snapshot_temp_dir(self.temp_dir)

        for i in range(4):
            new_path = self._write_file(f"n{i}.jpg")
            self._apply(XFCE_P1, new_path, new_path)
            _sweep_temp_files(self.temp_dir, pre, None)
            # Only monitor0's live file and monitor1's live S survive.
            self.assertEqual(self._jpgs(), sorted(["s.jpg", f"n{i}.jpg"]))
            pre = _snapshot_temp_dir(self.temp_dir)


class TestChangeWallpaperTempLifecycle(unittest.TestCase):
    """Acceptance through the real change_wallpaper() shell."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.temp_dir, ".config", "wallshuffle")
        os.makedirs(self.config_dir, exist_ok=True)
        self.img_path = os.path.join(self.temp_dir, "wall.jpg")
        Image.new("RGB", (64, 64), color="green").save(self.img_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _temp_files(self):
        temp_dir = os.path.join(self.config_dir, "temp")
        if not os.path.isdir(temp_dir):
            return []
        return sorted(os.listdir(temp_dir))

    def _run_failing_change(self):
        mock_cm = MagicMock()
        settings = {
            "source": WallpaperSource.LOCAL_FOLDER,
            "folder": self.img_path,
            "mode": "zoom",
            "effect": ImageEffect.GRAYSCALE,
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
                {"width": 1920, "height": 1080, "x": 0, "y": 0}
            ]
            manager_cls.return_value.apply_desktop_settings.return_value = (False, "no desktop")
            result, message = change_wallpaper()
        return result, message

    def test_repeated_failed_applies_do_not_accumulate(self):
        result, message = self._run_failing_change()
        self.assertEqual(result, WallpaperUpdateResult.DESKTOP_ENVIRONMENT_ERROR, message)
        after_first = self._temp_files()
        self.assertEqual(len(after_first), 1, f"expected exactly the attempt's file, got {after_first}")

        result, _ = self._run_failing_change()
        self.assertEqual(result, WallpaperUpdateResult.DESKTOP_ENVIRONMENT_ERROR)
        after_second = self._temp_files()
        # Second failing attempt swept the first generation; only one file left.
        self.assertEqual(len(after_second), 1, f"expected bounded temp dir, got {after_second}")
        self.assertEqual(after_first, after_second)

    @patch("wallshuffle.core.get_config_manager")
    @patch("wallshuffle.core.WallpaperManager")
    @patch("wallshuffle.core.requests.get")
    def test_url_oversize_rejection_closes_response(self, mock_get, mock_manager_cls, mock_get_cm):
        settings = {
            "source": WallpaperSource.URL,
            "hyperlink_url": "https://example.com/big.jpg",
            "mode": "zoom",
        }
        mock_get_cm.return_value = MagicMock()
        mock_get_cm.return_value.load_settings.return_value = {"Settings": settings}
        mock_get_cm.return_value.get_setting.side_effect = (
            lambda config, section, key, default=None, value_type=str: settings.get(key, default)
        )
        mock_manager_cls.return_value.get_monitor_info.return_value = [{"width": 1920, "height": 1080}]

        with patch("wallshuffle.core.CONFIG_DIR", self.config_dir):
            response = MagicMock()
            response.headers = {"Content-Length": str(51 * 1024 * 1024)}
            response.raise_for_status.return_value = None
            mock_get.return_value = response

            result, message = change_wallpaper()

        self.assertEqual(result, WallpaperUpdateResult.NETWORK_ERROR, message)
        self.assertIn("exceeds maximum", message)
        response.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
