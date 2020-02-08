from functools import partial

from graphql.utilities import build_schema
from graphql.validation import KnownDirectivesRule

from .harness import assert_validation_errors, assert_sdl_validation_errors

assert_errors = partial(assert_validation_errors, KnownDirectivesRule)

assert_valid = partial(assert_errors, errors=[])

assert_sdl_errors = partial(assert_sdl_validation_errors, KnownDirectivesRule)

assert_sdl_valid = partial(assert_sdl_errors, errors=[])


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
            [{"message": "Unknown directive '@unknown'.", "locations": [(3, 19)]}],
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
                {"message": "Unknown directive '@unknown'.", "locations": [(3, 19)]},
                {"message": "Unknown directive '@unknown'.", "locations": [(6, 21)]},
                {"message": "Unknown directive '@unknown'.", "locations": [(8, 22)]},
            ],
        )

    def with_well_placed_directives():
        assert_valid(
            """
            query ($var: Boolean) @onQuery {
              name @include(if: $var)
              ...Frag @include(if: true)
              skippedField @skip(if: true)
              ...SkippedFrag @skip(if: true)

              ... @skip(if: true) {
                skippedField
              }
            }

            mutation @onMutation {
              someField
            }

            subscription @onSubscription {
              someField
            }

            fragment Frag on SomeType @onFragmentDefinition {
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
                {
                    "message": "Directive '@include' may not be used on query.",
                    "locations": [(2, 38)],
                },
                {
                    "message": "Directive '@onQuery' may not be used on field.",
                    "locations": [(3, 20)],
                },
                {
                    "message": "Directive '@onQuery'"
                    " may not be used on fragment spread.",
                    "locations": [(4, 23)],
                },
                {
                    "message": "Directive '@onQuery' may not be used on mutation.",
                    "locations": [(7, 26)],
                },
            ],
        )

    def with_misplaced_variable_definition_directive():
        assert_errors(
            """
            query Foo($var: Boolean @onField) {
              name
            }
            """,
            [
                {
                    "message": "Directive '@onField'"
                    " may not be used on variable definition.",
                    "locations": [(2, 37)],
                },
            ],
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
                [{"message": "Unknown directive '@unknown'.", "locations": [(2, 35)]}],
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
                    {
                        "message": "Directive '@onInterface'"
                        " may not be used on object.",
                        "locations": [(2, 51)],
                    },
                    {
                        "message": "Directive '@onInputFieldDefinition'"
                        " may not be used on argument definition.",
                        "locations": [(3, 38)],
                    },
                    {
                        "message": "Directive '@onInputFieldDefinition'"
                        " may not be used on field definition.",
                        "locations": [(3, 71)],
                    },
                    {
                        "message": "Directive '@onEnum' may not be used on scalar.",
                        "locations": [(6, 33)],
                    },
                    {
                        "message": "Directive '@onObject'"
                        " may not be used on interface.",
                        "locations": [(8, 39)],
                    },
                    {
                        "message": "Directive '@onInputFieldDefinition'"
                        " may not be used on argument definition.",
                        "locations": [(9, 38)],
                    },
                    {
                        "message": "Directive '@onInputFieldDefinition'"
                        " may not be used on field definition.",
                        "locations": [(9, 71)],
                    },
                    {
                        "message": "Directive '@onEnumValue' may not be used on union.",
                        "locations": [(12, 31)],
                    },
                    {
                        "message": "Directive '@onScalar' may not be used on enum.",
                        "locations": [(14, 29)],
                    },
                    {
                        "message": "Directive '@onUnion'"
                        " may not be used on enum value.",
                        "locations": [(15, 28)],
                    },
                    {
                        "message": "Directive '@onEnum'"
                        " may not be used on input object.",
                        "locations": [(18, 31)],
                    },
                    {
                        "message": "Directive '@onArgumentDefinition'"
                        " may not be used on input field definition.",
                        "locations": [(19, 32)],
                    },
                    {
                        "message": "Directive '@onObject' may not be used on schema.",
                        "locations": [(22, 24)],
                    },
                    {
                        "message": "Directive '@onObject' may not be used on schema.",
                        "locations": [(26, 31)],
                    },
                ],
                schema_with_sdl_directives,
            )
