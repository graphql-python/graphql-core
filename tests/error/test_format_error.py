from pytest import raises

from graphql.error import GraphQLError, format_error
from graphql.language import Node, Source


def describe_format_error():
    def throw_if_not_an_error():
        with raises(ValueError):
            format_error(None)

    def format_graphql_error():
        source = Source(
            """
            query {
              something
            }"""
        )
        path = ["one", 2]
        extensions = {"ext": None}
        error = GraphQLError(
            "test message",
            Node(),
            source,
            [14, 40],
            path,
            ValueError("original"),
            extensions=extensions,
        )
        assert error == {
            "message": "test message",
            "locations": [(2, 14), (3, 20)],
            "path": path,
            "extensions": extensions,
        }

    def add_default_message():
        error = format_error(GraphQLError(None))
        assert error["message"] == "An unknown error occurred."
