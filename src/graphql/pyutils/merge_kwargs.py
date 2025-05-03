"""Merge arguments"""

from __future__ import annotations

from typing import Any, Dict, TypeVar, cast

T = TypeVar("T")


def merge_kwargs(base_dict: T, **kwargs: Any) -> T:
    """Return arbitrary typed dictionary with some keyword args merged in."""
    return cast("T", {**cast("Dict", base_dict), **kwargs})
