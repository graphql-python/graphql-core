from asyncio import Future, get_running_loop, isfuture, sleep

import pytest

from graphql.pyutils import BoxedAwaitableOrValue

pytestmark = pytest.mark.anyio


async def async_function() -> int:
    """A simple async function for testing awaitables."""
    return 42


def create_future() -> Future:
    """Create a new Future object."""
    return get_running_loop().create_future()


def describe_boxed_awaitable_futureor_value():
    def can_box_a_value():
        value = [42]
        boxed: BoxedAwaitableOrValue[list[int]] = BoxedAwaitableOrValue(value)

        assert boxed.value is value

    async def can_box_a_future():
        future: Future[int] = create_future()
        boxed: BoxedAwaitableOrValue[int] = BoxedAwaitableOrValue(future)

        assert boxed.value is future

    async def can_box_a_coroutine():
        awaitable = async_function()

        boxed: BoxedAwaitableOrValue[int] = BoxedAwaitableOrValue(awaitable)
        assert isfuture(boxed.value)

    async def updates_value_when_future_is_done():
        future: Future[list[int]] = create_future()
        boxed: BoxedAwaitableOrValue[list[int]] = BoxedAwaitableOrValue(future)
        assert boxed.value is future

        value = [42]
        future.set_result(value)
        # value is updated immediately
        assert boxed.value is value

        await sleep(0)
        # value is still available
        assert boxed.value is value

    async def updates_value_when_coroutine_was_awaited():
        awaitable = async_function()

        boxed: BoxedAwaitableOrValue[int] = BoxedAwaitableOrValue(awaitable)
        assert isfuture(boxed.value)

        await sleep(0)  # Allow the event loop to run the coroutine
        assert boxed.value == 42
