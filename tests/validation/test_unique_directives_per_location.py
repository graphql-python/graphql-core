from graphql.validation import UniqueDirectivesPerLocationRule
from graphql.validation.rules.unique_directives_per_location import (
    duplicate_directive_message)

from .harness import expect_fails_rule, expect_passes_rule


def duplicate_directive(directive_name, l1, c1, l2, c2):
    return {
        'message': duplicate_directive_message(directive_name),
        'locations': [(l1, c1), (l2, c2)]}


def describe_validate_directives_are_unique_per_location():

    def no_directives():
        expect_passes_rule(UniqueDirectivesPerLocationRule, """
            {
              field
            }
            """)

    def unique_directives_in_different_locations():
        expect_passes_rule(UniqueDirectivesPerLocationRule, """
            fragment Test on Type @directiveA {
              field @directiveB
            }
            """)

    def unique_directives_in_same_locations():
        expect_passes_rule(UniqueDirectivesPerLocationRule, """
            fragment Test on Type @directiveA @directiveB {
              field @directiveA @directiveB
            }
            """)

    def same_directives_in_different_locations():
        expect_passes_rule(UniqueDirectivesPerLocationRule, """
            fragment Test on Type @directiveA {
              field @directiveA
            }
            """)

    def same_directives_in_similar_locations():
        expect_passes_rule(UniqueDirectivesPerLocationRule, """
            fragment Test on Type {
              field @directive
              field @directive
            }
            """)

    def duplicate_directives_in_one_location():
        expect_fails_rule(UniqueDirectivesPerLocationRule, """
            fragment Test on Type {
              field @directive @directive @directive
            }
            """, [
            duplicate_directive('directive', 3, 21, 3, 32),
            duplicate_directive('directive', 3, 21, 3, 43),
        ])

    def different_duplicate_directives_in_one_location():
        expect_fails_rule(UniqueDirectivesPerLocationRule, """
            fragment Test on Type {
              field @directiveA @directiveB @directiveA @directiveB
            }
            """, [
            duplicate_directive('directiveA', 3, 21, 3, 45),
            duplicate_directive('directiveB', 3, 33, 3, 57),
        ])

    def different_duplicate_directives_in_many_locations():
        expect_fails_rule(UniqueDirectivesPerLocationRule, """
            fragment Test on Type @directive @directive {
              field @directive @directive
            }
            """, [
            duplicate_directive('directive', 2, 35, 2, 46),
            duplicate_directive('directive', 3, 21, 3, 32),
        ])
