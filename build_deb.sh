#!/bin/bash
set -e

APP_NAME="wallshuffle"
VERSION="1.0.0"
ARCH="all"
BUILD_DIR="build_deb"

echo "Cleaning up..."
rm -rf "$BUILD_DIR"
rm -f "${APP_NAME}_${VERSION}_${ARCH}.deb"

echo "Creating directory structure..."
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/usr/share/$APP_NAME"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/pixmaps"

echo "Copying application files..."
# Copy the python package
cp -r wallshuffle "$BUILD_DIR/usr/share/$APP_NAME/"
# Remove bytecode
find "$BUILD_DIR/usr/share/$APP_NAME" -name "__pycache__" -exec rm -rf {} +

echo "Creating launcher script..."
cat <<EOF > "$BUILD_DIR/usr/bin/$APP_NAME"
#!/bin/bash
export PYTHONPATH="/usr/share/$APP_NAME"
exec python3 -m wallshuffle "\$@"
EOF
chmod 755 "$BUILD_DIR/usr/bin/$APP_NAME"

echo "Creating .desktop file..."
# Ensure the Icon path is correct or uses the system icon name
cat <<EOF > "$BUILD_DIR/usr/share/applications/$APP_NAME.desktop"
[Desktop Entry]
Name=WallShuffle
Comment=Wallpaper Changer for Linux
Exec=$APP_NAME
Icon=$APP_NAME
Type=Application
Categories=Utility;Settings;DesktopSettings;
Terminal=false
StartupNotify=true
EOF

echo "Copying icon..."
cp icon.png "$BUILD_DIR/usr/share/pixmaps/$APP_NAME.png"

echo "Creating control file..."
cat <<EOF > "$BUILD_DIR/DEBIAN/control"
Package: $APP_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Depends: python3, python3-gi, python3-pil, python3-requests, gir1.2-gtk-3.0, gir1.2-appindicator3-0.1 | gir1.2-ayatanaappindicator3-0.1
Maintainer: Carlos <carlos@example.com>
Description: A GTK-based wallpaper changer for Linux desktops.
 WallShuffle allows you to automatically rotate wallpapers from a local folder
 or Unsplash. It supports multiple monitors, effects, and dynamic theming.
EOF

echo "Creating postinst script..."
cat <<EOF > "$BUILD_DIR/DEBIAN/postinst"
#!/bin/bash
set -e
if [ "\$1" = "configure" ]; then
    update-desktop-database -q || true
fi
EOF
chmod 755 "$BUILD_DIR/DEBIAN/postinst"

echo "Building .deb package..."
dpkg-deb --build "$BUILD_DIR" "${APP_NAME}_${VERSION}_${ARCH}.deb"

echo "Done! Package created: ${APP_NAME}_${VERSION}_${ARCH}.deb"
