"""Shared utilities for discovering image files in local folders."""

import logging
import os
from typing import List

from .constants import MAX_DIRECTORY_DEPTH, SUPPORTED_EXTENSIONS
from .image_index import load_cached_images, store_cached_images


def _is_image_file(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in SUPPORTED_EXTENSIONS


def find_images_in_folder(folder: str, recursive: bool = False) -> List[str]:
    """
    Return absolute paths to supported image files under folder.

    When recursive=True, follows symlinks with loop detection and a depth cap.
    """
    if not folder or not os.path.isdir(folder):
        return []

    cached_images = load_cached_images(folder, recursive)
    if cached_images is not None:
        return cached_images

    found_images: List[str] = []

    if recursive:
        visited_dirs = set()
        start_depth = folder.rstrip(os.sep).count(os.sep)

        for root, dirs, files in os.walk(folder, followlinks=True):
            try:
                real_root = os.path.realpath(root)
                if real_root in visited_dirs:
                    logging.warning(
                        f"Symlink loop detected or already visited: {root} -> {real_root}. Skipping."
                    )
                    dirs[:] = []
                    continue

                current_depth = root.rstrip(os.sep).count(os.sep)
                if (current_depth - start_depth) > MAX_DIRECTORY_DEPTH:
                    logging.warning(
                        f"Maximum directory traversal depth ({MAX_DIRECTORY_DEPTH}) exceeded at {root}."
                    )
                    dirs[:] = []
                    continue

                visited_dirs.add(real_root)
            except OSError as e:
                logging.warning(f"Error resolving path {root}: {e}. Skipping loop check.")

            for filename in files:
                if _is_image_file(filename):
                    found_images.append(os.path.join(root, filename))
    else:
        try:
            for filename in os.listdir(folder):
                full_path = os.path.join(folder, filename)
                if os.path.isfile(full_path) and _is_image_file(filename):
                    found_images.append(full_path)
        except OSError as e:
            logging.error(f"Error listing folder {folder}: {e}")

    store_cached_images(folder, recursive, found_images)
    return found_images


def count_images_in_folder(folder: str, recursive: bool = False) -> int:
    """Return the number of supported image files under folder."""
    return len(find_images_in_folder(folder, recursive))
