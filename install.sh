#!/bin/bash

# WallShuffle AppImage Installation Script
# Installs the WallShuffle AppImage for the current user.

set -e

APP_NAME="wallshuffle"
APP_IMAGE="WallShuffle-x86_64.AppImage"
# Install AppImage to Applications folder (user standard)
APP_DIR="$HOME/Applications"
INSTALL_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
ICON_FILE="icon.png"
DESKTOP_FILE_SOURCE="wallshuffle.desktop"

echo "--- Installing WallShuffle v1.0 (AppImage) ---"

# 1. Check if AppImage exists
if [ ! -f "$APP_IMAGE" ]; then
    echo "ERROR: $APP_IMAGE not found in current directory."
    echo "Please build it first using ./build_appimage.sh"
    exit 1
fi

# 2. Setup Directories
mkdir -p "$APP_DIR"
mkdir -p "$INSTALL_DIR"
mkdir -p "$DESKTOP_DIR"
mkdir -p "$ICON_DIR"

# 3. Install AppImage
echo "Installing AppImage to $APP_DIR..."
cp "$APP_IMAGE" "$APP_DIR/WallShuffle.AppImage"
chmod +x "$APP_DIR/WallShuffle.AppImage"

# 4. Create Wrapper in ~/.local/bin
echo "Creating wrapper script in $INSTALL_DIR/$APP_NAME..."
cat > "$INSTALL_DIR/$APP_NAME" <<'EOF'
#!/usr/bin/env bash
# Wallshuffle wrapper: execute the user-installed script, fallback to AppImage

# Try AppImage in ~/Applications
APPIMAGE_HOME="$HOME/Applications/WallShuffle.AppImage"
if [ -x "$APPIMAGE_HOME" ]; then
  exec "$APPIMAGE_HOME" "$@"
fi

# As a last resort, try APPIMAGE env (if running inside another AppImage)
if [ -n "$APPIMAGE" ] && [ -x "$APPIMAGE" ]; then
  exec "$APPIMAGE" "$@"
fi

echo "Wallshuffle: no executable found. Please install Wallshuffle or place the AppImage in ~/Applications."
exit 2
EOF
chmod +x "$INSTALL_DIR/$APP_NAME"

# 5. Install Icon
echo "Installing icon..."
if [ -f "$ICON_FILE" ]; then
    cp "$ICON_FILE" "$ICON_DIR/$APP_NAME.png"
else
    echo "WARNING: $ICON_FILE not found. Icon will be missing."
fi

# 6. Install Desktop Entry
echo "Configuring desktop entry..."
cp "$DESKTOP_FILE_SOURCE" "$DESKTOP_DIR/$APP_NAME.desktop"

# Update Exec path to wrapper
sed -i "s|^Exec=.*|Exec=$INSTALL_DIR/$APP_NAME|" "$DESKTOP_DIR/$APP_NAME.desktop"

# Ensure Icon line refers to the installed icon name
sed -i "s|^Icon=.*|Icon=$APP_NAME|" "$DESKTOP_DIR/$APP_NAME.desktop"

# 7. Update Desktop Database
if command -v update-desktop-database &> /dev/null; then
    echo "Updating desktop database..."
    update-desktop-database "$DESKTOP_DIR"
fi

echo ""
echo "--- Installation Complete! ---"
echo "WallShuffle v1.0 has been installed."
echo "You can launch it from your application menu."