from pytest import raises

from graphql import graphql_sync
from graphql.pyutils import dedent
from graphql.type import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLFloat,
    GraphQLID,
    GraphQLInt,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)
from graphql.utilities import (
    build_schema,
    build_client_schema,
    introspection_from_schema,
    print_schema,
)


def cycle_introspection(sdl_string):
    """Test that the client side introspection gives the same result.

    This function does a full cycle of going from a string with the contents of the SDL,
    build in-memory GraphQLSchema from it, produce a client-side representation of the
    schema by using "build_client_schema" and then finally printing that that schema
    into the SDL.
    """
    server_schema = build_schema(sdl_string)
    initial_introspection = introspection_from_schema(server_schema)
    client_schema = build_client_schema(initial_introspection)
    # If the client then runs the introspection query against the client-side schema,
    # it should get a result identical to what was returned by the server
    second_introspection = introspection_from_schema(client_schema)
    assert initial_introspection == second_introspection
    return print_schema(client_schema)


def describe_type_system_build_schema_from_introspection():
    def builds_a_simple_schema():
        sdl = dedent(
            '''
            schema {
              query: Simple
            }

            """This is simple type"""
            type Simple {
              """This is a string field"""
              string: String
            }
            '''
        )

        assert cycle_introspection(sdl) == sdl

    def builds_a_simple_schema_with_all_operation_types():
        sdl = dedent(
            '''
            schema {
              query: QueryType
              mutation: MutationType
              subscription: SubscriptionType
            }

            """This is a simple mutation type"""
            type MutationType {
              """Set the string field"""
              string: String
            }

            """This is a simple query type"""
            type QueryType {
              """This is a string field"""
              string: String
            }

            """This is a simple subscription type"""
            type SubscriptionType {
              """This is a string field"""
              string: String
            }
            '''
        )

        assert cycle_introspection(sdl) == sdl

    def uses_built_in_scalars_when_possible():
        sdl = dedent(
            """
            scalar CustomScalar

            type Query {
              int: Int
              float: Float
              string: String
              boolean: Boolean
              id: ID
              custom: CustomScalar
            }
            """
        )

        assert cycle_introspection(sdl) == sdl

        schema = build_schema(sdl)
        introspection = introspection_from_schema(schema)
        client_schema = build_client_schema(introspection)

        # Built-ins are used
        assert client_schema.get_type("Int") is GraphQLInt
        assert client_schema.get_type("Float") is GraphQLFloat
        assert client_schema.get_type("String") is GraphQLString
        assert client_schema.get_type("Boolean") is GraphQLBoolean
        assert client_schema.get_type("ID") is GraphQLID

        # Custom are built
        custom_scalar = schema.get_type("CustomScalar")
        assert client_schema.get_type("CustomScalar") is not custom_scalar

    def builds_a_schema_with_a_recursive_type_reference():
        sdl = dedent(
            """
            schema {
              query: Recur
            }

            type Recur {
              recur: Recur
            }
            """
        )

        assert cycle_introspection(sdl) == sdl

    def builds_a_schema_with_a_circular_type_reference():
        sdl = dedent(
            """
            type Dog {
              bestFriend: Human
            }

            type Human {
              bestFriend: Dog
            }

            type Query {
              dog: Dog
              human: Human
            }
            """
        )

        assert cycle_introspection(sdl) == sdl

    def builds_a_schema_with_an_interface():
        sdl = dedent(
            '''
            type Dog implements Friendly {
              bestFriend: Friendly
            }

            interface Friendly {
              """The best friend of this friendly thing"""
              bestFriend: Friendly
            }

            type Human implements Friendly {
              bestFriend: Friendly
            }

            type Query {
              friendly: Friendly
            }
            '''
        )

        assert cycle_introspection(sdl) == sdl

    def builds_a_schema_with_an_implicit_interface():
        sdl = dedent(
            '''
            type Dog implements Friendly {
              bestFriend: Friendly
            }

            interface Friendly {
              """The best friend of this friendly thing"""
              bestFriend: Friendly
            }

            type Query {
              dog: Dog
            }
            '''
        )

        assert cycle_introspection(sdl) == sdl

    def builds_a_schema_with_a_union():
        sdl = dedent(
            """
            type Dog {
              bestFriend: Friendly
            }

            union Friendly = Dog | Human

            type Human {
              bestFriend: Friendly
            }

            type Query {
              friendly: Friendly
            }
            """
        )

        assert cycle_introspection(sdl) == sdl

    def builds_a_schema_with_complex_field_values():
        sdl = dedent(
            """
            type Query {
              string: String
              listOfString: [String]
              nonNullString: String!
              nonNullListOfString: [String]!
              nonNullListOfNonNullString: [String!]!
            }
            """
        )

        assert cycle_introspection(sdl) == sdl

    def builds_a_schema_with_field_arguments():
        sdl = dedent(
            '''
            type Query {
              """A field with a single arg"""
              one(
                """This is an int arg"""
                intArg: Int
              ): String

              """A field with a two args"""
              two(
                """This is an list of int arg"""
                listArg: [Int]

                """This is a required arg"""
                requiredArg: Boolean!
              ): String
            }
            '''
        )

        assert cycle_introspection(sdl) == sdl

    def builds_a_schema_with_default_value_on_custom_scalar_field():
        sdl = dedent(
            """
            scalar CustomScalar

            type Query {
              testField(testArg: CustomScalar = "default"): String
            }
            """
        )

        assert cycle_introspection(sdl) == sdl

    def builds_a_schema_with_an_enum():
        food_enum = GraphQLEnumType(
            "Food",
            {
                "VEGETABLES": GraphQLEnumValue(
                    1, description="Foods that are vegetables."
                ),
                "FRUITS": GraphQLEnumValue(2, description="Foods that are fruits."),
                "OILS": GraphQLEnumValue(3, description="Foods that are oils."),
                "DAIRY": GraphQLEnumValue(4, description="Foods that are dairy."),
                "MEAT": GraphQLEnumValue(5, description="Foods that are meat."),
            },
            description="Varieties of food stuffs",
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "EnumFields",
                {
                    "food": GraphQLField(
                        food_enum,
                        args={
                            "kind": GraphQLArgument(
                                food_enum, description="what kind of food?"
                            )
                        },
                        description="Repeats the arg you give it",
                    )
                },
            )
        )

        introspection = introspection_from_schema(schema)
        client_schema = build_client_schema(introspection)
        second_introspection = introspection_from_schema(client_schema)
        assert second_introspection == introspection

        client_food_enum = client_schema.get_type("Food")

        # It's also an Enum type on the client.
        assert isinstance(client_food_enum, GraphQLEnumType)

        values = client_food_enum.values
        descriptions = {name: value.description for name, value in values.items()}
        assert descriptions == {
            "VEGETABLES": "Foods that are vegetables.",
            "FRUITS": "Foods that are fruits.",
            "OILS": "Foods that are oils.",
            "DAIRY": "Foods that are dairy.",
            "MEAT": "Foods that are meat.",
        }
        values = values.values()
        assert all(value.value is None for value in values)
        assert all(value.is_deprecated is False for value in values)
        assert all(value.deprecation_reason is None for value in values)
        assert all(value.ast_node is None for value in values)

    def builds_a_schema_with_an_input_object():
        sdl = dedent(
            '''
            """An input address"""
            input Address {
              """What street is this address?"""
              street: String!

              """The city the address is within?"""
              city: String!

              """The country (blank will assume USA)."""
              country: String = "USA"
            }

            type Query {
              """Get a geocode from an address"""
              geocode(
                """The address to lookup"""
                address: Address
              ): String
            }
            '''
        )

        assert cycle_introspection(sdl) == sdl

    def builds_a_schema_with_field_arguments_with_default_values():
        sdl = dedent(
            """
            input Geo {
              lat: Float
              lon: Float
            }

            type Query {
              defaultInt(intArg: Int = 30): String
              defaultList(listArg: [Int] = [1, 2, 3]): String
              defaultObject(objArg: Geo = {lat: 37.485, lon: -122.148}): String
              defaultNull(intArg: Int = null): String
              noDefault(intArg: Int): String
            }
            """
        )

        assert cycle_introspection(sdl) == sdl

    def builds_a_schema_with_custom_directives():
        sdl = dedent(
            '''
            """This is a custom directive"""
            directive @customDirective on FIELD

            type Query {
              string: String
            }
            '''
        )

        assert cycle_introspection(sdl) == sdl

    def builds_a_schema_aware_of_deprecation():
        sdl = dedent(
            '''
            enum Color {
              """So rosy"""
              RED

              """So grassy"""
              GREEN

              """So calming"""
              BLUE

              """So sickening"""
              MAUVE @deprecated(reason: "No longer in fashion")
            }

            type Query {
              """This is a shiny string field"""
              shinyString: String

              """This is a deprecated string field"""
              deprecatedString: String @deprecated(reason: "Use shinyString")
              color: Color
            }
            '''
        )

        assert cycle_introspection(sdl) == sdl

    def can_use_client_schema_for_limited_execution():
        schema = build_schema(
            """
            scalar CustomScalar

            type Query {
              foo(custom1: CustomScalar, custom2: CustomScalar): String
            }
            """
        )

        introspection = introspection_from_schema(schema)
        client_schema = build_client_schema(introspection)

        class Data:
            foo = "bar"
            unused = "value"

        result = graphql_sync(
            client_schema,
            "query Limited($v: CustomScalar) { foo(custom1: 123, custom2: $v) }",
            Data(),
            variable_values={"v": "baz"},
        )

        assert result.data == {"foo": "bar"}


def describe_throws_when_given_incomplete_introspection():
    def throws_when_given_empty_types():
        incomplete_introspection = {
            "__schema": {"queryType": {"name": "QueryType"}, "types": []}
        }

        with raises(TypeError) as exc_info:
            build_client_schema(incomplete_introspection)

        assert str(exc_info.value) == (
            "Invalid or incomplete schema, unknown type: QueryType."
            " Ensure that a full introspection query is used"
            " in order to build a client schema."
        )

    def throws_when_missing_kind():
        incomplete_introspection = {
            "__schema": {
                "queryType": {"name": "QueryType"},
                "types": [{"name": "QueryType"}],
            }
        }

        with raises(TypeError) as exc_info:
            build_client_schema(incomplete_introspection)

        assert str(exc_info.value) == (
            "Invalid or incomplete introspection result."
            " Ensure that a full introspection query is used"
            " in order to build a client schema: {'name': 'QueryType'}"
        )

    def throws_when_missing_interfaces():
        null_interface_introspection = {
            "__schema": {
                "queryType": {"name": "QueryType"},
                "types": [
                    {
                        "kind": "OBJECT",
                        "name": "QueryType",
                        "fields": [
                            {
                                "name": "aString",
                                "args": [],
                                "type": {
                                    "kind": "SCALAR",
                                    "name": "String",
                                    "ofType": None,
                                },
                                "isDeprecated": False,
                            }
                        ],
                    }
                ],
            }
        }

        with raises(TypeError) as exc_info:
            build_client_schema(null_interface_introspection)

        assert str(exc_info.value) == (
            "Introspection result missing interfaces:"
            " {'kind': 'OBJECT', 'name': 'QueryType',"
            " 'fields': [{'name': 'aString', 'args': [],"
            " 'type': {'kind': 'SCALAR', 'name': 'String', 'ofType': None},"
            " 'isDeprecated': False}]}"
        )

    def throws_when_missing_directive_locations():
        introspection = {
            "__schema": {"types": [], "directives": [{"name": "test", "args": []}]}
        }

        with raises(TypeError) as exc_info:
            build_client_schema(introspection)

        assert str(exc_info.value) == (
            "Introspection result missing directive locations:"
            " {'name': 'test', 'args': []}"
        )


def describe_very_deep_decorators_are_not_supported():
    def fails_on_very_deep_lists_more_than_7_levels():
        schema = build_schema(
            """
            type Query {
              foo: [[[[[[[[String]]]]]]]]
            }
            """
        )

        introspection = introspection_from_schema(schema)

        with raises(TypeError) as exc_info:
            build_client_schema(introspection)

        assert str(exc_info.value) == (
            "Query fields cannot be resolved:"
            " Decorated type deeper than introspection query."
        )

    def fails_on_a_very_deep_non_null_more_than_7_levels():
        schema = build_schema(
            """
            type Query {
              foo: [[[[String!]!]!]!]
            }
            """
        )

        introspection = introspection_from_schema(schema)

        with raises(TypeError) as exc_info:
            build_client_schema(introspection)

        assert str(exc_info.value) == (
            "Query fields cannot be resolved:"
            " Decorated type deeper than introspection query."
        )

    def succeeds_on_deep_types_less_or_equal_7_levels():
        # e.g., fully non-null 3D matrix
        sdl = dedent(
            """
            type Query {
              foo: [[[String!]!]!]!
            }
            """
        )

        assert cycle_introspection(sdl) == sdl

    def describe_prevents_infinite_recursion_on_invalid_introspection():
        def recursive_interfaces():
            introspection = {
                "__schema": {
                    "types": [
                        {
                            "name": "Foo",
                            "kind": "OBJECT",
                            "fields": [],
                            "interfaces": [{"name": "Foo"}],
                        }
                    ]
                }
            }
            with raises(TypeError) as exc_info:
                build_client_schema(introspection)
            assert str(exc_info.value) == (
                "Foo interfaces cannot be resolved: "
                "Expected Foo to be a GraphQL Interface type."
            )

        def recursive_union():
            introspection = {
                "__schema": {
                    "types": [
                        {
                            "name": "Foo",
                            "kind": "UNION",
                            "possibleTypes": [{"name": "Foo"}],
                        }
                    ]
                }
            }
            with raises(TypeError) as exc_info:
                build_client_schema(introspection)
            assert str(exc_info.value) == (
                "Foo types cannot be resolved: "
                "Expected Foo to be a GraphQL Object type."
            )
