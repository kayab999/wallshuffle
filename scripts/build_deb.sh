#!/bin/bash
set -euo pipefail

APP_NAME="wallshuffle"
VERSION="1.0.2"
ARCH="all"
BUILD_DIR="build_deb"
OUT="${APP_NAME}_${VERSION}_${ARCH}.deb"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "Cleaning up..."
rm -rf "$BUILD_DIR"
rm -f "$OUT"

echo "Creating directory structure..."
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/usr/lib/$APP_NAME"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/metainfo"
mkdir -p "$BUILD_DIR/usr/share/pixmaps"

echo "Copying application files..."
# Package lives at /usr/lib/wallshuffle/wallshuffle so PYTHONPATH=/usr/lib/wallshuffle works.
if command -v rsync >/dev/null 2>&1; then
  rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='logs' \
    wallshuffle/ "$BUILD_DIR/usr/lib/$APP_NAME/wallshuffle/"
else
  cp -r wallshuffle "$BUILD_DIR/usr/lib/$APP_NAME/"
  find "$BUILD_DIR/usr/lib/$APP_NAME" -name "__pycache__" -exec rm -rf {} +
  rm -rf "$BUILD_DIR/usr/lib/$APP_NAME/wallshuffle/logs"
fi
# About dialog second-candidate path: /usr/lib/wallshuffle/README.md
cp README.md "$BUILD_DIR/usr/lib/$APP_NAME/README.md"

echo "Creating launcher script..."
cat <<'EOF' > "$BUILD_DIR/usr/bin/$APP_NAME"
#!/bin/bash
export PYTHONPATH="/usr/lib/wallshuffle:${PYTHONPATH:-}"
exec /usr/bin/python3 -m wallshuffle "$@"
EOF
chmod 755 "$BUILD_DIR/usr/bin/$APP_NAME"

echo "Installing desktop entry, metainfo, and icon..."
# Keep the filename wallshuffle.desktop so uninstall.sh and menus stay consistent.
# Icon name matches /usr/share/pixmaps/wallshuffle.png.
awk '
  /^Icon=/ { print "Icon=wallshuffle"; next }
  /^X-GNOME-Autostart-enabled=/ { next }
  { print }
' data/io.github.kayab999.WallShuffle.desktop \
  > "$BUILD_DIR/usr/share/applications/${APP_NAME}.desktop"
cp data/io.github.kayab999.WallShuffle.metainfo.xml \
   "$BUILD_DIR/usr/share/metainfo/io.github.kayab999.WallShuffle.metainfo.xml"
cp assets/icon.png "$BUILD_DIR/usr/share/pixmaps/${APP_NAME}.png"

echo "Creating control file..."
INSTALLED_SIZE="$(du -sk "$BUILD_DIR" | cut -f1)"
cat <<EOF > "$BUILD_DIR/DEBIAN/control"
Package: $APP_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Installed-Size: $INSTALLED_SIZE
Depends: python3, python3-gi, python3-pil, python3-requests, gir1.2-gtk-3.0, gir1.2-appindicator3-0.1 | gir1.2-ayatanaappindicator3-0.1
Maintainer: Kayab Software <kayab999@users.noreply.github.com>
Homepage: https://github.com/kayab999/wallshuffle
Description: A GTK-based wallpaper changer for Linux desktops
 WallShuffle automatically rotates wallpapers from a local folder or Unsplash.
 It supports multiple monitors, image effects, and systemd user timers.
EOF

echo "Creating postinst script..."
cat <<'EOF' > "$BUILD_DIR/DEBIAN/postinst"
#!/bin/bash
set -e
if [ "$1" = "configure" ]; then
    update-desktop-database -q || true
    update-mime-database /usr/share/mime >/dev/null 2>&1 || true
fi
EOF
chmod 755 "$BUILD_DIR/DEBIAN/postinst"

echo "Building .deb package..."
dpkg-deb --root-owner-group --build "$BUILD_DIR" "$OUT"

echo "Done! Package created: $OUT"
echo "Inspect with: dpkg-deb -I $OUT && dpkg-deb -c $OUT | head"
