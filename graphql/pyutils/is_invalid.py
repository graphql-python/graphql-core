from typing import Any

from ..error import INVALID

__all__ = ["is_invalid"]


def is_invalid(value: Any) -> bool:
    """Return true if a value is undefined, or NaN."""
    return value is INVALID or value != value
