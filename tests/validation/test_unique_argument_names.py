from functools import partial
from graphql.validation import UniqueArgumentNamesRule
from graphql.validation.rules.unique_argument_names import duplicate_arg_message

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, UniqueArgumentNamesRule)

assert_valid = partial(assert_errors, errors=[])


def duplicate_arg(arg_name, l1, c1, l2, c2):
    return {
        "message": duplicate_arg_message(arg_name),
        "locations": [(l1, c1), (l2, c2)],
    }


def describe_validate_unique_argument_names():
    def no_arguments_on_field():
        assert_valid(
            """
            {
              field
            }
            """
        )

    def no_arguments_on_directive():
        assert_valid(
            """
            {
              field
            }
            """
        )

    def argument_on_field():
        assert_valid(
            """
            {
              field(arg: "value")
            }
            """
        )

    def argument_on_directive():
        assert_valid(
            """
            {
              field @directive(arg: "value")
            }
            """
        )

    def same_argument_on_two_fields():
        assert_valid(
            """
            {
              one: field(arg: "value")
              two: field(arg: "value")
            }
            """
        )

    def same_argument_on_field_and_directive():
        assert_valid(
            """
            {
              field(arg: "value") @directive(arg: "value")
            }
            """
        )

    def same_argument_on_two_directives():
        assert_valid(
            """
            {
              field @directive1(arg: "value") @directive2(arg: "value")
            }
            """
        )

    def multiple_field_arguments():
        assert_valid(
            """
            {
              field(arg1: "value", arg2: "value", arg3: "value")
            }
            """
        )

    def multiple_directive_arguments():
        assert_valid(
            """
            {
              field @directive(arg1: "value", arg2: "value", arg3: "value")
            }
            """
        )

    def duplicate_field_arguments():
        assert_errors(
            """
            {
              field(arg1: "value", arg1: "value")
            }
            """,
            [duplicate_arg("arg1", 3, 21, 3, 36)],
        )

    def many_duplicate_field_arguments():
        assert_errors(
            """
            {
              field(arg1: "value", arg1: "value", arg1: "value")
            }
            """,
            [duplicate_arg("arg1", 3, 21, 3, 36), duplicate_arg("arg1", 3, 21, 3, 51)],
        )

    def duplicate_directive_arguments():
        assert_errors(
            """
            {
              field @directive(arg1: "value", arg1: "value")
            }
            """,
            [duplicate_arg("arg1", 3, 32, 3, 47)],
        )

    def many_duplicate_directive_arguments():
        assert_errors(
            """
            {
              field @directive(arg1: "value", arg1: "value", arg1: "value")
            }
            """,
            [duplicate_arg("arg1", 3, 32, 3, 47), duplicate_arg("arg1", 3, 32, 3, 62)],
        )
