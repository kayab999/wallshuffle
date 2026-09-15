SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif"}

# Reverse-DNS id for Gtk.Application, desktop files, Flatpak, and AppStream.
APPLICATION_ID = "io.github.kayab999.WallShuffle"

CACHE_EXPIRATION_HOURS = 24

MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_IPC_MESSAGE_BYTES = 1024
MAX_DIRECTORY_DEPTH = 50
MAX_EFFECT_DIMENSION = 3840
# Hardening caps (prevent OOM/swap thrashing on huge multi-monitor or image sets)
# ~33 MP -> e.g., 8192x4096, 7680x4320 headroom; scales down larger canvases with BILINEAR
MAX_CANVAS_PIXELS = 33_554_432
MAX_CACHED_IMAGES = 10_000  # limit local discovery to avoid unbounded memory / I/O storms
WALLPAPER_CHANGE_TIMEOUT_SEC = 30  # watchdog for Next Wallpaper background thread


class WallpaperSource:
    LOCAL_FOLDER = "Local Folder"
    UNSPLASH = "Unsplash"
    URL = "URL / Hyperlink"
    ALL = (LOCAL_FOLDER, UNSPLASH, URL)


class MultiMonitorMode:
    SINGLE = "Single image on all monitors"
    DIFFERENT = "Different image on each monitor"
    SPAN = "Span image across all monitors"
    ALL = (SINGLE, DIFFERENT, SPAN)


class DisplayMode:
    ZOOM = "zoom"
    SCALED = "scaled"
    CENTERED = "centered"
    SPANNED = "spanned"
    STRETCHED = "stretched"
    ALL = (ZOOM, SCALED, CENTERED, SPANNED, STRETCHED)


class ImageEffect:
    NONE = "None"
    GRAYSCALE = "Grayscale"
    BLUR = "Blur"
    SEPIA = "Sepia"
    ALL = (NONE, GRAYSCALE, BLUR, SEPIA)

GNOME_COMPAT = [
    "gnome",
    "unity",
    "ubuntu",
    "cinnamon",
    "budgie",
    "mate",
    "pantheon",
    "pop",
]
