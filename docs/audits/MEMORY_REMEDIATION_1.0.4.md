# Memory & Temp Lifecycle Remediation — 1.0.4

Final audit pass (pre-commit gate) for the 1.0.4 remediation batch. Scope items
were approved during review; this document records what shipped and its
verification evidence. Automated evidence and real desktop-environment evidence
are labeled separately.

## Shipped fixes

### 1. Transactional temp-dir sweep with per-output reference journal
- `temp/` (~/.config/wallshuffle/temp) is snapshotted before each change and
  swept in a `finally` (`core.py`), on success AND on every failure path.
- Success: sweep keeps exactly the applied wallpaper files.
- Failure: sweep keeps the current attempt's files (new or overwritten; a
  partially applied DE config may reference them) plus whatever
  `references.json` still lists. Orphans that nothing references are removed.
- `references.json` (written by `wallpaper_manager.py`) is a live map with one
  slot per output: each XFCE `last-image` property, KDE per-desktop config, and
  GNOME/MATE picture URI. Slots are REPLACED on write; untouched slots keep
  their previous reference. XFCE journals per property (partial applies are
  recorded as they happen); KDE on success; GNOME/MATE on success (empty slot
  when the URI points at the isolated desktop-cache copy, temp path on the
  copy-failure fallback).
- Journal missing/corrupt → fail safe: nothing pre-existing is deleted.
- Boundedness: slots hold only their latest value; unreferenced generations
  are swept on the next attempt (worst case disk use = active references +
  one failed generation).

### 2. Input resolution cap (`MAX_INPUT_PIXELS = 50_000_000`)
- Applies per source image in `create_composite_image`,
  `create_multi_monitor_composite` (skip monitor, keep canvas background) and
  `effects.apply_image_effect` (return original path).
- Checked on the lazily opened header (`Image.open` gives size without decode)
  with a controlled error message. `MAX_CANVAS_PIXELS` caps the output canvas;
  this caps the decode cost of every input (JPEG `draft()` only helps JPEG —
  the cap is format-uniform).

### 3. Peak-RAM reduction (Fase 1+2 of the audit, verified)
- `_downscale_for_canvas` mutates in place (no `img.copy()`), and runs BEFORE
  `exif_transpose` so `thumbnail()` can `draft()`-decode JPEGs at half
  resolution.
- Isolated benchmark, 96 MP JPEG (old vs new algorithm): peak 925,304 KB →
  547,108 KB, Δ = 378,196 KB ≈ 369 MiB (~41%). Output size identical in both
  runs (1707×2560); pixel equality was NOT asserted.
- End-to-end pipeline with final code, 40 MP cap-eligible input:
  peak 331 MB (331,244 KB), output 2560×1440.

### 4. Atomic writers and cache policies
- Cache and folder-index writes: `mkstemp` + `os.replace` (same filesystem),
  fd closed via context manager, tmp unlinked on exception.
- `.tmp_wall_*` crash leftovers purged from CACHE_DIR by `cleanup_old_cache`
  (> 1 h age; an in-progress write lives milliseconds).
- Folder index gained its own retention policy (TTL 7 d, 64 files / 32 MB)
  hung off `cleanup_old_cache`; each `~/.cache/wallshuffle/folder_index/`
  *.tmp crash orphan is TTL-collected with the rest.
- Cache hits refresh mtime (real LRU instead of FIFO).

### 5. Misc
- Size-rejected URL downloads close the HTTP response (no socket leak).
- Duplicate start-up temp cleanup removed from `app.py` (single
  flock-protected pass remains).
- Dead first-pass operations removed from the per-monitor `centered` and
  `spanned` paths (the overwritten outputs were never usable).

## Verification

### Automated (all executed)
- `pytest`: 136 passed; coverage 53.89% (gate ≥51%); baseline was 104 passed /
  51.35%.
- `ruff check .`: only the 9 pre-existing findings remain (delta clean).
- `mypy wallshuffle`: 9 errors, identical to the pre-diff baseline
  (same codes; line numbers shifted only).
- New test coverage: journal retention semantics (present/corrupt/missing,
  overwrite-as-new, stale-tmp purge), XFCE partial-failure scenarios
  (S/A/B/C: A kept while live, B never referenced → swept, C replaces A),
  repeated partial failures bounded to 2 files, EXIF 6/8/no-EXIF/PNG geometry
  (quadrant mapping verified against `ImageOps.exif_transpose` on the same
  files; outputs carry no orientation tag), input-limit fallbacks, atomic
  writes, TTL/caps, 30-change session stability (temp set constant, RSS drift
  < 100 MB).

### Real-DE (observed incidentally + documented protocol)
- During the audit, the running WallShuffle installation (editable install of
  this repo) performed a scheduled change on this GNOME session. Observed
  postconditions matched the new code: `references.json` written as an
  empty-URI success slot, desktop-cache copy created, temp dir swept clean.
- Controlled XFCE partial-failure replication is NOT possible on this GNOME
  machine; `scripts/real_desktop_endurance_check.py` documents the manual
  protocol (50 real changes, RSS/VmHWM + temp stats, requires `--yes`; not
  executed automatically).

## Residual risks
- Journal slots grow with distinct XFCE property names (typically bounded by
  monitors × workspaces); dead slots are not time-expired.
- Files created during a failed attempt survive until the next attempt.
- A running instance that started before an upgrade keeps the old code in
  memory until restarted; scheduled child processes pick up the new code.
- If the journal is lost, fail-safe retention can keep pre-existing files
  until the journal is re-created (bounded storage, no wallpaper loss).

## Version artifacts
- `wallshuffle_1.0.4_all.deb` (164 KB) and `WallShuffle-1.0.4-x86_64.AppImage`
  rebuilt; `SHA256SUMS.txt` lists deb + both AppImage names.
