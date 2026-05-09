import datetime
import hashlib
import json
import logging
import os
import shutil
import time
from typing import Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .constants import CACHE_EXPIRATION_HOURS
from .utils import CACHE_DIR, CONFIG_DIR

class UnsplashConfigError(Exception):
    """Exception raised when Unsplash API is not properly configured."""
    pass


class OnlineSourceManager:
    # Circuit Breaker state (static across instances during app life)
    _consecutive_failures = 0
    _last_failure_time = None

    def __init__(self, config_manager, config):
        self.config_manager = config_manager
        self.config = config
        
        # Thresholds configurables (Fase 2 Hardening)
        self.max_failures = config_manager.get_setting(config, "Settings", "circuit_breaker_failures", 3, int)
        self.cooldown_minutes = config_manager.get_setting(config, "Settings", "circuit_breaker_cooldown", 15, int)
        self.max_cache_size_mb = config_manager.get_setting(config, "Settings", "max_cache_size_mb", 500, int)

        # Ensure restricted permissions on cache directory
        os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)
        self.session = self._create_resilient_session()

    def _create_resilient_session(self):
        """Creates a requests Session with retries and timeout defaults."""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _check_circuit_breaker(self):
        """Check if we are in a cooldown period."""
        if OnlineSourceManager._consecutive_failures >= self.max_failures:
            if OnlineSourceManager._last_failure_time:
                elapsed = datetime.datetime.now() - OnlineSourceManager._last_failure_time
                if elapsed < datetime.timedelta(minutes=self.cooldown_minutes):
                    remaining = self.cooldown_minutes - (elapsed.total_seconds() / 60)
                    logging.warning(f"Unsplash source is in cooldown. {remaining:.1f}m remaining.")
                    return False
                else:
                    # Cooldown expired, reset
                    OnlineSourceManager._consecutive_failures = 0
        return True

    def _record_failure(self):
        OnlineSourceManager._consecutive_failures += 1
        OnlineSourceManager._last_failure_time = datetime.datetime.now()
        if OnlineSourceManager._consecutive_failures >= self.max_failures:
            logging.error(f"Unsplash source entered cooldown after {self.max_failures} failures.")

    def _record_success(self):
        OnlineSourceManager._consecutive_failures = 0
        OnlineSourceManager._last_failure_time = None

    def _get_cache_key(self, keywords):
        """Generates a unique filename for the cache based on keywords."""
        safe_keywords = keywords.replace(" ", "_") if keywords else "random"
        # Combine keywords with date (daily rotation) to ensure freshness
        date_str = datetime.date.today().isoformat()
        key_str = f"{safe_keywords}_{date_str}"
        return hashlib.md5(key_str.encode()).hexdigest() + ".jpg"

    def _get_cached_image(self, keywords):
        """Returns path to valid cached image if available, else None."""
        filename = self._get_cache_key(keywords)
        cache_path = os.path.join(CACHE_DIR, filename)

        if os.path.exists(cache_path):
            # Check expiration
            file_time = os.path.getmtime(cache_path)
            age_hours = (time.time() - file_time) / 3600

            if age_hours < CACHE_EXPIRATION_HOURS:
                logging.info(f"Using cached Unsplash image: {cache_path}")
                return cache_path
            else:
                logging.debug("Cached image expired.")
                try:
                    os.remove(cache_path)
                except OSError:
                    pass

        return None

    def _save_image_to_cache(self, image_data, keywords):
        """Saves downloaded image data to cache directory."""
        filename = self._get_cache_key(keywords)
        cache_path = os.path.join(CACHE_DIR, filename)
        try:
            with open(cache_path, "wb") as f:
                f.write(image_data)
        except IOError as e:
            logging.error(f"Failed to save image to cache: {e}")

    def _save_image_file_to_cache(self, source_path, keywords):
        """Copies downloaded image file to cache directory."""
        filename = self._get_cache_key(keywords)
        cache_path = os.path.join(CACHE_DIR, filename)
        try:
            shutil.copy2(source_path, cache_path)
        except IOError as e:
            logging.error(f"Failed to copy image to cache: {e}")

    def fetch_unsplash_wallpaper(self, keywords, index=0) -> Tuple[Optional[str], str]:
        # First, try to get from cache
        cached_image_path = self._get_cached_image(keywords)
        if cached_image_path:
            return cached_image_path, ""

        if not self._check_circuit_breaker():
            return None, f"Unsplash source is in cooldown. Try again in {self.cooldown_minutes} minutes."

        unsplash_api_key = self.config_manager.get_setting(self.config, "Settings", "unsplash_api_key", "YOUR_UNSPLASH_API_KEY")
        if not unsplash_api_key or unsplash_api_key == "YOUR_UNSPLASH_API_KEY":
            error_msg = "Unsplash API key is not configured. Please set it in the settings."
            logging.error(error_msg)
            return None, error_msg
        url = f"https://api.unsplash.com/photos/random?query={keywords}&client_id={unsplash_api_key}"
        try:
            # Use self.session instead of requests directly
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            image_url = data["urls"]["full"]

            # Use self.session for image download too
            image_response = self.session.get(image_url, stream=True, timeout=10)
            image_response.raise_for_status()

            temp_dir = os.path.join(CONFIG_DIR, "temp")
            os.makedirs(temp_dir, mode=0o700, exist_ok=True)
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", dir=temp_dir) as f:
                for chunk in image_response.iter_content(chunk_size=8192):
                    f.write(chunk)
                image_path = f.name

            # Read back for cache
            self._save_image_file_to_cache(image_path, keywords)
            
            # Ejecutar limpieza proactiva de caché (Fase 2)
            OnlineSourceManager.cleanup_old_cache(max_size_mb=self.max_cache_size_mb)

            self._record_success()
            return image_path, ""
        except requests.exceptions.RetryError as e:
            error_msg = f"Max retries exceeded fetching from Unsplash for keywords: {keywords}. Error: {e}"
            logging.error(error_msg)
            self._record_failure()
            return None, error_msg
        except requests.exceptions.Timeout as e:
            error_msg = f"Timeout fetching from Unsplash for keywords: {keywords}. Error: {e}"
            logging.error(error_msg)
            self._record_failure()
            return None, error_msg
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error fetching from Unsplash for keywords: {keywords}. Error: {e}"
            logging.error(error_msg)
            self._record_failure()
            return None, error_msg
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "Unknown"
            error_msg = f"HTTP error fetching from Unsplash for keywords: {keywords} - {e}. Status Code: {status_code}"
            logging.error(error_msg)
            self._record_failure()
            return None, error_msg
        except requests.exceptions.SSLError as e:
            error_msg = f"SSL/Certificate error fetching from Unsplash (possible local system issue): {e}"
            logging.error(error_msg)
            return None, error_msg
        except requests.exceptions.RequestException as e:
            error_msg = f"General network request failure for keywords '{keywords}': {e}"
            logging.error(error_msg)
            return None, error_msg
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON response from Unsplash for keywords: {keywords}. Error: {e}"
            logging.error(error_msg)
            return None, error_msg
        except KeyError as e:
            error_msg = f"Missing data in Unsplash response for keywords: {keywords}. Error: {e}"
            logging.error(error_msg)
            return None, error_msg
        except IOError as e:
            error_msg = f"File I/O error while saving Unsplash image: {e}"
            logging.error(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"An unhandled error occurred in fetch_unsplash_wallpaper: {e}"
            logging.critical(error_msg, exc_info=True)
            return None, error_msg

    def test_api_connection(self, api_key):
        """
        Tests the Unsplash API connection with the provided key.
        Returns (True, "Success Message") or (False, "Error Message").
        """
        if not api_key or api_key == "YOUR_UNSPLASH_API_KEY":
            return False, "Please enter a valid API Key."

        url = f"https://api.unsplash.com/search/photos?query=nature&per_page=1&client_id={api_key}"

        try:
            # Also use resilient session for testing connection
            response = self.session.get(url, timeout=5)
            if response.status_code == 200:
                return True, "Connection successful! API Key is valid."
            elif response.status_code == 401:
                return False, "Unauthorized. Invalid API Key."
            elif response.status_code == 403:
                return False, "Forbidden. Rate limit exceeded or key disabled."
            else:
                return False, f"API returned error code: {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Could not connect to Unsplash servers. Check internet."
        except requests.exceptions.Timeout:
            return False, "Connection timed out."
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    # Placeholder for other online sources
    def fetch_flickr_wallpaper(self, keywords):
        logging.warning("Flickr integration not yet implemented.")
        return None

    def fetch_wallhaven_wallpaper(self, keywords):
        logging.warning("Wallhaven integration not yet implemented.")
        return None

    def fetch_reddit_wallpaper(self, subreddit):
        logging.warning("Reddit integration not yet implemented.")
        return None

    @staticmethod
    def cleanup_old_cache(max_size_mb: Optional[int] = None):
        """
        Removes cache files based on age and total directory size (LRU).
        """
        if not os.path.exists(CACHE_DIR):
            return

        now = time.time()
        expiration_seconds = CACHE_EXPIRATION_HOURS * 3600

        logging.debug("Starting cache maintenance...")
        
        files_data = []
        try:
            for f in os.listdir(CACHE_DIR):
                path = os.path.join(CACHE_DIR, f)
                if os.path.isfile(path):
                    try:
                        stat = os.stat(path)
                        files_data.append({
                            "path": path,
                            "size": stat.st_size,
                            "mtime": stat.st_mtime
                        })
                    except OSError:
                        continue

            # 1. Primero eliminar archivos expirados (por tiempo)
            removed_count = 0
            remaining_files = []
            for item in files_data:
                if (now - item["mtime"]) > expiration_seconds:
                    try:
                        os.remove(item["path"])
                        removed_count += 1
                    except OSError:
                        remaining_files.append(item)
                else:
                    remaining_files.append(item)
            
            if removed_count > 0:
                logging.info(f"Cache cleanup (expiration): Removed {removed_count} files.")

            # 2. Si se especifica max_size_mb, aplicar política LRU (por tamaño)
            if max_size_mb is not None:
                max_bytes = max_size_mb * 1024 * 1024
                current_bytes = sum(f["size"] for f in remaining_files)
                
                if current_bytes > max_bytes:
                    # Ordenar por mtime (más antiguo primero para LRU)
                    remaining_files.sort(key=lambda x: x["mtime"])
                    
                    purged_size = 0
                    purged_count = 0
                    for item in remaining_files:
                        if current_bytes <= max_bytes:
                            break
                        try:
                            os.remove(item["path"])
                            current_bytes -= item["size"]
                            purged_size += item["size"]
                            purged_count += 1
                        except OSError:
                            pass
                    
                    if purged_count > 0:
                        logging.info(f"Cache cleanup (LRU): Purged {purged_count} files ({purged_size / (1024*1024):.1f} MB) to stay under {max_size_mb} MB.")

        except Exception as e:
            logging.error(f"Error during cache cleanup: {e}")
