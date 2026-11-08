#!/usr/bin/env python3
"""Manual real-desktop endurance check — NOT part of the automated suite.

Measures process RSS/VmHWM and the wallshuffle temp dir across N REAL wallpaper
changes against the live desktop environment (XFCE/KDE/GNOME). This is the
real-DE counterpart of the mocked automated stability test
(tests/test_session_stability.py): it validates the journal + sweep against
what XFC/KDE/GNOME actually keep referenced between attempts.

Run manually from the repo root (explicitly; it CHANGES the visible wallpaper):

    .venv/bin/python scripts/real_desktop_endurance_check.py 50 --yes

Exit status 0 when the session looked bounded (guidance: peak RSS growth under
150 MB and temp dir price stable), 1 otherwise, 2 on refusal (no display, no
supported DE, or missing --yes).
"""

import os
import sys
import time

CONFIG_TEMP = os.path.join(os.path.expanduser("~"), ".config", "wallshuffle", "temp")
JOURNAL_NAMES = {"references.json", "references.json.tmp"}
SUPPORTED_DES = {"xfce", "kde", "gnome", "cinnamon", "mate", "plasma"}


def _usage(code: int) -> int:
    print(__doc__)
    return code


def _vm_kb(field: str):
    with open("/proc/self/status", "r") as handle:
        for line in handle:
            if line.startswith(field + ":"):
                return int(line.split()[1])
    return None


def _temp_stats():
    if not os.path.isdir(CONFIG_TEMP):
        return 0, 0
    files = [f for f in os.listdir(CONFIG_TEMP) if f not in JOURNAL_NAMES]
    return len(files), sum(
        os.path.getsize(os.path.join(CONFIG_TEMP, name)) for name in files
    )


def main(argv):
    iterations, explicit = 50, False
    for arg in argv:
        if arg == "--yes":
            explicit = True
        elif arg.isdigit():
            iterations = int(arg)
        else:
            return _usage(2)

    desktop = (os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION") or "").lower()
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    if not has_display or not any(de in desktop for de in SUPPORTED_DES):
        print(f"Refusing: needs a real desktop session (detected: '{desktop or 'none'}').")
        return 2
    if not explicit:
        print("Refusing: this changes your live wallpaper repeatedly. Rerun with --yes.")
        return 2

    from wallshuffle.core import change_wallpaper  # noqa: PLC0415 (delayed: after refusal gates)

    start_rss = _vm_kb("VmRSS") or 0
    start_count, start_bytes = _temp_stats()
    print("iter,result,rss_kb,hwm_kb,temp_files,temp_bytes")
    peak_rss = start_rss

    for i in range(1, iterations + 1):
        result, _message = change_wallpaper()
        rss, hwm = _vm_kb("VmRSS"), _vm_kb("VmHWM")
        files, nbytes = _temp_stats()
        peak_rss = max(peak_rss, rss)
        print(f"{i},{result.value},{rss},{hwm},{files},{nbytes}", flush=True)
        time.sleep(1)

    end_count, end_bytes = _temp_stats()
    hwm_growth_mb = ((_vm_kb("VmHWM") or 0) - start_rss) / 1024.0
    print(
        f"summary: HWM growth since start {hwm_growth_mb:.1f} MB | "
        f"peak RSS {peak_rss / 1024.0:.1f} MB | temp files {start_count}->{end_count} | "
        f"temp bytes {start_bytes}->{end_bytes}"
    )
    if hwm_growth_mb > 150:
        print("FAIL guidance: peak RSS growth > 150 MB over the session — investigate leaks.")
        return 1
    print("OK guidance: session looked bounded.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
