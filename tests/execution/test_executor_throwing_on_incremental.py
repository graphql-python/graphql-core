"""Tests for the executor throwing on incremental delivery.

The executor throwing on incremental delivery is used to execute operations
that must not produce multiple payloads. It is used for subscription events
by default; these tests exercise it directly for other operation types.
"""

from __future__ import annotations

from graphql import (
    GraphQLDeferDirective,
    GraphQLField,
    GraphQLList,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLStreamDirective,
    GraphQLString,
    parse,
    specified_directives,
)
from graphql.execution.executor_throwing_on_incremental import (
    ExecutorThrowingOnIncremental,
)

obj_type = GraphQLObjectType(
    "Obj",
    {
        "echo": GraphQLField(GraphQLString),
        "list": GraphQLField(GraphQLList(GraphQLString)),
    },
)

schema = GraphQLSchema(
    GraphQLObjectType(
        "Query",
        {
            "echo": GraphQLField(GraphQLString),
            "obj": GraphQLField(obj_type),
            "list": GraphQLField(GraphQLList(GraphQLString)),
        },
    ),
    subscription=GraphQLObjectType(
        "Subscription", {"echo": GraphQLField(GraphQLString)}
    ),
    directives=[
        *specified_directives,
        GraphQLDeferDirective,
        GraphQLStreamDirective,
    ],
)

MULTIPLE_PAYLOADS_MESSAGE = (
    "Executing this GraphQL operation would unexpectedly produce"
    " multiple payloads (due to @defer or @stream directive)"
)


def execute_throwing(source: str, root_value: dict | None = None):
    executor = ExecutorThrowingOnIncremental.build(schema, parse(source), root_value)
    assert isinstance(executor, ExecutorThrowingOnIncremental)
    return executor.execute_operation()


def describe_executor_throwing_on_incremental():
    def executes_operations_without_incremental_delivery():
        result = execute_throwing("{ echo }", {"echo": "hello"})
        assert result == ({"echo": "hello"}, None)

    def completes_list_values_without_stream_directives():
        result = execute_throwing("{ list }", {"list": ["a", "b"]})
        assert result == ({"list": ["a", "b"]}, None)

    def raises_when_subscription_root_fields_are_deferred():
        result = execute_throwing(
            "subscription { ... @defer { echo } }", {"echo": "hello"}
        )
        assert result == (
            None,
            [
                {
                    "message": "`@defer` directive not supported on subscription"
                    " operations. Disable `@defer` by setting the `if` argument"
                    " to `false`.",
                }
            ],
        )

    def raises_when_root_fields_are_deferred():
        result = execute_throwing("{ ... @defer { echo } }", {"echo": "hello"})
        assert result == (None, [{"message": MULTIPLE_PAYLOADS_MESSAGE}])

    def raises_when_subfields_are_deferred():
        result = execute_throwing(
            "{ obj { ... @defer { echo } } }", {"obj": {"echo": "hello"}}
        )
        assert result == (
            {"obj": None},
            [
                {
                    "message": MULTIPLE_PAYLOADS_MESSAGE,
                    "locations": [(1, 3)],
                    "path": ["obj"],
                }
            ],
        )

    def raises_when_list_fields_are_streamed():
        result = execute_throwing(
            "{ list @stream(initialCount: 1) }", {"list": ["a", "b"]}
        )
        assert result == (
            {"list": None},
            [
                {
                    "message": MULTIPLE_PAYLOADS_MESSAGE,
                    "locations": [(1, 3)],
                    "path": ["list"],
                }
            ],
        )
