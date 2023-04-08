from pytest import raises

from . import assert_matching_values


def describe_assert_matching_values():
    def throws_when_given_unequal_values():
        with raises(AssertionError):
            assert_matching_values({}, {}, {"test": "test"})

    def does_not_throw_when_given_equal_values():
        test_value = {"test": "test"}
        assert assert_matching_values(test_value, test_value, test_value) == test_value
