#!/usr/bin/env bash
set -euo pipefail

APP_NAME="wallshuffle"

usage() {
  echo "Usage: $0 [--purge] [--yes]"
  echo "  --purge   Also remove user configuration in ~/.config/$APP_NAME"
  echo "  --yes     Do not ask for confirmation (use with caution)"
}

PURGE=false
YES=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --purge) PURGE=true; shift;;
    --yes) YES=true; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown parameter: $1"; usage; exit 2;;
  esac
done

echo "Uninstalling WallShuffle..."

# Stop and disable systemd services
echo "Stopping user/systemd service (if exists)..."
systemctl --user stop wallpaper-changer.service 2>/dev/null || true
systemctl --user disable wallpaper-changer.timer 2>/dev/null || true

# Remove systemd files
rm -f "$HOME/.config/systemd/user/wallpaper-changer.service"
rm -f "$HOME/.config/systemd/user/wallpaper-changer.timer"
# Reload daemon to reflect changes
systemctl --user daemon-reload 2>/dev/null || true

echo "Removing binaries, wrappers, and icons..."
# Wrapper
rm -f "$HOME/.local/bin/wallshuffle"
# AppImage
rm -f "$HOME/Applications/WallShuffle.AppImage"
# Desktop file
rm -f "$HOME/.local/share/applications/wallshuffle.desktop"
# Icons
rm -f "$HOME/.local/share/icons/hicolor/256x256/apps/wallshuffle.png"
# Legacy/Scalable (just in case)
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/wallshuffle.svg"

# Update Desktop Database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$HOME/.local/share/applications"
fi

if [ "$PURGE" = true ]; then
  if [ "$YES" = false ]; then
    echo ""
    read -p "Delete configuration and logs in ~/.config/$APP_NAME ? [y/N]: " ans
    if [[ ! "$ans" =~ ^[Yy]$ ]]; then
      echo "Skipping configuration removal."
    else
      echo "Removing ~/.config/$APP_NAME ..."
      rm -rf "$HOME/.config/$APP_NAME"
    fi
  else
    echo "Removing ~/.config/$APP_NAME ..."
    rm -rf "$HOME/.config/$APP_NAME"
  fi
else
  echo "Configuration preserved in ~/.config/$APP_NAME"
  echo "Use --purge to remove it."
fi

echo "Uninstallation complete."