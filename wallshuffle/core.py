import logging
import os
import random
from enum import Enum, auto

from .config_manager import ConfigManager
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


def change_wallpaper():
    logging.info("--- Running change_wallpaper ---")
    config_manager = ConfigManager()
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
    multi_monitor_mode = config_manager.get_setting(
        config, "Settings", "multi_monitor_mode", "Single image on all monitors"
    )
    image_path = None

    logging.info(f"Source: {source}, Effect: {effect}, Multi-Monitor Mode: {multi_monitor_mode}")

    if source == "Local Folder":
        folder = config_manager.get_setting(config, "Settings", "folder")
        if not folder:
            logging.error("Local Folder source selected but no folder path provided.")
            return WallpaperUpdateResult.NO_SOURCE_CONFIGURED

        if os.path.isfile(folder):
            supported_extensions = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
            if folder.lower().endswith(supported_extensions):
                image_path = folder
                logging.info(f"Source is a direct file: {image_path}")
            else:
                logging.error(f"Selected file is not a supported image: {folder}")
                return WallpaperUpdateResult.NO_IMAGES_FOUND
        elif os.path.isdir(folder):
            try:
                supported_extensions = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
                recursive_search = config_manager.get_setting(
                    config, "Settings", "recursive_search", False, value_type=bool
                )

                images = []
                if recursive_search:
                    for root, _, files in os.walk(folder, followlinks=True):
                        for f in files:
                            if f.lower().endswith(supported_extensions):
                                images.append(os.path.join(root, f))
                else:
                    images = [
                        os.path.join(folder, f)
                        for f in os.listdir(folder)
                        if f.lower().endswith(supported_extensions)
                    ]

                if images:
                    image_path = random.choice(images)
                    logging.info(f"Selected image: {image_path}")
                else:
                    logging.warning(
                        f"No images found in folder: {folder} (Recursive: {recursive_search})"
                    )
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
            image_path = online_source_manager.fetch_unsplash_wallpaper(keywords)
            if not image_path:
                return WallpaperUpdateResult.NO_IMAGES_FOUND
        except Exception as e:
            logging.error(f"Network error fetching from Unsplash: {e}")
            return WallpaperUpdateResult.NETWORK_ERROR

    if not image_path:
        logging.warning("No image path resolved. Exiting change_wallpaper.")
        return WallpaperUpdateResult.NO_IMAGES_FOUND

    log_wallpaper_history(image_path)
    if effect != "None":
        logging.info(f"Applying effect: {effect}")
        image_path = apply_image_effect(image_path, effect)

    monitor_info = manager.get_monitor_info()
    if multi_monitor_mode == "Span image across all monitors":
        logging.info("Creating composite image for span mode.")
        image_path = manager.create_composite_image(image_path, monitor_info)

    mode = config_manager.get_setting(config, "Settings", "mode", "zoom")
    background_color = config_manager.get_setting(config, "Settings", "background_color", "#000000")

    logging.info(f"Applying wallpaper with mode: {mode} and background color: {background_color}")

    if manager.apply_desktop_settings(mode, [image_path], background_color):
        logging.info("--- change_wallpaper finished successfully ---")
        return WallpaperUpdateResult.SUCCESS
    else:
        logging.error("Failed to apply desktop settings via wallpaper_manager.")
        return WallpaperUpdateResult.COMMAND_FAILED
