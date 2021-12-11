from pytest import raises

from graphql.error import GraphQLError
from graphql.utilities import assert_valid_name


def describe_assert_valid_name():
    def pass_through_valid_name():
        assert assert_valid_name("_ValidName123") == "_ValidName123"

    def throws_for_use_of_leading_double_underscore():
        with raises(GraphQLError) as exc_info:
            assert assert_valid_name("__bad")
        msg = exc_info.value.message
        assert msg == (
            "Name '__bad' must not begin with '__',"
            " which is reserved by GraphQL introspection."
        )

    def throws_for_non_strings():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            assert_valid_name({})  # type: ignore
        msg = str(exc_info.value)
        assert msg == "Expected name to be a string."

    def throws_on_empty_strings():
        with raises(GraphQLError) as exc_info:
            assert_valid_name("")
        msg = str(exc_info.value)
        assert msg == "Expected name to be a non-empty string."

    def throws_for_names_with_invalid_characters():
        with raises(GraphQLError) as exc_info:
            assert_valid_name(">--()-->")
        msg = str(exc_info.value)
        assert msg == "Names must only contain [_a-zA-Z0-9] but '>--()-->' does not."

    def throws_for_names_starting_with_invalid_characters():
        with raises(GraphQLError) as exc_info:
            assert_valid_name("42MeaningsOfLife")
        msg = str(exc_info.value)
        assert msg == (
            "Names must start with [_a-zA-Z] but '42MeaningsOfLife' does not."
        )
