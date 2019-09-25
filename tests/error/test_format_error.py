from typing import List, Union

from pytest import raises  # type: ignore

from graphql.error import GraphQLError, format_error
from graphql.language import Node, Source


def describe_format_error():
    def throw_if_not_an_error():
        with raises(TypeError):
            # noinspection PyTypeChecker
            format_error(None)  # type: ignore

    def format_graphql_error():
        source = Source(
            """
            query {
              something
            }"""
        )
        path: List[Union[int, str]] = ["one", 2]
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
        formatted = format_error(error)
        assert formatted == {
            "message": "test message",
            "locations": [{"line": 2, "column": 14}, {"line": 3, "column": 20}],
            "path": path,
            "extensions": extensions,
        }

    def add_default_message():
        # noinspection PyTypeChecker
        error = format_error(GraphQLError(None))  # type: ignore
        assert error["message"] == "An unknown error occurred."
