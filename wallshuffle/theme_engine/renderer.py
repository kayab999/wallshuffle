import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from .spec import ThemeSpec

class ThemeRenderer:
    @staticmethod
    def render_to_css(spec: ThemeSpec) -> str:
        """Transforms ThemeSpec tokens into a GTK3 CSS string."""
        theme = spec.tokens
        
        css = f"""
* {{
    transition: background 200ms ease-in-out, border-color 200ms ease-in-out, box-shadow 200ms ease-in-out;
}}

#wallshuffle-main-window {{
    background-color: {theme["background"]};
    color: {theme["foreground"]};
    font-family: sans-serif;
}}

/* Titles */
#wallshuffle-main-window .title-2 {{
    font-weight: bold;
    font-size: 1.3em;
    margin-bottom: 12px;
    color: {theme["accent"]};
}}

/* Dim Labels */
#wallshuffle-main-window .dim-label {{
    opacity: 0.65;
    font-size: 0.9em;
}}

/* Cards (Gtk.Frame) */
#wallshuffle-main-window frame, #wallshuffle-main-window .card {{
    background-color: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
}}

#wallshuffle-main-window frame > border {{
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
}}

/* Flat Entries */
#wallshuffle-main-window entry.flat {{
    min-height: 0;
    padding: 4px;
    background-color: transparent;
    border: none;
    box-shadow: none;
    font-weight: bold;
}}

/* Standard Widgets */
#wallshuffle-main-window GtkLabel {{
    color: {theme["foreground"]};
}}

/* Button System */
#wallshuffle-main-window GtkButton, #wallshuffle-main-window button {{
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
    transition: all 200ms ease-in-out;
}}

#wallshuffle-main-window .primary-button,
#wallshuffle-main-window .suggested-action {{
    background-color: {theme["accent"]};
    color: {theme.get("button_text", "#FFFFFF")};
    border: none;
    font-weight: bold;
}}

#wallshuffle-main-window .primary-button:hover,
#wallshuffle-main-window .suggested-action:hover {{
    background-color: {theme.get("hover", theme["accent"])};
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
}}

#wallshuffle-main-window .primary-button:active,
#wallshuffle-main-window .suggested-action:active {{
    opacity: 0.8;
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}}

#wallshuffle-main-window .secondary-button {{
    background-color: rgba(255, 255, 255, 0.1);
    color: {theme["foreground"]};
    border: 1px solid rgba(255, 255, 255, 0.2);
}}

#wallshuffle-main-window .secondary-button:hover {{
    background-color: rgba(255, 255, 255, 0.15);
}}

#wallshuffle-main-window .danger-button {{
    background-color: #e53935;
    color: #ffffff;
    border: none;
}}

#wallshuffle-main-window .danger-button:hover {{
    background-color: #d32f2f;
}}

#wallshuffle-main-window GtkEntry {{
    background-color: rgba(0, 0, 0, 0.2);
    color: {theme["foreground"]};
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 6px;
}}

#wallshuffle-main-window GtkEntry:focus {{
    border-color: {theme["accent"]};
}}

#wallshuffle-main-window GtkComboBox GtkEntry {{
    background-color: transparent;
    border: none;
}}
"""
        return css

    @staticmethod
    def get_css_provider(spec: ThemeSpec) -> Gtk.CssProvider:
        """Helper to get a Gtk.CssProvider directly from a spec."""
        css = ThemeRenderer.render_to_css(spec)
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css.encode("utf-8"))
        return css_provider
