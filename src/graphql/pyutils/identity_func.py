from typing import Any, TypeVar, cast

from .undefined import Undefined


__all__ = ["identity_func"]


T = TypeVar("T")


def identity_func(x: T = cast(Any, Undefined), *_args: Any) -> T:
    """Return the first received argument."""
    return x
