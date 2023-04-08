import asyncio
from typing import Awaitable, Tuple, TypeVar, cast

from graphql.pyutils import is_awaitable

from .assert_matching_values import assert_matching_values


__all__ = ["assert_equal_awaitables_or_values"]

T = TypeVar("T")


def assert_equal_awaitables_or_values(*items: T) -> T:
    """Check whether the items are the same and either all awaitables or all values."""
    if all(is_awaitable(item) for item in items):
        awaitable_items = cast(Tuple[Awaitable], items)

        async def assert_matching_awaitables():
            return assert_matching_values(*(await asyncio.gather(*awaitable_items)))

        return assert_matching_awaitables()

    if all(not is_awaitable(item) for item in items):
        return assert_matching_values(*items)

    assert False, "Received an invalid mixture of promises and values."
