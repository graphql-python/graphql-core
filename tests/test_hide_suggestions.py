from pytest import mark

from graphql import graphql_sync, parse, subscribe
from graphql.execution import ExecutionContext, ExecutionResult, execute_sync
from graphql.utilities import build_schema


def describe_hide_suggestions():
    schema = build_schema("""
        type Subscription { search(filter: Filter): String }
        enum Color { RED GREEN BLUE }
        input Filter { color: Color }
        type Query {
          greeting(name: String): String
          search(filter: Filter): String
        }
        """)

    @mark.asyncio
    @mark.parametrize("hide_suggestions", [False, True])
    async def forwards_the_option_through_subscription_variable_coercion(
        hide_suggestions,
    ):
        document = parse("subscription ($filter: Filter) { search(filter: $filter) }")
        result = await subscribe(
            schema,
            document,
            variable_values={"filter": {"color": "REDD", "colr": "RED"}},
            hide_suggestions=hide_suggestions,
        )
        assert isinstance(result, ExecutionResult)
        assert result.errors
        assert len(result.errors) == 2
        for error in result.errors:
            assert ("Did you mean" in error.message) is not hide_suggestions

    @mark.parametrize(
        "source",
        [
            "{ greetingg }",
            "query ($value: Colr) { greeting }",
            '{ greeting(nam: "x") }',
            "{ greeting @skip(iff: true) }",
            "{ search(filter: { colr: RED }) }",
            "{ search(filter: { color: REDD }) }",
        ],
    )
    def omits_validation_suggestions_while_preserving_errors(source):
        visible = graphql_sync(schema, source)
        hidden = graphql_sync(schema, source, hide_suggestions=True)
        visible_messages = [error.message for error in visible.errors or []]
        hidden_messages = [error.message for error in hidden.errors or []]
        assert any("Did you mean" in message for message in visible_messages)
        assert len(hidden_messages) == len(visible_messages)
        assert not any("Did you mean" in message for message in hidden_messages)
        assert graphql_sync(schema, source, hide_suggestions=False) == visible

    @mark.parametrize("hide_suggestions", [False, True])
    def forwards_the_option_through_graphql_and_direct_execution_variable_coercion(
        hide_suggestions,
    ):
        source = "query ($filter: Filter) { search(filter: $filter) }"
        document = parse(source)
        variable_values = {"filter": {"color": "REDD", "colr": "RED"}}
        from_graphql = graphql_sync(
            schema,
            source,
            variable_values=variable_values,
            hide_suggestions=hide_suggestions,
        )
        from_execute = execute_sync(
            schema,
            document,
            variable_values=variable_values,
            hide_suggestions=hide_suggestions,
        )
        assert from_graphql.errors
        assert from_execute.errors
        assert [error.message for error in from_execute.errors] == [
            error.message for error in from_graphql.errors
        ]
        assert len(from_execute.errors) == 2
        for error in from_execute.errors:
            assert ("Did you mean" in error.message) is not hide_suggestions

    def does_not_pass_the_option_to_a_custom_build_method_unless_set():
        class FixedSignatureContext(ExecutionContext):
            @classmethod
            def build(  # type: ignore
                cls,
                schema,
                document,
                root_value,
                context_value,
                raw_variable_values,
                operation_name,
                field_resolver,
                type_resolver,
                subscribe_field_resolver,
                max_coercion_errors,
                middleware,
                is_awaitable,
            ):
                return super().build(
                    schema,
                    document,
                    root_value,
                    context_value,
                    raw_variable_values,
                    operation_name,
                    field_resolver,
                    type_resolver,
                    subscribe_field_resolver,
                    max_coercion_errors,
                    middleware,
                    is_awaitable,
                )

        result = execute_sync(
            schema,
            parse("{ greeting }"),
            execution_context_class=FixedSignatureContext,
        )
        assert result == ({"greeting": None}, None)

    def passes_the_option_to_a_custom_build_method_when_set():
        class OpenSignatureContext(ExecutionContext):
            @classmethod
            def build(cls, *args, **kwargs):
                return super().build(*args, **kwargs)

        result = execute_sync(
            schema,
            parse("query ($filter: Filter) { search(filter: $filter) }"),
            variable_values={"filter": {"colr": "RED"}},
            execution_context_class=OpenSignatureContext,
            hide_suggestions=True,
        )
        assert result.errors
        assert not any("Did you mean" in error.message for error in result.errors)
