from pytest import mark, raises

from graphql.execution import map_async_iterable


try:  # pragma: no cover
    anext
except NameError:  # pragma: no cover (Python < 3.10)
    # noinspection PyShadowingBuiltins
    async def anext(iterator):
        """Return the next item from an async iterator."""
        return await iterator.__anext__()


async def map_doubles(x: int) -> int:
    return x + x


def describe_map_async_iterable():
    @mark.asyncio
    async def inner_is_closed_when_outer_is_closed():
        class Inner:
            def __init__(self):
                self.closed = False

            async def aclose(self):
                self.closed = True

            def __aiter__(self):
                return self

            async def __anext__(self):
                return 1

        inner = Inner()
        outer = map_async_iterable(inner, map_doubles)
        iterator = outer.__aiter__()
        assert await anext(iterator) == 2
        assert not inner.closed
        await outer.aclose()
        assert inner.closed

    @mark.asyncio
    async def inner_is_closed_on_callback_error():
        class Inner:
            def __init__(self):
                self.closed = False

            async def aclose(self):
                self.closed = True

            def __aiter__(self):
                return self

            async def __anext__(self):
                return 1

        async def callback(v):
            raise RuntimeError()

        inner = Inner()
        outer = map_async_iterable(inner, callback)
        with raises(RuntimeError):
            await anext(outer)
        assert inner.closed

    @mark.asyncio
    async def test_inner_exits_on_callback_error():
        inner_exit = False

        async def inner():
            nonlocal inner_exit
            try:
                while True:
                    yield 1
            except GeneratorExit:
                inner_exit = True

        async def callback(v):
            raise RuntimeError

        outer = map_async_iterable(inner(), callback)
        with raises(RuntimeError):
            await anext(outer)
        assert inner_exit

    @mark.asyncio
    async def inner_has_no_close_method_when_outer_is_closed():
        class Inner:
            def __aiter__(self):
                return self

            async def __anext__(self):
                return 1

        outer = map_async_iterable(Inner(), map_doubles)
        iterator = outer.__aiter__()
        assert await anext(iterator) == 2
        await outer.aclose()

    @mark.asyncio
    async def inner_has_no_close_method_on_callback_error():
        class Inner:
            def __aiter__(self):
                return self

            async def __anext__(self):
                return 1

        async def callback(v):
            raise RuntimeError()

        outer = map_async_iterable(Inner(), callback)
        with raises(RuntimeError):
            await anext(outer)
