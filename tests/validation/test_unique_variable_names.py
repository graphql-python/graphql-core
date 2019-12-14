from functools import partial

from graphql.validation import UniqueVariableNamesRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, UniqueVariableNamesRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_unique_variable_names():
    def unique_variable_names():
        assert_valid(
            """
            query A($x: Int, $y: String) { __typename }
            query B($x: String, $y: Int) { __typename }
            """
        )

    def duplicate_variable_names():
        assert_errors(
            """
            query A($x: Int, $x: Int, $x: String) { __typename }
            query B($x: String, $x: Int) { __typename }
            query C($x: Int, $x: Int) { __typename }
            """,
            [
                {
                    "message": "There can be only one variable named '$x'.",
                    "locations": [(2, 22), (2, 31)],
                },
                {
                    "message": "There can be only one variable named '$x'.",
                    "locations": [(2, 22), (2, 40)],
                },
                {
                    "message": "There can be only one variable named '$x'.",
                    "locations": [(3, 22), (3, 34)],
                },
                {
                    "message": "There can be only one variable named '$x'.",
                    "locations": [(4, 22), (4, 31)],
                },
            ],
        )
