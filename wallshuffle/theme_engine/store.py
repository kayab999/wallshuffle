import os
import logging
from .spec import ThemeSpec
from .presets import THEMES

class ThemeStore:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._presets = {}
        self._load_presets()

    def _load_presets(self):
        """Loads themes from the legacy themes.py and wraps them in ThemeSpec."""
        for name, tokens in THEMES.items():
            self._presets[name] = ThemeSpec(id=name, tokens=tokens)
        self.logger.debug(f"Loaded {len(self._presets)} theme presets.")

    def get_preset(self, name: str) -> ThemeSpec:
        """Returns a theme preset by name."""
        if name not in self._presets:
            raise ValueError(f"Theme preset '{name}' not found.")
        return self._presets[name]

    def get_all_presets(self) -> dict:
        return self._presets
