import logging
import os
import random
from enum import Enum, auto

from .config_manager import get_config_manager
from .constants import SUPPORTED_EXTENSIONS
from .effects import apply_image_effect
from .online_sources import OnlineSourceManager
from .utils import log_wallpaper_history
from .wallpaper_manager import WallpaperManager


class WallpaperUpdateResult(Enum):
    SUCCESS = auto()
    NO_SOURCE_CONFIGURED = auto()
    NO_IMAGES_FOUND = auto()
    NETWORK_ERROR = auto()
    UNSUPPORTED_DESKTOP = auto()
    COMMAND_FAILED = auto()
    CONFIGURATION_ERROR = auto()
    FILE_SYSTEM_ERROR = auto()


def change_wallpaper() -> WallpaperUpdateResult:
    """
    Change the desktop wallpaper based on current configuration.

    This function serves as the main entry point for wallpaper changes, called
    from both the GUI and the systemd timer (wallshuffle --change).

    Returns:
        WallpaperUpdateResult: Enum indicating the outcome:
            - SUCCESS: Wallpaper changed successfully
            - NO_SOURCE_CONFIGURED: No valid source (folder/API) configured
            - NO_IMAGES_FOUND: Source configured but no images available
            - NETWORK_ERROR: Network failure when fetching online sources
            - UNSUPPORTED_DESKTOP: Desktop environment not supported
            - COMMAND_FAILED: Desktop settings command failed
            - CONFIGURATION_ERROR: Config file corrupted or missing
            - FILE_SYSTEM_ERROR: Cannot access local folder/files

    Thread-Safety:
        Uses singleton ConfigManager to ensure consistent state across calls.
    """
    logging.info("--- Running change_wallpaper ---")
    config_manager = get_config_manager()
    config = config_manager.load_settings()

    if "Settings" not in config:
        logging.error("Error: 'Settings' section not found in config file.")
        return WallpaperUpdateResult.CONFIGURATION_ERROR

    settings = config["Settings"]
    logging.info(f"Settings loaded: {dict(settings)}")

    manager = WallpaperManager()

    # Relaxed DE check: rely on WallpaperManager to handle unsupported/unknown types gracefully
    # or return an error from there.
    current_de = manager.get_desktop_environment()
    logging.info(f"Detected Desktop Environment: {current_de}")

    source = config_manager.get_setting(config, "Settings", "source", "Local Folder")
    effect = config_manager.get_setting(config, "Settings", "effect", "None")
    multi_monitor_mode = config_manager.get_setting(config, "Settings", "multi_monitor_mode", "Single image on all monitors")

    # Get monitor info early to determine how many images we need
    monitor_info = manager.get_monitor_info()
    monitor_count = len(monitor_info) if monitor_info else 1

    # Determine how many images to fetch
    images_needed = 1
    if multi_monitor_mode == "Different image on each monitor":
        images_needed = monitor_count
        logging.info(f"Multi-monitor mode active: Need {images_needed} distinct images.")

    image_paths = []

    logging.info(f"Source: {source}, Effect: {effect}, Multi-Monitor Mode: {multi_monitor_mode}")

    # Check for Unsplash configuration issues and fallback if necessary
    if source == "Unsplash":
        unsplash_api_key = config_manager.get_setting(config, "Settings", "unsplash_api_key", "")
        if not unsplash_api_key or unsplash_api_key == "YOUR_UNSPLASH_API_KEY":
            logging.warning("Unsplash source selected but no API Key found. Attempting fallback to Local Folder.")
            source = "Local Folder"

    if source == "Local Folder":
        folder = config_manager.get_setting(config, "Settings", "folder")
        if not folder:
            logging.error("Local Folder source selected but no folder path provided.")
            return WallpaperUpdateResult.NO_SOURCE_CONFIGURED

        if os.path.isfile(folder):
            if folder.lower().endswith(tuple(SUPPORTED_EXTENSIONS)):
                # If the source is a single file, we just use it (even if we need multiple, we can't invent more)
                image_paths = [folder] * images_needed
                logging.info(f"Source is a direct file: {folder}")
            else:
                logging.error(f"Selected file is not a supported image: {folder}")
                return WallpaperUpdateResult.NO_IMAGES_FOUND
        elif os.path.isdir(folder):
            try:
                recursive_search = config_manager.get_setting(config, "Settings", "recursive_search", False, value_type=bool)

                found_images = []
                if recursive_search:
                    # Recursive search with safe symlink following
                    visited_dirs = set()
                    for root, dirs, files in os.walk(folder, followlinks=True):
                        # Detect loops
                        try:
                            # Resolve symlinks to absolute paths for loop detection
                            real_root = os.path.realpath(root)
                            if real_root in visited_dirs:
                                logging.warning(f"Symlink loop detected or already visited: {root} -> {real_root}. Skipping.")
                                dirs[:] = [] # Don't recurse further
                                continue
                            visited_dirs.add(real_root)
                        except OSError as e:
                             logging.warning(f"Error resolving path {root}: {e}. Skipping loop check.")

                        for f in files:
                            if f.lower().endswith(tuple(SUPPORTED_EXTENSIONS)):
                                found_images.append(os.path.join(root, f))
                else:
                    found_images = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(tuple(SUPPORTED_EXTENSIONS))]

                if found_images:
                    # Select N unique images if possible
                    if len(found_images) >= images_needed:
                        image_paths = random.sample(found_images, images_needed)
                    else:
                        # Not enough images, fill with what we have (randomly sampling with replacement to fill gaps)
                        # But simpler: just shuffle and cycle
                        random.shuffle(found_images)
                        image_paths = [found_images[i % len(found_images)] for i in range(images_needed)]

                    logging.info(f"Selected images: {image_paths}")
                else:
                    logging.warning(f"No images found in folder: {folder} (Recursive: {recursive_search})")
                    return WallpaperUpdateResult.NO_IMAGES_FOUND
            except OSError as e:
                logging.error(f"Error accessing local folder {folder}: {e}")
                return WallpaperUpdateResult.FILE_SYSTEM_ERROR
        else:
            logging.error(f"Local path not found or invalid: {folder}")
            return WallpaperUpdateResult.NO_SOURCE_CONFIGURED

    elif source == "Unsplash":
        keywords = config_manager.get_setting(config, "Settings", "keywords", "")
        logging.info(f"Source: Unsplash, Keywords: {keywords}")
        online_source_manager = OnlineSourceManager(config_manager, config)
        try:
            # Current online source logic fetches only one.
            paths = []
            for i in range(images_needed):
                path = online_source_manager.fetch_unsplash_wallpaper(keywords, index=i)
                if path:
                    paths.append(path)
                else:
                    break

            if not paths:
                 return WallpaperUpdateResult.NO_IMAGES_FOUND

            image_paths = paths
            # If we failed to get enough, fill the rest
            while len(image_paths) < images_needed:
                 image_paths.append(image_paths[0])

        except Exception as e:
            logging.error(f"Network error fetching from Unsplash: {e}")
            return WallpaperUpdateResult.NETWORK_ERROR

    if not image_paths:
        logging.warning("No image paths resolved. Exiting change_wallpaper.")
        return WallpaperUpdateResult.NO_IMAGES_FOUND

    # Log history (just the first one or all? Let's log all reversed so last one is top)
    for p in reversed(image_paths):
        log_wallpaper_history(p)

    final_image_paths = []
    if effect != "None":
        logging.info(f"Applying effect: {effect}")
        for p in image_paths:
            final_image_paths.append(apply_image_effect(p, effect))
    else:
        final_image_paths = image_paths

    # If mode is Span, we need to composite N images into ONE big one if "Different image" was requested
    # But wait, "Span image across all monitors" is a DIFFERENT mode than "Different image on each monitor".
    # User Request: "Single Image in Each Monitor" mode.
    # So if multi_monitor_mode == "Span image across all monitors", we do the OLD logic (single image -> composite).
    # If multi_monitor_mode == "Different image on each monitor", we keep them separate (unless gnome requires stitching).

    if multi_monitor_mode == "Span image across all monitors":
        if not final_image_paths:
             logging.error("No images available for composition.")
             return WallpaperUpdateResult.NO_IMAGES_FOUND

        logging.info("Creating composite image for span mode from a SINGLE source image.")
        # Span mode implies taking ONE image and stretching it.
        # So we should probably use the first image chosen.
        try:
            single_image = final_image_paths[0]
        except IndexError:
            logging.error("IndexError accessing final_image_paths[0] despite check.")
            return WallpaperUpdateResult.NO_IMAGES_FOUND

        image_path = manager.create_composite_image(single_image, monitor_info)
        logging.info("Forcing mode to 'spanned' for multi-monitor composite image.")
        mode = "spanned"
        # Pass as a single-item list
        final_image_paths = [image_path]
    elif multi_monitor_mode == "Different image on each monitor":
         # We want the DE to put different images.
         # For GNOME, this might internally become a composite/stitched image,
         # but that implementation detail belongs in apply_desktop_settings (or manager helper).
         # We just pass the list of N images.
         # BUT, we need to know what 'mode' to set for the individual images (zoom, scaled, etc).
         mode = config_manager.get_setting(config, "Settings", "mode", "zoom")
    else:
        # "Single image on all monitors" (Duplicate)
        mode = config_manager.get_setting(config, "Settings", "mode", "zoom")
        # Ensure we just have one image (duplicated for logic if needed, but apply_desktop_settings usually takes one and applies it everywhere)
        # Actually Manager changes below might expect list.
        # If we selected 1 image above, we are good.
        # If we accidentally selected N images (due to logic change), we should pick 0.
        # But 'images_needed' was 1 if not "Different image on each monitor".
        pass

    background_color = config_manager.get_setting(config, "Settings", "background_color", "#000000")

    logging.info(f"Applying wallpaper with mode: {mode}, images: {len(final_image_paths)}")

    if manager.apply_desktop_settings(mode, final_image_paths, background_color):
        logging.info("--- change_wallpaper finished successfully ---")
        return WallpaperUpdateResult.SUCCESS
    else:
        logging.error("Failed to apply desktop settings via wallpaper_manager.")
        return WallpaperUpdateResult.COMMAND_FAILED
