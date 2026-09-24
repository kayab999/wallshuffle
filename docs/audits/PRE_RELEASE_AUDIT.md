# Pre-release audit report — WallShuffle 1.0.x RC

**Date:** 2026-08-12  
**Environment:** Ubuntu GNOME (Wayland + XWayland), `wallshuffle` 1.0.0 @ `~/.local/bin`  
**Gates:** 74 tests passed · ruff clean · coverage ~60% (fail-under 45%)

---

## Executive summary

A full baseline + automated gates + dual static review (core/DE + UI/packaging) was run against the post-hotfix RC. Several **P0/P1** residual bugs were confirmed and **fixed in-tree** during this audit. Remaining items are **P2/P3** (document, defer, or ship with known issues).

**Release readiness:** **Ship candidate** after CHANGELOG note + optional 1.0.1 bump, with known issues below.

---

## Session hotfixes (already present; re-verified)

| Item | Status |
|------|--------|
| Folder name dialog keyboard / Enter | OK |
| Symlink image sources + GNOME cache copy | OK |
| Super+W single binding → `~/.local/bin/wallshuffle --change` | OK |
| CLI `--change` logging / no X11 force | OK |

Dynamic smoke: `wallshuffle --change` exit 0; `picture-uri` → real file under `~/.cache/wallshuffle/desktop/`.

---

## Fixed during this audit

### [P0] Escape without tray orphaned the process
- **Fix:** Escape mirrors close: quit if no tray; hide only with tray. Removed unconditional `hold()` in `WallpaperApp.__init__` (hold only when tray succeeds).

### [P0] Timer only enabled when “On Startup” was checked
- **Fix:** Interval `0` disables automation; `interval > 0` enables systemd/cron timer. Checkbox relabeled **Also on login** and only adds `OnBootSec`. Cron schedule fixed for intervals ≥ 60 minutes.

### [P1] GNOME cache purged shared Unsplash cache + sticky URI
- **Fix:** Desktop copies live in `~/.cache/wallshuffle/desktop/` only; cache name includes mtime/size; `Path.as_uri()`; brief clear+set of `picture-uri`.

### [P1] Effect temp path not unique (multi-monitor + effect)
- **Fix:** `processed_{effect}_{hash(source)}.jpg` per source path.

### [P1] `install.sh` rewrote all `Exec=` lines (broke Next Wallpaper action)
- **Fix:** First-Exec-only rewrite; preserve/fix `--change` action; resolve desktop from repo assets.

### [P1] Folder index cache could store inconsistent partial lists
- **Fix:** Refuse to write cache when list length ≠ signature count; tests updated.

### [P2] About README path wrong; silent save failure
- **Fix:** Multi-path README resolve + fallback text; error dialog on save failure.

### [P2] Headless / image_index tests broken by symlink usability checks
- **Fix:** Real temp images in headless test; full list required for cache test.

---

## Remaining known issues (after remediations)

| Sev | Title | Notes |
|-----|--------|--------|
| P2 | Index cache still full-scans for signature | Performance only on huge trees |
| P2 | Flatpak not fully CI-built | Manifest fixed; full `flatpak-builder` dry-run still recommended |
| P2 | Cron “Also on login” is limited | No `@reboot` cron path; enable after login by running the app |
| P3 | Config pollution from tests (`test_key` in user config) | Test hygiene / isolate ConfigManager tests |
| P3 | Headless multi-monitor geometry best-effort | Wayland/xrandr/DRM fallbacks documented in code |

---

## Coverage blind spots (by design in `pyproject.toml`)

Omitted from coverage: `ui/*`, `app.py`, `__main__.py`. **Manual GUI smoke still required** for release.

### Manual GUI checklist (operator)

1. Launch with/without tray; Escape behavior  
2. Manage folders + name with Enter  
3. Symlink folder source + Next Wallpaper  
4. Super+W  
5. Save with interval 5 / “Also on login”; `systemctl --user status wallpaper-changer.timer`  
6. Interval 0 → timer disabled  
7. Theme switch; About text loads  
8. Unsplash test (if key)

---

## Packaging / version

| Source | Version |
|--------|---------|
| `wallshuffle/__init__.py` | 1.0.0 |
| `pyproject.toml` / `setup.py` | 1.0.0 |
| metainfo release | 1.0.0 (2026-04-14) |

Recommend **1.0.1** tag if shipping this audit batch, with CHANGELOG entries for timer, Escape, GNOME cache, symlinks, hotkeys.

---

## Quality gates snapshot

```
74 passed
ruff: All checks passed
coverage: ~60% (>= 45%)
mypy: not installed in host python3 (CI installs via make setup)
```

---

## Decision

| Option | When |
|--------|------|
| **Ship 1.0.1** | After CHANGELOG + optional metainfo date; accept remaining P2/P3 |
| **Delay** | If MATE/no-systemd/Flatpak are hard release requirements |
