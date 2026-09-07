"""Persists the last-used index for sequential (non-random) local folder rotation."""

import fcntl
import hashlib
import json
import logging
import os
import tempfile
import time
from typing import Any, Dict, List, cast

from .utils import CONFIG_DIR

# Fase 1: timeout monotónico 5s para flock no bloqueante (unifica con config_manager.py)
_SEQUENTIAL_LOCK_TIMEOUT = 5.0
_SEQUENTIAL_LOCK_POLL = 0.05


def _acquire_flock_with_timeout(handle, exclusive: bool, timeout: float = _SEQUENTIAL_LOCK_TIMEOUT) -> bool:
    """Intenta flock no bloqueante con timeout monotónico. Evita hilos colgados."""
    flags = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    flags |= fcntl.LOCK_NB
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            fcntl.flock(handle, flags)
            return True
        except (IOError, BlockingIOError, OSError):
            time.sleep(_SEQUENTIAL_LOCK_POLL)
    return False

SEQUENTIAL_STATE_FILE = os.path.join(CONFIG_DIR, "sequential_state.json")


def folder_state_key(folder: str) -> str:
    return hashlib.sha256(os.path.abspath(folder).encode()).hexdigest()[:16]


def _load_state() -> Dict[str, Any]:
    if not os.path.exists(SEQUENTIAL_STATE_FILE):
        return {}
    try:
        with open(SEQUENTIAL_STATE_FILE, "r") as handle:
            # Fase 1: flock no bloqueante 5s monotónico — evita bloquear GTK/timer concurrente
            if not _acquire_flock_with_timeout(handle, exclusive=False):
                logging.warning(
                    f"Timeout acquiring shared lock for {SEQUENTIAL_STATE_FILE} after {_SEQUENTIAL_LOCK_TIMEOUT}s — returning empty state"
                )
                return {}
            try:
                return cast(Dict[str, Any], json.load(handle))
            finally:
                try:
                    fcntl.flock(handle, fcntl.LOCK_UN)
                except OSError:
                    pass
    except (OSError, json.JSONDecodeError) as error:
        logging.warning(f"Could not read sequential state: {error}")
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    """Atomic write: temp file + replace so readers never see a truncated JSON."""
    dest_dir = os.path.dirname(os.path.abspath(SEQUENTIAL_STATE_FILE)) or CONFIG_DIR
    os.makedirs(dest_dir, mode=0o700, exist_ok=True)
    try:
        # Temp must live on the same filesystem as the destination for os.replace.
        fd, temp_path = tempfile.mkstemp(
            prefix="sequential_state_",
            suffix=".json",
            dir=dest_dir,
        )
        try:
            with os.fdopen(fd, "w") as handle:
                # Fase 1: flock no bloqueante 5s monotónico — evita hilos colgados en save concurrente
                if not _acquire_flock_with_timeout(handle, exclusive=True):
                    logging.warning(
                        f"Timeout acquiring exclusive lock for {SEQUENTIAL_STATE_FILE} — skip save, will retry next call"
                    )
                    # Notar: handle se cierra al salir del with; solo desvincula archivo temp (open-unlink es seguro en Linux)
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
                    return
                try:
                    json.dump(state, handle)
                    handle.flush()
                    os.fsync(handle.fileno())
                finally:
                    try:
                        fcntl.flock(handle, fcntl.LOCK_UN)
                    except OSError:
                        pass
            os.replace(temp_path, SEQUENTIAL_STATE_FILE)
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
    except OSError as error:
        logging.error(f"Could not save sequential state: {error}")


def select_sequential_images(images: List[str], folder: str, count: int) -> List[str]:
    """Return the next N images in order, advancing the persisted index."""
    if not images or count <= 0:
        return []

    key = folder_state_key(folder)
    state = _load_state()
    try:
        start_raw = state.get(key, 0)
        start = int(start_raw) % len(images)  # type: ignore[arg-type]
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logging.warning(f"Corrupt sequential state for {folder} ({e}); resetting to 0")
        start = 0
    try:
        selected = [images[(start + offset) % len(images)] for offset in range(count)]
        state[key] = (start + count) % len(images)
        _save_state(state)
    except Exception as e:
        logging.error(f"Failed sequential selection for {folder}: {e}")
        # Graceful fallback: return first N without advancing state
        return [images[i % len(images)] for i in range(count)]
    return selected
