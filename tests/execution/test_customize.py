from graphql.execution import execute, ExecutionContext
from graphql.language import parse
from graphql.type import GraphQLSchema, GraphQLObjectType, GraphQLString, GraphQLField


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
            def execute_field(self, parent_type, source, field_nodes, path):
                result = super().execute_field(parent_type, source, field_nodes, path)
                return result * 2  # type: ignore

        assert execute(schema, query, execution_context_class=TestExecutionContext) == (
            {"foo": "barbar"},
            None,
        )
