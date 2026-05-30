import re
from typing import Set, Dict, Callable

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{3,6}$")

REQUIRED_TOKENS: Set[str] = {
    "background",
    "foreground",
    "accent",
    "hover",
    "button_text",
}

OPTIONAL_TOKENS: Set[str] = {
    "border",
    "surface",
}

# Example of constrained tokens
CONSTRAINED_TOKENS: Dict[str, Callable[[str], bool]] = {
    "accent": lambda v: HEX_RE.match(v) is not None,
}

class ThemeValidator:
    @staticmethod
    def validate(spec: "ThemeSpec"):
        """Validates the ThemeSpec against required and constrained tokens."""
        missing = REQUIRED_TOKENS - spec.tokens.keys()
        if missing:
            raise ValueError(f"Missing required tokens: {missing}")

        for key, value in spec.tokens.items():
            # Validate hex colors for all known color tokens
            if key in REQUIRED_TOKENS | OPTIONAL_TOKENS:
                if not HEX_RE.match(value):
                    raise ValueError(f"Invalid hex color for {key}: {value}")
            
            # Apply specific constraints
            if key in CONSTRAINED_TOKENS:
                if not CONSTRAINED_TOKENS[key](value):
                    raise ValueError(f"Constraint failed for token {key}: {value}")
        
        return True
