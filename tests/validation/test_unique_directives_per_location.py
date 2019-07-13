from functools import partial

from graphql.language import parse
from graphql.utilities import extend_schema
from graphql.validation import UniqueDirectivesPerLocationRule
from graphql.validation.rules.unique_directives_per_location import (
    duplicate_directive_message,
)

from .harness import assert_validation_errors, assert_sdl_validation_errors, test_schema

extension_sdl = """
  directive @directive on FIELD | FRAGMENT_DEFINITION
  directive @directiveA on FIELD | FRAGMENT_DEFINITION
  directive @directiveB on FIELD | FRAGMENT_DEFINITION
  directive @repeatable repeatable on FIELD | FRAGMENT_DEFINITION
"""
schema_with_directives = extend_schema(test_schema, parse(extension_sdl))

assert_errors = partial(
    assert_validation_errors,
    UniqueDirectivesPerLocationRule,
    schema=schema_with_directives,
)

assert_valid = partial(assert_errors, errors=[])

assert_sdl_errors = partial(
    assert_sdl_validation_errors, UniqueDirectivesPerLocationRule
)


def duplicate_directive(directive_name, l1, c1, l2, c2):
    return {
        "message": duplicate_directive_message(directive_name),
        "locations": [(l1, c1), (l2, c2)],
    }


def describe_validate_directives_are_unique_per_location():
    def no_directives():
        assert_valid(
            """
            {
              field
            }
            """
        )

    def unique_directives_in_different_locations():
        assert_valid(
            """
            fragment Test on Type @directiveA {
              field @directiveB
            }
            """
        )

    def unique_directives_in_same_locations():
        assert_valid(
            """
            fragment Test on Type @directiveA @directiveB {
              field @directiveA @directiveB
            }
            """
        )

    def same_directives_in_different_locations():
        assert_valid(
            """
            fragment Test on Type @directiveA {
              field @directiveA
            }
            """
        )

    def same_directives_in_similar_locations():
        assert_valid(
            """
            fragment Test on Type {
              field @directive
              field @directive
            }
            """
        )

    def repeatable_directives_in_same_location():
        assert_valid(
            """
            fragment Test on Type @repeatable @repeatable {
              field @repeatable @repeatable
            }
            """
        )

    def unknown_directives_must_be_ignored():
        assert_valid(
            """
            type Test @unknown @unknown {
              field: String! @unknown @unknown
            }

            extend type Test @unknown {
              anotherField: String!
            }
            """
        )

    def duplicate_directives_in_one_location():
        assert_errors(
            """
            fragment Test on Type {
              field @directive @directive @directive
            }
            """,
            [
                duplicate_directive("directive", 3, 21, 3, 32),
                duplicate_directive("directive", 3, 21, 3, 43),
            ],
        )

    def different_duplicate_directives_in_one_location():
        assert_errors(
            """
            fragment Test on Type {
              field @directiveA @directiveB @directiveA @directiveB
            }
            """,
            [
                duplicate_directive("directiveA", 3, 21, 3, 45),
                duplicate_directive("directiveB", 3, 33, 3, 57),
            ],
        )

    def different_duplicate_directives_in_many_locations():
        assert_errors(
            """
            fragment Test on Type @directive @directive {
              field @directive @directive
            }
            """,
            [
                duplicate_directive("directive", 2, 35, 2, 46),
                duplicate_directive("directive", 3, 21, 3, 32),
            ],
        )

    def duplicate_directives_on_sdl_definitions():
        assert_sdl_errors(
            """
            directive @nonRepeatable on
              SCHEMA | SCALAR | OBJECT | INTERFACE | UNION | INPUT_OBJECT

            schema @nonRepeatable @nonRepeatable { query: Dummy }
            extend schema @nonRepeatable @nonRepeatable

            scalar TestScalar @nonRepeatable @nonRepeatable
            extend scalar TestScalar @nonRepeatable @nonRepeatable

            type TestObject @nonRepeatable @nonRepeatable
            extend type TestObject @nonRepeatable @nonRepeatable

            interface TestInterface @nonRepeatable @nonRepeatable
            extend interface TestInterface @nonRepeatable @nonRepeatable

            union TestUnion @nonRepeatable @nonRepeatable
            extend union TestUnion @nonRepeatable @nonRepeatable

            input TestInput @nonRepeatable @nonRepeatable
            extend input TestInput @nonRepeatable @nonRepeatable
            """,
            [
                duplicate_directive("nonRepeatable", 5, 20, 5, 35),
                duplicate_directive("nonRepeatable", 6, 27, 6, 42),
                duplicate_directive("nonRepeatable", 8, 31, 8, 46),
                duplicate_directive("nonRepeatable", 9, 38, 9, 53),
                duplicate_directive("nonRepeatable", 11, 29, 11, 44),
                duplicate_directive("nonRepeatable", 12, 36, 12, 51),
                duplicate_directive("nonRepeatable", 14, 37, 14, 52),
                duplicate_directive("nonRepeatable", 15, 44, 15, 59),
                duplicate_directive("nonRepeatable", 17, 29, 17, 44),
                duplicate_directive("nonRepeatable", 18, 36, 18, 51),
                duplicate_directive("nonRepeatable", 20, 29, 20, 44),
                duplicate_directive("nonRepeatable", 21, 36, 21, 51),
            ],
        )
