import os
import logging
from typing import Dict, Optional
from .spec import ThemeSpec
from .store import ThemeStore

class ThemeResolver:
    def __init__(self, store: ThemeStore, config_manager, config):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.store = store
        self.config_manager = config_manager
        self.config = config
        self._session_overrides: Dict[str, Dict[str, str]] = {}

    def detect_distro(self) -> (Optional[str], Optional[str]):
        """Detects the Linux distribution ID and ID_LIKE from /etc/os-release."""
        distro_id = None
        distro_like = None
        try:
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release") as f:
                    for line in f:
                        if line.startswith("ID="):
                            distro_id = line.split("=")[1].strip().strip('"')
                        elif line.startswith("ID_LIKE="):
                            distro_like = line.split("=")[1].strip().strip('"')
            return distro_id, distro_like
        except Exception as e:
            self.logger.error(f"Error reading /etc/os-release: {e}")
        return None, None

    def resolve(self, name: str) -> ThemeSpec:
        """
        Resolves a theme with the following precedence:
        1. Preset base
        2. Distro overlay (if applicable)
        3. User config overrides (from config.ini)
        4. Session overrides (runtime)
        """
        self.logger.debug(f"Resolving theme: {name}")
        
        # 1. Start with the preset base
        base_spec = self.store.get_preset(name)
        resolved_tokens = base_spec.tokens.copy()

        # 2. Distro overlay (Smart mapping logic)
        # If the requested name is 'Default', we try to auto-detect
        if name == "Default":
            distro_id, distro_like = self.detect_distro()
            possible_ids = [distro_id, distro_like] if distro_like else [distro_id]
            
            presets = self.store.get_all_presets()
            for d_id in filter(None, possible_ids):
                d_id = d_id.lower()
                found_key = next((k for k in presets.keys() if k.lower() == d_id or (d_id == "linuxmint" and k == "LinuxMint")), None)
                if found_key:
                    self.logger.info(f"Auto-detected distro theme for 'Default': {found_key}")
                    resolved_tokens.update(presets[found_key].tokens)
                    break

        # 3. User config overrides (Backward compatibility with config.ini)
        # We check for custom_background, custom_foreground, etc. if theme is 'Custom'
        if name == "Custom":
            resolved_tokens["background"] = self.config_manager.get_setting(self.config, "Settings", "custom_background", resolved_tokens["background"])
            resolved_tokens["foreground"] = self.config_manager.get_setting(self.config, "Settings", "custom_foreground", resolved_tokens["foreground"])
            resolved_tokens["accent"] = self.config_manager.get_setting(self.config, "Settings", "custom_accent", resolved_tokens["accent"])
            resolved_tokens["button_text"] = self.config_manager.get_setting(self.config, "Settings", "custom_button_text", resolved_tokens.get("button_text", "#FFFFFF"))

        # 4. Session overrides (Runtime)
        if name in self._session_overrides:
            self.logger.debug(f"Applying session overrides for {name}")
            resolved_tokens.update(self._session_overrides[name])

        return ThemeSpec(id=name, tokens=resolved_tokens, metadata=base_spec.metadata)

    def set_session_override(self, name: str, tokens: Dict[str, str]):
        self._session_overrides[name] = tokens
