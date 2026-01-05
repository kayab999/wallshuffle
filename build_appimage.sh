#!/bin/bash

# Exit on any error
set -e

# --- Configuration ---
APP_NAME="WallShuffle"
LOWER_APP_NAME="wallshuffle"
VENV_PATH="venv"
SPEC_FILE="${LOWER_APP_NAME}.spec"
ICON_FILE="icon.png"
DESKTOP_FILE="${LOWER_APP_NAME}.desktop"
FINAL_APPIMAGE_NAME="${APP_NAME}-x86_64.AppImage"

# --- 1. Run PyInstaller ---
echo "--- Running PyInstaller to bundle the application ---"
# Check if venv and pyinstaller exist
if [ ! -d "$VENV_PATH" ] || [ ! -x "$VENV_PATH/bin/pyinstaller" ]; then
    echo "Error: Virtual environment or PyInstaller not found."
    echo "Please run 'pip install pyinstaller' in your virtual environment first."
    exit 1
fi
"$VENV_PATH/bin/pyinstaller" "$SPEC_FILE"


# --- 2. Prepare AppDir ---
echo "--- Preparing AppDir structure ---"
APPDIR_PATH="${APP_NAME}.AppDir"
rm -rf "$APPDIR_PATH" # Clean previous build
mkdir -p "$APPDIR_PATH/usr/bin"
mkdir -p "$APPDIR_PATH/usr/share/applications"
mkdir -p "$APPDIR_PATH/usr/share/icons/hicolor/scalable/apps"


# --- 3. Copy Files into AppDir ---
echo "--- Copying bundled application and assets ---"
# Copy PyInstaller output
cp -r "dist/$LOWER_APP_NAME/"* "$APPDIR_PATH/usr/bin/"

# Copy desktop file and icon
cp "$DESKTOP_FILE" "$APPDIR_PATH/" # For appimagetool
cp "$DESKTOP_FILE" "$APPDIR_PATH/usr/share/applications/"
cp "$ICON_FILE" "$APPDIR_PATH/usr/share/icons/hicolor/scalable/apps/${LOWER_APP_NAME}.png"
ln -s "usr/share/icons/hicolor/scalable/apps/${LOWER_APP_NAME}.png" "$APPDIR_PATH/${LOWER_APP_NAME}.png"
ln -s "${LOWER_APP_NAME}.png" "$APPDIR_PATH/.DirIcon" # For AppImage icon

# --- 4. Create AppRun Entry Point ---
echo "--- Creating AppRun entry point ---"
cat > "$APPDIR_PATH/AppRun" <<'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
# Some GStreamer checks can cause issues, this can help
export GST_PLUGIN_SYSTEM_PATH_1_0=
# Run the main executable from the bundled app, passing all arguments
exec "$HERE/usr/bin/wallshuffle" "$@"
EOF
chmod +x "$APPDIR_PATH/AppRun"


# --- 5. Download and Run AppImageTool ---
echo "--- Downloading and running appimagetool ---"
APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
APPIMAGETOOL_PATH="appimagetool-x86_64.AppImage"

if [ ! -f "$APPIMAGETOOL_PATH" ]; then
    wget -c "$APPIMAGETOOL_URL" -O "$APPIMAGETOOL_PATH"
    chmod +x "$APPIMAGETOOL_PATH"
fi

# Set ARCH for appimagetool and generate the AppImage
ARCH=x86_64 ./"$APPIMAGETOOL_PATH" "$APPDIR_PATH"


# --- 6. Clean Up ---
echo "--- Cleaning up temporary build files ---"
rm -rf build/
rm -rf dist/
rm -f "$APPIMAGETOOL_PATH" # Optional: remove the tool after use

echo ""
echo "✅ Build complete!"
echo "AppImage created at: $(pwd)/${FINAL_APPIMAGE_NAME}"
