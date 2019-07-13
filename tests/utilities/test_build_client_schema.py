from pytest import raises  # type: ignore

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
    assert_enum_type,
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

    # If the client then runs the introspection query against the client-side
    # schema, it should get a result identical to what was returned by the server.
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

    def builds_a_schema_without_the_query_type():
        sdl = dedent(
            """
            type Query {
              foo: String
            }
            """
        )

        schema = build_schema(sdl)
        introspection = introspection_from_schema(schema)
        del introspection["__schema"]["queryType"]

        client_schema = build_client_schema(introspection)
        assert client_schema.query_type is None
        assert print_schema(client_schema) == sdl

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

    def include_standard_type_only_if_it_is_used():
        schema = build_schema(
            """
            type Query {
              foo: String
            }
            """
        )
        introspection = introspection_from_schema(schema)
        client_schema = build_client_schema(introspection)

        assert client_schema.get_type("Int") is None
        assert client_schema.get_type("Float") is None
        assert client_schema.get_type("ID") is None

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

        # It's also an Enum type on the client.
        client_food_enum = assert_enum_type(client_schema.get_type("Food"))

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

    def builds_a_schema_without_directives():
        sdl = dedent(
            """
            type Query {
              foo: String
            }
            """
        )

        schema = build_schema(sdl)
        introspection = introspection_from_schema(schema)
        del introspection["__schema"]["directives"]

        client_schema = build_client_schema(introspection)

        assert schema.directives
        assert client_schema.directives == []
        assert print_schema(client_schema) == sdl

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
            root_value=Data(),
            variable_values={"v": "baz"},
        )

        assert result.data == {"foo": "bar"}

    def describe_throws_when_given_invalid_introspection():
        dummy_schema = build_schema(
            """
            type Query {
              foo(bar: String): String
            }

            union SomeUnion = Query

            enum SomeEnum { FOO }

            input SomeInputObject {
              foo: String
            }

            directive @SomeDirective on QUERY
            """
        )

        def throws_when_introspection_is_missing_schema_property():
            with raises(TypeError) as exc_info:
                # noinspection PyTypeChecker
                build_client_schema(None)

            assert str(exc_info.value) == (
                "Invalid or incomplete introspection result. Ensure that you"
                " are passing the 'data' attribute of an introspection response"
                " and no 'errors' were returned alongside: None"
            )

            with raises(TypeError) as exc_info:
                # noinspection PyTypeChecker
                build_client_schema({})

            assert str(exc_info.value) == (
                "Invalid or incomplete introspection result. Ensure that you"
                " are passing the 'data' attribute of an introspection response"
                " and no 'errors' were returned alongside: {}"
            )

        def throws_when_referenced_unknown_type():
            introspection = introspection_from_schema(dummy_schema)

            introspection["__schema"]["types"] = [
                type_
                for type_ in introspection["__schema"]["types"]
                if type_["name"] != "Query"
            ]

            with raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value) == (
                "Invalid or incomplete schema, unknown type: Query."
                " Ensure that a full introspection query is used"
                " in order to build a client schema."
            )

        def throws_when_type_reference_is_missing_name():
            introspection = introspection_from_schema(dummy_schema)

            assert introspection["__schema"]["queryType"]["name"] == "Query"
            del introspection["__schema"]["queryType"]["name"]

            with raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value) == "Unknown type reference: {}"

        def throws_when_missing_kind():
            introspection = introspection_from_schema(dummy_schema)

            query_type_introspection = [
                type_
                for type_ in introspection["__schema"]["types"]
                if type_["name"] == "Query"
            ][0]
            assert query_type_introspection["kind"] == "OBJECT"
            del query_type_introspection["kind"]

            with raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value).startswith(
                "Invalid or incomplete introspection result."
                " Ensure that a full introspection query is used"
                " in order to build a client schema: {'name': 'Query',"
            )

        def throws_when_missing_interfaces():
            introspection = introspection_from_schema(dummy_schema)

            query_type_introspection = [
                type_
                for type_ in introspection["__schema"]["types"]
                if type_["name"] == "Query"
            ][0]
            assert query_type_introspection["interfaces"] == []
            del query_type_introspection["interfaces"]

            with raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value).startswith(
                "Introspection result missing interfaces:"
                " {'kind': 'OBJECT', 'name': 'Query',"
            )

        def throws_when_missing_fields():
            introspection = introspection_from_schema(dummy_schema)

            query_type_introspection = [
                type_
                for type_ in introspection["__schema"]["types"]
                if type_["name"] == "Query"
            ][0]
            assert query_type_introspection["fields"]
            del query_type_introspection["fields"]

            with raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value).startswith(
                "Query fields cannot be resolved:"
                " Introspection result missing fields:"
                " {'kind': 'OBJECT', 'name': 'Query',"
            )

        def throws_when_missing_field_args():
            introspection = introspection_from_schema(dummy_schema)

            query_type_introspection = [
                type_
                for type_ in introspection["__schema"]["types"]
                if type_["name"] == "Query"
            ][0]
            assert query_type_introspection["fields"][0]["args"]
            del query_type_introspection["fields"][0]["args"]

            with raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value).startswith(
                "Query fields cannot be resolved:"
                " Introspection result missing field args: {'name': 'foo',"
            )

        def throws_when_output_type_is_used_as_an_arg_type():
            introspection = introspection_from_schema(dummy_schema)

            query_type_introspection = [
                type_
                for type_ in introspection["__schema"]["types"]
                if type_["name"] == "Query"
            ][0]
            assert (
                query_type_introspection["fields"][0]["args"][0]["type"]["name"]
                == "String"
            )
            query_type_introspection["fields"][0]["args"][0]["type"][
                "name"
            ] = "SomeUnion"

            with raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value).startswith(
                "Query fields cannot be resolved:"
                " Introspection must provide input type for arguments,"
                " but received: SomeUnion."
            )

        def throws_when_input_type_is_used_as_a_field_type():
            introspection = introspection_from_schema(dummy_schema)

            query_type_introspection = [
                type_
                for type_ in introspection["__schema"]["types"]
                if type_["name"] == "Query"
            ][0]
            assert query_type_introspection["fields"][0]["type"]["name"] == "String"
            query_type_introspection["fields"][0]["type"]["name"] = "SomeInputObject"

            with raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value).startswith(
                "Query fields cannot be resolved:"
                " Introspection must provide output type for fields,"
                " but received: SomeInputObject."
            )

        def throws_when_missing_possible_types():
            introspection = introspection_from_schema(dummy_schema)

            some_union_introspection = [
                type_
                for type_ in introspection["__schema"]["types"]
                if type_["name"] == "SomeUnion"
            ][0]
            assert some_union_introspection["possibleTypes"]
            del some_union_introspection["possibleTypes"]

            with raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value).startswith(
                "Introspection result missing possibleTypes:"
                " {'kind': 'UNION', 'name': 'SomeUnion',"
            )

        def throws_when_missing_enum_values():
            introspection = introspection_from_schema(dummy_schema)

            some_enum_introspection = [
                type_
                for type_ in introspection["__schema"]["types"]
                if type_["name"] == "SomeEnum"
            ][0]
            assert some_enum_introspection["enumValues"]
            del some_enum_introspection["enumValues"]

            with raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value).startswith(
                "Introspection result missing enumValues:"
                " {'kind': 'ENUM', 'name': 'SomeEnum',"
            )

        def throws_when_missing_input_fields():
            introspection = introspection_from_schema(dummy_schema)

            some_input_object_introspection = [
                type_
                for type_ in introspection["__schema"]["types"]
                if type_["name"] == "SomeInputObject"
            ][0]
            assert some_input_object_introspection["inputFields"]
            del some_input_object_introspection["inputFields"]

            with raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value).startswith(
                "Introspection result missing inputFields:"
                " {'kind': 'INPUT_OBJECT', 'name': 'SomeInputObject',"
            )

        def throws_when_missing_directive_locations():
            introspection = introspection_from_schema(dummy_schema)

            some_directive_introspection = introspection["__schema"]["directives"][0]
            assert some_directive_introspection["name"] == "SomeDirective"
            assert some_directive_introspection["locations"] == ["QUERY"]
            del some_directive_introspection["locations"]

            with raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value).startswith(
                "Introspection result missing directive locations:"
                " {'name': 'SomeDirective',"
            )

        def throws_when_missing_directive_args():
            introspection = introspection_from_schema(dummy_schema)

            some_directive_introspection = introspection["__schema"]["directives"][0]
            assert some_directive_introspection["name"] == "SomeDirective"
            assert some_directive_introspection["args"] == []
            del some_directive_introspection["args"]

            with raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value).startswith(
                "Introspection result missing directive args:"
                " {'name': 'SomeDirective',"
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
            sdl = """
                type Query {
                  foo: Foo
                }

                type Foo {
                  foo: String
                }
                """
            schema = build_schema(sdl, assume_valid=True)
            introspection = introspection_from_schema(schema)

            foo_type_introspection = introspection["__schema"]["types"][1]
            assert foo_type_introspection["name"] == "Foo"
            assert foo_type_introspection["interfaces"] == []
            # we need to patch here since invalid interfaces cannot be built with Python
            foo_type_introspection["interfaces"] = [
                {"kind": "OBJECT", "name": "Foo", "ofType": None}
            ]

            with raises(TypeError) as exc_info:
                build_client_schema(introspection)
            assert str(exc_info.value) == (
                "Foo interfaces cannot be resolved: "
                "Expected Foo to be a GraphQL Interface type."
            )

        def recursive_union():
            sdl = """
                type Query {
                  foo: Foo
                }

                union Foo
                """
            schema = build_schema(sdl, assume_valid=True)
            introspection = introspection_from_schema(schema)

            foo_type_introspection = introspection["__schema"]["types"][1]
            assert foo_type_introspection["name"] == "Foo"
            assert foo_type_introspection["kind"] == "UNION"
            assert foo_type_introspection["possibleTypes"] == []
            # we need to patch here since invalid unions cannot be built with Python
            foo_type_introspection["possibleTypes"] = [
                {"kind": "UNION", "name": "Foo", "ofType": None}
            ]

            with raises(TypeError) as exc_info:
                build_client_schema(introspection)
            assert str(exc_info.value) == (
                "Foo types cannot be resolved:"
                " Expected Foo to be a GraphQL Object type."
            )
