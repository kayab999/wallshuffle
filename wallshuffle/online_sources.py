import datetime
import hashlib
import json
import logging
import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .utils import CONFIG_DIR, show_error_dialog

CACHE_DIR = os.path.join(CONFIG_DIR, "cache")
CACHE_EXPIRATION_HOURS = 24


class OnlineSourceManager:
    def __init__(self, config_manager, config):
        self.config_manager = config_manager
        self.config = config
        os.makedirs(CACHE_DIR, exist_ok=True)
        self.session = self._create_resilient_session()

    def _create_resilient_session(self):
        """
        Creates a requests Session with retry logic for robustness.
        Retries on 5xx errors and read timeouts.
        """
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,  # Wait 1s, 2s, 4s...
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _get_cache_path(self, keywords):
        # Create a hash of the keywords to use as part of the filename
        keyword_hash = hashlib.md5(keywords.encode("utf-8")).hexdigest()
        return os.path.join(CACHE_DIR, f"unsplash_{keyword_hash}.jpg")

    def _get_cached_image(self, keywords):
        cache_file = self._get_cache_path(keywords)
        if os.path.exists(cache_file):
            # Check if the cache file is still valid (e.g., not expired)
            file_mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(cache_file))
            if (
                datetime.datetime.now() - file_mod_time
            ).total_seconds() / 3600 < CACHE_EXPIRATION_HOURS:
                logging.info(f"Returning cached image for keywords: {keywords}")
                return cache_file
            else:
                logging.info(f"Cached image for keywords: {keywords} has expired. Deleting.")
                os.remove(cache_file)
        return None

    def _save_image_to_cache(self, image_data, keywords):
        cache_file = self._get_cache_path(keywords)
        try:
            with open(cache_file, "wb") as f:
                f.write(image_data)
            logging.info(f"Image cached for keywords: {keywords}")
        except IOError as e:
            logging.error(f"Error saving image to cache {cache_file}: {e}")

    def fetch_unsplash_wallpaper(self, keywords):
        # First, try to get from cache
        cached_image_path = self._get_cached_image(keywords)
        if cached_image_path:
            return cached_image_path

        unsplash_api_key = self.config_manager.get_setting(
            self.config, "Settings", "unsplash_api_key", "YOUR_UNSPLASH_API_KEY"
        )
        if unsplash_api_key == "YOUR_UNSPLASH_API_KEY":
            logging.error("Unsplash API key is not configured.")
            show_error_dialog(
                "Unsplash API key is not configured. Please set it in the settings.", parent=None
            )  # Parent is None as this is not a GUI context
            return None
        url = (
            f"https://api.unsplash.com/photos/random?query={keywords}&client_id={unsplash_api_key}"
        )
        try:
            # Use self.session instead of requests directly
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            image_url = data["urls"]["full"]
            
            # Use self.session for image download too
            image_response = self.session.get(image_url, stream=True, timeout=10)
            image_response.raise_for_status()

            # Read image data into memory before saving to temp and cache
            image_data = image_response.raw.read()

            temp_dir = os.path.join(CONFIG_DIR, "temp")
            os.makedirs(temp_dir, exist_ok=True)
            image_path = os.path.join(temp_dir, "unsplash_wallpaper.jpg")
            with open(image_path, "wb") as f:
                f.write(image_data)

            # Save to cache
            self._save_image_to_cache(image_data, keywords)

            return image_path
        except requests.exceptions.RetryError:
            logging.error(f"Max retries exceeded fetching from Unsplash for keywords: {keywords}")
            return None
        except requests.exceptions.Timeout:
            logging.error(f"Timeout fetching from Unsplash for keywords: {keywords}")
            return None
        except requests.exceptions.ConnectionError:
            logging.error(f"Connection error fetching from Unsplash for keywords: {keywords}")
            return None
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP error fetching from Unsplash for keywords: {keywords} - {e}")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(
                f"General request error fetching from Unsplash for keywords: {keywords} - {e}"
            )
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
            logging.critical(
                f"An unhandled error occurred in fetch_unsplash_wallpaper: {e}", exc_info=True
            )
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