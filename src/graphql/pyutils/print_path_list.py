"""Path printing"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection


def print_path_list(path: Collection[str | int]) -> str:
    """Build a string describing the path."""
    return "".join(f"[{key}]" if isinstance(key, int) else f".{key}" for key in path)
