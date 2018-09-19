from typing import Any

from ..error import INVALID

__all__ = ["is_nullish"]


def is_nullish(value: Any) -> bool:
    """Return true if a value is null, undefined, or NaN."""
    return value is None or value is INVALID or value != value
