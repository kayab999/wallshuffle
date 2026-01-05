# WallShuffle

A simple yet powerful wallpaper changer for Linux desktops, built with Python and GTK.

WallShuffle allows you to automatically change your desktop wallpaper at a defined interval, using images from a local folder or from the vast collection on Unsplash.

## Features

- **Multiple Sources:** Use images from a local folder or fetch them from Unsplash using keywords.
- **Custom Intervals:** Set wallpapers to change automatically at any minute-based interval.
- **Image Effects:** Apply simple effects like Grayscale, Blur, or Sepia to your wallpapers.
- **Multi-Monitor Support:** Includes basic support for spanning a single image across multiple monitors.
- **Theming:** Customize the application's appearance with built-in themes (e.g., Ubuntu).
- **Manual Control:** A "Next Wallpaper" button allows you to change the wallpaper on demand.
- **Persistent Configuration:** Saves your settings between sessions.
- **Single Instance:** Ensures only one instance of the application runs at a time.

## Installation (AppImage)

The easiest way to get started is by using the official AppImage.

1.  **Download:** Go to the [GitHub Releases page](https://github.com/your_username/wallshuffle/releases) and download the latest `WallShuffle-x86_64.AppImage` file.
2.  **Make it Executable:**
    ```bash
    chmod +x WallShuffle-x86_64.AppImage
    ```
3.  **Run:**
    ```bash
    ./WallShuffle-x86_64.AppImage
    ```
    On first run, you may be asked if you want to integrate the application with your system. If you agree, WallShuffle will be added to your application menu.

## Usage

When you launch the application, you will be presented with the following options:

- **Source:** Choose between "Local Folder" or "Unsplash".
- **Local Folder:** If you choose this source, click "Browse..." to select the folder containing your images.
- **Unsplash Keywords:** If you choose Unsplash, enter some keywords (e.g., "nature, landscapes") to guide the image selection.
- **Display Mode:** Control how the image is displayed (e.g., Zoom, Scaled, Centered).
- **Change Interval:** Set the number of minutes between automatic wallpaper changes. Set to 0 to disable automatic changes.
- **Change wallpaper on startup:** Check this to have the wallpaper change shortly after you log in.
- **Image Effect:** Apply an optional visual effect to the wallpapers.
- **Multi-Monitor Mode:** Choose how the wallpaper should be handled on multi-monitor setups.

Click **Save** to apply your settings and start the timer. The main window will hide, but the application will continue running in the background if an interval is set.

## ⌨ Keyboard Shortcut

Wallshuffle supports manual wallpaper change via the command line. You can use the AppImage directly to trigger a change.

You can bind this command to a system keyboard shortcut:

    /path/to/WallShuffle-x86_64.AppImage --change

### GNOME
Settings → Keyboard → Custom Shortcuts

### KDE
System Settings → Shortcuts → Custom Shortcuts

### XFCE
Settings → Keyboard → Application Shortcuts

## Building from Source

If you prefer to build the AppImage yourself:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your_username/wallshuffle.git
    cd wallshuffle
    ```
2.  **Set up the environment:**
    Ensure you have Python 3, a virtual environment, and `pip` installed.
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install pyinstaller
    ```
3.  **Run the build script:**
    ```bash
    ./build_appimage.sh
    ```
    The final AppImage will be located in the project's root directory.

## Troubleshooting

- **Systemd Dependency:** Wallshuffle uses `systemd` timers for scheduling wallpaper changes. This is standard on most modern Linux distributions (Ubuntu, Fedora, Arch, etc.). If you are using a distribution without `systemd` (like Devuan or Artix), the automatic scheduling feature will not work.
- **Wayland vs. X11:** Wallpaper setting mechanisms can differ between Wayland and X11 sessions. Wallshuffle uses standard command-line tools (`gsettings`, `dbus-send`, `xfconf-query`) that work reliably on major desktop environments (GNOME, KDE, XFCE) under both X11 and Wayland. However, if you are using a more niche window manager, you may encounter issues.
- **AppIndicator/Tray Icon:** The system tray icon relies on `AppIndicator` or `AyatanaAppIndicator`. If you are using a minimal desktop environment that does not have a tray that supports this standard, the icon may not appear. The application will still run in the background.

## Configuration

Configuration is stored in `~/.config/wallshuffle/config.ini`. You can edit this file manually or use the settings dialog in the application.

## Development

This project uses a `Makefile` to standardize development tasks.

### Prerequisites
- Python 3.10+
- `libgirepository1.0-dev` (for PyGObject)

### Setup
Initialize the virtual environment and install dependencies:
```bash
make setup
```

### Testing & Quality
Run the test suite:
```bash
make test
```

Check code style and types (Ruff & Mypy):
```bash
make lint
```

### Build
Create the AppImage:
```bash
make build
```

## Uninstall

To completely remove Wallshuffle from your system:

1.  **Stop and Disable systemd Timer (if enabled):**
    ```bash
    systemctl --user stop wallpaper-changer.timer
    systemctl --user disable wallpaper-changer.timer
    systemctl --user stop wallpaper-changer.service
    systemctl --user disable wallpaper-changer.service
    systemctl --user daemon-reload
    ```
    *Note: These commands will only work if `systemd` is available on your system and the timer was previously enabled.*

2.  **Remove Configuration Files:**
    ```bash
    rm -rf ~/.config/wallshuffle
    rm -f ~/.config/systemd/user/wallpaper-changer.service
    rm -f ~/.config/systemd/user/wallpaper-changer.timer
    ```

3.  **Remove the AppImage:**
    Simply delete the `WallShuffle-x86_64.AppImage` file from wherever you downloaded it.

4.  **Remove Desktop Entry and Icon (if integrated):**
    If you chose to integrate the AppImage with your system, you might also want to remove its desktop entry and icon. This typically involves removing files from `~/.local/share/applications/` and `~/.local/share/icons/`.
    ```bash
    rm -f ~/.local/share/applications/wallshuffle.desktop
    rm -f ~/.local/share/icons/hicolor/scalable/apps/wallshuffle.png
    update-desktop-database ~/.local/share/applications/
    ```