import configparser
import logging
import os
import fcntl

from .utils import CONFIG_DIR, CONFIG_FILE


class ConfigManager:
    def __init__(self):
        self._ensure_config_dir_exists()

    def _ensure_config_dir_exists(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
        except OSError as e:
            logging.critical(f"Error creating config directory {CONFIG_DIR}: {e}", exc_info=True)
            # In a GUI context, show_error_dialog would be called here.
            # For now, just log and let subsequent operations fail if directory is truly uncreatable.

    def load_settings(self):
        config = configparser.ConfigParser()
        try:
            if not os.path.exists(CONFIG_FILE):
                # If the config file doesn't exist, create it with default values
                self.create_default_config(config)
            else:
                with open(CONFIG_FILE, "r") as f:
                    try:
                        fcntl.flock(f, fcntl.LOCK_SH) # Shared lock for reading
                        config.read_file(f)
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)
        except (configparser.Error, IOError) as e:
            logging.error(f"Error reading config file {CONFIG_FILE}: {e}")
            # In case of an error, create a default config
            self.create_default_config(config)

        return config

    def create_default_config(self, config):
        """
        Creates a default configuration file.

        :param config: The ConfigParser object to create the default config in.
        """
        config["Settings"] = {"dark_mode": "false"}
        try:
            with open(CONFIG_FILE, "w") as configfile:
                try:
                    fcntl.flock(configfile, fcntl.LOCK_EX) # Exclusive lock for writing
                    config.write(configfile)
                finally:
                    fcntl.flock(configfile, fcntl.LOCK_UN)
        except IOError as e:
            logging.error(f"Error creating default config file {CONFIG_FILE}: {e}")

    def save_settings(self, config, settings_dict):
        """
        Saves the provided settings to the config file.

        :param config: The ConfigParser object to modify.
        :param settings_dict: A dictionary of settings to save.
        :return: True if successful, False otherwise.
        """
        if "Settings" not in config:
            config["Settings"] = {}
        for key, value in settings_dict.items():
            config["Settings"][key] = str(value)

        try:
            with open(CONFIG_FILE, "w") as configfile:
                try:
                    fcntl.flock(configfile, fcntl.LOCK_EX) # Exclusive lock for writing
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
        Retrieves a setting from the config, with type casting.

        :param config: The ConfigParser object to read from.
        :param section: The section of the setting.
        :param option: The option of the setting.
        :param fallback: The fallback value if the setting is not found.
        :param value_type: The type to cast the value to (e.g., int, bool, float, list).
        :return: The setting value, cast to the specified type.
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
            else:
                return fallback
        except ValueError as e:
            logging.error(
                f"Error converting config option {option} in section {section}: {e}. Returning fallback {fallback}"
            )
            return fallback
        except Exception as e:
            logging.critical(
                f"An unhandled error occurred while getting config setting {section}.{option}: {e}",
                exc_info=True,
            )
            return fallback
