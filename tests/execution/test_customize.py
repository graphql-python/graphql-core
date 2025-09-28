from inspect import isasyncgen

import pytest

from graphql.execution import ExecutionContext, GraphQLWrappedResult, execute, subscribe
from graphql.language import parse
from graphql.type import GraphQLField, GraphQLObjectType, GraphQLSchema, GraphQLString

pytestmark = pytest.mark.anyio

try:
    anext  # noqa: B018
except NameError:  # pragma: no cover (Python < 3.10)

    async def anext(iterator):
        """Return the next item from an async iterator."""
        return await iterator.__anext__()


def describe_customize_execution():
    def uses_a_custom_field_resolver():
        query = parse("{ foo }")

        schema = GraphQLSchema(
            GraphQLObjectType("Query", {"foo": GraphQLField(GraphQLString)})
        )

        # For the purposes of test, just return the name of the field!
        def custom_resolver(_source, info, **_args):
            return info.field_name

        assert execute(schema, query, field_resolver=custom_resolver) == (
            {"foo": "foo"},
            None,
        )

    def uses_a_custom_execution_context_class():
        query = parse("{ foo }")

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {"foo": GraphQLField(GraphQLString, resolve=lambda *_args: "bar")},
            )
        )

        class TestExecutionContext(ExecutionContext):
            def __init__(self, *args, **kwargs):
                assert kwargs.pop("custom_arg", None) == "baz"
                super().__init__(*args, **kwargs)

            def execute_field(
                self,
                parent_type,
                source,
                field_group,
                path,
                incremental_context,
                defer_map,
            ):
                result = super().execute_field(
                    parent_type,
                    source,
                    field_group,
                    path,
                    incremental_context,
                    defer_map,
                )
                assert isinstance(result, GraphQLWrappedResult)
                result.result *= 2
                return result

        assert execute(
            schema,
            query,
            execution_context_class=TestExecutionContext,
            custom_arg="baz",
        ) == (
            {"foo": "barbar"},
            None,
        )


def describe_customize_subscription():
    async def uses_a_custom_subscribe_field_resolver():
        schema = GraphQLSchema(
            query=GraphQLObjectType("Query", {"foo": GraphQLField(GraphQLString)}),
            subscription=GraphQLObjectType(
                "Subscription", {"foo": GraphQLField(GraphQLString)}
            ),
        )

        class Root:
            @staticmethod
            async def custom_foo():
                yield {"foo": "FooValue"}

        subscription = subscribe(
            schema,
            document=parse("subscription { foo }"),
            root_value=Root(),
            subscribe_field_resolver=lambda root, _info: root.custom_foo(),
        )
        assert isasyncgen(subscription)

        assert await anext(subscription) == (
            {"foo": "FooValue"},
            None,
        )

        await subscription.aclose()

    async def uses_a_custom_execution_context_class():
        class TestExecutionContext(ExecutionContext):
            def __init__(self, *args, **kwargs):
                assert kwargs.pop("custom_arg", None) == "baz"
                super().__init__(*args, **kwargs)

            def build_resolve_info(self, *args, **kwargs):
                resolve_info = super().build_resolve_info(*args, **kwargs)
                resolve_info.context["foo"] = "bar"
                return resolve_info

        async def generate_foo(_obj, info):
            yield info.context["foo"]

        def resolve_foo(message, _info):
            return message

        schema = GraphQLSchema(
            query=GraphQLObjectType("Query", {"foo": GraphQLField(GraphQLString)}),
            subscription=GraphQLObjectType(
                "Subscription",
                {
                    "foo": GraphQLField(
                        GraphQLString,
                        resolve=resolve_foo,
                        subscribe=generate_foo,
                    )
                },
            ),
        )

        document = parse("subscription { foo }")
        subscription = subscribe(
            schema,
            document,
            context_value={},
            execution_context_class=TestExecutionContext,
            custom_arg="baz",
        )
        assert isasyncgen(subscription)

        assert await anext(subscription) == ({"foo": "bar"}, None)
