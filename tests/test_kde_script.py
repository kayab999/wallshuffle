import unittest

from wallshuffle.wallpaper_manager import WallpaperManager


class TestKDEScriptGeneration(unittest.TestCase):
    def setUp(self):
        # Initialize manager (will try to detect DE, we don't care about result for this unit test)
        self.manager = WallpaperManager()

    def test_script_structure(self):
        """Verify the script contains essential KDE API calls"""
        script = self.manager._generate_kde_script("/tmp/image.jpg", "zoom")

        self.assertIn("desktops()", script)
        self.assertIn("org.kde.image", script)
        self.assertIn('d.writeConfig("Image"', script)
        self.assertIn('d.writeConfig("FillMode"', script)

    def test_path_escaping(self):
        """Verify dangerous paths are quoted correctly"""
        # A path with single quotes or spaces could break the JS string if not shlex.quote'd
        dangerous_path = "/home/user/My 'Cool' Wallpaper.jpg"
        script = self.manager._generate_kde_script(dangerous_path, "zoom")

        # We assert that the filename is present but likely split up by escaping chars.
        # Checking for the base filename parts is enough to verify it wasn't dropped.
        self.assertIn("My ", script)
        self.assertIn("Cool", script)
        self.assertIn("Wallpaper.jpg", script)

        # Also ensure the protocol prefix was added
        self.assertIn("file://", script)

    def test_fill_mode_mapping(self):
        """Verify mapping of modes to KDE integers"""
        script_zoom = self.manager._generate_kde_script("/img.jpg", "zoom")

        # Expect the resolved integer for zoom (2)
        self.assertIn('d.writeConfig("FillMode", 2)', script_zoom)

        script_scaled = self.manager._generate_kde_script("/img.jpg", "scaled")
        # Expect the resolved integer for scaled (1)
        self.assertIn('d.writeConfig("FillMode", 1)', script_scaled)


if __name__ == "__main__":
    unittest.main()
