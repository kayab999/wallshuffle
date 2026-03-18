"""
Tests for ConfigManager singleton pattern and thread-safety.
"""

import configparser
import sys
import threading
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from wallshuffle.config_manager import get_config_manager


def test_singleton_returns_same_instance():
    """Verify that get_config_manager() always returns the same instance."""
    instance1 = get_config_manager()
    instance2 = get_config_manager()

    assert instance1 is instance2, "get_config_manager() should return the same instance"
    print("✓ Singleton test passed: Same instance returned")


def test_singleton_thread_safety():
    """Verify that get_config_manager() is thread-safe during concurrent access."""
    instances = []

    def get_instance():
        instances.append(get_config_manager())

    # Create 10 threads that simultaneously try to get the instance
    threads = [threading.Thread(target=get_instance) for _ in range(10)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # All instances should be the same object
    first_instance = instances[0]
    for instance in instances:
        assert instance is first_instance, "All threads should get the same instance"

    print(f"✓ Thread-safety test passed: All {len(instances)} threads got same instance")


def test_config_operations():
    """Test basic config operations work with singleton."""
    cm = get_config_manager()

    # Load config
    config = cm.load_settings()
    assert isinstance(config, configparser.ConfigParser), "Should return ConfigParser"

    # Test get_setting
    value = cm.get_setting(config, "Settings", "dark_mode", "false")
    assert value in ["true", "false"], f"dark_mode should be boolean string, got: {value}"

    # Test save_settings
    test_settings = {"test_key": "test_value"}
    success = cm.save_settings(config, test_settings)
    assert success, "save_settings should succeed"

    # Reload and verify
    config2 = cm.load_settings()
    retrieved = cm.get_setting(config2, "Settings", "test_key", None)
    assert retrieved == "test_value", f"Expected 'test_value', got: {retrieved}"

    print("✓ Config operations test passed")


def test_type_casting():
    """Test that get_setting properly casts types."""
    cm = get_config_manager()
    config = cm.load_settings()

    # Save test values
    cm.save_settings(config, {
        "int_test": "42",
        "bool_test": "true",
        "float_test": "3.14",
        "list_test": "a, b, c",
    })

    # Reload
    config = cm.load_settings()

    # Test int casting
    int_val = cm.get_setting(config, "Settings", "int_test", 0, value_type=int)
    assert int_val == 42, f"Expected 42, got {int_val}"
    assert isinstance(int_val, int), "Should be int type"

    # Test bool casting
    bool_val = cm.get_setting(config, "Settings", "bool_test", False, value_type=bool)
    assert bool_val is True, f"Expected True, got {bool_val}"
    assert isinstance(bool_val, bool), "Should be bool type"

    # Test float casting
    float_val = cm.get_setting(config, "Settings", "float_test", 0.0, value_type=float)
    assert abs(float_val - 3.14) < 0.001, f"Expected 3.14, got {float_val}"
    assert isinstance(float_val, float), "Should be float type"

    # Test list casting
    list_val = cm.get_setting(config, "Settings", "list_test", [], value_type=list)
    assert list_val == ["a", "b", "c"], f"Expected ['a', 'b', 'c'], got {list_val}"
    assert isinstance(list_val, list), "Should be list type"

    print("✓ Type casting test passed")


def test_fallback_on_missing():
    """Test that fallback values are returned when keys don't exist."""
    cm = get_config_manager()
    config = cm.load_settings()

    # Test with non-existent key
    value = cm.get_setting(config, "Settings", "nonexistent_key", "default_value")
    assert value == "default_value", f"Expected fallback, got: {value}"

    # Test with int fallback
    int_val = cm.get_setting(config, "Settings", "nonexistent_int", 99, value_type=int)
    assert int_val == 99, f"Expected 99, got: {int_val}"

    print("✓ Fallback test passed")


if __name__ == "__main__":
    print("Running ConfigManager Tests...\n")

    try:
        test_singleton_returns_same_instance()
        test_singleton_thread_safety()
        test_config_operations()
        test_type_casting()
        test_fallback_on_missing()

        print("\n" + "="*50)
        print("✅ All tests passed!")
        print("="*50)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
