from typing import Any

from .undefined import Undefined

__all__ = ["is_invalid"]


def is_invalid(value: Any) -> bool:
    """Return true if a value is undefined, or NaN."""
    return value is Undefined or value != value
