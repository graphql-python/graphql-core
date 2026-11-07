"""Natural sort order"""

from __future__ import annotations

import re

__all__ = ["natural_comparison_key"]

_re_digits = re.compile(r"(\d+)")


def natural_comparison_key(key: str) -> tuple:
    """Comparison key function for sorting strings by natural sort order.

    See: https://en.wikipedia.org/wiki/Natural_sort_order
    """
    # letters only (no decimal digits) is the common case, check it cheaply first
    if type(key) is str and key.isalpha():
        return (key,)
    parts = _re_digits.split(key)
    parts[1::2] = [(int(part), part) for part in parts[1::2]]
    return tuple(parts)
