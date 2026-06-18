import unittest
from unittest.mock import MagicMock

from wallshuffle.online_sources import OnlineSourceManager


class TestOnlineSourcesCache(unittest.TestCase):
    def setUp(self):
        self.mock_config_manager = MagicMock()
        self.mock_config = {"Settings": {}}
        self.mock_config_manager.get_setting.side_effect = lambda config, section, option, fallback, vtype=None: {
            "circuit_breaker_failures": 3,
            "circuit_breaker_cooldown": 15,
            "max_cache_size_mb": 500,
        }.get(option, fallback)
        self.manager = OnlineSourceManager(self.mock_config_manager, self.mock_config)

    def test_cache_keys_differ_by_index(self):
        key_a = self.manager._get_cache_key("nature", index=0)
        key_b = self.manager._get_cache_key("nature", index=1)
        self.assertNotEqual(key_a, key_b)

    def test_cache_keys_encode_keywords_consistently(self):
        key_a = self.manager._get_cache_key("nature city", index=0)
        key_b = self.manager._get_cache_key("nature city", index=0)
        self.assertEqual(key_a, key_b)


if __name__ == "__main__":
    unittest.main()
