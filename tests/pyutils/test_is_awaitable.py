import asyncio
from collections.abc import AsyncIterable
from inspect import isawaitable
from sys import version_info as python_version
from typing import Any

import pytest

from graphql.pyutils import is_async_iterable, is_awaitable

pytestmark = pytest.mark.anyio


def isasynciterable(value: Any) -> bool:
    """Helper function to check if an object is an async iterable."""
    return isinstance(value, AsyncIterable)


def describe_is_awaitable():
    def declines_the_none_value():
        assert not isawaitable(None)
        assert not is_awaitable(None)

    def declines_a_boolean_value():
        assert not isawaitable(True)
        assert not is_awaitable(True)

    def declines_an_int_value():
        assert not is_awaitable(42)

    def declines_a_string_value():
        assert not isawaitable("some_string")
        assert not is_awaitable("some_string")

    def declines_a_dict_value():
        assert not isawaitable({})
        assert not is_awaitable({})

    def declines_an_object_instance():
        assert not isawaitable(object())
        assert not is_awaitable(object())

    def declines_the_type_class():
        assert not isawaitable(type)
        assert not is_awaitable(type)

    def declines_a_lambda_function():
        assert not isawaitable(lambda: True)  # pragma: no cover
        assert not is_awaitable(lambda: True)  # pragma: no cover

    def declines_a_normal_function():
        def some_function():
            return True

        assert not isawaitable(some_function())
        assert not is_awaitable(some_function)

    def declines_a_normal_generator_function():
        def some_generator():
            yield True  # pragma: no cover

        assert not isawaitable(some_generator)
        assert not is_awaitable(some_generator)

    def declines_a_normal_generator_object():
        def some_generator():
            yield True  # pragma: no cover

        assert not isawaitable(some_generator())
        assert not is_awaitable(some_generator())

    def declines_a_coroutine_function():
        async def some_async_function():
            return True  # pragma: no cover

        assert not isawaitable(some_async_function)
        assert not is_awaitable(some_async_function)

    async def recognizes_a_coroutine_object():
        async def some_async_function():
            return True

        some_coroutine = some_async_function()

        assert isawaitable(some_coroutine)
        assert is_awaitable(some_coroutine)

        assert await some_coroutine is True

    @pytest.mark.filterwarnings("ignore::Warning")  # Deprecation and Runtime warnings
    @pytest.mark.skipif(
        python_version >= (3, 11),
        reason="Generator-based coroutines not supported any more since Python 3.11",
    )
    @pytest.mark.parametrize("anyio_backend", ["asyncio"], indirect=True)
    async def recognizes_an_old_style_coroutine():  # pragma: no cover
        @asyncio.coroutine  # type: ignore
        def some_function():
            yield True

        some_old_style_coroutine = some_function()
        assert is_awaitable(some_old_style_coroutine)
        assert is_awaitable(some_old_style_coroutine)

    async def recognizes_a_future_object():
        async def some_async_function():
            return True

        some_coroutine = some_async_function()
        some_future = asyncio.ensure_future(some_coroutine)

        assert is_awaitable(some_future)
        assert is_awaitable(some_future)

        assert await some_future is True

    async def declines_an_async_generator():
        async def some_async_generator_function():
            yield True

        some_async_generator = some_async_generator_function()

        assert not isawaitable(some_async_generator)
        assert not is_awaitable(some_async_generator)

        assert await some_async_generator.__anext__() is True


def describe_is_async_iterable():
    def declines_the_none_value():
        assert not isasynciterable(None)
        assert not is_async_iterable(None)

    def declines_a_boolean_value():
        assert not isasynciterable(True)
        assert not is_async_iterable(True)

    def declines_an_int_value():
        assert not isasynciterable(42)
        assert not is_async_iterable(42)

    def declines_a_string_value():
        assert not isasynciterable("some_string")
        assert not is_async_iterable("some_string")

    def declines_a_dict_value():
        assert not isasynciterable({})
        assert not is_async_iterable({})

    def declines_an_object_instance():
        assert not isasynciterable(object())
        assert not is_async_iterable(object())

    def declines_the_type_class():
        assert not isasynciterable(type)
        assert not is_async_iterable(type)

    def declines_a_lambda_function():
        assert not isasynciterable(lambda: True)  # pragma: no cover
        assert not is_async_iterable(lambda: True)  # pragma: no cover

    def declines_a_function():
        def some_function():
            return True

        assert not isasynciterable(some_function())
        assert not is_async_iterable(some_function)

    def declines_a_normal_iterable():
        normal_iterable = [1, 2, 3]

        assert not isasynciterable(normal_iterable)
        assert not is_async_iterable(normal_iterable)

        normal_iterator = iter(normal_iterable)

        assert not isasynciterable(normal_iterator)
        assert not is_async_iterable(normal_iterator)

    async def recognizes_an_async_generator():
        async def some_async_generator_function():
            yield True  # pragma: no cover

        some_async_generator = some_async_generator_function()

        assert isasynciterable(some_async_generator)
        assert is_async_iterable(some_async_generator)

    def recognizes_a_custom_async_iterable():
        class SomeAsyncIterator:
            def __aiter__(self):
                return self  # pragma: no cover

            async def __anext__(self):
                raise StopAsyncIteration  # pragma: no cover

        class SomeAsyncIterable:
            def __aiter__(self):
                return SomeAsyncIterator()  # pragma: no cover

        some_async_iterable = SomeAsyncIterable()

        assert isasynciterable(some_async_iterable)
        assert is_async_iterable(some_async_iterable)
