from functools import partial

from graphql.validation import UniqueDirectivesPerLocationRule
from graphql.validation.rules.unique_directives_per_location import (
    duplicate_directive_message
)

from .harness import expect_fails_rule, expect_passes_rule, expect_sdl_errors_from_rule

expect_sdl_errors = partial(
    expect_sdl_errors_from_rule, UniqueDirectivesPerLocationRule
)


def duplicate_directive(directive_name, l1, c1, l2, c2):
    return {
        "message": duplicate_directive_message(directive_name),
        "locations": [(l1, c1), (l2, c2)],
    }


def describe_validate_directives_are_unique_per_location():
    def no_directives():
        expect_passes_rule(
            UniqueDirectivesPerLocationRule,
            """
            {
              field
            }
            """,
        )

    def unique_directives_in_different_locations():
        expect_passes_rule(
            UniqueDirectivesPerLocationRule,
            """
            fragment Test on Type @directiveA {
              field @directiveB
            }
            """,
        )

    def unique_directives_in_same_locations():
        expect_passes_rule(
            UniqueDirectivesPerLocationRule,
            """
            fragment Test on Type @directiveA @directiveB {
              field @directiveA @directiveB
            }
            """,
        )

    def same_directives_in_different_locations():
        expect_passes_rule(
            UniqueDirectivesPerLocationRule,
            """
            fragment Test on Type @directiveA {
              field @directiveA
            }
            """,
        )

    def same_directives_in_similar_locations():
        expect_passes_rule(
            UniqueDirectivesPerLocationRule,
            """
            fragment Test on Type {
              field @directive
              field @directive
            }
            """,
        )

    def duplicate_directives_in_one_location():
        expect_fails_rule(
            UniqueDirectivesPerLocationRule,
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
        expect_fails_rule(
            UniqueDirectivesPerLocationRule,
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
        expect_fails_rule(
            UniqueDirectivesPerLocationRule,
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
        assert (
            expect_sdl_errors(
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
                """
            )
            == [
                duplicate_directive("directive", 2, 24, 2, 35),
                duplicate_directive("directive", 3, 31, 3, 42),
                duplicate_directive("directive", 5, 35, 5, 46),
                duplicate_directive("directive", 6, 42, 6, 53),
                duplicate_directive("directive", 8, 33, 8, 44),
                duplicate_directive("directive", 9, 40, 9, 51),
                duplicate_directive("directive", 11, 41, 11, 52),
                duplicate_directive("directive", 12, 48, 12, 59),
                duplicate_directive("directive", 14, 33, 14, 44),
                duplicate_directive("directive", 15, 40, 15, 51),
                duplicate_directive("directive", 17, 33, 17, 44),
                duplicate_directive("directive", 18, 40, 18, 51),
            ]
        )
