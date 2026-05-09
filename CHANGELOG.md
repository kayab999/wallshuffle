# Changelog - WallShuffle

## [1.0.0] - 2026-05-08
### Hardening & Production Ready
- **Concurrency Serialization:** Implemented exclusive file-based locking (`fcntl.flock`) in the core engine to eliminate race conditions between systemd and GUI.
- **Resilient Locking:** Refactored locks to be non-blocking with a 5s retry loop, preventing indefinite hangs from orphan processes.
- **Dynamic Session Awareness:** Migrated systemd integration to use dynamic specifiers (%U) and `import-environment`, ensuring stability across session changes.
- **Resource Management (LRU):** Implemented a bounded cache system with LRU purging (Default 500MB) to prevent uncontrolled disk growth.
- **Security Hardening:** Universal application of restricted directory permissions (0o700) and shell-escaping (`shlex.quote`) in integrations to prevent command injection.
- **Performance Optimization:** Refactored critical path imports and optimized status polling to eliminate UI thread exhaustion.
- **Graceful Lifecycle:** Replaced forced exits with clean GTK application shutdown for orderly resource cleanup.

## [1.0.0-rc1] - 2026-04-03
### Added
- **Refresh Status:** Manual sync button in header bar to immediately refresh system status.
- **Environment Validation:** Added proactive checks for `DISPLAY` and `DBUS` to improve headless/GUI error reporting.
- **Improved Polling:** Adaptive polling interval (5s on focus, 30s background) for better responsiveness without overhead.

### Fixed
- **Zombification Bug:** Fixed critical issue where app would hang in background if closed without tray support.
- **Locking Reinforcement:** Enhanced single-instance socket mechanism to probe and cleanup stale primary instances safely.
- **Theme Desync:** Fixed theme/CSS not always refreshing after saving settings in the UI.
- **GNOME Backend:** Hardened GSettings application logic and improved dark-mode URI handling.

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
