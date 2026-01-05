#!/usr/bin/env python3

import logging
import os
import sys

from .app import WallpaperApp
from .core import WallpaperUpdateResult, change_wallpaper
from .ui import WallpaperAppWindow
from .utils import show_error_dialog

# Force prioritize local package directory in module search
app_root = os.path.dirname(os.path.abspath(__file__))
if app_root not in sys.path:
    sys.path.insert(0, app_root)
    logging.debug(f"Prepended to sys.path: {app_root}")

__all__ = [
    "show_error_dialog",
    "change_wallpaper",
    "WallpaperUpdateResult",
    "WallpaperApp",
    "WallpaperAppWindow",
]
