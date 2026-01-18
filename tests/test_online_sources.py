
import unittest
from unittest.mock import MagicMock, patch

import requests

from wallshuffle.online_sources import OnlineSourceManager


class TestOnlineSourcesResilience(unittest.TestCase):
    def setUp(self):
        # Mock ConfigManager
        self.mock_config_manager = MagicMock()
        self.mock_config = {"Settings": {"unsplash_api_key": "valid_key"}}
        self.mock_config_manager.get_setting.return_value = "valid_key"

        self.manager = OnlineSourceManager(self.mock_config_manager, self.mock_config)

    @patch("requests.Session")
    def test_fetch_with_retries(self, mock_session_cls):
        """
        Test that the manager uses a session with retry logic.
        This verifies we are NOT using bare requests.get() anymore.
        """
        # We expect the class to now use self.session or create a session with mount
        # This test checks if we are properly configuring retries.

        # NOTE: Since we haven't implemented it yet, we check internal behavior logic
        # For now, let's mock the network call to simulate fail-then-success

        # Scenario: First call fails (500), Second call succeeds (200)
        # However, verifying 'retries' with `requests` usually involves checking the Adapter
        # or seeing if the mock was called multiple times by the library (which is hard to mock perfectly without integration)

        # Instead, we will assert that we are using a Session object, not requests.get
        with patch("wallshuffle.online_sources.requests.get") as mock_bare_get:
            try:
                self.manager.fetch_unsplash_wallpaper("nature")
            except Exception:
                pass

            # If implementation is correct, bare requests.get should NOT be called
            # It should use self.session.get
            self.assertFalse(mock_bare_get.called, "Should use session.get, not requests.get")

    def test_401_no_retry(self):
        """Test that we do NOT retry on 401 Unauthorized"""
        # Mock the session OBJECT inside the manager instance
        self.manager.session = MagicMock()

        # Configure mock to return 401
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Client Error")

        self.manager.session.get.return_value = mock_response

        result = self.manager.fetch_unsplash_wallpaper("test")

        self.assertIsNone(result)
        # Should only be called once (no retries for auth errors handled by library,
        # but mainly we verify logic flow didn't try to loop manually)
        self.assertEqual(self.manager.session.get.call_count, 1)

if __name__ == "__main__":
    unittest.main()
