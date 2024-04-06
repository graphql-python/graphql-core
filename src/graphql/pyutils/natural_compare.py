"""Natural sort order"""

from __future__ import annotations

import re
from itertools import cycle

__all__ = ["natural_comparison_key"]

_re_digits = re.compile(r"(\d+)")


def natural_comparison_key(key: str) -> tuple:
    """Comparison key function for sorting strings by natural sort order.

    See: https://en.wikipedia.org/wiki/Natural_sort_order
    """
    return tuple(
        (int(part), part) if is_digit else part
        for part, is_digit in zip(_re_digits.split(key), cycle((False, True)))
    )
