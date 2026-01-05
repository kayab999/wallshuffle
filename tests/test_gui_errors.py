import configparser
from unittest.mock import patch

import gi
import pytest

gi.require_version("Gtk", "3.0")


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


# Test that an error dialog is shown when Unsplash API key is not configured
def test_unsplash_api_key_missing_shows_dialog(mock_show_error_dialog, mock_config_file):
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
        return fallback

    # Temporarily set UNSPLASH_API_KEY to the default placeholder
    with patch(
        "wallshuffle.config_manager.ConfigManager.get_setting", side_effect=get_setting_side_effect
    ), patch(
        "wallshuffle.wallpaper_manager.WallpaperManager.get_desktop_environment", return_value="gnome"
    ):
        # Import change_wallpaper here to ensure mocks are active when it's loaded
        from wallshuffle import change_wallpaper

        change_wallpaper()

    # Assert that show_error_dialog was called
    mock_show_error_dialog.assert_called_once()
    mock_show_error_dialog.assert_called_with(
        "Unsplash API key is not configured. Please set it in the settings.", parent=None
    )
