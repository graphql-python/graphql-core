import sys
from asyncio import Event, ensure_future, sleep

from pytest import mark, raises  # type: ignore

from graphql.subscription.map_async_iterator import MapAsyncIterator


async def anext(iterable):
    """Return the next item from an async iterator."""
    return await iterable.__anext__()


def describe_map_async_iterator():
    @mark.asyncio
    async def maps_over_async_values():
        async def source():
            yield 1
            yield 2
            yield 3

        doubles = MapAsyncIterator(source(), lambda x: x + x)

        assert [value async for value in doubles] == [2, 4, 6]

    @mark.asyncio
    async def maps_over_async_values_with_async_function():
        async def source():
            yield 1
            yield 2
            yield 3

        async def double(x):
            return x + x

        doubles = MapAsyncIterator(source(), double)

        assert [value async for value in doubles] == [2, 4, 6]

    @mark.asyncio
    async def allows_returning_early_from_async_values():
        async def source():
            yield 1
            yield 2
            yield 3

        doubles = MapAsyncIterator(source(), lambda x: x + x)

        assert await anext(doubles) == 2
        assert await anext(doubles) == 4

        # Early return
        await doubles.aclose()

        # Subsequent nexts
        with raises(StopAsyncIteration):
            await anext(doubles)
        with raises(StopAsyncIteration):
            await anext(doubles)

    @mark.asyncio
    async def passes_through_early_return_from_async_values():
        async def source():
            try:
                yield 1
                yield 2
                yield 3
            finally:
                yield "done"
                yield "last"

        doubles = MapAsyncIterator(source(), lambda x: x + x)

        assert await anext(doubles) == 2
        assert await anext(doubles) == 4

        # Early return
        await doubles.aclose()

        # Subsequent nexts may yield from finally block
        assert await anext(doubles) == "lastlast"
        with raises(GeneratorExit):
            assert await anext(doubles)

    @mark.asyncio
    async def allows_throwing_errors_through_async_generators():
        async def source():
            yield 1
            yield 2
            yield 3

        doubles = MapAsyncIterator(source(), lambda x: x + x)

        assert await anext(doubles) == 2
        assert await anext(doubles) == 4

        # Throw error
        with raises(RuntimeError) as exc_info:
            await doubles.athrow(RuntimeError("ouch"))

        assert str(exc_info.value) == "ouch"

        with raises(StopAsyncIteration):
            await anext(doubles)
        with raises(StopAsyncIteration):
            await anext(doubles)

    @mark.asyncio
    async def passes_through_caught_errors_through_async_generators():
        async def source():
            try:
                yield 1
                yield 2
                yield 3
            except Exception as e:
                yield e

        doubles = MapAsyncIterator(source(), lambda x: x + x)

        assert await anext(doubles) == 2
        assert await anext(doubles) == 4

        # Throw error
        await doubles.athrow(RuntimeError("ouch"))

        with raises(StopAsyncIteration):
            await anext(doubles)
        with raises(StopAsyncIteration):
            await anext(doubles)

    @mark.asyncio
    async def does_not_normally_map_over_thrown_errors():
        async def source():
            yield "Hello"
            raise RuntimeError("Goodbye")

        doubles = MapAsyncIterator(source(), lambda x: x + x)

        assert await anext(doubles) == "HelloHello"

        with raises(RuntimeError):
            await anext(doubles)

    @mark.asyncio
    async def does_not_normally_map_over_externally_thrown_errors():
        async def source():
            yield "Hello"

        doubles = MapAsyncIterator(source(), lambda x: x + x)

        assert await anext(doubles) == "HelloHello"

        with raises(RuntimeError):
            await doubles.athrow(RuntimeError("Goodbye"))

    @mark.asyncio
    async def maps_over_thrown_errors_if_second_callback_provided():
        async def source():
            yield "Hello"
            raise RuntimeError("Goodbye")

        doubles = MapAsyncIterator(source(), lambda x: x + x, lambda error: error)

        assert await anext(doubles) == "HelloHello"

        result = await anext(doubles)
        assert isinstance(result, RuntimeError)
        assert str(result) == "Goodbye"

        with raises(StopAsyncIteration):
            await anext(doubles)

    @mark.asyncio
    async def can_use_simple_iterator_instead_of_generator():
        async def source():
            yield 1
            yield 2
            yield 3

        class Source:
            def __init__(self):
                self.counter = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                self.counter += 1
                if self.counter > 3:
                    raise StopAsyncIteration
                return self.counter

        for iterator in source, Source:
            doubles = MapAsyncIterator(iterator(), lambda x: x + x)

            await doubles.aclose()

            with raises(StopAsyncIteration):
                await anext(doubles)

            doubles = MapAsyncIterator(iterator(), lambda x: x + x)

            assert await anext(doubles) == 2
            assert await anext(doubles) == 4
            assert await anext(doubles) == 6

            with raises(StopAsyncIteration):
                await anext(doubles)

            doubles = MapAsyncIterator(iterator(), lambda x: x + x)

            assert await anext(doubles) == 2
            assert await anext(doubles) == 4

            # Throw error
            with raises(RuntimeError) as exc_info:
                await doubles.athrow(RuntimeError("ouch"))

            assert str(exc_info.value) == "ouch"

            with raises(StopAsyncIteration):
                await anext(doubles)
            with raises(StopAsyncIteration):
                await anext(doubles)

            await doubles.athrow(RuntimeError("no more ouch"))

            with raises(StopAsyncIteration):
                await anext(doubles)

            await doubles.aclose()

            doubles = MapAsyncIterator(iterator(), lambda x: x + x)

            assert await anext(doubles) == 2
            assert await anext(doubles) == 4

            try:
                raise ValueError("bad")
            except ValueError:
                tb = sys.exc_info()[2]

            # Throw error
            with raises(ValueError):
                await doubles.athrow(ValueError, None, tb)

    @mark.asyncio
    async def stops_async_iteration_on_close():
        async def source():
            yield 1
            await Event().wait()  # Block forever
            yield 2
            yield 3

        singles = source()
        doubles = MapAsyncIterator(singles, lambda x: x * 2)

        result = await anext(doubles)
        assert result == 2

        # Make sure it is blocked
        doubles_future = ensure_future(anext(doubles))
        await sleep(0.05)
        assert not doubles_future.done()

        # Unblock and watch StopAsyncIteration propagate
        await doubles.aclose()
        await sleep(0.05)
        assert doubles_future.done()
        assert isinstance(doubles_future.exception(), StopAsyncIteration)

        with raises(StopAsyncIteration):
            await anext(singles)
