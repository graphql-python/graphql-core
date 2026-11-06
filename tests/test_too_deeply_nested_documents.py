from pytest import mark

from graphql import graphql, graphql_sync
from graphql.utilities import build_schema

schema = build_schema("type Query { a: String, f(a: String): String }")

depth = 100_000
message = "Syntax Error: Document is nested too deeply. Parsing aborted."

documents = {
    "nested fields": "{a" * depth + "}" * depth,
    "inline fragments": "{" + "...{" * depth + "a" + "}" * depth + "}",
    "object literal": "{f(a:" + "{a:" * depth + "1" + "}" * depth + ")}",
    "list literal": "{f(a:" + "[" * depth + "]" * depth + ")}",
    "list type": "query($a:" + "[" * depth + "A" + "]" * depth + "){f}",
}


def _assert_parse_error(result):
    assert result.data is None
    assert result.errors
    assert len(result.errors) == 1
    error = result.errors[0]
    assert error.message == message
    assert error.locations
    assert error.__context__ is None
    assert error.__cause__ is None


def describe_too_deeply_nested_documents():
    @mark.parametrize("shape", documents)
    def graphql_sync_returns_a_parse_error(shape):
        _assert_parse_error(graphql_sync(schema, documents[shape]))

    @mark.parametrize("shape", documents)
    @mark.asyncio
    async def graphql_returns_a_parse_error(shape):
        _assert_parse_error(await graphql(schema, documents[shape]))
