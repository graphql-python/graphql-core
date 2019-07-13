from typing import Any
from math import isfinite

__all__ = ["is_finite"]


def is_finite(value: Any) -> bool:
    """Return true if a value is a finite number."""
    return isinstance(value, int) or (isinstance(value, float) and isfinite(value))
