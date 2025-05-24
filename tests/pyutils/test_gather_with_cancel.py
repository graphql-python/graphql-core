from __future__ import annotations

from asyncio import Event, create_task, gather, sleep, wait_for
from typing import Callable

import pytest

from graphql.pyutils import gather_with_cancel, is_awaitable


class Controller:
    def reset(self, wait=False):
        self.event = Event()
        if not wait:
            self.event.set()
        self.returned = []


controller = Controller()


async def coroutine(value: int) -> int:
    """Simple coroutine that returns a value."""
    if value > 2:
        raise RuntimeError("Oops")
    await controller.event.wait()
    controller.returned.append(value)
    return value


class CustomAwaitable:
    """Custom awaitable that return a value."""

    def __init__(self, value: int):
        self.value = value
        self.coroutine = coroutine(value)

    def __await__(self):
        return self.coroutine.__await__()


awaitable_factories: dict[str, Callable] = {
    "coroutine": coroutine,
    "task": lambda value: create_task(coroutine(value)),
    "custom": lambda value: CustomAwaitable(value),
}

with_all_types_of_awaitables = pytest.mark.parametrize(
    "type_of_awaitable", awaitable_factories
)


def describe_gather_with_cancel():
    @with_all_types_of_awaitables
    @pytest.mark.asyncio
    async def gathers_all_values(type_of_awaitable: str):
        factory = awaitable_factories[type_of_awaitable]
        values = list(range(3))

        controller.reset()
        aws = [factory(i) for i in values]

        assert await gather(*aws) == values
        assert controller.returned == values

        controller.reset()
        aws = [factory(i) for i in values]

        result = gather_with_cancel(*aws)
        assert is_awaitable(result)

        awaited = await wait_for(result, 1)
        assert awaited == values

    @with_all_types_of_awaitables
    @pytest.mark.asyncio
    async def raises_on_exception(type_of_awaitable: str):
        factory = awaitable_factories[type_of_awaitable]
        values = list(range(4))

        controller.reset()
        aws = [factory(i) for i in values]

        with pytest.raises(RuntimeError, match="Oops"):
            await gather(*aws)
        assert controller.returned == values[:-1]

        controller.reset()
        aws = [factory(i) for i in values]

        result = gather_with_cancel(*aws)
        assert is_awaitable(result)

        with pytest.raises(RuntimeError, match="Oops"):
            await wait_for(result, 1)
        assert controller.returned == values[:-1]

    @with_all_types_of_awaitables
    @pytest.mark.asyncio
    async def cancels_on_exception(type_of_awaitable: str):
        factory = awaitable_factories[type_of_awaitable]
        values = list(range(4))

        controller.reset(wait=True)
        aws = [factory(i) for i in values]

        with pytest.raises(RuntimeError, match="Oops"):
            await gather(*aws)
        assert not controller.returned

        # check that the standard gather continues to produce results
        controller.event.set()
        await sleep(0)
        assert controller.returned == values[:-1]

        controller.reset(wait=True)
        aws = [factory(i) for i in values]

        result = gather_with_cancel(*aws)
        assert is_awaitable(result)

        with pytest.raises(RuntimeError, match="Oops"):
            await wait_for(result, 1)
        assert not controller.returned

        # check that gather_with_cancel stops producing results
        controller.event.set()
        await sleep(0)
        if type_of_awaitable == "custom":
            # Cancellation of custom awaitables is not supported
            assert controller.returned == values[:-1]
        else:
            assert not controller.returned
