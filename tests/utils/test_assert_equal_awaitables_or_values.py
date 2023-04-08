from pytest import mark, raises

from . import assert_equal_awaitables_or_values


def describe_assert_equal_awaitables_or_values():
    def throws_when_given_unequal_values():
        with raises(AssertionError):
            assert_equal_awaitables_or_values({}, {}, {"test": "test"})

    def does_not_throw_when_given_equal_values():
        test_value = {"test": "test"}
        assert (
            assert_equal_awaitables_or_values(test_value, test_value, test_value)
            == test_value
        )

    @mark.asyncio
    async def does_not_throw_when_given_equal_awaitables():
        async def test_value():
            return {"test": "test"}

        assert (
            await assert_equal_awaitables_or_values(
                test_value(), test_value(), test_value()
            )
            == await test_value()
        )

    @mark.asyncio
    async def throws_when_given_unequal_awaitables():
        async def test_value(value):
            return value

        with raises(AssertionError):
            await assert_equal_awaitables_or_values(
                test_value({}), test_value({}), test_value({"test": "test"})
            )

    @mark.asyncio
    async def throws_when_given_mixture_of_equal_values_and_awaitables():
        async def test_value():
            return {"test": "test"}

        with raises(
            AssertionError,
            match=r"Received an invalid mixture of promises and values\.",
        ):
            await assert_equal_awaitables_or_values(await test_value(), test_value())
