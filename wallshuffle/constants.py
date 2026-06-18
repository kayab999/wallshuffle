SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif"}

CACHE_EXPIRATION_HOURS = 24

MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_IPC_MESSAGE_BYTES = 1024
MAX_DIRECTORY_DEPTH = 50
MAX_EFFECT_DIMENSION = 3840


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
