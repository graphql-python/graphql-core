from graphql import graphql_sync
from graphql.error import GraphQLError
from graphql.language import SourceLocation
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
    def _test_schema(test_field):
        return GraphQLSchema(GraphQLObjectType("Query", {"test": test_field}))

    def default_function_accesses_attributes():
        schema = _test_schema(GraphQLField(GraphQLString))

        class Source:
            test = "testValue"

        assert graphql_sync(schema, "{ test }", Source()) == (
            {"test": "testValue"},
            None,
        )

    def default_function_accesses_keys():
        schema = _test_schema(GraphQLField(GraphQLString))

        source = {"test": "testValue"}

        assert graphql_sync(schema, "{ test }", source) == ({"test": "testValue"}, None)

    def default_function_calls_methods():
        schema = _test_schema(GraphQLField(GraphQLString))

        class Source:
            _secret = "testValue"

            def test(self, _info):
                return self._secret

        assert graphql_sync(schema, "{ test }", Source()) == (
            {"test": "testValue"},
            None,
        )

    def default_function_passes_args_and_context():
        schema = _test_schema(
            GraphQLField(GraphQLInt, args={"addend1": GraphQLArgument(GraphQLInt)})
        )

        class Adder:
            _num: int

            def __init__(self, num):
                self._num = num

            def test(self, info, addend1):
                return self._num + addend1 + info.context.addend2

        source = Adder(700)

        class Context:
            addend2 = 9

        assert graphql_sync(schema, "{ test(addend1: 80) }", source, Context()) == (
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

        assert graphql_sync(schema, "{ test }") == ({"test": "[None, {}]"}, None)

        assert graphql_sync(schema, "{ test }", "Source!") == (
            {"test": "['Source!', {}]"},
            None,
        )

        assert graphql_sync(schema, '{ test(aStr: "String!") }', "Source!") == (
            {"test": "['Source!', {'aStr': 'String!'}]"},
            None,
        )

        assert graphql_sync(
            schema, '{ test(aInt: -123, aStr: "String!") }', "Source!"
        ) == ({"test": "['Source!', {'aStr': 'String!', 'aInt': -123}]"}, None)

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

        assert graphql_sync(schema, "{ test }") == ({"test": "[None, {}]"}, None)

        assert graphql_sync(schema, "{ test }", "Source!") == (
            {"test": "['Source!', {}]"},
            None,
        )

        assert graphql_sync(schema, '{ test(aStr: "String!") }', "Source!") == (
            {"test": "['Source!', {'a_str': 'String!'}]"},
            None,
        )

        assert graphql_sync(
            schema, '{ test(aInt: -123, aStr: "String!") }', "Source!"
        ) == ({"test": "['Source!', {'a_str': 'String!', 'a_int': -123}]"}, None)

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

        assert graphql_sync(schema, "{ test }") == ({"test": "[None, {}]"}, None)

        assert graphql_sync(
            schema, '{ test(aInput: {inputOne: "String!"}) }', "Source!"
        ) == ({"test": "['Source!', {'a_input': {'input_one': 'String!'}}]"}, None)

        assert graphql_sync(
            schema,
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
        result = graphql_sync(schema, "{ test }")

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
