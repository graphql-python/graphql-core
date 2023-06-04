from pytest import mark, raises

from graphql.execution import map_async_iterable


try:  # pragma: no cover
    anext
except NameError:  # pragma: no cover (Python < 3.10)
    # noinspection PyShadowingBuiltins
    async def anext(iterator):
        """Return the next item from an async iterator."""
        return await iterator.__anext__()


async def double(x: int) -> int:
    """Test callback that doubles the input value."""
    return x + x


async def throw(_x: int) -> int:
    """Test callback that raises a RuntimeError."""
    raise RuntimeError("Ouch")


def describe_map_async_iterable():
    @mark.asyncio
    async def maps_over_async_generator():
        async def source():
            yield 1
            yield 2
            yield 3

        doubles = map_async_iterable(source(), double)

        assert await anext(doubles) == 2
        assert await anext(doubles) == 4
        assert await anext(doubles) == 6
        with raises(StopAsyncIteration):
            assert await anext(doubles)

    @mark.asyncio
    async def maps_over_async_iterable():
        items = [1, 2, 3]

        class Iterable:
            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return items.pop(0)
                except IndexError:
                    raise StopAsyncIteration

        doubles = map_async_iterable(Iterable(), double)

        values = [value async for value in doubles]

        assert not items
        assert values == [2, 4, 6]

    @mark.asyncio
    async def compatible_with_async_for():
        async def source():
            yield 1
            yield 2
            yield 3

        doubles = map_async_iterable(source(), double)

        values = [value async for value in doubles]

        assert values == [2, 4, 6]

    @mark.asyncio
    async def allows_returning_early_from_mapped_async_generator():
        async def source():
            yield 1
            yield 2
            yield 3  # pragma: no cover

        doubles = map_async_iterable(source(), double)

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
    async def allows_returning_early_from_mapped_async_iterable():
        items = [1, 2, 3]

        class Iterable:
            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return items.pop(0)
                except IndexError:  # pragma: no cover
                    raise StopAsyncIteration

        doubles = map_async_iterable(Iterable(), double)

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
    async def allows_throwing_errors_through_async_iterable():
        items = [1, 2, 3]

        class Iterable:
            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return items.pop(0)
                except IndexError:  # pragma: no cover
                    raise StopAsyncIteration

        doubles = map_async_iterable(Iterable(), double)

        assert await anext(doubles) == 2
        assert await anext(doubles) == 4

        # Throw error
        message = "allows throwing errors when mapping async iterable"
        with raises(RuntimeError) as exc_info:
            await doubles.athrow(RuntimeError(message))

        assert str(exc_info.value) == message

        with raises(StopAsyncIteration):
            await anext(doubles)
        with raises(StopAsyncIteration):
            await anext(doubles)

    @mark.asyncio
    async def allows_throwing_errors_with_values_through_async_iterables():
        class Iterable:
            def __aiter__(self):
                return self

            async def __anext__(self):
                return 1

        one = map_async_iterable(Iterable(), double)

        assert await anext(one) == 2

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
    async def allows_throwing_errors_with_traceback_through_async_iterables():
        class Iterable:
            def __aiter__(self):
                return self

            async def __anext__(self):
                return 1

        one = map_async_iterable(Iterable(), double)

        assert await anext(one) == 2

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
    async def does_not_map_over_thrown_errors():
        async def source():
            yield 1
            raise RuntimeError("Goodbye")

        doubles = map_async_iterable(source(), double)

        assert await anext(doubles) == 2

        with raises(RuntimeError) as exc_info:
            await anext(doubles)

        assert str(exc_info.value) == "Goodbye"

    @mark.asyncio
    async def does_not_map_over_externally_thrown_errors():
        async def source():
            yield 1

        doubles = map_async_iterable(source(), double)

        assert await anext(doubles) == 2

        with raises(RuntimeError) as exc_info:
            await doubles.athrow(RuntimeError("Goodbye"))

        assert str(exc_info.value) == "Goodbye"

    @mark.asyncio
    async def iterable_is_closed_when_mapped_iterable_is_closed():
        class Iterable:
            def __init__(self):
                self.closed = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                return 1

            async def aclose(self):
                self.closed = True

        iterable = Iterable()
        doubles = map_async_iterable(iterable, double)
        assert await anext(doubles) == 2
        assert not iterable.closed
        await doubles.aclose()
        assert iterable.closed
        with raises(StopAsyncIteration):
            await anext(doubles)

    @mark.asyncio
    async def iterable_is_closed_on_callback_error():
        class Iterable:
            def __init__(self):
                self.closed = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                return 1

            async def aclose(self):
                self.closed = True

        iterable = Iterable()
        doubles = map_async_iterable(iterable, throw)
        with raises(RuntimeError, match="Ouch"):
            await anext(doubles)
        assert iterable.closed
        with raises(StopAsyncIteration):
            await anext(doubles)

    @mark.asyncio
    async def iterable_exits_on_callback_error():
        exited = False

        async def iterable():
            nonlocal exited
            try:
                while True:
                    yield 1
            except GeneratorExit:
                exited = True

        doubles = map_async_iterable(iterable(), throw)
        with raises(RuntimeError, match="Ouch"):
            await anext(doubles)
        assert exited
        with raises(StopAsyncIteration):
            await anext(doubles)

    @mark.asyncio
    async def mapped_iterable_is_closed_when_iterable_cannot_be_closed():
        class Iterable:
            def __aiter__(self):
                return self

            async def __anext__(self):
                return 1

        doubles = map_async_iterable(Iterable(), double)
        assert await anext(doubles) == 2
        await doubles.aclose()
        with raises(StopAsyncIteration):
            await anext(doubles)

    @mark.asyncio
    async def ignores_that_iterable_cannot_be_closed_on_callback_error():
        class Iterable:
            def __aiter__(self):
                return self

            async def __anext__(self):
                return 1

        doubles = map_async_iterable(Iterable(), throw)
        with raises(RuntimeError, match="Ouch"):
            await anext(doubles)
        with raises(StopAsyncIteration):
            await anext(doubles)
