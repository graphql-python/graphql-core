from functools import reduce

from pytest import mark

from graphql.pyutils import async_reduce, is_awaitable


def describe_async_reduce():
    def works_like_reduce_for_lists_of_ints():
        initial_value = -15

        def callback(accumulator, current_value):
            return accumulator + current_value

        values = range(7, 13)
        result = async_reduce(callback, values, initial_value)
        assert result == 42
        assert result == reduce(callback, values, initial_value)

    @mark.asyncio
    async def works_with_sync_values_and_sync_initial_value():
        def callback(accumulator, current_value):
            return accumulator + "-" + current_value

        values = ["bar", "baz"]
        result = async_reduce(callback, values, "foo")
        assert not is_awaitable(result)
        assert result == "foo-bar-baz"

    @mark.asyncio
    async def works_with_async_initial_value():
        async def async_initial_value():
            return "foo"

        def callback(accumulator, current_value):
            return accumulator + "-" + current_value

        values = ["bar", "baz"]
        result = async_reduce(callback, values, async_initial_value())
        assert is_awaitable(result)
        assert await result == "foo-bar-baz"

    @mark.asyncio
    async def works_with_async_callback():
        async def async_callback(accumulator, current_value):
            return accumulator + "-" + current_value

        values = ["bar", "baz"]
        result = async_reduce(async_callback, values, "foo")
        assert is_awaitable(result)
        assert await result == "foo-bar-baz"

    @mark.asyncio
    async def works_with_async_callback_and_async_initial_value():
        async def async_initial_value():
            return 1 / 8

        async def async_callback(accumulator, current_value):
            return accumulator * current_value

        result = async_reduce(async_callback, range(6, 9), async_initial_value())
        assert is_awaitable(result)
        assert await result == 42
