from pytest import raises  # type: ignore

from graphql.error import GraphQLError
from graphql.utilities import assert_valid_name


def describe_assert_valid_name():
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
            assert_valid_name({})
        msg = str(exc_info.value)
        assert msg == "Expected string"

    def throws_for_names_with_invalid_characters():
        with raises(GraphQLError, match="Names must match"):
            assert_valid_name(">--()-->")
