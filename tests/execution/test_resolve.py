from collections import ChainMap
from typing import Any

from graphql.error import GraphQLError
from graphql.execution import execute_sync, ExecutionResult
from graphql.language import parse, SourceLocation
from graphql.type import (
    GraphQLArgument,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)


def describe_execute_resolve_function():
    def _test_schema(test_field: GraphQLField) -> GraphQLSchema:
        return GraphQLSchema(GraphQLObjectType("Query", {"test": test_field}))

    def default_function_accesses_attributes():
        class RootValue:
            test = "testValue"

        assert execute_sync(
            schema=_test_schema(GraphQLField(GraphQLString)),
            document=parse("{ test }"),
            root_value=RootValue(),
        ) == (
            {"test": "testValue"},
            None,
        )

    def default_function_accesses_keys_of_dict():
        root_value = {"test": "testValue"}

        assert (
            execute_sync(
                schema=_test_schema(GraphQLField(GraphQLString)),
                document=parse("{ test }"),
                root_value=root_value,
            )
            == ({"test": "testValue"}, None)
        )

    def default_function_accesses_keys_of_chain_map():
        # use a mapping that is not a subclass of dict
        root_value = ChainMap({"test": "testValue"})

        assert (
            execute_sync(
                schema=_test_schema(GraphQLField(GraphQLString)),
                document=parse("{ test }"),
                root_value=root_value,
            )
            == ({"test": "testValue"}, None)
        )

    def default_function_calls_methods():
        class RootValue:
            _secret = "secretValue"

            def test(self, _info):
                return self._secret

        assert execute_sync(
            schema=_test_schema(GraphQLField(GraphQLString)),
            document=parse("{ test }"),
            root_value=RootValue(),
        ) == (
            {"test": "secretValue"},
            None,
        )

    def default_function_passes_args_and_context():
        class Adder:
            _num: int

            def __init__(self, num):
                self._num = num

            def test(self, info, addend1: int):
                return self._num + addend1 + info.context.addend2

        root_value = Adder(700)

        schema = _test_schema(
            GraphQLField(GraphQLInt, args={"addend1": GraphQLArgument(GraphQLInt)})
        )

        class ContextValue:
            addend2 = 9

        context_value = ContextValue()
        document = parse("{ test(addend1: 80) }")

        assert execute_sync(
            schema=schema,
            document=document,
            root_value=root_value,
            context_value=context_value,
        ) == (
            {"test": 789},
            None,
        )

    def uses_provided_resolve_function():
        schema = _test_schema(
            GraphQLField(
                GraphQLString,
                args={
                    "aStr": GraphQLArgument(GraphQLString),
                    "aInt": GraphQLArgument(GraphQLInt),
                },
                resolve=lambda source, info, **args: repr([source, args]),
            )
        )

        def execute_query(query: str, root_value: Any = None) -> ExecutionResult:
            document = parse(query)
            return execute_sync(
                schema=schema,
                document=document,
                root_value=root_value,
            )

        assert execute_query("{ test }") == ({"test": "[None, {}]"}, None)

        assert execute_query("{ test }", "Source!") == (
            {"test": "['Source!', {}]"},
            None,
        )

        assert execute_query('{ test(aStr: "String!") }', "Source!") == (
            {"test": "['Source!', {'aStr': 'String!'}]"},
            None,
        )

        assert execute_query('{ test(aInt: -123, aStr: "String!") }', "Source!") == (
            {"test": "['Source!', {'aStr': 'String!', 'aInt': -123}]"},
            None,
        )

    def transforms_arguments_using_out_names():
        # This is an extension of GraphQL.js.
        schema = _test_schema(
            GraphQLField(
                GraphQLString,
                args={
                    "aStr": GraphQLArgument(GraphQLString, out_name="a_str"),
                    "aInt": GraphQLArgument(GraphQLInt, out_name="a_int"),
                },
                resolve=lambda source, info, **args: repr([source, args]),
            )
        )

        def execute_query(query: str, root_value: Any = None) -> ExecutionResult:
            document = parse(query)
            return execute_sync(schema=schema, document=document, root_value=root_value)

        assert execute_query("{ test }") == ({"test": "[None, {}]"}, None)

        assert execute_query("{ test }", "Source!") == (
            {"test": "['Source!', {}]"},
            None,
        )

        assert execute_query('{ test(aStr: "String!") }', "Source!") == (
            {"test": "['Source!', {'a_str': 'String!'}]"},
            None,
        )

        assert execute_query('{ test(aInt: -123, aStr: "String!") }', "Source!") == (
            {"test": "['Source!', {'a_str': 'String!', 'a_int': -123}]"},
            None,
        )

    def transforms_arguments_with_inputs_using_out_names():
        # This is an extension of GraphQL.js.
        TestInputObject = GraphQLInputObjectType(
            "TestInputObjectType",
            lambda: {
                "inputOne": GraphQLInputField(GraphQLString, out_name="input_one"),
                "inputRecursive": GraphQLInputField(
                    TestInputObject, out_name="input_recursive"
                ),
            },
        )

        schema = _test_schema(
            GraphQLField(
                GraphQLString,
                args={"aInput": GraphQLArgument(TestInputObject, out_name="a_input")},
                resolve=lambda source, info, **args: repr([source, args]),
            )
        )

        def execute_query(query: str, root_value: Any = None) -> ExecutionResult:
            document = parse(query)
            return execute_sync(schema=schema, document=document, root_value=root_value)

        assert execute_query("{ test }") == ({"test": "[None, {}]"}, None)

        assert execute_query('{ test(aInput: {inputOne: "String!"}) }', "Source!") == (
            {"test": "['Source!', {'a_input': {'input_one': 'String!'}}]"},
            None,
        )

        assert execute_query(
            '{ test(aInput: {inputRecursive: {inputOne: "SourceRecursive!"}}) }',
            "Source!",
        ) == (
            {
                "test": "['Source!',"
                " {'a_input': {'input_recursive': {'input_one': 'SourceRecursive!'}}}]"
            },
            None,
        )

    def pass_error_from_resolver_wrapped_as_located_graphql_error():
        def resolve(_obj, _info):
            raise ValueError("Some error")

        schema = _test_schema(GraphQLField(GraphQLString, resolve=resolve))
        result = execute_sync(schema, parse("{ test }"))

        assert result == (
            {"test": None},
            [{"message": "Some error", "locations": [(1, 3)], "path": ["test"]}],
        )

        assert result.errors is not None
        error = result.errors[0]
        assert isinstance(error, GraphQLError)
        assert str(error) == "Some error\n\nGraphQL request:1:3\n1 | { test }\n  |   ^"
        assert error.positions == [2]
        locations = error.locations
        assert locations == [(1, 3)]
        location = locations[0]
        assert isinstance(location, SourceLocation)
        assert location == SourceLocation(1, 3)
        original_error = error.original_error
        assert isinstance(original_error, ValueError)
        assert str(original_error) == "Some error"
