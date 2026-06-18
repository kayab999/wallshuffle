"""mtime-based cache for local folder image discovery."""

import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from .constants import MAX_DIRECTORY_DEPTH, SUPPORTED_EXTENSIONS
from .utils import CACHE_DIR

INDEX_CACHE_DIR = os.path.join(CACHE_DIR, "folder_index")


def _is_image_file(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in SUPPORTED_EXTENSIONS


def _cache_path(folder: str, recursive: bool) -> str:
    key = hashlib.sha256(f"{os.path.abspath(folder)}:{int(recursive)}".encode()).hexdigest()[:20]
    return os.path.join(INDEX_CACHE_DIR, f"{key}.json")


def _image_signature(folder: str, recursive: bool) -> Tuple[int, float]:
    """Return image file count and max mtime for supported files only."""
    count = 0
    max_mtime = 0.0

    if recursive:
        visited_dirs = set()
        start_depth = folder.rstrip(os.sep).count(os.sep)
        for root, dirs, files in os.walk(folder, followlinks=True):
            try:
                real_root = os.path.realpath(root)
                if real_root in visited_dirs:
                    dirs[:] = []
                    continue
                current_depth = root.rstrip(os.sep).count(os.sep)
                if (current_depth - start_depth) > MAX_DIRECTORY_DEPTH:
                    dirs[:] = []
                    continue
                visited_dirs.add(real_root)
            except OSError:
                continue

            for filename in files:
                if not _is_image_file(filename):
                    continue
                try:
                    stat = os.stat(os.path.join(root, filename))
                except OSError:
                    continue
                count += 1
                max_mtime = max(max_mtime, stat.st_mtime)
    else:
        try:
            for filename in os.listdir(folder):
                full_path = os.path.join(folder, filename)
                if not os.path.isfile(full_path) or not _is_image_file(filename):
                    continue
                try:
                    stat = os.stat(full_path)
                except OSError:
                    continue
                count += 1
                max_mtime = max(max_mtime, stat.st_mtime)
        except OSError:
            return 0, 0.0

    return count, max_mtime


def _is_cache_valid(entry: Dict[str, Any], folder: str, recursive: bool) -> bool:
    if entry.get("recursive") != recursive:
        return False
    try:
        image_count, max_image_mtime = _image_signature(folder, recursive)
    except OSError:
        return False
    return (
        entry.get("image_count") == image_count
        and entry.get("max_image_mtime") == max_image_mtime
    )


def load_cached_images(folder: str, recursive: bool) -> Optional[List[str]]:
    cache_file = _cache_path(folder, recursive)
    if not os.path.isfile(cache_file):
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as handle:
            entry = json.load(handle)
        if not _is_cache_valid(entry, folder, recursive):
            return None
        images = entry.get("images", [])
        if isinstance(images, list):
            logging.debug(f"Folder index cache hit for {folder} ({len(images)} images)")
            return [str(path) for path in images]
    except (OSError, json.JSONDecodeError, TypeError) as error:
        logging.debug(f"Folder index cache read failed for {folder}: {error}")
    return None


def store_cached_images(folder: str, recursive: bool, images: List[str]) -> None:
    try:
        image_count, max_image_mtime = _image_signature(folder, recursive)
    except OSError as error:
        logging.warning(f"Could not snapshot folder for cache ({folder}): {error}")
        return

    os.makedirs(INDEX_CACHE_DIR, mode=0o700, exist_ok=True)
    entry = {
        "folder": os.path.abspath(folder),
        "recursive": recursive,
        "image_count": image_count,
        "max_image_mtime": max_image_mtime,
        "cached_at": time.time(),
        "images": images,
    }
    cache_file = _cache_path(folder, recursive)
    try:
        with open(cache_file, "w", encoding="utf-8") as handle:
            json.dump(entry, handle)
        logging.debug(f"Stored folder index cache for {folder} ({len(images)} images)")
    except OSError as error:
        logging.warning(f"Could not write folder index cache for {folder}: {error}")


def invalidate_folder_cache(folder: str, recursive: Optional[bool] = None) -> None:
    variants = (True, False) if recursive is None else (recursive,)
    for variant in variants:
        cache_file = _cache_path(folder, variant)
        try:
            if os.path.exists(cache_file):
                os.remove(cache_file)
        except OSError as error:
            logging.debug(f"Could not remove cache file {cache_file}: {error}")
