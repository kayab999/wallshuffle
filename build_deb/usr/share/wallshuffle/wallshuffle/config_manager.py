import configparser
import fcntl
import logging
import os

from .utils import CONFIG_DIR, CONFIG_FILE


class ConfigManager:
    def __init__(self):
        self._ensure_config_dir_exists()

    def _ensure_config_dir_exists(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
        except OSError as e:
            logging.critical(f"Error creating config directory {CONFIG_DIR}: {e}", exc_info=True)

    def load_settings(self):
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
        except (configparser.Error, IOError) as e:
            logging.error(f"Error reading config file {CONFIG_FILE}: {e}")
            self.create_default_config(config)

        return config

    def create_default_config(self, config):
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

    def save_settings(self, config, settings_dict):
        if "Settings" not in config:
            config["Settings"] = {}
        for key, value in settings_dict.items():
            config["Settings"][key] = str(value)

        try:
            with open(CONFIG_FILE, "w") as configfile:
                try:
                    fcntl.flock(configfile, fcntl.LOCK_EX)
                    config.write(configfile)
                finally:
                    fcntl.flock(configfile, fcntl.LOCK_UN)
            return True
        except IOError as e:
            logging.error(f"Error writing config file {CONFIG_FILE}: {e}")
            return False
        except Exception as e:
            logging.critical(f"An unhandled error occurred while saving config: {e}", exc_info=True)
            return False

    def get_setting(self, config, section, option, fallback=None, value_type=str):
        """
        Retrieves a setting from the config, with type casting and fallback support.
        Acts as a 'Safe Harbor' that never raises an exception.
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
