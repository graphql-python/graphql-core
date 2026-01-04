import pytest

from graphql.execution import map_async_iterable

pytestmark = pytest.mark.anyio


async def double(x: int) -> int:
    """Test callback that doubles the input value."""
    return x + x


async def throw(_x: int) -> int:
    """Test callback that raises a RuntimeError."""
    raise RuntimeError("Ouch")


def describe_map_async_iterable():
    async def maps_over_async_generator():
        async def source():
            yield 1
            yield 2
            yield 3

        doubles = map_async_iterable(source(), double)

        assert await anext(doubles) == 2
        assert await anext(doubles) == 4
        assert await anext(doubles) == 6
        with pytest.raises(StopAsyncIteration):
            assert await anext(doubles)

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

    async def compatible_with_async_for():
        async def source():
            yield 1
            yield 2
            yield 3

        doubles = map_async_iterable(source(), double)

        values = [value async for value in doubles]

        assert values == [2, 4, 6]

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
        with pytest.raises(StopAsyncIteration):
            await anext(doubles)
        with pytest.raises(StopAsyncIteration):
            await anext(doubles)

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
        with pytest.raises(StopAsyncIteration):
            await anext(doubles)
        with pytest.raises(StopAsyncIteration):
            await anext(doubles)

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
        with pytest.raises(RuntimeError) as exc_info:
            await doubles.athrow(RuntimeError(message))

        assert str(exc_info.value) == message

        with pytest.raises(StopAsyncIteration):
            await anext(doubles)
        with pytest.raises(StopAsyncIteration):
            await anext(doubles)

    async def allows_throwing_errors_with_traceback_through_async_iterables():
        class Iterable:
            def __aiter__(self):
                return self

            async def __anext__(self):
                return 1

        one = map_async_iterable(Iterable(), double)

        assert await anext(one) == 2

        try:
            raise RuntimeError("Ouch")
        except RuntimeError as error:
            with pytest.raises(RuntimeError, match="Ouch") as exc_info:
                await one.athrow(error)

            assert exc_info.value is error  # noqa: PT017
            assert exc_info.tb
            assert error.__traceback__  # noqa: PT017
            assert exc_info.tb is error.__traceback__  # noqa: PT017

        with pytest.raises(StopAsyncIteration):
            await anext(one)

    async def does_not_map_over_thrown_errors():
        async def source():
            yield 1
            raise RuntimeError("Goodbye")

        doubles = map_async_iterable(source(), double)

        assert await anext(doubles) == 2

        with pytest.raises(RuntimeError) as exc_info:
            await anext(doubles)

        assert str(exc_info.value) == "Goodbye"

    async def does_not_map_over_externally_thrown_errors():
        async def source():
            yield 1

        doubles = map_async_iterable(source(), double)

        assert await anext(doubles) == 2

        with pytest.raises(RuntimeError) as exc_info:
            await doubles.athrow(RuntimeError("Goodbye"))

        assert str(exc_info.value) == "Goodbye"

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
        with pytest.raises(StopAsyncIteration):
            await anext(doubles)

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
        with pytest.raises(RuntimeError, match="Ouch"):
            await anext(doubles)
        assert iterable.closed
        with pytest.raises(StopAsyncIteration):
            await anext(doubles)

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
        with pytest.raises(RuntimeError, match="Ouch"):
            await anext(doubles)
        assert exited
        with pytest.raises(StopAsyncIteration):
            await anext(doubles)

    async def mapped_iterable_is_closed_when_iterable_cannot_be_closed():
        class Iterable:
            def __aiter__(self):
                return self

            async def __anext__(self):
                return 1

        doubles = map_async_iterable(Iterable(), double)
        assert await anext(doubles) == 2
        await doubles.aclose()
        with pytest.raises(StopAsyncIteration):
            await anext(doubles)

    async def ignores_that_iterable_cannot_be_closed_on_callback_error():
        class Iterable:
            def __aiter__(self):
                return self

            async def __anext__(self):
                return 1

        doubles = map_async_iterable(Iterable(), throw)
        with pytest.raises(RuntimeError, match="Ouch"):
            await anext(doubles)
        with pytest.raises(StopAsyncIteration):
            await anext(doubles)
