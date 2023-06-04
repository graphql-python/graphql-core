from typing import AsyncGenerator

from pytest import mark, raises

from graphql.execution import flatten_async_iterable


try:  # pragma: no cover
    anext
except NameError:  # pragma: no cover (Python < 3.10)
    # noinspection PyShadowingBuiltins
    async def anext(iterator):
        """Return the next item from an async iterator."""
        return await iterator.__anext__()


def describe_flatten_async_iterable():
    @mark.asyncio
    async def flattens_nested_async_generators():
        async def source():
            async def nested1() -> AsyncGenerator[float, None]:
                yield 1.1
                yield 1.2

            async def nested2() -> AsyncGenerator[float, None]:
                yield 2.1
                yield 2.2

            yield nested1()
            yield nested2()

        doubles = flatten_async_iterable(source())

        result = [x async for x in doubles]

        assert result == [1.1, 1.2, 2.1, 2.2]

    @mark.asyncio
    async def allows_returning_early_from_a_nested_async_generator():
        async def source():
            async def nested1() -> AsyncGenerator[float, None]:
                yield 1.1
                yield 1.2

            async def nested2() -> AsyncGenerator[float, None]:
                yield 2.1
                # Not reachable, early return
                yield 2.2  # pragma: no cover

            # Not reachable, early return
            async def nested3() -> AsyncGenerator[float, None]:
                yield 3.1  # pragma: no cover
                yield 3.2  # pragma: no cover

            yield nested1()
            yield nested2()
            yield nested3()  # pragma: no cover

        doubles = flatten_async_iterable(source())

        assert await anext(doubles) == 1.1
        assert await anext(doubles) == 1.2
        assert await anext(doubles) == 2.1

        # early return
        try:
            await doubles.aclose()
        except RuntimeError:  # Python < 3.8
            pass

        # subsequent anext calls
        with raises(StopAsyncIteration):
            assert await anext(doubles)
        with raises(StopAsyncIteration):
            assert await anext(doubles)

    @mark.asyncio
    async def allows_throwing_errors_from_a_nested_async_generator():
        async def source():
            async def nested1() -> AsyncGenerator[float, None]:
                yield 1.1
                yield 1.2

            async def nested2() -> AsyncGenerator[float, None]:
                yield 2.1
                # Not reachable, early return
                yield 2.2  # pragma: no cover

            # Not reachable, early return
            async def nested3() -> AsyncGenerator[float, None]:
                yield 3.1  # pragma: no cover
                yield 3.2  # pragma: no cover

            yield nested1()
            yield nested2()
            yield nested3()  # pragma: no cover

        doubles = flatten_async_iterable(source())

        assert await anext(doubles) == 1.1
        assert await anext(doubles) == 1.2
        assert await anext(doubles) == 2.1

        # throw error
        with raises(RuntimeError, match="ouch"):
            await doubles.athrow(RuntimeError, "ouch")

    @mark.asyncio
    async def completely_yields_sub_iterables_even_when_anext_called_in_parallel():
        async def source():
            async def nested1() -> AsyncGenerator[float, None]:
                yield 1.1
                yield 1.2

            async def nested2() -> AsyncGenerator[float, None]:
                yield 2.1
                yield 2.2

            yield nested1()
            yield nested2()

        doubles = flatten_async_iterable(source())

        anext1 = anext(doubles)
        anext2 = anext(doubles)
        assert await anext1 == 1.1
        assert await anext2 == 1.2
        assert await anext(doubles) == 2.1
        assert await anext(doubles) == 2.2
        with raises(StopAsyncIteration):
            assert await anext(doubles)

    @mark.asyncio
    async def closes_nested_async_iterators():
        closed = []

        class Source:
            def __init__(self):
                self.counter = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.counter == 2:
                    raise StopAsyncIteration
                self.counter += 1
                return Nested(self.counter)

            async def aclose(self):
                nonlocal closed
                closed.append(self.counter)

        class Nested:
            def __init__(self, value):
                self.value = value
                self.counter = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.counter == 2:
                    raise StopAsyncIteration
                self.counter += 1
                return self.value + self.counter / 10

            async def aclose(self):
                nonlocal closed
                closed.append(self.value + self.counter / 10)

        doubles = flatten_async_iterable(Source())

        result = [x async for x in doubles]

        assert result == [1.1, 1.2, 2.1, 2.2]

        assert closed == [1.2, 2.2, 2]

    @mark.asyncio
    async def works_with_nested_async_iterators_that_have_no_close_method():
        class Source:
            def __init__(self):
                self.counter = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.counter == 2:
                    raise StopAsyncIteration
                self.counter += 1
                return Nested(self.counter)

        class Nested:
            def __init__(self, value):
                self.value = value
                self.counter = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.counter == 2:
                    raise StopAsyncIteration
                self.counter += 1
                return self.value + self.counter / 10

        doubles = flatten_async_iterable(Source())

        result = [x async for x in doubles]

        assert result == [1.1, 1.2, 2.1, 2.2]
