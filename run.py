#!/usr/bin/env python3
import os
import sys

if getattr(sys, 'frozen', False):
    # If running as a PyInstaller bundle
    base_dir = sys._MEIPASS
    typelib_dir = os.path.join(base_dir, 'gi_typelibs')
    
    # Prepend to GI_TYPELIB_PATH
    current_path = os.environ.get('GI_TYPELIB_PATH', '')
    os.environ['GI_TYPELIB_PATH'] = f"{typelib_dir}{os.pathsep}{current_path}"

from wallshuffle.__main__ import main

if __name__ == '__main__':
    main()
