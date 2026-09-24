#!/bin/bash
set -euo pipefail

# --- Configuration ---
APP_NAME="WallShuffle"
LOWER_APP_NAME="wallshuffle"
VERSION="1.0.3"
VENV_PATH=".venv"
SPEC_FILE="${LOWER_APP_NAME}.spec"
ICON_FILE="assets/icon.png"
FINAL_APPIMAGE_NAME="${APP_NAME}-x86_64.AppImage"
VERSIONED_APPIMAGE_NAME="${APP_NAME}-${VERSION}-x86_64.AppImage"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -x "$VENV_PATH/bin/python" ]; then
    echo "Error: Virtual environment not found at $VENV_PATH. Run: make setup"
    exit 1
fi

echo "--- Ensuring PyInstaller is installed ---"
"$VENV_PATH/bin/pip" install -q "pyinstaller>=6.0"

echo "--- Writing PyInstaller spec (GTK/GI + package data) ---"
cat > "$SPEC_FILE" <<'PY'
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

hiddenimports = collect_submodules("wallshuffle")
hiddenimports += [
    "gi",
    "gi.repository.Gtk",
    "gi.repository.Gdk",
    "gi.repository.GLib",
    "gi.repository.Gio",
    "gi.repository.GObject",
    "gi.repository.GdkPixbuf",
    "gi.repository.Pango",
    "gi.repository.cairo",
    "cairo",
    "requests",
    "urllib3",
    "certifi",
    "charset_normalizer",
    "idna",
    "PIL",
    "PIL.Image",
    "PIL.ImageFilter",
    "PIL.ImageOps",
    "PIL.ImageEnhance",
]

# Optional tray backends — include whichever is present on the build host.
try:
    import gi
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3  # noqa: F401
    hiddenimports.append("gi.repository.AyatanaAppIndicator3")
except Exception:
    try:
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import AppIndicator3  # noqa: F401
        hiddenimports.append("gi.repository.AppIndicator3")
    except Exception:
        pass

datas = [
    ("assets", "assets"),
    ("data", "data"),
    ("assets/icon.png", "."),
    ("README.md", "."),
]
datas += collect_data_files("certifi")
try:
    datas += copy_metadata("requests")
except Exception:
    pass

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="wallshuffle",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["assets/icon.png"],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="wallshuffle",
)
PY

echo "--- Running PyInstaller ---"
"$VENV_PATH/bin/pyinstaller" --noconfirm --clean "$SPEC_FILE"

if [ ! -x "dist/${LOWER_APP_NAME}/wallshuffle" ]; then
    echo "Error: PyInstaller did not produce dist/${LOWER_APP_NAME}/wallshuffle"
    exit 1
fi

echo "--- Preparing AppDir structure ---"
APPDIR_PATH="${APP_NAME}.AppDir"
rm -rf "$APPDIR_PATH"
mkdir -p "$APPDIR_PATH/usr/bin"
mkdir -p "$APPDIR_PATH/usr/share/applications"
mkdir -p "$APPDIR_PATH/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$APPDIR_PATH/usr/share/metainfo"

echo "--- Copying bundled application and assets ---"
cp -a "dist/${LOWER_APP_NAME}/." "$APPDIR_PATH/usr/bin/"

# Desktop file for appimagetool (Name=/Icon=/Exec= must match the binary).
# Only rewrite the first Exec= so the Next Wallpaper action keeps --change.
awk '
  /^Icon=/ { print "Icon=wallshuffle"; next }
  /^Exec=/ && !done { print "Exec=wallshuffle"; done=1; next }
  /^X-GNOME-Autostart-enabled=/ { next }
  { print }
' data/io.github.kayab999.WallShuffle.desktop \
  > "$APPDIR_PATH/${LOWER_APP_NAME}.desktop"
cp "$APPDIR_PATH/${LOWER_APP_NAME}.desktop" "$APPDIR_PATH/usr/share/applications/"

cp "$ICON_FILE" "$APPDIR_PATH/usr/share/icons/hicolor/256x256/apps/${LOWER_APP_NAME}.png"
cp "$ICON_FILE" "$APPDIR_PATH/${LOWER_APP_NAME}.png"
ln -sf "${LOWER_APP_NAME}.png" "$APPDIR_PATH/.DirIcon"
cp data/io.github.kayab999.WallShuffle.metainfo.xml \
   "$APPDIR_PATH/usr/share/metainfo/io.github.kayab999.WallShuffle.metainfo.xml"

echo "--- Creating AppRun entry point ---"
cat > "$APPDIR_PATH/AppRun" <<'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"

export APPDIR="$HERE"
export PATH="$HERE/usr/bin:${PATH:-}"
export LD_LIBRARY_PATH="$HERE/usr/bin${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export XDG_DATA_DIRS="$HERE/usr/share${XDG_DATA_DIRS:+:$XDG_DATA_DIRS}"
export GI_TYPELIB_PATH="$HERE/usr/bin${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
if [ -d "$HERE/usr/bin/gi_typelibs" ]; then
    export GI_TYPELIB_PATH="$HERE/usr/bin/gi_typelibs:$GI_TYPELIB_PATH"
fi

exec "$HERE/usr/bin/wallshuffle" "$@"
EOF
chmod +x "$APPDIR_PATH/AppRun"

echo "--- Downloading and running appimagetool ---"
APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
APPIMAGETOOL_PATH="./appimagetool-x86_64.AppImage"

if [ ! -f "$APPIMAGETOOL_PATH" ]; then
    wget -c "$APPIMAGETOOL_URL" -O "$APPIMAGETOOL_PATH"
    chmod +x "$APPIMAGETOOL_PATH"
fi

rm -f "$FINAL_APPIMAGE_NAME" "$VERSIONED_APPIMAGE_NAME"
ARCH=x86_64 "$APPIMAGETOOL_PATH" --appimage-extract-and-run "$APPDIR_PATH" "$FINAL_APPIMAGE_NAME"
cp -a "$FINAL_APPIMAGE_NAME" "$VERSIONED_APPIMAGE_NAME"
chmod +x "$FINAL_APPIMAGE_NAME" "$VERSIONED_APPIMAGE_NAME"

echo ""
echo "Build complete."
echo "AppImage: $(pwd)/${FINAL_APPIMAGE_NAME}"
echo "Versioned: $(pwd)/${VERSIONED_APPIMAGE_NAME}"
