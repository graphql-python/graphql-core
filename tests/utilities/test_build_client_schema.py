from typing import TYPE_CHECKING, cast

import pytest

from graphql import graphql_sync
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
    build_client_schema,
    build_schema,
    introspection_from_schema,
    print_schema,
)

if TYPE_CHECKING:
    from graphql.utilities.get_introspection_query import (
        IntrospectionEnumType,
        IntrospectionInputObjectType,
        IntrospectionInterfaceType,
        IntrospectionObjectType,
        IntrospectionType,
        IntrospectionUnionType,
    )

from ..utils import dedent


def cycle_introspection(sdl_string: str):
    """Test that the client side introspection gives the same result.

    This function does a full cycle of going from a string with the contents of the SDL,
    build in-memory GraphQLSchema from it, produce a client-side representation of the
    schema by using "build_client_schema" and then return that schema printed as SDL.
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
            """Simple schema"""
            schema {
              query: Simple
            }

            """This is a simple type"""
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
        del introspection["__schema"]["queryType"]  # type: ignore

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

    def includes_standard_types_only_if_they_are_used():
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

    def builds_a_schema_with_an_interface_hierarchy():
        sdl = dedent(
            '''
            type Dog implements Friendly & Named {
              bestFriend: Friendly
              name: String
            }

            interface Friendly implements Named {
              """The best friend of this friendly thing"""
              bestFriend: Friendly
              name: String
            }

            type Human implements Friendly & Named {
              bestFriend: Friendly
              name: String
            }

            interface Named {
              name: String
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
                """This is a list of int arg"""
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
                "FRUITS": GraphQLEnumValue(2),
                "OILS": GraphQLEnumValue(3, deprecation_reason="Too fatty."),
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

        # Client types do not get server-only values, so the values mirror the names,
        # rather than using the integers defined in the "server" schema.
        values = {
            name: value.to_kwargs() for name, value in client_food_enum.values.items()
        }
        assert values == {
            "VEGETABLES": {
                "value": "VEGETABLES",
                "description": "Foods that are vegetables.",
                "deprecation_reason": None,
                "extensions": {},
                "ast_node": None,
            },
            "FRUITS": {
                "value": "FRUITS",
                "description": None,
                "deprecation_reason": None,
                "extensions": {},
                "ast_node": None,
            },
            "OILS": {
                "value": "OILS",
                "description": None,
                "deprecation_reason": "Too fatty.",
                "extensions": {},
                "ast_node": None,
            },
        }

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
              defaultObject(objArg: Geo = { lat: 37.485, lon: -122.148 }): String
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
            directive @customDirective repeatable on FIELD

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
        del introspection["__schema"]["directives"]  # type: ignore

        client_schema = build_client_schema(introspection)

        assert schema.directives
        assert client_schema.directives == ()
        assert print_schema(client_schema) == sdl

    def builds_a_schema_aware_of_deprecation():
        sdl = dedent(
            '''
            directive @someDirective(
              """This is a shiny new argument"""
              shinyArg: SomeInputObject

              """This was our design mistake :("""
              oldArg: String @deprecated(reason: "Use shinyArg")
            ) on QUERY

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

            input SomeInputObject {
              """Nothing special about it, just deprecated for some unknown reason"""
              oldField: String @deprecated(reason: "Don't use it, use newField instead!")

              """Same field but with a new name"""
              newField: String
            }

            type Query {
              """This is a shiny string field"""
              shinyString: String

              """This is a deprecated string field"""
              deprecatedString: String @deprecated(reason: "Use shinyString")

              """Color of a week"""
              color: Color

              """Some random field"""
              someField(
                """This is a shiny new argument"""
                shinyArg: SomeInputObject

                """This was our design mistake :("""
                oldArg: String @deprecated(reason: "Use shinyArg")
              ): String
            }
            '''  # noqa: E501
        )

        assert cycle_introspection(sdl) == sdl

    def builds_a_schema_with_empty_deprecation_reasons():
        sdl = dedent(
            """
            directive @someDirective(someArg: SomeInputObject @deprecated(reason: "")) on QUERY

            type Query {
              someField(someArg: SomeInputObject @deprecated(reason: "")): SomeEnum @deprecated(reason: "")
            }

            input SomeInputObject {
              someInputField: String @deprecated(reason: "")
            }

            enum SomeEnum {
              SOME_VALUE @deprecated(reason: "")
            }
            """  # noqa: E501
        )

        assert cycle_introspection(sdl) == sdl

    def builds_a_schema_with_specified_by_url():
        sdl = dedent(
            """
            scalar Foo @specifiedBy(url: "https://example.com/foo_spec")

            type Query {
              foo: Foo
            }
            """
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

    def can_build_invalid_schema():
        schema = build_schema("type Query", assume_valid=True)

        introspection = introspection_from_schema(schema)
        client_schema = build_client_schema(introspection, assume_valid=True)

        assert client_schema.to_kwargs()["assume_valid"] is True

    def describe_throws_when_given_invalid_introspection():
        dummy_schema = build_schema(
            """
            type Query {
              foo(bar: String): String
            }

            interface SomeInterface {
              foo: String
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
            with pytest.raises(TypeError) as exc_info:
                # noinspection PyTypeChecker
                build_client_schema(None)  # type: ignore

            assert str(exc_info.value) == (
                "Invalid or incomplete introspection result. Ensure that you"
                " are passing the 'data' attribute of an introspection response"
                " and no 'errors' were returned alongside: None."
            )

            with pytest.raises(TypeError) as exc_info:
                # noinspection PyTypeChecker
                build_client_schema({})  # type: ignore

            assert str(exc_info.value) == (
                "Invalid or incomplete introspection result. Ensure that you"
                " are passing the 'data' attribute of an introspection response"
                " and no 'errors' were returned alongside: {}."
            )

        def throws_when_referenced_unknown_type():
            introspection = introspection_from_schema(dummy_schema)

            introspection["__schema"]["types"] = [
                type_
                for type_ in introspection["__schema"]["types"]
                if type_["name"] != "Query"
            ]

            with pytest.raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value) == (
                "Invalid or incomplete schema, unknown type: Query."
                " Ensure that a full introspection query is used"
                " in order to build a client schema."
            )

        def throws_when_missing_definition_for_one_of_the_standard_scalars():
            schema = build_schema(
                """
                type Query {
                  foo: Float
                }
                """
            )
            introspection = introspection_from_schema(schema)
            introspection["__schema"]["types"] = [
                type_
                for type_ in introspection["__schema"]["types"]
                if type_["name"] != "Float"
            ]

            with pytest.raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value).endswith(
                "Invalid or incomplete schema, unknown type: Float."
                " Ensure that a full introspection query is used"
                " in order to build a client schema."
            )

        def throws_when_type_reference_is_missing_name():
            introspection = introspection_from_schema(dummy_schema)
            query_type = cast(
                "IntrospectionType", introspection["__schema"]["queryType"]
            )
            assert query_type["name"] == "Query"
            del query_type["name"]  # type: ignore

            with pytest.raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value) == "Unknown type reference: {}."

        def throws_when_missing_kind():
            introspection = introspection_from_schema(dummy_schema)
            query_type_introspection = next(
                type_
                for type_ in introspection["__schema"]["types"]
                if type_["name"] == "Query"
            )
            assert query_type_introspection["kind"] == "OBJECT"
            del query_type_introspection["kind"]

            with pytest.raises(
                TypeError,
                match=r"^Invalid or incomplete introspection result\."
                " Ensure that a full introspection query is used"
                r" in order to build a client schema: {'name': 'Query', .*}\.$",
            ):
                build_client_schema(introspection)

        def throws_when_missing_interfaces():
            introspection = introspection_from_schema(dummy_schema)
            query_type_introspection = cast(
                "IntrospectionObjectType",
                next(
                    type_
                    for type_ in introspection["__schema"]["types"]
                    if type_["name"] == "Query"
                ),
            )

            assert query_type_introspection["interfaces"] == []
            del query_type_introspection["interfaces"]  # type: ignore

            with pytest.raises(
                TypeError,
                match="^Query interfaces cannot be resolved."
                " Introspection result missing interfaces:"
                r" {'kind': 'OBJECT', 'name': 'Query', .*}\.$",
            ):
                build_client_schema(introspection)

        def legacy_support_for_interfaces_with_null_as_interfaces_field():
            introspection = introspection_from_schema(dummy_schema)
            some_interface_introspection = cast(
                "IntrospectionInterfaceType",
                next(
                    type_
                    for type_ in introspection["__schema"]["types"]
                    if type_["name"] == "SomeInterface"
                ),
            )

            assert some_interface_introspection["interfaces"] == []
            some_interface_introspection["interfaces"] = None  # type: ignore

            client_schema = build_client_schema(introspection)
            assert print_schema(client_schema) == print_schema(dummy_schema)

        def throws_when_missing_fields():
            introspection = introspection_from_schema(dummy_schema)
            query_type_introspection = cast(
                "IntrospectionObjectType",
                next(
                    type_
                    for type_ in introspection["__schema"]["types"]
                    if type_["name"] == "Query"
                ),
            )

            assert query_type_introspection["fields"]
            del query_type_introspection["fields"]  # type: ignore

            with pytest.raises(
                TypeError,
                match="^Query fields cannot be resolved."
                " Introspection result missing fields:"
                r" {'kind': 'OBJECT', 'name': 'Query', .*}\.$",
            ):
                build_client_schema(introspection)

        def throws_when_missing_field_args():
            introspection = introspection_from_schema(dummy_schema)
            query_type_introspection = cast(
                "IntrospectionObjectType",
                next(
                    type_
                    for type_ in introspection["__schema"]["types"]
                    if type_["name"] == "Query"
                ),
            )

            field = query_type_introspection["fields"][0]
            assert field["args"]
            del field["args"]  # type: ignore

            with pytest.raises(
                TypeError,
                match="^Query fields cannot be resolved."
                r" Introspection result missing field args: {'name': 'foo', .*}\.$",
            ):
                build_client_schema(introspection)

        def throws_when_output_type_is_used_as_an_arg_type():
            introspection = introspection_from_schema(dummy_schema)
            query_type_introspection = cast(
                "IntrospectionObjectType",
                next(
                    type_
                    for type_ in introspection["__schema"]["types"]
                    if type_["name"] == "Query"
                ),
            )

            arg = query_type_introspection["fields"][0]["args"][0]
            assert arg["type"]["name"] == "String"
            arg["type"]["name"] = "SomeUnion"

            with pytest.raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value).startswith(
                "Query fields cannot be resolved."
                " Introspection must provide input type for arguments,"
                " but received: SomeUnion."
            )

        def throws_when_output_type_is_used_as_an_input_value_type():
            introspection = introspection_from_schema(dummy_schema)
            input_object_type_introspection = cast(
                "IntrospectionInputObjectType",
                next(
                    type_
                    for type_ in introspection["__schema"]["types"]
                    if type_["name"] == "SomeInputObject"
                ),
            )

            input_field = input_object_type_introspection["inputFields"][0]
            assert input_field["type"]["name"] == "String"
            input_field["type"]["name"] = "SomeUnion"

            with pytest.raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value).startswith(
                "SomeInputObject fields cannot be resolved."
                " Introspection must provide input type for input fields,"
                " but received: SomeUnion."
            )

        def throws_when_input_type_is_used_as_a_field_type():
            introspection = introspection_from_schema(dummy_schema)
            query_type_introspection = cast(
                "IntrospectionObjectType",
                next(
                    type_
                    for type_ in introspection["__schema"]["types"]
                    if type_["name"] == "Query"
                ),
            )

            field = query_type_introspection["fields"][0]
            assert field["type"]["name"] == "String"
            field["type"]["name"] = "SomeInputObject"

            with pytest.raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value).startswith(
                "Query fields cannot be resolved."
                " Introspection must provide output type for fields,"
                " but received: SomeInputObject."
            )

        def throws_when_missing_possible_types():
            introspection = introspection_from_schema(dummy_schema)
            some_union_introspection = cast(
                "IntrospectionUnionType",
                next(
                    type_
                    for type_ in introspection["__schema"]["types"]
                    if type_["name"] == "SomeUnion"
                ),
            )

            assert some_union_introspection["possibleTypes"]
            del some_union_introspection["possibleTypes"]  # type: ignore

            with pytest.raises(
                TypeError,
                match="^Introspection result missing possibleTypes:"
                r" {'kind': 'UNION', 'name': 'SomeUnion', .*}\.$",
            ):
                build_client_schema(introspection)

        def throws_when_missing_enum_values():
            introspection = introspection_from_schema(dummy_schema)
            some_enum_introspection = cast(
                "IntrospectionEnumType",
                next(
                    type_
                    for type_ in introspection["__schema"]["types"]
                    if type_["name"] == "SomeEnum"
                ),
            )

            assert some_enum_introspection["enumValues"]
            del some_enum_introspection["enumValues"]  # type: ignore

            with pytest.raises(
                TypeError,
                match="^Introspection result missing enumValues:"
                r" {'kind': 'ENUM', 'name': 'SomeEnum', .*}\.$",
            ):
                build_client_schema(introspection)

        def throws_when_missing_input_fields():
            introspection = introspection_from_schema(dummy_schema)
            some_input_object_introspection = cast(
                "IntrospectionInputObjectType",
                next(
                    type_
                    for type_ in introspection["__schema"]["types"]
                    if type_["name"] == "SomeInputObject"
                ),
            )

            assert some_input_object_introspection["inputFields"]
            del some_input_object_introspection["inputFields"]  # type: ignore

            with pytest.raises(
                TypeError,
                match="^Introspection result missing inputFields:"
                r" {'kind': 'INPUT_OBJECT', 'name': 'SomeInputObject', .*}\.$",
            ):
                build_client_schema(introspection)

        def throws_when_missing_directive_locations():
            introspection = introspection_from_schema(dummy_schema)
            some_directive_introspection = introspection["__schema"]["directives"][0]

            assert some_directive_introspection["name"] == "SomeDirective"
            assert some_directive_introspection["locations"] == ["QUERY"]
            del some_directive_introspection["locations"]  # type: ignore

            with pytest.raises(
                TypeError,
                match="^Introspection result missing directive locations:"
                r" {'name': 'SomeDirective', .*}\.$",
            ):
                build_client_schema(introspection)

        def throws_when_missing_directive_args():
            introspection = introspection_from_schema(dummy_schema)
            some_directive_introspection = introspection["__schema"]["directives"][0]

            assert some_directive_introspection["name"] == "SomeDirective"
            assert some_directive_introspection["args"] == []
            del some_directive_introspection["args"]  # type: ignore

            with pytest.raises(
                TypeError,
                match="^Introspection result missing directive args:"
                r" {'name': 'SomeDirective', .*}\.$",
            ):
                build_client_schema(introspection)

    def describe_very_deep_decorators_are_not_supported():
        def fails_on_very_deep_lists_more_than_8_levels():
            schema = build_schema(
                """
                type Query {
                  foo: [[[[[[[[[[String]]]]]]]]]]
                }
                """
            )

            introspection = introspection_from_schema(schema)

            with pytest.raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value) == (
                "Query fields cannot be resolved."
                " Decorated type deeper than introspection query."
            )

        def fails_on_a_very_deep_more_than_8_levels_non_null():
            schema = build_schema(
                """
                type Query {
                  foo: [[[[[String!]!]!]!]!]
                }
                """
            )

            introspection = introspection_from_schema(schema)

            with pytest.raises(TypeError) as exc_info:
                build_client_schema(introspection)

            assert str(exc_info.value) == (
                "Query fields cannot be resolved."
                " Decorated type deeper than introspection query."
            )

        def succeeds_on_deep_less_or_equal_8_levels_types():
            # e.g., fully non-null 4D matrix
            sdl = dedent(
                """
                type Query {
                  foo: [[[[String!]!]!]!]!
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
            foo_introspection = cast(
                "IntrospectionObjectType",
                next(
                    type_
                    for type_ in introspection["__schema"]["types"]
                    if type_["name"] == "Foo"
                ),
            )

            assert foo_introspection["interfaces"] == []
            # we need to patch here since invalid interfaces cannot be built with Python
            foo_introspection["interfaces"] = [
                {"kind": "OBJECT", "name": "Foo", "ofType": None}
            ]

            with pytest.raises(TypeError) as exc_info:
                build_client_schema(introspection)
            assert str(exc_info.value) == (
                "Foo interfaces cannot be resolved."
                " Expected Foo to be a GraphQL Interface type."
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
            foo_introspection = next(
                type_
                for type_ in introspection["__schema"]["types"]
                if type_["name"] == "Foo"
            )

            assert foo_introspection["kind"] == "UNION"
            assert foo_introspection["possibleTypes"] == []
            # we need to patch here since invalid unions cannot be built with Python
            foo_introspection["possibleTypes"] = [
                {"kind": "UNION", "name": "Foo", "ofType": None}
            ]

            with pytest.raises(TypeError) as exc_info:
                build_client_schema(introspection)
            assert str(exc_info.value) == (
                "Foo types cannot be resolved."
                " Expected Foo to be a GraphQL Object type."
            )
