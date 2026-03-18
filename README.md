# WallShuffle

A simple yet powerful wallpaper changer for Linux desktops, built with Python and GTK.

WallShuffle allows you to automatically change your desktop wallpaper at a defined interval, using images from a local folder or from the vast collection on Unsplash.

## ⚠️ Important: AppImage Requirements (Ubuntu/Debian)

On some modern distributions (Ubuntu 22.04+, Debian 12+), AppImages require **`libfuse2`** to run.
If the application does not start when you double-click the AppImage, please install this library:

```bash
sudo apt update && sudo apt install libfuse2
```

Alternatively, you can install WallShuffle in development mode (which avoids the AppImage wrapper issue):
```bash
pip install -e . --user
```

**Recommended:** Use the provided `./install.sh` script, which handles checking for this requirement.

## Features

- **Multiple Sources:** Use images from a local folder or fetch them from Unsplash using keywords.
- **Custom Intervals:** Set wallpapers to change automatically at any minute-based interval.
- **Display Ordering:** Choose between random or sequential (alphabetical) wallpaper display.
- **Image Effects:** Apply simple effects like Grayscale, Blur, or Sepia to your wallpapers.
- **Multi-Monitor Support:** Includes basic support for spanning a single image across multiple monitors.
- **Theming:** Customize the application's appearance with built-in themes (e.g., Ubuntu).
- **Manual Control:** A "Next Wallpaper" button allows you to change the wallpaper on demand.
- **Persistent Configuration:** Saves your settings between sessions.
- **Single Instance:** Ensures only one instance of the application runs at a time.

## Installation

### Method 1: AppImage (Recommended)
The **AppImage** is a single executable file that runs on most Linux distributions.

1.  **Download** the latest `WallShuffle-x86_64.AppImage` from the [Releases page](#).
2.  **Make it executable:**
    ```bash
    chmod +x WallShuffle-x86_64.AppImage
    ```
3.  **Run it:** Double-click the file or run `./WallShuffle-x86_64.AppImage`.

*Note for Ubuntu 22.04+ users:* If the AppImage does not start, install `libfuse2`:
```bash
sudo apt update && sudo apt install libfuse2
```

### Method 2: Debian Package (.deb)
For Debian, Ubuntu, Linux Mint, and derivatives:

1.  **Download** the `wallshuffle_1.0.0_all.deb` file.
2.  **Install** via terminal:
    ```bash
    sudo apt install ./wallshuffle_1.0.0_all.deb
    ```
    (Using `apt` instead of `dpkg` automatically handles dependencies like `python3-gi`).

### Method 3: From Source (Developers)
```bash
git clone https://github.com/carlos/wallshuffle.git
cd wallshuffle
./install.sh
```

## Usage

**Launch:**
- If installed via AppImage: Double-click the file.
- If installed via `.deb` or source: Search for **WallShuffle** in your application menu.

---

## Troubleshooting

- **Wayland Compatibility:** If you are running a Wayland session (common in Ubuntu 22.04+), WallShuffle automatically forces the **X11 backend (via XWayland)** to ensure the GTK3 interface renders correctly and remains visible. This is handled internally.
- **Systemd Dependency:** Wallshuffle uses `systemd` timers for scheduling. This will not work on non-systemd distros (e.g., Devuan, Artix).
- **libfuse2:** AppImages require `libfuse2`. If the app won't start, run: `sudo apt install libfuse2`.

## Configuration Options

When you launch the application, you will be presented with the following options:

- **Source:** Choose between "Local Folder" or "Unsplash".
- **Local Folder:** If you choose this source, click "Browse..." to select the folder containing your images.
- **Unsplash Keywords:** If you choose Unsplash, enter some keywords (e.g., "nature, landscapes") to guide the image selection.
- **Display Mode:** Control how the image is displayed (e.g., Zoom, Scaled, Centered).
- **Change Interval:** Set the number of minutes between automatic wallpaper changes. Set to 0 to disable automatic changes.
- **Change wallpaper on startup:** Check this to have the wallpaper change shortly after you log in.
- **Random Order:** Toggle whether to display wallpapers in a random or sequential order.
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

## 🛡️ Sovereignty & Limitations

- **Privacy First:** WallShuffle does not collect metrics, telemetry, or crash reports. It is 100% local-first.
- **Wayland Note:** On Wayland sessions, the app forces the X11 backend to ensure GTK3 stability and correct window positioning.
- **Dependencies:** If using the `.deb` package, ensure you have `gir1.2-gtk-3.0` and `python3-pil` installed.

## ☕ Support Development

If WallShuffle makes your desktop better, consider supporting the developer:
- **Ko-fi:** `https://ko-fi.com/nysekf`
- **GitHub Sponsors:** Look for the "Sponsor" button on my profile.

## Uninstall

To completely remove Wallshuffle from your system, use the provided uninstall script:

```bash
./uninstall.sh
```

This script will safely remove the AppImage, wrapper, desktop entries, icons, and disable any active systemd timers.

Options:
- `./uninstall.sh --purge`: Also removes configuration files and logs.
- `./uninstall.sh --help`: Show usage information.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
