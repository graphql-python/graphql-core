from pytest import mark, raises

from graphql.execution import map_async_iterable


async def map_doubles(x):
    return x + x


def describe_map_async_iterable():
    @mark.asyncio
    async def test_inner_close_called():
        """
        Test that a custom iterator with aclose() gets an aclose() call
        when outer is closed
        """

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
        it = outer.__aiter__()
        assert await it.__anext__() == 2
        assert not inner.closed
        await outer.aclose()
        assert inner.closed

    @mark.asyncio
    async def test_inner_close_called_on_callback_err():
        """
        Test that a custom iterator with aclose() gets an aclose() call
        when the callback errors and the outer iterator aborts.
        """

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
            async for _ in outer:
                pass
        assert inner.closed

    @mark.asyncio
    async def test_inner_exit_on_callback_err():
        """
        Test that a custom iterator with aclose() gets an aclose() call
        when the callback errors and the outer iterator aborts.
        """

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
            async for _ in outer:
                pass
        assert inner_exit
