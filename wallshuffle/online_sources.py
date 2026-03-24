import datetime
import hashlib
import json
import logging
import os
import shutil
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .utils import CONFIG_DIR

CACHE_DIR = os.path.join(CONFIG_DIR, "cache")
CACHE_EXPIRATION_HOURS = 24

class UnsplashConfigError(Exception):
    """Exception raised when Unsplash API is not properly configured."""
    pass


class OnlineSourceManager:
    # Circuit Breaker state (static across instances during app life)
    _consecutive_failures = 0
    _last_failure_time = None
    _COOLDOWN_MINUTES = 15
    _MAX_FAILURES = 3

    def __init__(self, config_manager, config):
        self.config_manager = config_manager
        self.config = config
        os.makedirs(CACHE_DIR, exist_ok=True)
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
        if OnlineSourceManager._consecutive_failures >= OnlineSourceManager._MAX_FAILURES:
            if OnlineSourceManager._last_failure_time:
                elapsed = datetime.datetime.now() - OnlineSourceManager._last_failure_time
                if elapsed < datetime.timedelta(minutes=OnlineSourceManager._COOLDOWN_MINUTES):
                    remaining = OnlineSourceManager._COOLDOWN_MINUTES - (elapsed.total_seconds() / 60)
                    logging.warning(f"Unsplash source is in cooldown. {remaining:.1f}m remaining.")
                    return False
                else:
                    # Cooldown expired, reset
                    OnlineSourceManager._consecutive_failures = 0
        return True

    def _record_failure(self):
        OnlineSourceManager._consecutive_failures += 1
        OnlineSourceManager._last_failure_time = datetime.datetime.now()
        if OnlineSourceManager._consecutive_failures >= OnlineSourceManager._MAX_FAILURES:
            logging.error(f"Unsplash source entered cooldown after {OnlineSourceManager._MAX_FAILURES} failures.")

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
        # Legacy method kept if needed, but we prefer file copy
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

    def fetch_unsplash_wallpaper(self, keywords, index=0):
        # First, try to get from cache
        # We only cache based on keywords, so index doesn't affect cache lookup
        # unless we want different images for different monitors to be cached separately.
        # For now, let's keep it simple: cache is a single 'daily' image for keywords.
        cached_image_path = self._get_cached_image(keywords)
        if cached_image_path:
            return cached_image_path

        if not self._check_circuit_breaker():
            return None

        unsplash_api_key = self.config_manager.get_setting(self.config, "Settings", "unsplash_api_key", "YOUR_UNSPLASH_API_KEY")
        if unsplash_api_key == "YOUR_UNSPLASH_API_KEY":
            logging.error("Unsplash API key is not configured.")
            raise UnsplashConfigError("Unsplash API key is not configured. Please set it in the settings.")
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
            os.makedirs(temp_dir, exist_ok=True)
            # Use index in filename to avoid overwrites during multi-monitor fetches
            # Use secure temp file creation
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", dir=temp_dir) as f:
                for chunk in image_response.iter_content(chunk_size=8192):
                    f.write(chunk)
                image_path = f.name

            # Read back for cache
            self._save_image_file_to_cache(image_path, keywords)

            self._record_success()
            return image_path
        except requests.exceptions.RetryError:
            logging.error(f"Max retries exceeded fetching from Unsplash for keywords: {keywords}")
            self._record_failure()
            return None
        except requests.exceptions.Timeout:
            logging.error(f"Timeout fetching from Unsplash for keywords: {keywords}")
            self._record_failure()
            return None
        except requests.exceptions.ConnectionError:
            logging.error(f"Connection error fetching from Unsplash for keywords: {keywords}")
            self._record_failure()
            return None
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP error fetching from Unsplash for keywords: {keywords} - {e}")
            self._record_failure()
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"General request error fetching from Unsplash for keywords: {keywords} - {e}")
            return None
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON response from Unsplash for keywords: {keywords}")
            return None
        except KeyError:
            logging.error(f"Missing data in Unsplash response for keywords: {keywords}")
            return None
        except IOError as e:
            logging.error(f"File I/O error while saving Unsplash image: {e}")
            return None
        except Exception as e:
            logging.critical(f"An unhandled error occurred in fetch_unsplash_wallpaper: {e}", exc_info=True)
            return None

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
    def cleanup_old_cache():
        """Removes all cache files older than CACHE_EXPIRATION_HOURS."""
        if not os.path.exists(CACHE_DIR):
            return

        now = time.time()
        expiration_seconds = CACHE_EXPIRATION_HOURS * 3600

        logging.info("Starting cache cleanup...")
        removed_count = 0
        try:
            for f in os.listdir(CACHE_DIR):
                path = os.path.join(CACHE_DIR, f)
                if os.path.isfile(path):
                    try:
                        file_time = os.path.getmtime(path)
                        if (now - file_time) > expiration_seconds:
                            os.remove(path)
                            removed_count += 1
                    except OSError:
                        pass
            if removed_count > 0:
                logging.info(f"Cleanup complete. Removed {removed_count} expired cache files.")
        except Exception as e:
            logging.error(f"Error during cache cleanup: {e}")
