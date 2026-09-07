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
        """Verify paths with spaces/quotes become valid percent-encoded file URIs in JS."""
        dangerous_path = "/home/user/My 'Cool' Wallpaper.jpg"
        script = self.manager._generate_kde_script(dangerous_path, "zoom")

        # Path.as_uri() encodes spaces and quotes for a safe JS string.
        self.assertIn("file://", script)
        self.assertIn("%20", script)
        self.assertIn("Cool", script)
        self.assertIn("Wallpaper.jpg", script)
        # Single quote should not appear raw inside the JS array string payload.
        self.assertNotIn("My 'Cool'", script)

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
