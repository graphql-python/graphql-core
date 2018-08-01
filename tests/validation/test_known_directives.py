from graphql.validation import KnownDirectivesRule
from graphql.validation.rules.known_directives import (
    unknown_directive_message, misplaced_directive_message)

from .harness import expect_fails_rule, expect_passes_rule


def unknown_directive(directive_name, line, column):
    return {
        'message': unknown_directive_message(directive_name),
        'locations': [(line, column)]}


def misplaced_directive(directive_name, placement, line, column):
    return {
        'message': misplaced_directive_message(directive_name, placement),
        'locations': [(line, column)]}


def describe_known_directives():

    def with_no_directives():
        expect_passes_rule(KnownDirectivesRule, """
            query Foo {
              name
              ...Frag
            }

            fragment Frag on Dog {
              name
            }
            """)

    def with_known_directives():
        expect_passes_rule(KnownDirectivesRule, """
            {
              dog @include(if: true) {
                name
              }
              human @skip(if: false) {
                name
              }
            }
            """)

    def with_unknown_directive():
        expect_fails_rule(KnownDirectivesRule, """
            {
              dog @unknown(directive: "value") {
                name
              }
            }
            """, [
            unknown_directive('unknown', 3, 19)
        ])

    def with_many_unknown_directives():
        expect_fails_rule(KnownDirectivesRule, """
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
            """, [
            unknown_directive('unknown', 3, 19),
            unknown_directive('unknown', 6, 21),
            unknown_directive('unknown', 8, 22)
        ])

    def with_well_placed_directives():
        expect_passes_rule(KnownDirectivesRule, """
            query Foo @onQuery{
              name @include(if: true)
              ...Frag @include(if: true)
              skippedField @skip(if: true)
              ...SkippedFrag @skip(if: true)
            }

            mutation Bar @onMutation {
              someField
            }
            """)

    def with_misplaced_directives():
        expect_fails_rule(KnownDirectivesRule, """
            query Foo @include(if: true) {
              name @onQuery
              ...Frag @onQuery
            }

            mutation Bar @onQuery {
              someField
            }
            """, [
            misplaced_directive('include', 'query', 2, 23),
            misplaced_directive('onQuery', 'field', 3, 20),
            misplaced_directive('onQuery', 'fragment spread', 4, 23),
            misplaced_directive('onQuery', 'mutation', 7, 26),
        ])

    def describe_within_schema_language():

        # noinspection PyShadowingNames
        def with_well_placed_directives():
            expect_passes_rule(KnownDirectivesRule, """
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
                """)  # noqa

        # noinspection PyShadowingNames
        def with_misplaced_directives():
            expect_fails_rule(KnownDirectivesRule, """
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
                """, [  # noqa
                misplaced_directive('onInterface', 'object', 2, 51),
                misplaced_directive(
                    'onInputFieldDefinition', 'argument definition', 3, 38),
                misplaced_directive(
                    'onInputFieldDefinition', 'field definition', 3, 71),
                misplaced_directive('onEnum', 'scalar', 6, 33),
                misplaced_directive('onObject', 'interface', 8, 39),
                misplaced_directive(
                    'onInputFieldDefinition', 'argument definition', 9, 38),
                misplaced_directive(
                    'onInputFieldDefinition', 'field definition', 9, 71),
                misplaced_directive('onEnumValue', 'union', 12, 31),
                misplaced_directive('onScalar', 'enum', 14, 29),
                misplaced_directive('onUnion', 'enum value', 15, 28),
                misplaced_directive('onEnum', 'input object', 18, 31),
                misplaced_directive(
                    'onArgumentDefinition', 'input field definition', 19, 32),
                misplaced_directive('onObject', 'schema', 22, 24),
                misplaced_directive('onObject', 'schema', 26, 31)
            ])
