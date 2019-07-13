from typing import Any
from math import isfinite

__all__ = ["is_integer"]


def is_integer(value: Any) -> bool:
    """Return true if a value is an integer number."""
    return (isinstance(value, int) and not isinstance(value, bool)) or (
        isinstance(value, float) and isfinite(value) and int(value) == value
    )
