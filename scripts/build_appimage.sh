#!/bin/bash

# Exit on any error
set -e

# --- Configuration ---
APP_NAME="WallShuffle"
LOWER_APP_NAME="wallshuffle"
VENV_PATH=".venv"
SPEC_FILE="${LOWER_APP_NAME}.spec"
ICON_FILE="assets/icon.png"
DESKTOP_FILE="assets/wallshuffle.desktop"
FINAL_APPIMAGE_NAME="${APP_NAME}-x86_64.AppImage"

# --- 1. Run PyInstaller ---
echo "--- Running PyInstaller to bundle the application ---"
# Check if venv and pyinstaller exist
if [ ! -d "$VENV_PATH" ]; then
    echo "Error: Virtual environment not found at $VENV_PATH."
    exit 1
fi

# Ensure pyinstaller is installed in venv
"$VENV_PATH/bin/pip" install pyinstaller

"$VENV_PATH/bin/pyinstaller" --noconfirm "$SPEC_FILE"


# --- 2. Prepare AppDir ---
echo "--- Preparing AppDir structure ---"
APPDIR_PATH="${APP_NAME}.AppDir"
rm -rf "$APPDIR_PATH" # Clean previous build
mkdir -p "$APPDIR_PATH/usr/bin"
mkdir -p "$APPDIR_PATH/usr/share/applications"
mkdir -p "$APPDIR_PATH/usr/share/icons/hicolor/256x256/apps"


# --- 3. Copy Files into AppDir ---
echo "--- Copying bundled application and assets ---"
# Copy PyInstaller output
cp -r "dist/$LOWER_APP_NAME/"* "$APPDIR_PATH/usr/bin/"

# Copy desktop file and icon
cp "$DESKTOP_FILE" "$APPDIR_PATH/" # For appimagetool root
cp "$DESKTOP_FILE" "$APPDIR_PATH/usr/share/applications/"
cp "$ICON_FILE" "$APPDIR_PATH/usr/share/icons/hicolor/256x256/apps/${LOWER_APP_NAME}.png"
cp "$ICON_FILE" "$APPDIR_PATH/${LOWER_APP_NAME}.png" # Root icon
ln -s "${LOWER_APP_NAME}.png" "$APPDIR_PATH/.DirIcon" # For AppImage icon

# --- 4. Create AppRun Entry Point ---
echo "--- Creating AppRun entry point ---"
# This script ensures the bundled libraries and typelibs are found
cat > "$APPDIR_PATH/AppRun" <<'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"

export APPDIR="$HERE"
export PATH="$HERE/usr/bin:$PATH"
export LD_LIBRARY_PATH="$HERE/usr/bin:$LD_LIBRARY_PATH"
export XDG_DATA_DIRS="$HERE/usr/share:$XDG_DATA_DIRS"

# GI typelibs are usually bundled by pyinstaller in the root of the collection
export GI_TYPELIB_PATH="$HERE/usr/bin:$GI_TYPELIB_PATH"

# Run the main executable
exec "$HERE/usr/bin/wallshuffle" "$@"
EOF
chmod +x "$APPDIR_PATH/AppRun"


# --- 5. Download and Run AppImageTool ---
echo "--- Downloading and running appimagetool ---"
APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
APPIMAGETOOL_PATH="./appimagetool-x86_64.AppImage"

if [ ! -f "$APPIMAGETOOL_PATH" ]; then
    wget -c "$APPIMAGETOOL_URL" -O "$APPIMAGETOOL_PATH"
    chmod +x "$APPIMAGETOOL_PATH"
fi

# Set ARCH for appimagetool and generate the AppImage
# We use --appimage-extract-and-run because we might be in a container/restricted env
ARCH=x86_64 "$APPIMAGETOOL_PATH" --appimage-extract-and-run "$APPDIR_PATH" "$FINAL_APPIMAGE_NAME"


# --- 6. Clean Up ---
echo "--- Cleaning up temporary build files ---"
# rm -rf build/
# rm -rf dist/
# rm -rf "$APPDIR_PATH"
# rm -f "$APPIMAGETOOL_PATH"

echo ""
echo "✅ Build complete!"
echo "AppImage created at: $(pwd)/${FINAL_APPIMAGE_NAME}"
