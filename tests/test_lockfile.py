"""
Test lockfile functionality including creation, stale detection, and cleanup.
"""

import os
import time
from unittest.mock import patch

import pytest

# We test the lockfile logic by importing and testing the WallpaperApp class
# Note: This requires GTK which may not be available in all test environments


def test_lockfile_stale_detection_with_dead_process(tmp_path):
    """Test that stale lock with dead PID is detected"""
    from wallshuffle.app import WallpaperApp

    # Create a mock lock file with a non-existent PID
    lock_file = tmp_path / "wallshuffle.lock"
    lock_file.write_text("999999\n")  # Very unlikely to be a real PID

    # Create app instance (but don't start it)
    with patch("wallshuffle.app.CONFIG_DIR", str(tmp_path)):
        app = WallpaperApp()

        # Test stale lock detection
        is_stale = app._is_lock_stale(str(lock_file))

        assert is_stale is True, "Lock with dead PID should be detected as stale"


def test_lockfile_stale_detection_with_running_process(tmp_path):
    """Test that lock with running process is NOT detected as stale"""
    from wallshuffle.app import WallpaperApp

    # Create a mock lock file with current process PID
    lock_file = tmp_path / "wallshuffle.lock"
    lock_file.write_text(f"{os.getpid()}\n")

    # Create app instance
    with patch("wallshuffle.app.CONFIG_DIR", str(tmp_path)):
        app = WallpaperApp()

        # Test stale lock detection
        is_stale = app._is_lock_stale(str(lock_file))

        assert is_stale is False, "Lock with running PID should NOT be detected as stale"


def test_lockfile_stale_detection_by_age(tmp_path):
    """Test that old lockfile without valid PID is detected as stale"""
    from wallshuffle.app import WallpaperApp

    # Create a mock lock file with invalid PID
    lock_file = tmp_path / "wallshuffle.lock"
    lock_file.write_text("not_a_pid\n")

    # Make it old (modify mtime to 2hours ago)
    two_hours_ago = time.time() - (2 * 3600)
    os.utime(lock_file, (two_hours_ago, two_hours_ago))

    # Create app instance
    with patch("wallshuffle.app.CONFIG_DIR", str(tmp_path)):
        app = WallpaperApp()

        # Test stale lock detection (default threshold is 1 hour)
        is_stale = app._is_lock_stale(str(lock_file))

        assert is_stale is True, "Old lockfile should be detected as stale"


def test_lockfile_not_stale_if_recent(tmp_path):
    """Test that recent lockfile without valid PID is NOT stale"""
    from wallshuffle.app import WallpaperApp

    # Create a mock lock file with invalid PID but recent timestamp
    lock_file = tmp_path / "wallshuffle.lock"
    lock_file.write_text("not_a_pid\n")
    # File is freshly created, so it's recent

    # Create app instance
    with patch("wallshuffle.app.CONFIG_DIR", str(tmp_path)):
        app = WallpaperApp()

        # Test stale lock detection (file is fresh,so not stale)
        is_stale = app._is_lock_stale(str(lock_file))

        assert is_stale is False, "Recent lockfile should NOT be stale"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
