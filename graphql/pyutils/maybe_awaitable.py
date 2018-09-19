from typing import Awaitable, TypeVar, Union

__all__ = ["MaybeAwaitable"]


T = TypeVar("T")

MaybeAwaitable = Union[Awaitable[T], T]
