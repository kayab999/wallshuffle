__version__ = "1.0.3"
__all__ = ["change_wallpaper", "__version__"]


def __getattr__(name: str):
    # Lazy so --version / error paths don't require gi / PIL / requests.
    if name == "change_wallpaper":
        from .core import change_wallpaper

        return change_wallpaper
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
