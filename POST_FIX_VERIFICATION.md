# Post-fix verification audit — WallShuffle 1.0.1

**Date:** 2026-08-12  
**Scope:** Regression check after remediations; confirm planned behaviors still work.

---

## Verdict

| Result | Detail |
|--------|--------|
| **PASS** | No regressions detected in automated suite, behavioral matrix, or live GNOME smoke |
| **Version** | 1.0.1 consistent across package metadata |
| **Tests** | **79 passed**, coverage **~61%** (≥ 45%) |
| **Lint** | ruff clean |

---

## Automated gates

| Gate | Result |
|------|--------|
| `pytest` (with cov) | 79 passed |
| `ruff check wallshuffle tests` | All checks passed |
| Import smoke (core, UI dialogs, helpers) | OK |
| Concurrent `wallshuffle --change` ×2 | Both finished successfully (no lock timeout) |

---

## Live environment (this machine)

| Check | Result |
|-------|--------|
| `wallshuffle --version` | `WallShuffle 1.0.1` |
| `wallshuffle --change` | exit 0 |
| GNOME `picture-uri` | `file://…/.cache/wallshuffle/desktop/wallpaper_*.png` |
| Cache file | real file (not symlink), under `desktop/` subdir |
| Super+W bindings | **exactly 1** → `/home/carlos/.local/bin/wallshuffle --change` |
| Log markers | `CLI --change requested` + `CLI wallpaper change finished successfully` |

---

## Planned-behavior matrix (23/23 PASS)

| Area | Checks |
|------|--------|
| **Discovery** | File symlink, extensionless symlink, skip non-image, reject dangling |
| **Index cache** | Full-list hit; partial list does not corrupt cache |
| **Sequential** | Advances 0–1 → 2–3; state file written atomically |
| **Effects** | Two sources → two distinct processed paths |
| **Resolve path** | Symlink → realpath; dangling → None |
| **MATE** | `picture-filename` set; no `picture-uri` |
| **XFCE** | Fails when no `last-image` props |
| **Cron** | `*/30`, `0 */2` for 120m, interval 0 removes entry |
| **CLI** | `--change` exit 0; does **not** call `configure_backend` |
| **Desktop files** | `NextWallpaper` + `--change` present |
| **Version** | 1.0.1 |

---

## Static plan checklist (source)

Confirmed in code:

- `--change` returns before `configure_backend()` is called (line ~125 vs ~131 in `__main__.py`)  
- No `hold()` in `App.__init__`; Escape quits without tray  
- Interval `lower=0`; timer enable when `interval > 0`  
- Dialog `wire_dialog_default` + `grab_focus`  
- Config `optionxform = str`  
- GNOME desktop cache subdir; MATE filename key; XFCE fail-empty  
- QUIT on hung primary; uninstall strips cron; Unsplash size cap  
- Sequential `os.replace`; effects per-source hash  

(Static string-position heuristic for `--change`/backend once flagged a false positive; runtime matrix confirmed no X11 force on CLI.)  

---

## UI / manual residual (not automated here)

These need a human with the GUI open (coverage intentionally omits most of `ui/*`):

1. Manage Folders → add folder → type name + **Enter**  
2. Escape with tray (hide) vs without tray (quit)  
3. Save with interval **5** → timer active; interval **0** → timer disabled  
4. “Also on login” only affects boot trigger  
5. Theme switch / About text / Ctrl+S  

No automated failure in those code paths; logic was verified statically.

---

## Known non-blockers (unchanged)

- Index cache still does a full signature scan (performance on huge trees)  
- Flatpak manifest improved but not dry-run built in CI  
- Cron has no true `@reboot` for “Also on login”  
- User `config.ini` may still contain old test keys from prior test pollution  

---

## Conclusion

**Post-fix state is healthy for release as 1.0.1.**  
No regressions found relative to planned remediations. Remaining gaps are optional polish / manual GUI smoke, not functional breakages in the verified surface.
