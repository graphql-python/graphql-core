from typing import List, Union

from pytest import raises  # type: ignore

from graphql.error import GraphQLError, format_error
from graphql.language import Node, Source
from graphql.pyutils import Undefined


def describe_format_error():
    def formats_graphql_error():
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
        assert formatted == error.formatted
        assert formatted == {
            "message": "test message",
            "locations": [{"line": 2, "column": 14}, {"line": 3, "column": 20}],
            "path": path,
            "extensions": extensions,
        }

    def uses_default_message():
        # noinspection PyTypeChecker
        formatted = format_error(GraphQLError(None))  # type: ignore

        assert formatted == {
            "message": "An unknown error occurred.",
            "locations": None,
            "path": None,
        }

    def includes_path():
        path: List[Union[int, str]] = ["path", 3, "to", "field"]
        error = GraphQLError("msg", path=path)
        formatted = format_error(error)
        assert formatted == error.formatted
        assert formatted == {"message": "msg", "locations": None, "path": path}

    def includes_extension_fields():
        error = GraphQLError("msg", extensions={"foo": "bar"})
        formatted = format_error(error)
        assert formatted == error.formatted
        assert formatted == {
            "message": "msg",
            "locations": None,
            "path": None,
            "extensions": {"foo": "bar"},
        }

    def rejects_none_and_undefined_errors():
        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            format_error(None)  # type: ignore
        assert str(exc_info.value) == "Expected a GraphQLError."

        with raises(TypeError) as exc_info:
            # noinspection PyTypeChecker
            format_error(Undefined)  # type: ignore
        assert str(exc_info.value) == "Expected a GraphQLError."
