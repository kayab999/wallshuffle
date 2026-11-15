# Runtime hook: ensure PyGObject overrides are applied in the frozen bundle.
# PyInstaller does not collect gi.overrides automatically, and without them
# GLib.timeout_add / timeout_add_seconds / idle_add / source_remove fall back
# to the raw introspected bindings that require 4 arguments, crashing the GUI.
import gi

gi.require_version("GLib", "2.0")
gi.require_version("GObject", "2.0")
gi.require_version("Gio", "2.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GObject, Gtk  # noqa: F401

for _mod in (
    "gi.overrides",
    "gi.overrides.GLib",
    "gi.overrides.GObject",
    "gi.overrides.Gio",
    "gi.overrides.Gtk",
    "gi.overrides.Gdk",
    "gi.overrides.GdkPixbuf",
    "gi.overrides.Pango",
):
    try:
        __import__(_mod)
    except Exception:
        pass
