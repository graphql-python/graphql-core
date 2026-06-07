from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphql.execution import ExecutionResult, execute
from graphql.language import parse
from graphql.utilities import build_schema

if TYPE_CHECKING:
    from graphql.pyutils import AwaitableOrValue

sync_error = RuntimeError("bar")


def throwing_foo(_info: Any) -> int:
    raise sync_error


throwing_data = {"foo": throwing_foo}


schema = build_schema("""
    type Query {
      foo: Int!
    }

    directive @experimental_disableErrorPropagation on QUERY | MUTATION | SUBSCRIPTION
    """)


def execute_query(query: str, root_value: Any) -> AwaitableOrValue[ExecutionResult]:
    return execute(schema, parse(query), root_value)


def describe_execute_handles_errors():
    def with_experimental_disable_error_propagation_returns_null():
        query = """
            query getFoo @experimental_disableErrorPropagation {
              foo
            }
            """
        result = execute_query(query, throwing_data)
        assert result == (
            {"foo": None},
            [{"message": "bar", "path": ["foo"], "locations": [(3, 15)]}],
        )

    def without_experimental_disable_error_propagation_propagates_the_error():
        query = """
            query getFoo {
              foo
            }
            """
        result = execute_query(query, throwing_data)
        assert result == (
            None,
            [{"message": "bar", "path": ["foo"], "locations": [(3, 15)]}],
        )
