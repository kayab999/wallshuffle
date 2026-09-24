# Changelog - WallShuffle

## [1.0.3] - 2026-09-24
### Fixed — Dock launch regression (v1.0.2 broke GUI open)
- **GUI crash:** Remove local `from gi.repository import GLib` shadowing global in `WallpaperApp.__init__` (`UnboundLocalError` on every dock launch); hermetic `WALLSHUFFLE_INSTANCE` socket suffix, no `sys.exit` in GTK vfuncs, `do_open` routing, fix missing `present_window` (`app.py`).
- **Display gate:** Accept `DISPLAY` or `WAYLAND_DISPLAY`; prefer X11 with native Wayland retry (`__main__.py`); lazy `__init__` for `--version` without heavy deps.
- **Desktop activation:** Reverse-DNS `io.github.kayab999.WallShuffle.desktop` primary + `DBusActivatable`, compat symlink, aligned icons/Exec (`data/`, `setup.py`, `install.sh`, `uninstall.sh`, `build_deb.sh`).
- **Packaging:** `pyproject` `include wallshuffle*` (wheel omitted `ui/`), `pygobject<3.51` pin, icon filename fix.
- **Scheduler/secrets:** APPIMAGE-stable timer path (no `/tmp/.mount` persistence), `shlex.quote` cron exec, Wayland env in cron/systemd, Unsplash key via `Authorization` header + circuit-breaker on SSL/network/JSON.
- **Data-loss/polling:** Corrupt config backup (no silent wipe), one-shot initial poll, history shared-lock read, thumbnail generation guard.

## [1.0.2] - 2026-09-15
### Fixed — Fase 1 Hardening (Silent Failures)
- **Config lock:** `ConfigLockTimeoutError` con `monotonic 5s` en `load_settings` — evita pérdida silenciosa, muestra `show_error_dialog` en GUI y `FILE_SYSTEM_ERROR` en headless (`config_manager.py`, `core.py`, `app.py`).
- **Sequential/history locks:** Unifica `LOCK_SH/EX` no bloqueante `5s monotonic` en `sequential_state.py` y `utils.py` (evita hilos colgados timer+hotkey).
- **I/O storm:** Hard break en `_scan_folder_once` tras `MAX_CACHED_IMAGES=10k` — no `stat` extra, evita asfixia NAS/directorios masivos (`image_index.py`).
- **Thread leaks:** Debounce `300ms` en `update_image_count` (`ui/handlers/source.py`), guard `_tray_polling_in_progress` en tray (`app.py`), `get_monitor_info` cache `1s` + `event.wait 0.5s` vs `2.0s` (`wallpaper_manager.py`).
- **Timeouts:** Usa `WALLPAPER_CHANGE_TIMEOUT_SEC=30` en 3 watchdogs (`app.py`, `core.py`, `ui/handlers/wallpaper.py`) + `time.monotonic` en circuit breaker (`online_sources.py`).
- **Canvas/EXIF:** Cap `MAX_CANVAS_PIXELS=33M` con `BILINEAR` pre-scale (ya), + `ImageOps.exif_transpose` (`wallpaper_manager.py`, `effects.py`).

### Tests & Coverage
- Nuevos tests: `cap 33M`, `bilinear threshold`, `lock timeout monotonic`, `hard break 10k`, `history concurrent`, `circuit breaker monotonic`, `monitor cache`, `tray guard`.
- `pyproject.toml` incluye `app.py` en coverage, `cov-fail-under 45→51` (51.08% actual, 92 tests).

### Packaging
- Version `1.0.2` en `pyproject.toml`, `setup.py`, `__init__.py`, `build_deb.sh`, metainfo.
- Public identity aligned with GitHub (`kayab999/wallshuffle`): application id `io.github.kayab999.WallShuffle`, Kayab Software metadata, no in-repo user config or editor settings.
- Binary GitHub release: `wallshuffle_1.0.2_all.deb` and `WallShuffle-1.0.2-x86_64.AppImage`.

## [1.0.1] - 2026-08-12
### Fixed
- **Folder name dialog:** Keyboard input, Enter to confirm, modal focus for local folder sources.
- **Symlink wallpapers:** Discover and apply images that are symlinks to real files (including extensionless link names); GNOME cache copies under `~/.cache/wallshuffle/desktop/`.
- **Super+W / CLI:** Reliable `wallshuffle --change` (no forced X11); desktop action **Next Wallpaper**; clearer CLI logs.
- **Automation timer:** Interval `0` disables auto-rotation; `interval > 0` enables systemd timer; “Also on login” only controls boot trigger.
- **No-systemd systems:** Automation UI stays enabled and uses crontab fallback; uninstall removes `WALLSHUFFLE_TIMER` lines.
- **Escape without tray:** Quits instead of hiding a held zombie process.
- **Single-instance:** Unresponsive primary receives `QUIT` before rebind retry.
- **Effects + multi-monitor:** Unique processed filenames so DIFFERENT monitors do not share one temp file.
- **MATE:** Uses `picture-filename` (path) instead of GNOME `picture-uri`.
- **XFCE:** Fails clearly when no `last-image` properties exist.
- **Unsplash downloads:** Enforce the same max size cap as URL source.
- **Sequential state:** Atomic temp+replace write (no truncate-before-lock).
- **Install / deb:** Preserve Desktop Action `--change`; deb includes Next Wallpaper action.
- **About dialog / Save errors:** Correct README lookup + fallback text; surface save failures.
- **Folder index cache:** Refuse inconsistent partial caches; keep category name casing.

### Packaging
- Version **1.0.1** across package metadata, metainfo, and deb builder.
- Flatpak manifest: real `requests` sha256, pinned Pillow commit, narrower filesystem permissions.

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
