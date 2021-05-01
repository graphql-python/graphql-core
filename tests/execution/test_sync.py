from gc import collect
from inspect import isawaitable
from typing import Awaitable, cast

from pytest import mark, raises

from graphql import graphql_sync
from graphql.execution import execute, execute_sync
from graphql.language import parse
from graphql.type import GraphQLField, GraphQLObjectType, GraphQLSchema, GraphQLString
from graphql.validation import validate


def describe_execute_synchronously_when_possible():
    def _resolve_sync(root_value, _info):
        return root_value

    async def _resolve_async(root_value, _info):
        return root_value

    schema = GraphQLSchema(
        GraphQLObjectType(
            "Query",
            {
                "syncField": GraphQLField(GraphQLString, resolve=_resolve_sync),
                "asyncField": GraphQLField(GraphQLString, resolve=_resolve_async),
            },
        ),
        GraphQLObjectType(
            "Mutation",
            {"syncMutationField": GraphQLField(GraphQLString, resolve=_resolve_sync)},
        ),
    )

    def does_not_return_an_awaitable_for_initial_errors():
        doc = "fragment Example on Query { syncField }"
        assert execute(schema, parse(doc), "rootValue") == (
            None,
            [{"message": "Must provide an operation."}],
        )

    def does_not_return_an_awaitable_if_fields_are_all_synchronous():
        doc = "query Example { syncField }"
        assert execute(schema, parse(doc), "rootValue") == (
            {"syncField": "rootValue"},
            None,
        )

    def does_not_return_an_awaitable_if_mutation_fields_are_all_synchronous():
        doc = "mutation Example { syncMutationField }"
        assert execute(schema, parse(doc), "rootValue") == (
            {"syncMutationField": "rootValue"},
            None,
        )

    @mark.asyncio
    async def returns_an_awaitable_if_any_field_is_asynchronous():
        doc = "query Example { syncField, asyncField }"
        result = execute(schema, parse(doc), "rootValue")
        assert isawaitable(result)
        result = cast(Awaitable, result)
        assert await result == (
            {"syncField": "rootValue", "asyncField": "rootValue"},
            None,
        )

    def describe_execute_sync():
        def does_not_return_an_awaitable_for_sync_execution():
            doc = "query Example { syncField }"
            result = execute_sync(schema, document=parse(doc), root_value="rootValue")
            assert result == (
                {"syncField": "rootValue"},
                None,
            )

        def does_not_throw_if_not_encountering_async_execution_with_check_sync():
            doc = "query Example { syncField }"
            result = execute_sync(
                schema, document=parse(doc), root_value="rootValue", check_sync=True
            )
            assert result == (
                {"syncField": "rootValue"},
                None,
            )

        @mark.asyncio
        @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
        async def throws_if_encountering_async_execution_with_check_sync():
            doc = "query Example { syncField, asyncField }"
            with raises(RuntimeError) as exc_info:
                execute_sync(
                    schema, document=parse(doc), root_value="rootValue", check_sync=True
                )
            msg = str(exc_info.value)
            assert msg == "GraphQL execution failed to complete synchronously."

        @mark.asyncio
        @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
        async def throws_if_encountering_async_operation_without_check_sync():
            doc = "query Example { syncField, asyncField }"
            result = execute_sync(schema, document=parse(doc), root_value="rootValue")
            assert result == (
                {"syncField": "rootValue", "asyncField": None},
                [
                    {
                        "message": "String cannot represent value:"
                        " <coroutine _resolve_async>",
                        "locations": [(1, 28)],
                        "path": ["asyncField"],
                    }
                ],
            )
            # garbage collect coroutine in order to not postpone the warning
            del result
            collect()

    def describe_graphql_sync():
        def reports_errors_raised_during_schema_validation():
            bad_schema = GraphQLSchema()
            result = graphql_sync(schema=bad_schema, source="{ __typename }")
            assert result == (None, [{"message": "Query root type must be provided."}])

        def does_not_return_an_awaitable_for_syntax_errors():
            doc = "fragment Example on Query { { { syncField }"
            assert graphql_sync(schema, doc) == (
                None,
                [
                    {
                        "message": "Syntax Error: Expected Name, found '{'.",
                        "locations": [(1, 29)],
                    }
                ],
            )

        def does_not_return_an_awaitable_for_validation_errors():
            doc = "fragment Example on Query { unknownField }"
            validation_errors = validate(schema, parse(doc))
            result = graphql_sync(schema, doc)
            assert result == (None, validation_errors)

        def does_not_return_an_awaitable_for_sync_execution():
            doc = "query Example { syncField }"
            assert graphql_sync(schema, doc, "rootValue") == (
                {"syncField": "rootValue"},
                None,
            )

        def does_not_throw_if_not_encountering_async_operation_with_check_sync():
            doc = "query Example { syncField }"
            assert graphql_sync(schema, doc, "rootValue") == (
                {"syncField": "rootValue"},
                None,
            )

        @mark.asyncio
        @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
        async def throws_if_encountering_async_operation_with_check_sync():
            doc = "query Example { syncField, asyncField }"
            with raises(RuntimeError) as exc_info:
                graphql_sync(schema, doc, "rootValue", check_sync=True)
            msg = str(exc_info.value)
            assert msg == "GraphQL execution failed to complete synchronously."

        @mark.asyncio
        @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
        async def throws_if_encountering_async_operation_without_check_sync():
            doc = "query Example { syncField, asyncField }"
            result = graphql_sync(schema, doc, "rootValue")
            assert result == (
                {"syncField": "rootValue", "asyncField": None},
                [
                    {
                        "message": "String cannot represent value:"
                        " <coroutine _resolve_async>",
                        "locations": [(1, 28)],
                        "path": ["asyncField"],
                    }
                ],
            )
            # garbage collect coroutine in order to not postpone the warning
            del result
            collect()
