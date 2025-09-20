import pytest

from . import assert_equal_awaitables_or_values

pytestmark = pytest.mark.anyio


def describe_assert_equal_awaitables_or_values():
    def throws_when_given_unequal_values():
        with pytest.raises(AssertionError):
            assert_equal_awaitables_or_values({}, {}, {"test": "test"})

    def does_not_throw_when_given_equal_values():
        test_value = {"test": "test"}
        assert (
            assert_equal_awaitables_or_values(test_value, test_value, test_value)
            == test_value
        )

    async def does_not_throw_when_given_equal_awaitables():
        async def test_value():
            return {"test": "test"}

        assert (
            await assert_equal_awaitables_or_values(
                test_value(), test_value(), test_value()
            )
            == await test_value()
        )

    async def throws_when_given_unequal_awaitables():
        async def test_value(value):
            return value

        with pytest.raises(AssertionError):
            await assert_equal_awaitables_or_values(
                test_value({}), test_value({}), test_value({"test": "test"})
            )

    async def throws_when_given_mixture_of_equal_values_and_awaitables():
        async def test_value():
            return {"test": "test"}

        value1 = await test_value()
        value2 = test_value()

        with pytest.raises(
            AssertionError,
            match=r"Received an invalid mixture of promises and values\.",
        ):
            await assert_equal_awaitables_or_values(value1, value2)

        assert await value2 == value1
