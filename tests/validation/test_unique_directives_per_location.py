from functools import partial

from graphql.validation import UniqueDirectivesPerLocationRule
from graphql.validation.rules.unique_directives_per_location import (
    duplicate_directive_message,
)

from .harness import assert_validation_errors, assert_sdl_validation_errors

assert_errors = partial(assert_validation_errors, UniqueDirectivesPerLocationRule)

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
            schema @directive @directive { query: Dummy }
            extend schema @directive @directive

            scalar TestScalar @directive @directive
            extend scalar TestScalar @directive @directive

            type TestObject @directive @directive
            extend type TestObject @directive @directive

            interface TestInterface @directive @directive
            extend interface TestInterface @directive @directive

            union TestUnion @directive @directive
            extend union TestUnion @directive @directive

            input TestInput @directive @directive
            extend input TestInput @directive @directive
            """,
            [
                duplicate_directive("directive", 2, 20, 2, 31),
                duplicate_directive("directive", 3, 27, 3, 38),
                duplicate_directive("directive", 5, 31, 5, 42),
                duplicate_directive("directive", 6, 38, 6, 49),
                duplicate_directive("directive", 8, 29, 8, 40),
                duplicate_directive("directive", 9, 36, 9, 47),
                duplicate_directive("directive", 11, 37, 11, 48),
                duplicate_directive("directive", 12, 44, 12, 55),
                duplicate_directive("directive", 14, 29, 14, 40),
                duplicate_directive("directive", 15, 36, 15, 47),
                duplicate_directive("directive", 17, 29, 17, 40),
                duplicate_directive("directive", 18, 36, 18, 47),
            ],
        )
