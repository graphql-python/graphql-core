from pytest import mark, raises

from graphql.error import GraphQLError
from graphql.type import assert_name, assert_enum_value_name


def describe_assert_name():
    def pass_through_valid_name():
        assert assert_name("_ValidName123") == "_ValidName123"

    def throws_for_non_strings():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            assert_name({})  # type: ignore
        msg = str(exc_info.value)
        assert msg == "Expected name to be a string."

    def throws_on_empty_strings():
        with raises(GraphQLError) as exc_info:
            assert_name("")
        msg = str(exc_info.value)
        assert msg == "Expected name to be a non-empty string."

    def throws_for_names_with_invalid_characters():
        with raises(GraphQLError) as exc_info:
            assert_name(">--()-->")
        msg = str(exc_info.value)
        assert msg == "Names must only contain [_a-zA-Z0-9] but '>--()-->' does not."

    def throws_for_names_starting_with_invalid_characters():
        with raises(GraphQLError) as exc_info:
            assert_name("42MeaningsOfLife")
        msg = str(exc_info.value)
        assert msg == (
            "Names must start with [_a-zA-Z] but '42MeaningsOfLife' does not."
        )


def describe_assert_enum_value_name():
    def pass_through_valid_name():
        assert assert_enum_value_name("_ValidName123") == "_ValidName123"

    def throws_for_non_strings():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            assert_enum_value_name({})  # type: ignore
        msg = str(exc_info.value)
        assert msg == "Expected name to be a string."

    def throws_on_empty_strings():
        with raises(GraphQLError) as exc_info:
            assert_enum_value_name("")
        msg = str(exc_info.value)
        assert msg == "Expected name to be a non-empty string."

    def throws_for_names_with_invalid_characters():
        with raises(GraphQLError) as exc_info:
            assert_enum_value_name(">--()-->")
        msg = str(exc_info.value)
        assert msg == "Names must only contain [_a-zA-Z0-9] but '>--()-->' does not."

    def throws_for_names_starting_with_invalid_characters():
        with raises(GraphQLError) as exc_info:
            assert_enum_value_name("42MeaningsOfLife")
        msg = str(exc_info.value)
        assert msg == (
            "Names must start with [_a-zA-Z] but '42MeaningsOfLife' does not."
        )

    @mark.parametrize("name", ("true", "false", "null"))
    def throws_for_restricted_names(name):
        with raises(GraphQLError) as exc_info:
            assert_enum_value_name(name)
        msg = str(exc_info.value)
        assert msg == (f"Enum values cannot be named: {name}.")
