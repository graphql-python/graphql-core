from asyncio import sleep

import pytest

from graphql import default_harness, execute, graphql, graphql_sync
from graphql.error import GraphQLError
from graphql.language import Source
from graphql.type import (
    GraphQLField,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)
from graphql.validation import ValidationRule

from .fixtures import cleanup

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.filterwarnings("ignore:coroutine .* was never awaited:RuntimeWarning"),
]


def _resolve_context_echo(_source, info):
    return str(info.context)  # pragma: no cover


def _resolve_root_value(root_value, _info):
    return root_value


async def _resolve_root_value_async(root_value, _info):
    return root_value


schema = GraphQLSchema(
    query=GraphQLObjectType(
        "Query",
        {
            "a": GraphQLField(GraphQLString, resolve=lambda *_args: "A"),
            "b": GraphQLField(GraphQLString, resolve=lambda *_args: "B"),
            "contextEcho": GraphQLField(GraphQLString, resolve=_resolve_context_echo),
            "syncField": GraphQLField(GraphQLString, resolve=_resolve_root_value),
            "asyncField": GraphQLField(
                GraphQLString, resolve=_resolve_root_value_async
            ),
        },
    )
)


def describe_graphql():
    async def passes_source_through_to_parse():
        source = Source("{", "custom-query.graphql")

        result = await graphql(schema, source)

        assert result.errors
        assert result.errors[0].source is not None
        assert result.errors[0].source.name == "custom-query.graphql"

    async def passes_rules_through_to_validate():
        class CustomRule(ValidationRule):
            def enter_field(self, node, *_args):
                self.context.report_error(GraphQLError("custom rule error", node))

        result = await graphql(schema, "{ a }", rules=[CustomRule])

        assert result.errors
        assert result.errors[0].message == "custom rule error"

    async def passes_parse_options_through_to_parse():
        class CustomRule(ValidationRule):
            def enter_operation_definition(self, node, *_args):
                message = "no location" if node.loc is None else "has location"
                self.context.report_error(GraphQLError(message, node))

        result = await graphql(schema, "{ a }", no_location=True, rules=[CustomRule])

        assert result.errors
        assert result.errors[0].message == "no location"

    async def passes_validation_options_through_to_validate():
        result = await graphql(schema, "{ contextEho }", hide_suggestions=True)

        assert result.errors
        assert (
            result.errors[0].message
            == "Cannot query field 'contextEho' on type 'Query'."
        )

    async def passes_execution_args_through_to_execute():
        result = await graphql(
            schema,
            """
            query First {
              a
            }

            query Second {
              b
            }
            """,
            operation_name="Second",
        )

        assert result == ({"b": "B"}, None)

    async def returns_schema_validation_errors():
        bad_schema = GraphQLSchema()
        result = await graphql(bad_schema, "{ __typename }")

        assert result.errors
        assert result.errors[0].message == "Query root type must be provided."

    async def works_when_a_custom_harness_is_provided():
        def custom_execute(schema, document, root_value=None, *args, **kwargs):
            return execute(schema, document, f"**{root_value}**", *args, **kwargs)

        result = await graphql(
            schema,
            "{ syncField }",
            root_value="rootValue",
            harness=default_harness._replace(execute=custom_execute),
        )

        assert result == ({"syncField": "**rootValue**"}, None)

    async def returns_parse_errors_thrown_synchronously_by_a_custom_harness():
        parse_error = GraphQLError("sync parse error")

        def custom_parse(*_args, **_kwargs):
            raise parse_error

        result = await graphql(
            schema,
            "{ syncField }",
            harness=default_harness._replace(parse=custom_parse),
        )

        assert result == (None, [parse_error])

    async def works_with_asynchronous_parse_from_a_custom_harness():
        async def custom_parse(source, **options):
            return default_harness.parse(source, **options)

        result = await graphql(
            schema,
            "{ syncField }",
            root_value="rootValue",
            harness=default_harness._replace(parse=custom_parse),
        )

        assert result == ({"syncField": "rootValue"}, None)

    async def handles_errors_from_an_asynchronous_parse_from_a_custom_harness():
        parse_error = GraphQLError("async parse error")

        async def custom_parse(*_args, **_kwargs):
            raise parse_error

        result = await graphql(
            schema,
            "{ syncField }",
            harness=default_harness._replace(parse=custom_parse),
        )

        assert result == (None, [parse_error])

    async def works_with_asynchronous_validation_from_a_custom_harness():
        async def custom_validate(schema, document, *args, **kwargs):
            return default_harness.validate(schema, document, *args, **kwargs)

        result = await graphql(
            schema,
            "{ syncField }",
            root_value="rootValue",
            harness=default_harness._replace(validate=custom_validate),
        )

        assert result == ({"syncField": "rootValue"}, None)

    async def returns_validation_errors_from_synchronous_validation():
        validation_error = GraphQLError("async validation error")

        def custom_validate(*_args, **_kwargs):
            return [validation_error]

        result = await graphql(
            schema,
            "{ syncField }",
            harness=default_harness._replace(validate=custom_validate),
        )

        assert result == (None, [validation_error])

    async def returns_validation_errors_from_asynchronous_validation():
        validation_error = GraphQLError("async validation error")

        async def custom_validate(*_args, **_kwargs):
            return [validation_error]

        result = await graphql(
            schema,
            "{ syncField }",
            harness=default_harness._replace(validate=custom_validate),
        )

        assert result == (None, [validation_error])

    async def works_with_asynchronous_parse_and_asynchronous_execution():
        # Unlike JS promises, Python coroutines do not auto-flatten, so the
        # asynchronous parse path must await the asynchronous execution result.
        async def custom_parse(source, **options):
            return default_harness.parse(source, **options)

        result = await graphql(
            schema,
            "{ asyncField }",
            root_value="rootValue",
            harness=default_harness._replace(parse=custom_parse),
        )

        assert result == ({"asyncField": "rootValue"}, None)

    async def works_with_asynchronous_validation_and_asynchronous_execution():
        async def custom_validate(schema, document, *args, **kwargs):
            return default_harness.validate(schema, document, *args, **kwargs)

        result = await graphql(
            schema,
            "{ asyncField }",
            root_value="rootValue",
            harness=default_harness._replace(validate=custom_validate),
        )

        assert result == ({"asyncField": "rootValue"}, None)


def describe_graphql_sync():
    def returns_result_for_synchronous_execution():
        result = graphql_sync(schema, "{ syncField }", root_value="rootValue")

        assert result == ({"syncField": "rootValue"}, None)

    async def throws_for_asynchronous_execution():
        # Unlike graphql-js, graphql_sync only detects asynchronous execution when
        # check_sync is set; without it, the coroutine is treated as a plain value.
        with pytest.raises(RuntimeError) as exc_info:
            graphql_sync(
                schema, "{ asyncField }", root_value="rootValue", check_sync=True
            )
        assert (
            str(exc_info.value) == "GraphQL execution failed to complete synchronously."
        )
        del exc_info
        await sleep(0)  # let the loop process the cancelled execution task
        cleanup()
