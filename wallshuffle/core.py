import fcntl
import logging
import os
import random
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum, auto
from typing import List, Optional, Tuple

import requests

from .config_manager import get_config_manager
from .constants import (
    MAX_DOWNLOAD_BYTES,
    SUPPORTED_EXTENSIONS,
    ImageEffect,
    MultiMonitorMode,
    WallpaperSource,
)
from .effects import apply_image_effect
from .image_discovery import find_images_in_folder
from .online_sources import OnlineSourceManager
from .sequential_state import select_sequential_images
from .utils import CONFIG_DIR, log_wallpaper_history
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
    DESKTOP_ENVIRONMENT_ERROR = auto()


def change_wallpaper() -> Tuple[WallpaperUpdateResult, str]:
    """
    Change the desktop wallpaper based on current configuration.

    This function serves as the main entry point for wallpaper changes, called
    from both the GUI and the systemd timer (wallshuffle --change).

    Returns:
        (WallpaperUpdateResult, str): A tuple indicating the outcome and an
            associated error message if applicable.
            - WallpaperUpdateResult: Enum indicating the outcome.
            - str: An empty string on success, or a descriptive error message on failure.

    Thread-Safety:
        Uses singleton ConfigManager to ensure consistent state across calls.
    """
    logging.info("--- Running change_wallpaper ---")

    # Log execution context
    display = os.environ.get("DISPLAY", "NOT SET")
    wayland = os.environ.get("WAYLAND_DISPLAY", "NOT SET")
    is_headless = display == "NOT SET" and wayland == "NOT SET"
    context_type = "Headless/Timer Context" if is_headless else "GUI/Interactive Context"
    logging.info(f"Execution Context: {context_type} | DISPLAY='{display}' | WAYLAND_DISPLAY='{wayland}'")

    # Serializar ejecuciones para evitar condiciones de carrera con timeout
    lock_path = os.path.join(CONFIG_DIR, "change_wallpaper.lock")
    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)

    try:
        lock_file = open(lock_path, "w")

        # Bloqueo no bloqueante con reintentos para evitar esperas infinitas (Fase 1 Hardening)
        import time
        start_time = time.time()
        timeout = 5.0 # Segundos
        acquired = False

        while time.time() - start_time < timeout:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except (IOError, BlockingIOError):
                time.sleep(0.1)

        if not acquired:
            logging.error(f"Could not acquire wallpaper change lock within {timeout}s. Another process might be hung.")
            lock_file.close()
            return (WallpaperUpdateResult.FILE_SYSTEM_ERROR, "Lock timeout: Another instance is still running or hung.")

        logging.debug("Adquired wallpaper change lock.")
    except Exception as e:
        logging.error(f"Failed to setup wallpaper change lock: {e}")
        return (WallpaperUpdateResult.FILE_SYSTEM_ERROR, f"Lock error: {e}")

    try:
        return _change_wallpaper_impl()
    finally:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
            logging.debug("Released wallpaper change lock.")
        except Exception as e:
            logging.error(f"Error releasing wallpaper change lock: {e}")

def _change_wallpaper_impl() -> Tuple[WallpaperUpdateResult, str]:
    config_manager = get_config_manager()
    config = config_manager.load_settings()

    if "Settings" not in config:
        logging.error("Error: 'Settings' section not found in config file.")
        return (WallpaperUpdateResult.CONFIGURATION_ERROR, "Configuration file is missing the 'Settings' section.")

    settings = config["Settings"]
    # Redact sensitive fields before logging
    safe_settings = dict(settings)
    if "unsplash_api_key" in safe_settings:
        key = safe_settings["unsplash_api_key"]
        safe_settings["unsplash_api_key"] = key[:4] + "****" if len(key) > 4 else "****"
    logging.info(f"Settings loaded: {safe_settings}")

    manager = WallpaperManager()

    # Relaxed DE check: rely on WallpaperManager to handle unsupported/unknown types gracefully
    # or return an error from there.
    current_de = manager.get_desktop_environment()
    logging.info(f"Detected Desktop Environment: {current_de}")

    source: str = config_manager.get_setting(config, "Settings", "source", WallpaperSource.LOCAL_FOLDER, str)
    effect: str = config_manager.get_setting(config, "Settings", "effect", ImageEffect.NONE, str)
    multi_monitor_mode: str = config_manager.get_setting(
        config, "Settings", "multi_monitor_mode", MultiMonitorMode.SINGLE, str
    )

    # Get monitor info early to determine how many images we need
    monitor_info = manager.get_monitor_info()
    monitor_count = len(monitor_info) if monitor_info else 1

    # Determine how many images to fetch
    images_needed = 1
    if multi_monitor_mode == MultiMonitorMode.DIFFERENT:
        images_needed = monitor_count
        logging.info(f"Multi-monitor mode active: Need {images_needed} distinct images.")

    image_paths: List[str] = []

    logging.info(f"Source: {source}, Effect: {effect}, Multi-Monitor Mode: {multi_monitor_mode}")

    # Check for Unsplash configuration issues and fallback if necessary
    if source == WallpaperSource.UNSPLASH:
        unsplash_api_key: str = config_manager.get_setting(config, "Settings", "unsplash_api_key", "", str)
        if not unsplash_api_key or unsplash_api_key == "YOUR_UNSPLASH_API_KEY":
            logging.warning("Unsplash source selected but no API Key found. Attempting fallback to Local Folder.")
            source = WallpaperSource.LOCAL_FOLDER

    if source == WallpaperSource.LOCAL_FOLDER:
        folder_setting: str = config_manager.get_setting(config, "Settings", "folder", "", str)
        if not folder_setting:
            logging.error("Local Folder source selected but no folder path provided.")
            return (WallpaperUpdateResult.NO_SOURCE_CONFIGURED, "No local folder path has been configured.")
        folder: str = folder_setting  # Ensure folder is str

        if os.path.isfile(folder):
            if folder.lower().endswith(tuple(SUPPORTED_EXTENSIONS)):
                # If the source is a single file, we just use it (even if we need multiple, we can't invent more)
                image_paths = [folder] * images_needed
                logging.info(f"Source is a direct file: {folder}")
            else:
                logging.error(f"Selected file is not a supported image: {folder}")
                return (WallpaperUpdateResult.NO_IMAGES_FOUND, f"The selected file '{folder}' is not a supported image type.")
        elif os.path.isdir(folder):
            try:
                recursive_search: bool = config_manager.get_setting(config, "Settings", "recursive_search", False, bool)
                found_images = find_images_in_folder(folder, recursive=recursive_search)

                if found_images:
                    random_order: bool = config_manager.get_setting(config, "Settings", "random_order", True, bool)
                    if not random_order:
                        found_images.sort()

                    # Select N unique images if possible
                    if len(found_images) >= images_needed:
                        if random_order:
                            image_paths = random.sample(found_images, images_needed)
                        else:
                            image_paths = select_sequential_images(found_images, folder, images_needed)
                    else:
                        # Not enough images, fill with what we have (randomly sampling with replacement to fill gaps)
                        # But simpler: just shuffle and cycle, or cycle in order
                        if random_order:
                            random.shuffle(found_images)
                        image_paths = [found_images[i % len(found_images)] for i in range(images_needed)]

                    logging.info(f"Selected images: {image_paths}")
                else:
                    logging.warning(f"No images found in folder: {folder} (Recursive: {recursive_search})")
                    return (WallpaperUpdateResult.NO_IMAGES_FOUND, f"No supported images found in the selected folder: '{folder}'.")
            except OSError as e:
                logging.error(f"Error accessing local folder {folder}: {e}")
                return (WallpaperUpdateResult.FILE_SYSTEM_ERROR, f"Error accessing local folder '{folder}': {e}")
        else:
            logging.error(f"Local path not found or invalid: {folder}")
            return (WallpaperUpdateResult.NO_SOURCE_CONFIGURED, f"The configured local path '{folder}' is not a valid folder or file.")

    elif source == WallpaperSource.UNSPLASH:
        keywords: str = config_manager.get_setting(config, "Settings", "keywords", "", str)
        logging.info(f"Source: Unsplash, Keywords: {keywords}")

        online_source_manager = OnlineSourceManager(config_manager, config)
        try:
            paths_temp: List[str] = [""] * images_needed

            def fetch_at_index(index: int) -> Tuple[int, Optional[str], str]:
                path, error_msg = online_source_manager.fetch_unsplash_wallpaper(keywords, index=index)
                return index, path, error_msg

            max_workers = min(images_needed, 4)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(fetch_at_index, index) for index in range(images_needed)]
                for future in as_completed(futures):
                    index, path, error_msg = future.result()
                    if path:
                        paths_temp[index] = path
                    elif error_msg:
                        return (WallpaperUpdateResult.NETWORK_ERROR, error_msg)

            paths_temp = [path for path in paths_temp if path]
            if not paths_temp:
                return (WallpaperUpdateResult.NO_IMAGES_FOUND, "Unsplash source returned no images. Check keywords or API key.")

            image_paths = paths_temp
            # If we failed to get enough, fill the rest
            while len(image_paths) < images_needed:
                image_paths.append(image_paths[0])

        except Exception as e:
            logging.error(f"Error fetching from Unsplash: {e}")
            return (WallpaperUpdateResult.NETWORK_ERROR, f"Error fetching from Unsplash: {e}")

    elif source == WallpaperSource.URL:
        hyperlink_url: str = config_manager.get_setting(config, "Settings", "hyperlink_url", "", str)
        if not hyperlink_url or not hyperlink_url.startswith("http"):
            logging.error("URL / Hyperlink source selected but no valid URL provided.")
            return (WallpaperUpdateResult.NO_SOURCE_CONFIGURED, "No valid URL provided for Hyperlink source.")

        logging.info(f"Source: URL, Fetching from: {hyperlink_url}")
        try:
            response = requests.get(hyperlink_url, stream=True, timeout=15)
            response.raise_for_status()

            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    if int(content_length) > MAX_DOWNLOAD_BYTES:
                        return (
                            WallpaperUpdateResult.NETWORK_ERROR,
                            f"Remote image exceeds maximum allowed size ({MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB).",
                        )
                except ValueError:
                    logging.warning(f"Invalid Content-Length header: {content_length}")

            temp_dir = os.path.join(CONFIG_DIR, "temp")
            os.makedirs(temp_dir, mode=0o700, exist_ok=True)
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", dir=temp_dir)
            downloaded = 0
            try:
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    downloaded += len(chunk)
                    if downloaded > MAX_DOWNLOAD_BYTES:
                        raise ValueError(
                            f"Download exceeded maximum allowed size ({MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB)"
                        )
                    tmp_file.write(chunk)
                tmp_file.close()
                image_path = tmp_file.name
            except Exception:
                tmp_file.close()
                try:
                    os.unlink(tmp_file.name)
                except OSError:
                    pass
                raise

            image_paths = [image_path] * images_needed

        except requests.exceptions.RequestException as e:
            logging.error(f"Network error fetching from URL {hyperlink_url}: {e}")
            return (WallpaperUpdateResult.NETWORK_ERROR, f"Network error fetching from URL: {e}")
        except ValueError as e:
            logging.error(f"URL download rejected: {e}")
            return (WallpaperUpdateResult.NETWORK_ERROR, str(e))
        except Exception as e:
            logging.error(f"Error saving image from URL: {e}")
            return (WallpaperUpdateResult.FILE_SYSTEM_ERROR, f"Error saving image from URL: {e}")

    if not image_paths:
        logging.warning("No image paths resolved. Exiting change_wallpaper.")
        return (WallpaperUpdateResult.NO_IMAGES_FOUND, "No image paths could be resolved from the configured source.")

    # Log history (just the first one or all? Let's log all reversed so last one is top)
    for p in reversed(image_paths):
        log_wallpaper_history(p)

    final_image_paths: List[str] = []
    if effect != ImageEffect.NONE:
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

    if multi_monitor_mode == MultiMonitorMode.SPAN:
        if not final_image_paths:
            logging.error("No images available for composition.")
            return (WallpaperUpdateResult.NO_IMAGES_FOUND, "No images available for spanning across monitors.")

        logging.info("Creating composite image for span mode from a SINGLE source image.")
        # Span mode implies taking ONE image and stretching it.
        # So we should probably use the first image chosen.
        try:
            single_image: str = final_image_paths[0]
        except IndexError:
            logging.error("IndexError accessing final_image_paths[0] despite check.")
            return (WallpaperUpdateResult.NO_IMAGES_FOUND, "Internal error: No image found for spanning.")

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
        mode = config_manager.get_setting(config, "Settings", "mode", "zoom", str)
    else:
        # "Single image on all monitors" (Duplicate)
        mode = config_manager.get_setting(config, "Settings", "mode", "zoom", str)
        # Ensure we just have one image (duplicated for logic if needed, but apply_desktop_settings usually takes one and applies it everywhere)
        # Actually Manager changes below might expect list.
        # If we selected 1 image above, we are good.
        # If we accidentally selected N images (due to logic change), we should pick 0.
        # But 'images_needed' was 1 if not "Different image on each monitor".
        pass

    background_color: str = config_manager.get_setting(config, "Settings", "background_color", "#000000", str)

    logging.info(f"Applying wallpaper with mode: {mode}, images: {len(final_image_paths)}")

    success, error_message = manager.apply_desktop_settings(mode, final_image_paths, background_color)

    if success:
        # Proactive Safe Temp File Cleanup
        try:
            temp_dir = os.path.join(CONFIG_DIR, "temp")
            if os.path.exists(temp_dir):
                kept_files = set(os.path.abspath(p) for p in final_image_paths if p)
                cleaned_count = 0
                for filename in os.listdir(temp_dir):
                    file_path = os.path.abspath(os.path.join(temp_dir, filename))
                    if file_path not in kept_files:
                        try:
                            os.remove(file_path)
                            cleaned_count += 1
                        except OSError:
                            pass
                if cleaned_count > 0:
                    logging.info(f"Cleaned up {cleaned_count} old temporary file(s).")
        except Exception as e:
            logging.error(f"Failed to clean up old temp files safely: {e}")

        logging.info("--- change_wallpaper finished successfully ---")
        return (WallpaperUpdateResult.SUCCESS, "")
    else:
        logging.error(f"Failed to apply desktop settings via wallpaper_manager: {error_message}")
        return (WallpaperUpdateResult.DESKTOP_ENVIRONMENT_ERROR, error_message)
