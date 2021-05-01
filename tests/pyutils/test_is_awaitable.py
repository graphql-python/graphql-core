import asyncio
from inspect import isawaitable

from pytest import mark

from graphql.pyutils import is_awaitable


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
        async def some_coroutine():
            return True  # pragma: no cover

        assert not isawaitable(some_coroutine)
        assert not is_awaitable(some_coroutine)

    @mark.asyncio
    @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
    async def recognizes_a_coroutine_object():
        async def some_coroutine():
            return False  # pragma: no cover

        assert isawaitable(some_coroutine())
        assert is_awaitable(some_coroutine())

    @mark.filterwarnings("ignore::Warning")  # Deprecation and Runtime
    def recognizes_an_old_style_coroutine():
        @asyncio.coroutine
        def some_old_style_coroutine():
            yield False  # pragma: no cover

        assert is_awaitable(some_old_style_coroutine())
        assert is_awaitable(some_old_style_coroutine())

    @mark.asyncio
    @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
    async def recognizes_a_future_object():
        async def some_coroutine():
            return False  # pragma: no cover

        some_future = asyncio.ensure_future(some_coroutine())

        assert is_awaitable(some_future)
        assert is_awaitable(some_future)

    @mark.asyncio
    @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
    def declines_an_async_generator():
        async def some_async_generator():
            yield True  # pragma: no cover

        assert not isawaitable(some_async_generator())
        assert not is_awaitable(some_async_generator())
