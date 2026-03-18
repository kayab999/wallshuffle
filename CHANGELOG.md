# Changelog - WallShuffle

## [1.0.0] - 2026-02-13
### Added
- **Multi-Monitor Support:** Different wallpapers per monitor or spanned mode.
- **Dynamic Theming:** Auto-detection of system colors (Ubuntu, Fedora, Arch, Custom).
- **Systemd Integration:** Robust background timer with atomic config locking.
- **Online Sources:** Unsplash integration with keyword support and fallback logic.

### Fixed
- **Timer Recursion:** Fixed a critical bug where recursive directory walking could hang the system.
- **Scaling/DPI:** Corrected multi-monitor scaling for high-resolution displays.
- **Thread Safety:** Implemented Singleton pattern for ConfigManager to prevent data corruption.
- **Memory Leaks:** Optimized image processing loop to release resources between updates.

### Security
- **Path Sanitization:** Hardened systemd service generation against path injection.
- **Zero Tracking:** Pure offline-first architecture.

### Known Issues
- **Wayland Compatibility:** GUI uses X11 backend via XWayland for stability on GNOME/KDE.
- **DEB Dependencies:** Requires manual `apt-get install -f` if installed via `dpkg`.
