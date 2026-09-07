"""mtime-based cache for local folder image discovery."""

import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from .constants import MAX_CACHED_IMAGES, MAX_DIRECTORY_DEPTH, SUPPORTED_EXTENSIONS
from .utils import CACHE_DIR

INDEX_CACHE_DIR = os.path.join(CACHE_DIR, "folder_index")


def _has_supported_extension(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in SUPPORTED_EXTENSIONS


def _is_usable_image_path(path: str) -> bool:
    """Match image_discovery.is_usable_image_path (kept local to avoid import cycles)."""
    if not path:
        return False
    try:
        if not os.path.isfile(path):
            return False
        os.stat(path)
        if _has_supported_extension(os.path.basename(path)):
            return True
        if os.path.islink(path):
            return _has_supported_extension(os.path.basename(os.path.realpath(path)))
        return False
    except OSError:
        return False


def _cache_path(folder: str, recursive: bool) -> str:
    key = hashlib.sha256(f"{os.path.abspath(folder)}:{int(recursive)}".encode()).hexdigest()[:20]
    return os.path.join(INDEX_CACHE_DIR, f"{key}.json")


def _scan_folder_once(folder: str, recursive: bool) -> Tuple[List[str], int, float]:
    """
    Single-scan helper: collect usable image paths and compute signature (count, max_mtime)
    in one os.walk pass to avoid triple scans. Applies MAX_CACHED_IMAGES cap to list.
    """
    images: List[str] = []
    count = 0
    max_mtime = 0.0

    capped_warned = False
    # Fase 1: hard break — evita I/O storm: no stat/iter tras alcanzar MAX_CACHED_IMAGES (previene os.stat masivo)
    hard_break = False
    if recursive:
        visited_dirs = set()
        start_depth = folder.rstrip(os.sep).count(os.sep)
        for root, dirs, files in os.walk(folder, followlinks=True):
            if hard_break:
                break
            try:
                real_root = os.path.realpath(root)
                if real_root in visited_dirs:
                    logging.warning(f"Symlink loop detected or already visited: {root} -> {real_root}. Skipping.")
                    dirs[:] = []
                    continue
                current_depth = root.rstrip(os.sep).count(os.sep)
                if (current_depth - start_depth) > MAX_DIRECTORY_DEPTH:
                    logging.warning(f"Maximum directory traversal depth ({MAX_DIRECTORY_DEPTH}) exceeded at {root}.")
                    dirs[:] = []
                    continue
                visited_dirs.add(real_root)
            except OSError:
                continue

            for filename in files:
                # Fase 1: hard break — si ya alcanzamos cap, no stat ni iter restantes
                if count >= MAX_CACHED_IMAGES and len(images) >= MAX_CACHED_IMAGES:
                    if not capped_warned:
                        logging.warning(
                            f"Folder {folder} exceeds {MAX_CACHED_IMAGES} images; truncating list to cap to prevent OOM. "
                            f"Consider using a more specific subfolder or disabling recursive_search."
                        )
                        capped_warned = True
                    # Vacía dirs para no descender más y marca break externo
                    dirs[:] = []
                    hard_break = True
                    break
                full_path = os.path.join(root, filename)
                if not _is_usable_image_path(full_path):
                    continue
                try:
                    stat = os.stat(full_path)
                except OSError:
                    continue
                count += 1
                max_mtime = max(max_mtime, stat.st_mtime)
                # Cap list size to prevent unbounded memory
                if len(images) < MAX_CACHED_IMAGES:
                    images.append(full_path)
                elif not capped_warned:
                    logging.warning(
                        f"Folder {folder} exceeds {MAX_CACHED_IMAGES} images; truncating list to cap to prevent OOM. "
                        f"Consider using a more specific subfolder or disabling recursive_search."
                    )
                    capped_warned = True
                # Si acabamos de alcanzar cap, siguiente iteración hará hard break sin stat
                if count >= MAX_CACHED_IMAGES and len(images) >= MAX_CACHED_IMAGES:
                    dirs[:] = []
                    hard_break = True
                    break
    else:
        try:
            for filename in os.listdir(folder):
                # Fase 1: hard break sin stat si ya alcanzamos cap
                if count >= MAX_CACHED_IMAGES and len(images) >= MAX_CACHED_IMAGES:
                    if not capped_warned:
                        logging.warning(
                            f"Folder {folder} exceeds {MAX_CACHED_IMAGES} images; truncating list to cap."
                        )
                        capped_warned = True
                    break
                full_path = os.path.join(folder, filename)
                if not _is_usable_image_path(full_path):
                    continue
                try:
                    stat = os.stat(full_path)
                except OSError:
                    continue
                count += 1
                max_mtime = max(max_mtime, stat.st_mtime)
                if len(images) < MAX_CACHED_IMAGES:
                    images.append(full_path)
                elif not capped_warned:
                    logging.warning(
                        f"Folder {folder} exceeds {MAX_CACHED_IMAGES} images; truncating list to cap."
                    )
                    capped_warned = True
                if count >= MAX_CACHED_IMAGES and len(images) >= MAX_CACHED_IMAGES:
                    break
        except OSError as e:
            logging.error(f"Error listing folder {folder}: {e}")
            return [], 0, 0.0

    # If truncated, images length == cap but count may be larger; caller handles skip-cache logic
    return images, count, max_mtime


def _image_signature(folder: str, recursive: bool) -> Tuple[int, float]:
    """Return usable image file count and max mtime (follows symlinks)."""
    _, count, max_mtime = _scan_folder_once(folder, recursive)
    return count, max_mtime


def _is_cache_valid(entry: Dict[str, Any], folder: str, recursive: bool) -> bool:
    if entry.get("recursive") != recursive:
        return False
    images = entry.get("images", [])
    if not isinstance(images, list):
        return False
    # Reject caches that list paths which are no longer usable (e.g. dangling symlinks).
    if any(not _is_usable_image_path(str(path)) for path in images):
        return False
    try:
        image_count, max_image_mtime = _image_signature(folder, recursive)
    except OSError:
        return False
    return (
        entry.get("image_count") == image_count
        and entry.get("max_image_mtime") == max_image_mtime
        and len(images) == image_count
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


def store_cached_images(
    folder: str, recursive: bool, images: List[str], precomputed_signature: Optional[Tuple[int, float]] = None
) -> None:
    usable = [path for path in images if _is_usable_image_path(path)]
    try:
        if precomputed_signature is not None:
            image_count, max_image_mtime = precomputed_signature
        else:
            image_count, max_image_mtime = _image_signature(folder, recursive)
    except OSError as error:
        logging.warning(f"Could not snapshot folder for cache ({folder}): {error}")
        return

    # Only cache when the provided list matches the live folder signature.
    # Partial lists (or dangling-link noise) would otherwise load as stale hits.
    if len(usable) != image_count:
        logging.debug(
            f"Skip folder index cache for {folder}: list has {len(usable)} usable "
            f"paths but signature count is {image_count}"
        )
        return

    os.makedirs(INDEX_CACHE_DIR, mode=0o700, exist_ok=True)
    entry = {
        "folder": os.path.abspath(folder),
        "recursive": recursive,
        "image_count": image_count,
        "max_image_mtime": max_image_mtime,
        "cached_at": time.time(),
        "images": usable,
    }
    cache_file = _cache_path(folder, recursive)
    try:
        with open(cache_file, "w", encoding="utf-8") as handle:
            json.dump(entry, handle)
        logging.debug(f"Stored folder index cache for {folder} ({len(usable)} images)")
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
