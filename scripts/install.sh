#!/bin/bash

# WallShuffle AppImage Installation Script
# Installs the WallShuffle AppImage for the current user.

set -e

APP_NAME="wallshuffle"
APP_ID="io.github.kayab999.WallShuffle"
APP_IMAGE="WallShuffle-x86_64.AppImage"
# Install AppImage to Applications folder (user standard)
APP_DIR="$HOME/Applications"
INSTALL_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
ICON_FILE="assets/icon.png"
DESKTOP_FILE_SOURCE="data/$APP_ID.desktop"

echo "--- Installing WallShuffle v1.0.3 (AppImage) ---"

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
  # Use a direct call instead of 'exec' to ensure environment variables are inherited
  "$APPIMAGE_HOME" "$@"
  exit $?
fi

# 3. As a last resort, try APPIMAGE env (if running inside another AppImage)
if [ -n "${APPIMAGE:-}" ] && [ -x "$APPIMAGE" ]; then
  # Use a direct call here as well
  "$APPIMAGE" "$@"
  exit $?
fi

echo "Wallshuffle: no executable found. Please install Wallshuffle or place the AppImage in ~/Applications."
exit 2
EOF
chmod +x "$INSTALL_DIR/$APP_NAME"

# 5. Install Icon
echo "Installing icon..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
if [ -f "$REPO_ROOT/$ICON_FILE" ]; then
    cp "$REPO_ROOT/$ICON_FILE" "$ICON_DIR/$APP_ID.png"
    # Compat name for legacy desktop entries
    cp "$REPO_ROOT/$ICON_FILE" "$ICON_DIR/$APP_NAME.png"
elif [ -f "$ICON_FILE" ]; then
    cp "$ICON_FILE" "$ICON_DIR/$APP_ID.png"
    cp "$ICON_FILE" "$ICON_DIR/$APP_NAME.png"
else
    echo "WARNING: $ICON_FILE not found. Icon will be missing."
fi

# 6. Install Desktop Entry (reverse-DNS primary + legacy compat symlink)
echo "Configuring desktop entry..."
if [ -f "$REPO_ROOT/data/$APP_ID.desktop" ]; then
  DESKTOP_SRC="$REPO_ROOT/data/$APP_ID.desktop"
elif [ -f "$REPO_ROOT/assets/wallshuffle_installed.desktop" ]; then
  DESKTOP_SRC="$REPO_ROOT/assets/wallshuffle_installed.desktop"
elif [ -f "$DESKTOP_FILE_SOURCE" ]; then
  DESKTOP_SRC="$DESKTOP_FILE_SOURCE"
else
  DESKTOP_SRC="$REPO_ROOT/assets/wallshuffle.desktop"
fi
cp "$DESKTOP_SRC" "$DESKTOP_DIR/$APP_ID.desktop"

# Rewrite only the main Desktop Entry Exec (first Exec=), not Desktop Action lines.
if grep -q '^Exec=' "$DESKTOP_DIR/$APP_ID.desktop"; then
  # Replace first Exec= only
  awk -v exe="$INSTALL_DIR/$APP_NAME" '
    BEGIN { done=0 }
    /^Exec=/ && !done { print "Exec=" exe; done=1; next }
    { print }
  ' "$DESKTOP_DIR/$APP_ID.desktop" > "$DESKTOP_DIR/$APP_ID.desktop.tmp"
  mv "$DESKTOP_DIR/$APP_ID.desktop.tmp" "$DESKTOP_DIR/$APP_ID.desktop"
fi

# Ensure action keeps --change with full wrapper path
sed -i "s|^Exec=wallshuffle --change|Exec=$INSTALL_DIR/$APP_NAME --change|" "$DESKTOP_DIR/$APP_ID.desktop"
sed -i "s|^Exec=wallshuffle$|Exec=$INSTALL_DIR/$APP_NAME|" "$DESKTOP_DIR/$APP_ID.desktop"

# Ensure Icon/WMClass match reverse-DNS identity for dock matching
sed -i "s|^Icon=.*|Icon=$APP_ID|" "$DESKTOP_DIR/$APP_ID.desktop"
if grep -q '^StartupWMClass=' "$DESKTOP_DIR/$APP_ID.desktop"; then
  sed -i "s|^StartupWMClass=.*|StartupWMClass=$APP_ID|" "$DESKTOP_DIR/$APP_ID.desktop"
else
  printf 'StartupWMClass=%s\n' "$APP_ID" >> "$DESKTOP_DIR/$APP_ID.desktop"
fi
if ! grep -q '^DBusActivatable=' "$DESKTOP_DIR/$APP_ID.desktop"; then
  printf 'DBusActivatable=true\n' >> "$DESKTOP_DIR/$APP_ID.desktop"
fi
# Legacy compat: keep old name as symlink so existing pins still resolve
ln -sf "$APP_ID.desktop" "$DESKTOP_DIR/$APP_NAME.desktop"

# 7. Update Desktop Database
if command -v update-desktop-database &> /dev/null; then
    echo "Updating desktop database..."
    update-desktop-database "$DESKTOP_DIR"
fi

echo "--- Installation Complete! ---"
echo "WallShuffle v1.0.3 has been installed."
echo "You can launch it from your application menu."
echo "NOTE: dock pins to the old entry must be re-pinned once to $APP_ID."

# Check PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
  echo ""
  echo "NOTE: ~/.local/bin is not in your PATH."
  echo "To run 'wallshuffle' from the terminal, add this to your ~/.bashrc or ~/.zshrc:"
  echo '  export PATH="$HOME/.local/bin:$PATH"'
  echo "Or simply restart your session."
fi