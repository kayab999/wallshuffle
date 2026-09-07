"""Fase 1: tray poll guard y get_monitor_info cache."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest


def test_tray_poll_guard_prevents_thread_leak():
    """_poll_systemd_timer_state_tray debe usar guard _tray_polling_in_progress."""
    import pathlib

    src = pathlib.Path("wallshuffle/app.py").read_text()
    assert "_tray_polling_in_progress" in src
    assert 'if getattr(self, "_tray_polling_in_progress"' in src
    assert "GLib.idle_add(lambda: setattr(self, \"_tray_polling_in_progress\"" in src


def test_monitor_info_cache_ttl():
    """get_monitor_info debe cachear 1s y timeout 0.5s."""
    from wallshuffle.wallpaper_manager import WallpaperManager

    wm = WallpaperManager.__new__(WallpaperManager)
    import logging
    wm.logger = logging.getLogger("test")
    wm._monitor_info_cache = None
    wm._monitor_cache_ttl = 1.0
    # Mock _get_monitor_info_main to count calls
    calls = {"n": 0}

    def fake_main():
        calls["n"] += 1
        return [{"name": "M0", "width": 1920, "height": 1080, "x": 0, "y": 0}]

    wm._get_monitor_info_main = fake_main  # type: ignore
    wm._get_monitor_info_headless = lambda: []  # type: ignore
    # Need to be on main thread to hit cache path
    import threading as th

    assert th.current_thread() is th.main_thread()
    info1 = wm.get_monitor_info()
    info2 = wm.get_monitor_info()
    assert calls["n"] == 1  # second hit cached
    time.sleep(1.05)
    info3 = wm.get_monitor_info()
    assert calls["n"] == 2  # expired
