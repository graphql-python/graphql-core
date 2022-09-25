from typing import Any, TypeVar, cast

from .undefined import Undefined


__all__ = ["identity_func"]


T = TypeVar("T")

DEFAULT_VALUE = cast(Any, Undefined)


def identity_func(x: T = DEFAULT_VALUE, *_args: Any) -> T:
    """Return the first received argument."""
    return x
