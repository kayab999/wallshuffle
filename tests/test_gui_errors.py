import configparser
from unittest.mock import patch

import gi
import pytest

gi.require_version("Gtk", "3.0")

from wallshuffle.core import WallpaperUpdateResult


# Mock the Gtk.MessageDialog for testing GUI interactions
@pytest.fixture
def mock_show_error_dialog():
    with patch("wallshuffle.online_sources.show_error_dialog") as mock_dialog:
        yield mock_dialog


# Mock configparser to control settings for tests
@pytest.fixture
def mock_config_file(tmp_path):
    # Create a temporary config directory and file for the test
    test_config_dir = tmp_path / ".config" / "wallshuffle"
    test_config_dir.mkdir(parents=True)
    test_config_file = test_config_dir / "config.ini"

    # Patch CONFIG_DIR and CONFIG_FILE in the wallshuffle module
    with (
        patch("wallshuffle.config_manager.CONFIG_DIR", str(test_config_dir)),
        patch("wallshuffle.config_manager.CONFIG_FILE", str(test_config_file)),
    ):
        yield test_config_file


# Test that change_wallpaper returns NO_SOURCE_CONFIGURED when Unsplash API key is missing (fallback to Local Folder with no folder)
def test_unsplash_api_key_missing_fallback(mock_config_file):
    # Ensure the config file exists but doesn't have the API key set
    config = configparser.ConfigParser()
    config["Settings"] = {"source": "Unsplash", "keywords": "test"}
    with open(mock_config_file, "w") as f:
        config.write(f)

    def get_setting_side_effect(config, section, option, fallback=None, value_type=str):
        if option == "source":
            return "Unsplash"
        if option == "unsplash_api_key":
            return "YOUR_UNSPLASH_API_KEY"
        if option == "folder":
            return "" # Fallback to local folder with no folder
        return fallback

    # Temporarily set UNSPLASH_API_KEY to the default placeholder
    with patch(
        "wallshuffle.core.get_config_manager"
    ) as mock_get_cm, patch(
        "wallshuffle.wallpaper_manager.WallpaperManager.get_desktop_environment", return_value="gnome"
    ):
        mock_instance = mock_get_cm.return_value
        mock_instance.get_setting.side_effect = get_setting_side_effect
        mock_instance.load_settings.return_value = config

        # Import change_wallpaper here to ensure mocks are active when it's loaded
        from wallshuffle.core import change_wallpaper

        result = change_wallpaper()

    # Assert that it returned NO_SOURCE_CONFIGURED (because of the fallback to empty local folder)
    assert result == WallpaperUpdateResult.NO_SOURCE_CONFIGURED
