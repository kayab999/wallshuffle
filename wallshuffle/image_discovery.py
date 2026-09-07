"""Shared utilities for discovering image files in local folders."""

import logging
import os
from typing import List

from .constants import MAX_CACHED_IMAGES, SUPPORTED_EXTENSIONS
from .image_index import _scan_folder_once, load_cached_images, store_cached_images


def _has_supported_extension(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in SUPPORTED_EXTENSIONS


def is_usable_image_path(path: str) -> bool:
    """
    True if path is a readable regular image file after following symlinks.

    Accepts symlink-to-file (common "hyperlinks" wallpaper folders), including
    extensionless link names whose resolved target has a supported extension.
    Rejects dangling symlinks, directories, and unreadable targets.
    """
    if not path:
        return False
    try:
        # isfile() follows symlinks; False for dangling links / dirs.
        if not os.path.isfile(path):
            return False
        # Confirm the final target is stat-able (permission / mount issues).
        os.stat(path)
        if _has_supported_extension(os.path.basename(path)):
            return True
        # Extensionless symlink (or odd name) → check resolved target basename.
        if os.path.islink(path):
            return _has_supported_extension(os.path.basename(os.path.realpath(path)))
        return False
    except OSError:
        return False


def find_images_in_folder(folder: str, recursive: bool = False) -> List[str]:
    """
    Return absolute paths to supported image files under folder.

    Includes regular files and symlinks to image files. When recursive=True,
    follows directory symlinks with loop detection and a depth cap.
    """
    if not folder or not os.path.isdir(folder):
        return []

    cached_images = load_cached_images(folder, recursive)
    if cached_images is not None:
        return cached_images

    # Single-scan: collect images and signature together to avoid triple walk
    found_images, image_count, max_mtime = _scan_folder_once(folder, recursive)

    # _scan_folder_once uses _is_usable_image_path which matches is_usable_image_path;
    # already filtered, but keep as-is. The helper already caps at MAX_CACHED_IMAGES.
    if image_count > MAX_CACHED_IMAGES:
        logging.warning(
            f"Found {image_count} images in {folder} but capped to {MAX_CACHED_IMAGES} to prevent OOM/I/O storm."
        )

    # Store with precomputed signature to avoid second walk
    store_cached_images(folder, recursive, found_images, precomputed_signature=(image_count, max_mtime))
    return found_images


def count_images_in_folder(folder: str, recursive: bool = False) -> int:
    """Return the number of supported image files under folder."""
    return len(find_images_in_folder(folder, recursive))
