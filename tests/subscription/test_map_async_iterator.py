import sys
from asyncio import Event, ensure_future, sleep

from pytest import mark, raises  # type: ignore

from graphql.subscription.map_async_iterator import MapAsyncIterator


async def anext(iterable):
    """Return the next item from an async iterator."""
    return await iterable.__anext__()


def describe_map_async_iterator():
    @mark.asyncio
    async def maps_over_async_generator():
        async def source():
            yield 1
            yield 2
            yield 3

        doubles = MapAsyncIterator(source(), lambda x: x + x)

        assert await anext(doubles) == 2
        assert await anext(doubles) == 4
        assert await anext(doubles) == 6
        with raises(StopAsyncIteration):
            assert await anext(doubles)

    @mark.asyncio
    async def maps_over_async_iterator():
        items = [1, 2, 3]

        class Iterator:
            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return items.pop(0)
                except IndexError:
                    raise StopAsyncIteration

        doubles = MapAsyncIterator(Iterator(), lambda x: x + x)

        values = [value async for value in doubles]

        assert not items
        assert values == [2, 4, 6]

    @mark.asyncio
    async def compatible_with_async_for():
        async def source():
            yield 1
            yield 2
            yield 3

        doubles = MapAsyncIterator(source(), lambda x: x + x)

        values = [value async for value in doubles]

        assert values == [2, 4, 6]

    @mark.asyncio
    async def maps_over_async_values_with_async_function():
        async def source():
            yield 1
            yield 2
            yield 3

        async def double(x):
            return x + x

        doubles = MapAsyncIterator(source(), double)

        values = [value async for value in doubles]

        assert values == [2, 4, 6]

    @mark.asyncio
    async def allows_returning_early_from_mapped_async_generator():
        async def source():
            yield 1
            yield 2
            yield 3  # pragma: no cover

        doubles = MapAsyncIterator(source(), lambda x: x + x)

        assert await anext(doubles) == 2
        assert await anext(doubles) == 4

        # Early return
        await doubles.aclose()

        # Subsequent next calls
        with raises(StopAsyncIteration):
            await anext(doubles)
        with raises(StopAsyncIteration):
            await anext(doubles)

    @mark.asyncio
    async def allows_returning_early_from_mapped_async_iterator():
        items = [1, 2, 3]

        class Iterator:
            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return items.pop(0)
                except IndexError:  # pragma: no cover
                    raise StopAsyncIteration

        doubles = MapAsyncIterator(Iterator(), lambda x: x + x)

        assert await anext(doubles) == 2
        assert await anext(doubles) == 4

        # Early return
        await doubles.aclose()

        # Subsequent next calls
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
                yield 3  # pragma: no cover
            finally:
                yield "Done"
                yield "Last"

        doubles = MapAsyncIterator(source(), lambda x: x + x)

        assert await anext(doubles) == 2
        assert await anext(doubles) == 4

        # Early return
        await doubles.aclose()

        # Subsequent next calls may yield from finally block
        assert await anext(doubles) == "LastLast"
        with raises(GeneratorExit):
            assert await anext(doubles)

    @mark.asyncio
    async def allows_throwing_errors_through_async_iterators():
        items = [1, 2, 3]

        class Iterator:
            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return items.pop(0)
                except IndexError:  # pragma: no cover
                    raise StopAsyncIteration

        doubles = MapAsyncIterator(Iterator(), lambda x: x + x)

        assert await anext(doubles) == 2
        assert await anext(doubles) == 4

        # Throw error
        with raises(RuntimeError, match="Ouch") as exc_info:
            await doubles.athrow(RuntimeError("Ouch"))

        assert str(exc_info.value) == "Ouch"

        with raises(StopAsyncIteration):
            await anext(doubles)
        with raises(StopAsyncIteration):
            await anext(doubles)

    @mark.asyncio
    async def allows_throwing_errors_with_values_through_async_iterators():
        class Iterator:
            def __aiter__(self):
                return self

            async def __anext__(self):
                return 1

        one = MapAsyncIterator(Iterator(), lambda x: x)

        assert await anext(one) == 1

        # Throw error with value passed separately
        try:
            raise RuntimeError("Ouch")
        except RuntimeError as error:
            with raises(RuntimeError, match="Ouch") as exc_info:
                await one.athrow(error.__class__, error)

            assert exc_info.value is error
            assert exc_info.tb is error.__traceback__

        with raises(StopAsyncIteration):
            await anext(one)

    @mark.asyncio
    async def allows_throwing_errors_with_traceback_through_async_iterators():
        class Iterator:
            def __aiter__(self):
                return self

            async def __anext__(self):
                return 1

        one = MapAsyncIterator(Iterator(), lambda x: x)

        assert await anext(one) == 1

        # Throw error with traceback passed separately
        try:
            raise RuntimeError("Ouch")
        except RuntimeError as error:
            with raises(RuntimeError) as exc_info:
                await one.athrow(error.__class__, None, error.__traceback__)

            assert exc_info.tb and error.__traceback__
            assert exc_info.tb.tb_frame is error.__traceback__.tb_frame

        with raises(StopAsyncIteration):
            await anext(one)

    @mark.asyncio
    async def passes_through_caught_errors_through_async_generators():
        async def source():
            try:
                yield 1
                yield 2
                yield 3  # pragma: no cover
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

        with raises(RuntimeError) as exc_info:
            await anext(doubles)

        assert str(exc_info.value) == "Goodbye"

    @mark.asyncio
    async def does_not_normally_map_over_externally_thrown_errors():
        async def source():
            yield "Hello"

        doubles = MapAsyncIterator(source(), lambda x: x + x)

        assert await anext(doubles) == "HelloHello"

        with raises(RuntimeError) as exc_info:
            await doubles.athrow(RuntimeError("Goodbye"))

        assert str(exc_info.value) == "Goodbye"

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

        def double(x):
            return x + x

        for iterator in source, Source:
            doubles = MapAsyncIterator(iterator(), double)

            await doubles.aclose()

            with raises(StopAsyncIteration):
                await anext(doubles)

            doubles = MapAsyncIterator(iterator(), double)

            assert await anext(doubles) == 2
            assert await anext(doubles) == 4
            assert await anext(doubles) == 6

            with raises(StopAsyncIteration):
                await anext(doubles)

            doubles = MapAsyncIterator(iterator(), double)

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

            doubles = MapAsyncIterator(iterator(), double)

            assert await anext(doubles) == 2
            assert await anext(doubles) == 4

            try:
                raise ValueError("bad")
            except ValueError:
                tb = sys.exc_info()[2]

            # Throw error
            with raises(ValueError):
                await doubles.athrow(ValueError, None, tb)

        await sleep(0)

    @mark.asyncio
    async def stops_async_iteration_on_close():
        async def source():
            yield 1
            await Event().wait()  # Block forever
            yield 2  # pragma: no cover
            yield 3  # pragma: no cover

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

    @mark.asyncio
    async def can_unset_closed_state_of_async_iterator():
        items = [1, 2, 3]

        class Iterator:
            def __init__(self):
                self.is_closed = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.is_closed:
                    raise StopAsyncIteration
                try:
                    return items.pop(0)
                except IndexError:
                    raise StopAsyncIteration

            async def aclose(self):
                self.is_closed = True

        iterator = Iterator()
        doubles = MapAsyncIterator(iterator, lambda x: x + x)

        assert await anext(doubles) == 2
        assert await anext(doubles) == 4
        assert not iterator.is_closed
        await doubles.aclose()
        assert iterator.is_closed
        with raises(StopAsyncIteration):
            await anext(iterator)
        with raises(StopAsyncIteration):
            await anext(doubles)
        assert doubles.is_closed

        iterator.is_closed = False
        doubles.is_closed = False
        assert not doubles.is_closed

        assert await anext(doubles) == 6
        assert not doubles.is_closed
        assert not iterator.is_closed
        with raises(StopAsyncIteration):
            await anext(iterator)
        with raises(StopAsyncIteration):
            await anext(doubles)
        assert not doubles.is_closed
        assert not iterator.is_closed
