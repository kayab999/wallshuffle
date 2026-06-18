"""Persists the last-used index for sequential (non-random) local folder rotation."""

import fcntl
import hashlib
import json
import logging
import os
from typing import Any, Dict, List, cast

from .utils import CONFIG_DIR

SEQUENTIAL_STATE_FILE = os.path.join(CONFIG_DIR, "sequential_state.json")


def folder_state_key(folder: str) -> str:
    return hashlib.sha256(os.path.abspath(folder).encode()).hexdigest()[:16]


def _load_state() -> Dict[str, Any]:
    if not os.path.exists(SEQUENTIAL_STATE_FILE):
        return {}
    try:
        with open(SEQUENTIAL_STATE_FILE, "r") as handle:
            fcntl.flock(handle, fcntl.LOCK_SH)
            try:
                return cast(Dict[str, Any], json.load(handle))
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
    except (OSError, json.JSONDecodeError) as error:
        logging.warning(f"Could not read sequential state: {error}")
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
    try:
        with open(SEQUENTIAL_STATE_FILE, "w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                json.dump(state, handle)
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
    except OSError as error:
        logging.error(f"Could not save sequential state: {error}")


def select_sequential_images(images: List[str], folder: str, count: int) -> List[str]:
    """Return the next N images in order, advancing the persisted index."""
    if not images or count <= 0:
        return []

    key = folder_state_key(folder)
    state = _load_state()
    start = int(state.get(key, 0)) % len(images)
    selected = [images[(start + offset) % len(images)] for offset in range(count)]
    state[key] = (start + count) % len(images)
    _save_state(state)
    return selected
