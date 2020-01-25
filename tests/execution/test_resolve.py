from graphql import graphql_sync
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
        class RootValue:
            test = "testValue"

        assert graphql_sync(
            schema=_test_schema(GraphQLField(GraphQLString)),
            source="{ test }",
            root_value=RootValue(),
        ) == ({"test": "testValue"}, None,)

    def default_function_accesses_keys():
        root_value = {"test": "testValue"}

        assert graphql_sync(
            schema=_test_schema(GraphQLField(GraphQLString)),
            source="{ test }",
            root_value=root_value,
        ) == ({"test": "testValue"}, None)

    def default_function_calls_methods():
        class RootValue:
            _secret = "secretValue"

            def test(self, _info):
                return self._secret

        assert graphql_sync(
            schema=_test_schema(GraphQLField(GraphQLString)),
            source="{ test }",
            root_value=RootValue(),
        ) == ({"test": "secretValue"}, None,)

    def default_function_passes_args_and_context():
        class Adder:
            _num: int

            def __init__(self, num):
                self._num = num

            def test(self, info, addend1):
                return self._num + addend1 + info.context.addend2

        root_value = Adder(700)

        schema = _test_schema(
            GraphQLField(GraphQLInt, args={"addend1": GraphQLArgument(GraphQLInt)})
        )

        class ContextValue:
            addend2 = 9

        context_value = ContextValue()
        source = "{ test(addend1: 80) }"

        assert graphql_sync(
            schema=schema,
            source=source,
            root_value=root_value,
            context_value=context_value,
        ) == ({"test": 789}, None,)

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

        def execute(source, root_value=None, context_value=None):
            return graphql_sync(
                schema=schema,
                source=source,
                root_value=root_value,
                context_value=context_value,
            )

        assert execute("{ test }") == ({"test": "[None, {}]"}, None)

        assert execute("{ test }", "Source!") == ({"test": "['Source!', {}]"}, None,)

        assert execute('{ test(aStr: "String!") }', "Source!") == (
            {"test": "['Source!', {'aStr': 'String!'}]"},
            None,
        )

        assert execute('{ test(aInt: -123, aStr: "String!") }', "Source!") == (
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

        def execute(source, root_value=None):
            return graphql_sync(schema=schema, source=source, root_value=root_value)

        assert execute("{ test }") == ({"test": "[None, {}]"}, None)

        assert execute("{ test }", "Source!") == ({"test": "['Source!', {}]"}, None,)

        assert execute('{ test(aStr: "String!") }', "Source!") == (
            {"test": "['Source!', {'a_str': 'String!'}]"},
            None,
        )

        assert execute('{ test(aInt: -123, aStr: "String!") }', "Source!") == (
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

        def execute(source, root_value=None):
            return graphql_sync(schema=schema, source=source, root_value=root_value,)

        assert execute("{ test }") == ({"test": "[None, {}]"}, None)

        assert execute('{ test(aInput: {inputOne: "String!"}) }', "Source!") == (
            {"test": "['Source!', {'a_input': {'input_one': 'String!'}}]"},
            None,
        )

        assert execute(
            '{ test(aInput: {inputRecursive: {inputOne: "SourceRecursive!"}}) }',
            "Source!",
        ) == (
            {
                "test": "['Source!',"
                " {'a_input': {'input_recursive': {'input_one': 'SourceRecursive!'}}}]"
            },
            None,
        )
