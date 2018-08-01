from graphql.validation import UniqueArgumentNamesRule
from graphql.validation.rules.unique_argument_names import (
    duplicate_arg_message)

from .harness import expect_fails_rule, expect_passes_rule


def duplicate_arg(arg_name, l1, c1, l2, c2):
    return {
        'message': duplicate_arg_message(arg_name),
        'locations': [(l1, c1), (l2, c2)]}


def describe_validate_unique_argument_names():

    def no_arguments_on_field():
        expect_passes_rule(UniqueArgumentNamesRule, """
            {
              field
            }
            """)

    def no_arguments_on_directive():
        expect_passes_rule(UniqueArgumentNamesRule, """
            {
              field
            }
            """)

    def argument_on_field():
        expect_passes_rule(UniqueArgumentNamesRule, """
            {
              field(arg: "value")
            }
            """)

    def argument_on_directive():
        expect_passes_rule(UniqueArgumentNamesRule, """
            {
              field @directive(arg: "value")
            }
            """)

    def same_argument_on_two_fields():
        expect_passes_rule(UniqueArgumentNamesRule, """
            {
              one: field(arg: "value")
              two: field(arg: "value")
            }
            """)

    def same_argument_on_field_and_directive():
        expect_passes_rule(UniqueArgumentNamesRule, """
            {
              field(arg: "value") @directive(arg: "value")
            }
            """)

    def same_argument_on_two_directives():
        expect_passes_rule(UniqueArgumentNamesRule, """
            {
              field @directive1(arg: "value") @directive2(arg: "value")
            }
            """)

    def multiple_field_arguments():
        expect_passes_rule(UniqueArgumentNamesRule, """
            {
              field(arg1: "value", arg2: "value", arg3: "value")
            }
            """)

    def multiple_directive_arguments():
        expect_passes_rule(UniqueArgumentNamesRule, """
            {
              field @directive(arg1: "value", arg2: "value", arg3: "value")
            }
            """)

    def duplicate_field_arguments():
        expect_fails_rule(UniqueArgumentNamesRule, """
            {
              field(arg1: "value", arg1: "value")
            }
            """, [
            duplicate_arg('arg1', 3, 21, 3, 36)
        ])

    def many_duplicate_field_arguments():
        expect_fails_rule(UniqueArgumentNamesRule, """
            {
              field(arg1: "value", arg1: "value", arg1: "value")
            }
            """, [
            duplicate_arg('arg1', 3, 21, 3, 36),
            duplicate_arg('arg1', 3, 21, 3, 51)
        ])

    def duplicate_directive_arguments():
        expect_fails_rule(UniqueArgumentNamesRule, """
            {
              field @directive(arg1: "value", arg1: "value")
            }
            """, [
            duplicate_arg('arg1', 3, 32, 3, 47)
        ])

    def many_duplicate_directive_arguments():
        expect_fails_rule(UniqueArgumentNamesRule, """
            {
              field @directive(arg1: "value", arg1: "value", arg1: "value")
            }
            """, [
            duplicate_arg('arg1', 3, 32, 3, 47),
            duplicate_arg('arg1', 3, 32, 3, 62)
        ])
