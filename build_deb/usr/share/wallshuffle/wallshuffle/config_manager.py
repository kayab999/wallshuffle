"""
Configuration manager with thread-safe singleton pattern.

This module provides a centralized configuration management system that ensures
all parts of the application (GUI, daemon, systemd timers) share the same
in-memory configuration state, preventing desynchronization issues.
"""

import configparser
import fcntl
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Type, Union

from .utils import CONFIG_DIR, CONFIG_FILE

# Singleton instance and lock for thread-safe initialization
_instance: Optional["ConfigManager"] = None
_lock = threading.Lock()


def get_config_manager() -> "ConfigManager":
    """
    Get the singleton ConfigManager instance.

    This function ensures that only one ConfigManager instance exists throughout
    the application lifecycle, preventing configuration desynchronization between
    different components (UI, background daemon, systemd timer).

    Returns:
        ConfigManager: The singleton configuration manager instance.

    Thread-Safety:
        Uses double-checked locking pattern to minimize lock contention while
        ensuring thread-safe initialization.
    """
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = ConfigManager()
    return _instance


class ConfigManager:
    """
    Manages application configuration with thread-safe file I/O.

    This class handles reading, writing, and type-safe retrieval of configuration
    values. All file operations use fcntl file locking to prevent race conditions
    between concurrent processes (e.g., GUI and systemd timer).

    Note:
        Do not instantiate directly. Use get_config_manager() to obtain the
        singleton instance.
    """

    def __init__(self) -> None:
        """Initialize the configuration manager and ensure config directory exists."""
        self._ensure_config_dir_exists()

    def _ensure_config_dir_exists(self) -> None:
        """
        Create the configuration directory if it doesn't exist.

        Logs a critical error if directory creation fails, but does not raise
        an exception to allow the application to continue with in-memory config.
        """
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
        except OSError as e:
            logging.critical(
                f"Error creating config directory {CONFIG_DIR}: {e}", exc_info=True
            )

    def load_settings(self) -> configparser.ConfigParser:
        """
        Load configuration from disk with file locking.

        If the config file doesn't exist or is corrupted, creates a new default
        configuration automatically.

        Returns:
            configparser.ConfigParser: Loaded configuration object.

        Thread-Safety:
            Uses shared file lock (LOCK_SH) to allow concurrent reads but prevent
            writes during read operations.
        """
        config = configparser.ConfigParser()
        try:
            if not os.path.exists(CONFIG_FILE):
                self.create_default_config(config)
            else:
                with open(CONFIG_FILE, "r") as f:
                    try:
                        fcntl.flock(f, fcntl.LOCK_SH)
                        config.read_file(f)
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)

                # Legacy Migration: If "Settings.folder" exists but no "FolderCategories", migrate it.
                if config.has_option("Settings", "folder") and not config.has_section("FolderCategories"):
                    old_folder = config.get("Settings", "folder")
                    if old_folder:
                        config.add_section("FolderCategories")
                        config.set("FolderCategories", "Default", old_folder)
                        # We don't delete the old setting yet to maintain temporary backward compat,
                        # or we can just leave it as the 'default' selection.

        except (configparser.Error, IOError) as e:
            logging.error(f"Error reading config file {CONFIG_FILE}: {e}")
            self.create_default_config(config)

        return config

    def create_default_config(self, config: configparser.ConfigParser) -> None:
        """
        Create a default configuration file.

        Args:
            config: ConfigParser object to populate with defaults and write to disk.

        Thread-Safety:
            Uses exclusive file lock (LOCK_EX) to prevent concurrent writes.
        """
        config["Settings"] = {"dark_mode": "false"}
        try:
            with open(CONFIG_FILE, "w") as configfile:
                try:
                    fcntl.flock(configfile, fcntl.LOCK_EX)
                    config.write(configfile)
                finally:
                    fcntl.flock(configfile, fcntl.LOCK_UN)
        except IOError as e:
            logging.error(f"Error creating default config file {CONFIG_FILE}: {e}")

    def save_settings(
        self, config: configparser.ConfigParser, settings_dict: Dict[str, Any]
    ) -> bool:
        """
        Save configuration settings to disk.

        To prevent race conditions and stale data overwrites, this method:
        1. Reloads the latest data from disk.
        2. Applies only the specific changes in settings_dict.
        3. Saves the merged configuration back to disk.

        Args:
            config: ConfigParser object (unused for reading, but updated for consistency).
            settings_dict: Dictionary of key-value pairs to save.

        Returns:
            bool: True if save succeeded, False otherwise.

        Thread-Safety:
            Uses exclusive file lock (LOCK_EX) to prevent concurrent writes.
        """
        try:
            # Atomic Read-Modify-Write
            # We open the file in 'r+' mode to allow both reading and writing with a single file descriptor and lock
            # If the file doesn't exist, we fallback to 'w' (create) but that loses the atomicity of read-current-state.
            # However, ensure_config_dir_exists and load_settings usually ensure existence.

            # Using os.open to ensure it works even if file doesn't exist (handle creation)
            if not os.path.exists(CONFIG_FILE):
                 open(CONFIG_FILE, 'w').close()

            with open(CONFIG_FILE, "r+") as configfile:
                try:
                    # Acquire Exclusive Lock immediately
                    fcntl.flock(configfile, fcntl.LOCK_EX)

                    # 1. Read current state from disk
                    disk_config = configparser.ConfigParser()
                    disk_config.read_file(configfile)

                    if "Settings" not in disk_config:
                        disk_config["Settings"] = {}

                    # 2. Merge changes
                    for key, value in settings_dict.items():
                        disk_config["Settings"][key] = str(value)
                        # Sync in-memory object too
                        if "Settings" not in config:
                            config["Settings"] = {}
                        config["Settings"][key] = str(value)

                    # 3. Write back
                    configfile.seek(0)
                    disk_config.write(configfile)
                    configfile.truncate() # Ensure we don't leave old tail data

                finally:
                    fcntl.flock(configfile, fcntl.LOCK_UN)
            return True
        except IOError as e:
            logging.error(f"Error writing config file {CONFIG_FILE}: {e}")
            return False
        except Exception as e:
            logging.critical(
                f"An unhandled error occurred while saving config: {e}", exc_info=True
            )
            return False

    def get_setting(
        self,
        config: configparser.ConfigParser,
        section: str,
        option: str,
        fallback: Any = None,
        value_type: Type = str,
    ) -> Union[str, int, float, bool, List[str], None]:
        """
        Retrieve a setting from config with type casting and fallback support.

        This method acts as a 'Safe Harbor' that never raises exceptions, always
        returning a valid value (either the setting or the fallback).

        Args:
            config: ConfigParser object to read from.
            section: Configuration section name (e.g., "Settings").
            option: Option name within the section.
            fallback: Default value to return if option doesn't exist or parsing fails.
            value_type: Expected type for automatic casting. Supported types:
                - str: Return as string (default)
                - int: Parse as integer
                - float: Parse as float
                - bool: Parse as boolean (true/false, yes/no, 1/0)
                - list: Split by comma and strip whitespace

        Returns:
            The configuration value cast to the specified type, or fallback if
            the option doesn't exist or parsing fails.

        Examples:
            >>> cm = get_config_manager()
            >>> config = cm.load_settings()
            >>> interval = cm.get_setting(config, "Settings", "interval", 300, int)
            >>> enabled = cm.get_setting(config, "Settings", "enabled", False, bool)
        """
        try:
            if config.has_option(section, option):
                value = config.get(section, option)
                if value_type is int:
                    return int(value)
                elif value_type is bool:
                    return config.getboolean(section, option)
                elif value_type is float:
                    return float(value)
                elif value_type is list:
                    return [item.strip() for item in value.split(",")]
                else:
                    return value
            return fallback
        except Exception as e:
            # Log the error but DO NOT CRASH. Return the safe default.
            logging.error(f"Config read error ({section}.{option}): {e}")
            return fallback

    def save_categories(self, categories: Dict[str, str]) -> bool:
        """
        Save folder categories to the config file with locking.
        """
        try:
             # Atomic Read-Modify-Write
            if not os.path.exists(CONFIG_FILE):
                 open(CONFIG_FILE, 'w').close()

            with open(CONFIG_FILE, "r+") as configfile:
                try:
                    fcntl.flock(configfile, fcntl.LOCK_EX)

                    disk_config = configparser.ConfigParser()
                    disk_config.read_file(configfile)

                    if not disk_config.has_section("FolderCategories"):
                        disk_config.add_section("FolderCategories")
                    else:
                        disk_config.remove_section("FolderCategories")
                        disk_config.add_section("FolderCategories")

                    for name, path in categories.items():
                        disk_config.set("FolderCategories", name, path)

                    configfile.seek(0)
                    disk_config.write(configfile)
                    configfile.truncate()
                finally:
                    fcntl.flock(configfile, fcntl.LOCK_UN)
            return True
        except Exception as e:
            logging.error(f"Error saving categories: {e}")
            return False
