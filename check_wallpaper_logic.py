import logging

from wallshuffle.wallpaper_manager import WallpaperManager

logging.basicConfig(level=logging.DEBUG)
manager = WallpaperManager()
de = manager.desktop_environment
print(f"Detected DE: {de}")

# Test the mapping logic internally
def test_kde_mapping():
    fill_mode_map = {"zoom": 2, "scaled": 1, "centered": 5, "spanned": 4, "stretched": 0}
    # Current map in code is: {"zoom": 6, "scaled": 2, "centered": 1, "spanned": 4, "stretched": 0}
    # If mode is "scaled", it currently sends 2.
    # If mode is "centered", it currently sends 1.
    print("Testing KDE Mapping (Corrected version):")
    for mode in ["zoom", "scaled", "centered", "spanned", "stretched"]:
        print(f"  {mode} -> {fill_mode_map.get(mode)}")

test_kde_mapping()

# Attempt to apply 'scaled' mode and see what happens in logs
# Note: This will actually change the wallpaper if run.
# manager.apply_desktop_settings("scaled", ["/usr/share/backgrounds/warp.png"], "#FF0000")
