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

# --- 0. Pre-flight Check: libfuse2 (Critical for AppImages on modern Ubuntu/Debian) ---
check_libfuse2() {
  # dpkg-query returns 0 if package installed
  if command -v dpkg-query >/dev/null 2>&1; then
    if dpkg-query -W -f='${Status}' libfuse2 2>/dev/null | grep -q "install ok installed"; then
      return 0
    else
      return 1
    fi
  fi

  # Fallback: check if fuse lib exists (generic)
  if ldconfig -p 2>/dev/null | grep -q "libfuse"; then
    return 0
  fi

  return 1
}

if ! check_libfuse2; then
  echo ""
  echo "WARNING: On this distribution, AppImages may require 'libfuse2' to run."
  echo "If the AppImage fails to start, you likely need to install it."
  echo ""
  echo "  sudo apt update && sudo apt install libfuse2"
  echo ""
  
  # Only ask if interactive
  if [ -t 0 ]; then
      read -p "Do you want to try installing libfuse2 now? [y/N]: " yn
      case "$yn" in
        [Yy]* )
          if command -v sudo >/dev/null 2>&1; then
            sudo apt update && sudo apt install -y libfuse2
          else
            echo "sudo not found. Please install libfuse2 manually."
          fi
          ;;
        * ) echo "Proceeding without installing libfuse2. AppImage might not run.";;
      esac
  else
      echo "Non-interactive mode detected. Skipping optional libfuse2 installation."
  fi
fi

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

# 1. Prefer an editable install (pip install -e .) if found in PATH, BUT
# ensure we don't just find this script itself recursively.
if command -v wallshuffle >/dev/null 2>&1 && [ "$(command -v wallshuffle)" != "$0" ]; then
  exec "$(command -v wallshuffle)" "$@"
fi

# 2. Try AppImage in ~/Applications
APPIMAGE_HOME="$HOME/Applications/WallShuffle.AppImage"
if [ -x "$APPIMAGE_HOME" ]; then
  exec "$APPIMAGE_HOME" "$@"
fi

# 3. As a last resort, try APPIMAGE env (if running inside another AppImage)
if [ -n "${APPIMAGE:-}" ] && [ -x "$APPIMAGE" ]; then
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