import os
import unittest
from unittest.mock import patch, MagicMock
from wallshuffle.core import change_wallpaper, WallpaperUpdateResult

class TestHeadlessMode(unittest.TestCase):
    """Tests the application behavior in headless environments."""

    @patch("wallshuffle.wallpaper_manager.subprocess.run")
    @patch("wallshuffle.config_manager.ConfigManager.load_settings")
    @patch("wallshuffle.wallpaper_manager.shutil.which")
    def test_change_wallpaper_headless(self, mock_which, mock_load_settings, mock_run):
        """
        Tests that change_wallpaper succeeds even if no DISPLAY is set,
        using the xrandr fallback and avoiding Gdk crashes.
        """
        # 1. Setup headless environment
        env_patch = {
            "DISPLAY": "",
            "WAYLAND_DISPLAY": "",
            "XDG_CURRENT_DESKTOP": "gnome"
        }
        
        # 2. Mock configuration (Local Folder with one image)
        mock_config = MagicMock()
        settings_data = {
            "source": "Local Folder",
            "folder": "/tmp/test_wallpapers",
            "mode": "zoom",
            "effect": "None",
            "multi_monitor_mode": "Single image on all monitors"
        }
        mock_config.__contains__.side_effect = lambda key: key in ["Settings", "FolderCategories"]
        mock_config.__getitem__.side_effect = lambda key: settings_data if key == "Settings" else {}
        mock_config.has_option.side_effect = lambda section, option: True
        mock_config.get.side_effect = lambda section, option, **kwargs: settings_data.get(option)
        mock_config.getboolean.side_effect = lambda section, option: settings_data.get(option, False)
        mock_load_settings.return_value = mock_config
        
        # 3. Mock file system
        def side_effect_isfile(path):
            return path.endswith(".jpg")
        def side_effect_isdir(path):
            return not path.endswith(".jpg")
        def side_effect_exists(path):
            return True

        with patch("os.path.exists", side_effect=side_effect_exists), \
             patch("os.path.isdir", side_effect=side_effect_isdir), \
             patch("os.listdir", return_value=["img1.jpg"]), \
             patch("os.path.isfile", side_effect=side_effect_isfile), \
             patch("os.path.getsize", return_value=1024):
            
            # 4. Mock tool availability (xrandr found, gsettings found)
            def side_effect_which(tool):
                if tool in ["xrandr", "gsettings"]:
                    return f"/usr/bin/{tool}"
                return None
            mock_which.side_effect = side_effect_which
            
            # 5. Mock subprocess for xrandr query and gsettings set
            mock_run.return_value = MagicMock(returncode=0, stdout="connected 1920x1080+0+0")
            
            # 6. Execute
            with patch.dict(os.environ, env_patch, clear=False):
                # Ensure no Gdk is imported/used or it's isolated
                result = change_wallpaper()
                
            # 7. Verify
            self.assertEqual(result, WallpaperUpdateResult.SUCCESS)
            
            # Check if gsettings was called (standard GNOME behavior)
            # Find the call that sets the uri
            gsettings_calls = [call for call in mock_run.call_args_list if "gsettings" in call.args[0]]
            self.assertTrue(len(gsettings_calls) > 0, "gsettings should have been called to set wallpaper")

if __name__ == "__main__":
    unittest.main()
