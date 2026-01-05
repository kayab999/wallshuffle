import logging
import sys
import os

# Ensure we can import the package
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from wallshuffle.utils import check_systemd_available
from wallshuffle.wallpaper_manager import WallpaperManager

# Setup logging to console
logging.basicConfig(level=logging.DEBUG)

print("--- Systemd Check (from wallshuffle.utils) ---")
is_systemd = check_systemd_available()
print(f"Result: {is_systemd}")

print("\n--- DE Check (from wallshuffle.wallpaper_manager) ---")
manager = WallpaperManager()
de = manager.get_desktop_environment()
print(f"Result: {de}")

if is_systemd and de != "unknown":
    print("\nSUCCESS: Both checks passed with new logic.")
    sys.exit(0)
else:
    print("\nFAILURE: One or both checks failed.")
    sys.exit(1)
