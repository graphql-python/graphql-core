from functools import partial

from graphql.validation.rules.unique_argument_definition_names import (
    UniqueArgumentDefinitionNamesRule,
)

from .harness import assert_sdl_validation_errors

assert_sdl_errors = partial(
    assert_sdl_validation_errors, UniqueArgumentDefinitionNamesRule
)

assert_sdl_valid = partial(assert_sdl_errors, errors=[])


def describe_validate_unique_argument_definition_names():
    def no_args():
        assert_sdl_valid(
            """
            type SomeObject {
              someField: String
            }

            interface SomeInterface {
              someField: String
            }

            directive @someDirective on QUERY
            """
        )

    def one_argument():
        assert_sdl_valid(
            """
            type SomeObject {
              someField(foo: String): String
            }

            interface SomeInterface {
              someField(foo: String): String
            }

            extend type SomeObject {
              anotherField(foo: String): String
            }

            extend interface SomeInterface {
              anotherField(foo: String): String
            }

            directive @someDirective(foo: String) on QUERY
            """
        )

    def multiple_arguments():
        assert_sdl_valid(
            """
            type SomeObject {
              someField(
                foo: String
                bar: String
              ): String
            }

            interface SomeInterface {
              someField(
                foo: String
                bar: String
              ): String
            }

            extend type SomeObject {
              anotherField(
                foo: String
                bar: String
              ): String
            }

            extend interface SomeInterface {
              anotherField(
                foo: String
                bar: String
              ): String
            }

            directive @someDirective(
              foo: String
              bar: String
            ) on QUERY
            """
        )

    def duplicating_arguments():
        assert_sdl_errors(
            """
            type SomeObject {
              someField(
                foo: String
                bar: String
                foo: String
              ): String
            }

            interface SomeInterface {
              someField(
                foo: String
                bar: String
                foo: String
              ): String
            }

            extend type SomeObject {
              anotherField(
                foo: String
                bar: String
                bar: String
              ): String
            }

            extend interface SomeInterface {
              anotherField(
                bar: String
                foo: String
                foo: String
              ): String
            }

            directive @someDirective(
              foo: String
              bar: String
              foo: String
            ) on QUERY
            """,
            [
                {
                    "message": "Argument 'SomeObject.someField(foo:)'"
                    " can only be defined once.",
                    "locations": [(4, 17), (6, 17)],
                },
                {
                    "message": "Argument 'SomeInterface.someField(foo:)'"
                    " can only be defined once.",
                    "locations": [(12, 17), (14, 17)],
                },
                {
                    "message": "Argument 'SomeObject.anotherField(bar:)'"
                    " can only be defined once.",
                    "locations": [(21, 17), (22, 17)],
                },
                {
                    "message": "Argument 'SomeInterface.anotherField(foo:)'"
                    " can only be defined once.",
                    "locations": [(29, 17), (30, 17)],
                },
                {
                    "message": "Argument '@someDirective(foo:)'"
                    " can only be defined once.",
                    "locations": [(35, 15), (37, 15)],
                },
            ],
        )
