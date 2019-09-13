from math import isfinite
from typing import Any

__all__ = ["is_finite"]


def is_finite(value: Any) -> bool:
    """Return true if a value is a finite number."""
    return (isinstance(value, int) and not isinstance(value, bool)) or (
        isinstance(value, float) and isfinite(value)
    )
