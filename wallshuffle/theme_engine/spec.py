from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass(frozen=True)
class ThemeSpec:
    """Immutable specification of a theme."""
    id: str
    tokens: Dict[str, str]
    metadata: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.tokens, dict):
            raise TypeError("tokens must be a dict")
