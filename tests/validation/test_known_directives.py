from functools import partial

from graphql.utilities import build_schema
from graphql.validation import KnownDirectivesRule
from graphql.validation.rules.known_directives import (
    unknown_directive_message,
    misplaced_directive_message,
)

from .harness import assert_validation_errors, assert_sdl_validation_errors

assert_errors = partial(assert_validation_errors, KnownDirectivesRule)

assert_valid = partial(assert_errors, errors=[])

assert_sdl_errors = partial(assert_sdl_validation_errors, KnownDirectivesRule)

assert_sdl_valid = partial(assert_sdl_errors, errors=[])


def unknown_directive(directive_name, line, column):
    return {
        "message": unknown_directive_message(directive_name),
        "locations": [(line, column)],
    }


def misplaced_directive(directive_name, placement, line, column):
    return {
        "message": misplaced_directive_message(directive_name, placement),
        "locations": [(line, column)],
    }


schema_with_sdl_directives = build_schema(
    """
    directive @onSchema on SCHEMA
    directive @onScalar on SCALAR
    directive @onObject on OBJECT
    directive @onFieldDefinition on FIELD_DEFINITION
    directive @onArgumentDefinition on ARGUMENT_DEFINITION
    directive @onInterface on INTERFACE
    directive @onUnion on UNION
    directive @onEnum on ENUM
    directive @onEnumValue on ENUM_VALUE
    directive @onInputObject on INPUT_OBJECT
    directive @onInputFieldDefinition on INPUT_FIELD_DEFINITION
    """
)


def describe_known_directives():
    def with_no_directives():
        assert_valid(
            """
            query Foo {
              name
              ...Frag
            }

            fragment Frag on Dog {
              name
            }
            """
        )

    def with_known_directives():
        assert_valid(
            """
            {
              dog @include(if: true) {
                name
              }
              human @skip(if: false) {
                name
              }
            }
            """
        )

    def with_unknown_directive():
        assert_errors(
            """
            {
              dog @unknown(directive: "value") {
                name
              }
            }
            """,
            [unknown_directive("unknown", 3, 19)],
        )

    def with_many_unknown_directives():
        assert_errors(
            """
            {
              dog @unknown(directive: "value") {
                name
              }
              human @unknown(directive: "value") {
                name
                pets @unknown(directive: "value") {
                  name
                }
              }
            }
            """,
            [
                unknown_directive("unknown", 3, 19),
                unknown_directive("unknown", 6, 21),
                unknown_directive("unknown", 8, 22),
            ],
        )

    def with_well_placed_directives():
        assert_valid(
            """
            query Foo($var: Boolean) @onQuery {
              name @include(if: $var)
              ...Frag @include(if: true)
              skippedField @skip(if: true)
              ...SkippedFrag @skip(if: true)
            }

            mutation Bar @onMutation {
              someField
            }
            """
        )

    def with_well_placed_variable_definition_directive():
        assert_valid(
            """
            query Foo($var: Boolean @onVariableDefinition) {
              name
            }
            """
        )

    def with_misplaced_directives():
        assert_errors(
            """
            query Foo($var: Boolean) @include(if: true) {
              name @onQuery @include(if: $var)
              ...Frag @onQuery
            }

            mutation Bar @onQuery {
              someField
            }
            """,
            [
                misplaced_directive("include", "query", 2, 38),
                misplaced_directive("onQuery", "field", 3, 20),
                misplaced_directive("onQuery", "fragment spread", 4, 23),
                misplaced_directive("onQuery", "mutation", 7, 26),
            ],
        )

    def with_misplaced_variable_definition_directive():
        assert_errors(
            """
            query Foo($var: Boolean @onField) {
              name
            }
            """,
            [misplaced_directive("onField", "variable definition", 2, 37)],
        )

    def describe_within_sdl():
        def with_directive_defined_inside_sdl():
            assert_sdl_valid(
                """
                type Query {
                  foo: String @test
                }

                directive @test on FIELD_DEFINITION
                """
            )

        def with_standard_directive():
            assert_sdl_valid(
                """
                type Query {
                  foo: String @deprecated
                }
                """
            )

        def with_overridden_standard_directive():
            assert_sdl_valid(
                """
                schema @deprecated {
                  query: Query
                }
                directive @deprecated on SCHEMA
                """
            )

        def with_directive_defined_in_schema_extension():
            schema = build_schema(
                """
                type Query {
                  foo: String
                }
                """
            )
            assert_sdl_valid(
                """
                directive @test on OBJECT

                extend type Query @test
                """,
                schema=schema,
            )

        def with_directive_used_in_schema_extension():
            schema = build_schema(
                """
                directive @test on OBJECT

                type Query {
                  foo: String
                }
                """
            )
            assert_sdl_valid(
                """
                extend type Query @test
                """,
                schema=schema,
            )

        def with_unknown_directive_in_schema_extension():
            schema = build_schema(
                """
                type Query {
                  foo: String
                }
                """
            )
            assert_sdl_errors(
                """
                extend type Query @unknown
                """,
                [unknown_directive("unknown", 2, 35)],
                schema,
            )

        def with_well_placed_directives():
            assert_sdl_valid(
                """
                type MyObj implements MyInterface @onObject {
                  myField(myArg: Int @onArgumentDefinition): String @onFieldDefinition
                }

                extend type MyObj @onObject

                scalar MyScalar @onScalar

                extend scalar MyScalar @onScalar

                interface MyInterface @onInterface {
                  myField(myArg: Int @onArgumentDefinition): String @onFieldDefinition
                }

                extend interface MyInterface @onInterface

                union MyUnion @onUnion = MyObj | Other

                extend union MyUnion @onUnion

                enum MyEnum @onEnum {
                  MY_VALUE @onEnumValue
                }

                extend enum MyEnum @onEnum

                input MyInput @onInputObject {
                  myField: Int @onInputFieldDefinition
                }

                extend input MyInput @onInputObject

                schema @onSchema {
                  query: MyQuery
                }

                extend schema @onSchema
                """,
                schema=schema_with_sdl_directives,
            )

        def with_misplaced_directives():
            assert_sdl_errors(
                """
                type MyObj implements MyInterface @onInterface {
                  myField(myArg: Int @onInputFieldDefinition): String @onInputFieldDefinition
                }

                scalar MyScalar @onEnum

                interface MyInterface @onObject {
                  myField(myArg: Int @onInputFieldDefinition): String @onInputFieldDefinition
                }

                union MyUnion @onEnumValue = MyObj | Other

                enum MyEnum @onScalar {
                  MY_VALUE @onUnion
                }

                input MyInput @onEnum {
                  myField: Int @onArgumentDefinition
                }

                schema @onObject {
                  query: MyQuery
                }

                extend schema @onObject
                """,  # noqa: E501
                [
                    misplaced_directive("onInterface", "object", 2, 51),
                    misplaced_directive(
                        "onInputFieldDefinition", "argument definition", 3, 38
                    ),
                    misplaced_directive(
                        "onInputFieldDefinition", "field definition", 3, 71
                    ),
                    misplaced_directive("onEnum", "scalar", 6, 33),
                    misplaced_directive("onObject", "interface", 8, 39),
                    misplaced_directive(
                        "onInputFieldDefinition", "argument definition", 9, 38
                    ),
                    misplaced_directive(
                        "onInputFieldDefinition", "field definition", 9, 71
                    ),
                    misplaced_directive("onEnumValue", "union", 12, 31),
                    misplaced_directive("onScalar", "enum", 14, 29),
                    misplaced_directive("onUnion", "enum value", 15, 28),
                    misplaced_directive("onEnum", "input object", 18, 31),
                    misplaced_directive(
                        "onArgumentDefinition", "input field definition", 19, 32
                    ),
                    misplaced_directive("onObject", "schema", 22, 24),
                    misplaced_directive("onObject", "schema", 26, 31),
                ],
                schema_with_sdl_directives,
            )
