import platform
import sys
from asyncio import CancelledError, Event, ensure_future, sleep

from pytest import mark, raises

from graphql.execution import map_async_iterable


is_pypy = platform.python_implementation() == "PyPy"

try:  # pragma: no cover
    anext
except NameError:  # pragma: no cover (Python < 3.10)
    # noinspection PyShadowingBuiltins
    async def anext(iterator):
        """Return the next item from an async iterator."""
        return await iterator.__anext__()


async def map_single(x):
    return x


async def map_doubles(x):
    return x + x


def describe_map_async_iterable():
    @mark.asyncio
    async def maps_over_async_generator():
        async def source():
            yield 1
            yield 2
            yield 3

        doubles = map_async_iterable(source(), map_doubles)

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

        doubles = map_async_iterable(Iterable(), map_doubles)

        values = [value async for value in doubles]

        assert not items
        assert values == [2, 4, 6]

    @mark.asyncio
    async def compatible_with_async_for():
        async def source():
            yield 1
            yield 2
            yield 3

        doubles = map_async_iterable(source(), map_doubles)

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

        doubles = map_async_iterable(source(), double)

        values = [value async for value in doubles]

        assert values == [2, 4, 6]

    @mark.asyncio
    async def allows_returning_early_from_mapped_async_generator():
        async def source():
            yield 1
            yield 2
            yield 3  # pragma: no cover

        doubles = map_async_iterable(source(), map_doubles)

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

        doubles = map_async_iterable(Iterable(), map_doubles)

        assert await anext(doubles) == 2
        assert await anext(doubles) == 4

        # Early return
        await doubles.aclose()

        # Subsequent next calls
        with raises(StopAsyncIteration):
            await anext(doubles)
        with raises(StopAsyncIteration):
            await anext(doubles)

    # async iterators must not yield after aclose() is called
    @mark.asyncio
    async def ignored_generator_exit():
        async def source():
            try:
                yield 1
                yield 2
                yield 3  # pragma: no cover
            finally:
                yield "Done"
                yield "Last"  # pragma: no cover

        doubles = map_async_iterable(source(), map_doubles)

        assert await anext(doubles) == 2
        assert await anext(doubles) == 4

        with raises(RuntimeError) as exc_info:
            await doubles.aclose()
        assert str(exc_info.value) == "async generator ignored GeneratorExit"

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

        doubles = map_async_iterable(Iterable(), map_doubles)

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

        one = map_async_iterable(Iterable(), map_single)

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
    async def allows_throwing_errors_with_traceback_through_async_iterables():
        class Iterable:
            def __aiter__(self):
                return self

            async def __anext__(self):
                return 1

        one = map_async_iterable(Iterable(), map_single)

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

        doubles = map_async_iterable(source(), map_doubles)

        assert await anext(doubles) == 2
        assert await anext(doubles) == 4

        # Throw error
        with raises(RuntimeError):
            await doubles.athrow(RuntimeError("ouch"))

    @mark.asyncio
    async def does_not_normally_map_over_thrown_errors():
        async def source():
            yield "Hello"
            raise RuntimeError("Goodbye")

        doubles = map_async_iterable(source(), map_doubles)

        assert await anext(doubles) == "HelloHello"

        with raises(RuntimeError) as exc_info:
            await anext(doubles)

        assert str(exc_info.value) == "Goodbye"

    @mark.asyncio
    async def does_not_normally_map_over_externally_thrown_errors():
        async def source():
            yield "Hello"

        doubles = map_async_iterable(source(), map_doubles)

        assert await anext(doubles) == "HelloHello"

        with raises(RuntimeError) as exc_info:
            await doubles.athrow(RuntimeError("Goodbye"))

        assert str(exc_info.value) == "Goodbye"

    @mark.asyncio
    async def can_use_simple_iterable_instead_of_generator():
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

        async def double(x):
            return x + x

        for iterable in source, Source:
            doubles = map_async_iterable(iterable(), double)

            await doubles.aclose()

            with raises(StopAsyncIteration):
                await anext(doubles)

            doubles = map_async_iterable(iterable(), double)

            assert await anext(doubles) == 2
            assert await anext(doubles) == 4
            assert await anext(doubles) == 6

            with raises(StopAsyncIteration):
                await anext(doubles)

            doubles = map_async_iterable(iterable(), double)

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

            # no more exceptions should be thrown
            if is_pypy:
                # need to investigate why this is needed with PyPy
                await doubles.aclose()  # pragma: no cover
            await doubles.athrow(RuntimeError("no more ouch"))

            with raises(StopAsyncIteration):
                await anext(doubles)

            await doubles.aclose()

            doubles = map_async_iterable(iterable(), double)

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

        async def double(x):
            return x * 2

        doubles = map_async_iterable(singles, double)

        result = await anext(doubles)
        assert result == 2

        # Make sure it is blocked
        doubles_future = ensure_future(anext(doubles))
        await sleep(0.05)
        assert not doubles_future.done()

        # with python 3.8 and higher, close() cannot be used to unblock a generator.
        # instead, the task should be killed.  AsyncGenerators are not re-entrant.
        if sys.version_info[:2] >= (3, 8):
            with raises(RuntimeError):
                await doubles.aclose()
            doubles_future.cancel()
            await sleep(0.05)
            assert doubles_future.done()
            with raises(CancelledError):
                doubles_future.exception()

        else:
            # old behaviour, where aclose() could unblock a Task
            # Unblock and watch StopAsyncIteration propagate
            await doubles.aclose()
            await sleep(0.05)
            assert doubles_future.done()
            assert isinstance(doubles_future.exception(), StopAsyncIteration)

        with raises(StopAsyncIteration):
            await anext(singles)

    @mark.asyncio
    async def can_cancel_async_iterable_while_waiting():
        class Iterable:
            def __init__(self):
                self.is_closed = False
                self.value = 1

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    await sleep(0.5)
                    return self.value  # pragma: no cover
                except CancelledError:
                    self.value = -1
                    raise

            async def aclose(self):
                self.is_closed = True

        iterable = Iterable()
        doubles = map_async_iterable(iterable, map_doubles)  # pragma: no cover exit
        cancelled = False

        async def iterator_task():
            nonlocal cancelled
            try:
                async for _ in doubles:
                    assert False  # pragma: no cover
            except CancelledError:
                cancelled = True

        task = ensure_future(iterator_task())
        await sleep(0.05)
        assert not cancelled
        assert iterable.value == 1
        assert not iterable.is_closed
        task.cancel()
        await sleep(0.05)
        assert cancelled
        assert iterable.value == -1
        assert iterable.is_closed
