import logging
from typing import Optional
from .events import EventBus
from .store import ThemeStore
from .resolver import ThemeResolver
from .validator import ThemeValidator
from .renderer import ThemeRenderer
from .backend import ThemeBackend, GTKBackend
from .spec import ThemeSpec

class ThemeEngine:
    def __init__(self, config_manager, config, backend: Optional[ThemeBackend] = None, event_bus: Optional[EventBus] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config_manager = config_manager
        self.config = config
        self.events = event_bus or EventBus()
        self.backend = backend or GTKBackend()
        self.store = ThemeStore()
        self.resolver = ThemeResolver(self.store, self.config_manager, self.config)
        self.current_spec: Optional[ThemeSpec] = None

    def set_theme(self, name: str, save: bool = True):
        """Resolves, validates, renders, and applies a theme by name."""
        try:
            self.logger.info(f"Setting theme to: {name}")
            
            # Resolve the spec (Preset -> Distro -> User -> Session)
            spec = self.resolver.resolve(name)
            
            # Validate the spec
            ThemeValidator.validate(spec)
            
            # Render to CSS provider
            css_provider = ThemeRenderer.get_css_provider(spec)
            
            # Apply via backend
            self.backend.apply(css_provider)
            
            # Update state
            self.current_spec = spec
            
            # Persist if requested
            if save:
                self.config_manager.save_settings(self.config, {"theme": name})
            
            # Notify subscribers
            self.events.emit("theme_changed", spec)
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to set theme '{name}': {e}", exc_info=True)
            return False

    def override_session(self, name: str, tokens: dict):
        """Provides a temporary session override and re-applies if active."""
        self.resolver.set_session_override(name, tokens)
        if self.current_spec and self.current_spec.id == name:
            self.reload()

    def reload(self):
        """Reloads the current theme."""
        if self.current_spec:
            return self.set_theme(self.current_spec.id, save=False)
        return False

    def get_current_theme_name(self) -> str:
        if self.current_spec:
            return self.current_spec.id
        return self.config_manager.get_setting(self.config, "Settings", "theme", "Ubuntu")
