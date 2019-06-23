from typing import cast, Any, TypeVar

from ..error import INVALID

__all__ = ["identity_func"]


T = TypeVar("T")


def identity_func(x: T = cast(Any, INVALID), *_args: Any) -> T:
    """Return the first received argument."""
    return x
