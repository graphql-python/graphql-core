from inspect import isawaitable

from pytest import mark, raises  # type: ignore

from graphql import graphql_sync
from graphql.execution import execute
from graphql.language import parse
from graphql.type import GraphQLField, GraphQLObjectType, GraphQLSchema, GraphQLString


def describe_execute_synchronously_when_possible():
    def _resolve_sync(root_value, info_):
        return root_value

    async def _resolve_async(root_value, info_):
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

    def does_not_return_a_promise_for_initial_errors():
        doc = "fragment Example on Query { syncField }"
        assert execute(schema, parse(doc), "rootValue") == (
            None,
            [{"message": "Must provide an operation."}],
        )

    def does_not_return_a_promise_if_fields_are_all_synchronous():
        doc = "query Example { syncField }"
        assert execute(schema, parse(doc), "rootValue") == (
            {"syncField": "rootValue"},
            None,
        )

    def does_not_return_a_promise_if_mutation_fields_are_all_synchronous():
        doc = "mutation Example { syncMutationField }"
        assert execute(schema, parse(doc), "rootValue") == (
            {"syncMutationField": "rootValue"},
            None,
        )

    @mark.asyncio
    async def returns_a_promise_if_any_field_is_asynchronous():
        doc = "query Example { syncField, asyncField }"
        result = execute(schema, parse(doc), "rootValue")
        assert isawaitable(result)
        assert await result == (
            {"syncField": "rootValue", "asyncField": "rootValue"},
            None,
        )

    def describe_graphql_sync():
        def does_not_return_a_promise_for_syntax_errors():
            doc = "fragment Example on Query { { { syncField }"
            assert graphql_sync(schema, doc) == (
                None,
                [
                    {
                        "message": "Syntax Error: Expected Name, found {",
                        "locations": [(1, 29)],
                    }
                ],
            )

        def does_not_return_a_promise_for_validation_errors():
            doc = "fragment Example on Query { unknownField }"
            assert graphql_sync(schema, doc) == (
                None,
                [
                    {
                        "message": "Cannot query field 'unknownField' on type 'Query'."
                        " Did you mean 'syncField' or 'asyncField'?",
                        "locations": [(1, 29)],
                    },
                    {
                        "message": "Fragment 'Example' is never used.",
                        "locations": [(1, 1)],
                    },
                ],
            )

        def does_not_return_a_promise_for_sync_execution():
            doc = "query Example { syncField }"
            assert graphql_sync(schema, doc, "rootValue") == (
                {"syncField": "rootValue"},
                None,
            )

        def throws_if_encountering_async_operation():
            doc = "query Example { syncField, asyncField }"
            with raises(RuntimeError) as exc_info:
                graphql_sync(schema, doc, "rootValue")
            msg = str(exc_info.value)
            assert msg == "GraphQL execution failed to complete synchronously."
