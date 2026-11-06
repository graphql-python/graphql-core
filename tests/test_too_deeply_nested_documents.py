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
    @mark.usefixtures("without_nesting_limit")
    def graphql_sync_returns_a_parse_error(shape):
        _assert_parse_error(graphql_sync(schema, documents[shape]))

    @mark.parametrize("shape", documents)
    @mark.asyncio
    @mark.usefixtures("without_nesting_limit")
    async def graphql_returns_a_parse_error(shape):
        _assert_parse_error(await graphql(schema, documents[shape]))

    def _fragment_chain():
        # Far beyond the recursion limit on all interpreters.
        count = 10_000
        chain = " ".join(
            f"fragment F{i} on Query {{ ...F{i + 1} }}" for i in range(count)
        )
        return f"{{ ...F0 }} {chain} fragment F{count} on Query {{ a }}"

    def _assert_validation_aborted(result):
        assert result.data is None
        assert result.errors
        assert len(result.errors) == 1
        error = result.errors[0]
        assert error.message == "Validation aborted."
        assert error.locations is None
        assert error.__traceback__ is None
        assert error.__context__ is None

    @mark.usefixtures("without_nesting_limit")
    def graphql_sync_aborts_validation_of_a_fragment_chain():
        _assert_validation_aborted(graphql_sync(schema, _fragment_chain()))

    @mark.asyncio
    @mark.usefixtures("without_nesting_limit")
    async def graphql_aborts_validation_of_a_fragment_chain():
        _assert_validation_aborted(await graphql(schema, _fragment_chain()))
