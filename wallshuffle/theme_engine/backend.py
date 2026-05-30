import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk
import logging

class ThemeBackend:
    def apply(self, css_provider: Gtk.CssProvider):
        raise NotImplementedError("Subclasses must implement apply()")

class GTKBackend(ThemeBackend):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def apply(self, css_provider: Gtk.CssProvider):
        """Applies the CSS provider to the default screen (GTK3)."""
        try:
            screen = Gdk.Screen.get_default()
            Gtk.StyleContext.add_provider_for_screen(
                screen,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            self.logger.debug("Successfully applied CSS provider to GTK screen.")
        except Exception as e:
            self.logger.error(f"Failed to apply CSS to GTK screen: {e}")
