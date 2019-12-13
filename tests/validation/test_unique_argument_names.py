from functools import partial
from graphql.validation import UniqueArgumentNamesRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, UniqueArgumentNamesRule)

assert_valid = partial(assert_errors, errors=[])


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
            [
                {
                    "message": "There can be only one argument named 'arg1'.",
                    "locations": [(3, 21), (3, 36)],
                },
            ],
        )

    def many_duplicate_field_arguments():
        assert_errors(
            """
            {
              field(arg1: "value", arg1: "value", arg1: "value")
            }
            """,
            [
                {
                    "message": "There can be only one argument named 'arg1'.",
                    "locations": [(3, 21), (3, 36)],
                },
                {
                    "message": "There can be only one argument named 'arg1'.",
                    "locations": [(3, 21), (3, 51)],
                },
            ],
        )

    def duplicate_directive_arguments():
        assert_errors(
            """
            {
              field @directive(arg1: "value", arg1: "value")
            }
            """,
            [
                {
                    "message": "There can be only one argument named 'arg1'.",
                    "locations": [(3, 32), (3, 47)],
                },
            ],
        )

    def many_duplicate_directive_arguments():
        assert_errors(
            """
            {
              field @directive(arg1: "value", arg1: "value", arg1: "value")
            }
            """,
            [
                {
                    "message": "There can be only one argument named 'arg1'.",
                    "locations": [(3, 32), (3, 47)],
                },
                {
                    "message": "There can be only one argument named 'arg1'.",
                    "locations": [(3, 32), (3, 62)],
                },
            ],
        )
