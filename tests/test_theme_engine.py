import pytest
from unittest.mock import MagicMock
from wallshuffle.theme_engine.engine import ThemeEngine
from wallshuffle.theme_engine.spec import ThemeSpec
from wallshuffle.theme_engine.events import EventBus
from wallshuffle.theme_engine.validator import ThemeValidator

class MockConfigManager:
    def __init__(self):
        self.settings = {"Settings": {"theme": "Ubuntu"}}
    
    def load_settings(self):
        return self.settings
    
    def get_setting(self, config, section, key, default=None, value_type=None):
        val = self.settings.get(section, {}).get(key, default)
        if value_type and val is not None:
            return value_type(val)
        return val
    
    def save_settings(self, config, settings_dict):
        self.settings["Settings"].update(settings_dict)
        return True

@pytest.fixture
def engine():
    mock_cm = MockConfigManager()
    config = mock_cm.load_settings()
    # Mock backend to avoid GTK calls during tests
    mock_backend = MagicMock()
    return ThemeEngine(mock_cm, config, backend=mock_backend)

def test_theme_resolution_ubuntu(engine):
    assert engine.set_theme("Ubuntu") is True
    assert engine.current_spec.id == "Ubuntu"
    assert engine.current_spec.tokens["accent"] == "#DD4814"

def test_theme_resolution_custom_overrides(engine):
    engine.config_manager.settings["Settings"]["custom_accent"] = "#FF00FF"
    assert engine.set_theme("Custom") is True
    assert engine.current_spec.tokens["accent"] == "#FF00FF"

def test_event_bus_reactivity(engine):
    callback = MagicMock()
    engine.events.on("theme_changed", callback)
    
    engine.set_theme("Arch")
    
    callback.assert_called_once()
    spec = callback.call_args[0][0]
    assert isinstance(spec, ThemeSpec)
    assert spec.id == "Arch"

def test_session_override(engine):
    engine.set_theme("Ubuntu")
    original_accent = engine.current_spec.tokens["accent"]
    
    # Apply session override
    engine.override_session("Ubuntu", {"accent": "#00FF00"})
    
    assert engine.current_spec.tokens["accent"] == "#00FF00"
    # Verify it didn't change the preset base forever (well, it stays in resolver)
    
def test_validation_fails_on_invalid_hex(engine):
    # Manually trigger a resolution that would fail validation
    with pytest.raises(ValueError):
        invalid_spec = ThemeSpec(id="Broken", tokens={"background": "not-a-color"})
        ThemeValidator.validate(invalid_spec)

def test_distro_detection_mock(engine, monkeypatch):
    # Mock /etc/os-release detection
    monkeypatch.setattr(engine.resolver, "detect_distro", lambda: ("arch", "archlinux"))
    
    # 'Default' theme should now resolve to Arch tokens
    engine.set_theme("Default")
    assert engine.current_spec.tokens["accent"] == "#1793D1" # Arch accent
