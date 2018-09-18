from graphql.validation import UniqueVariableNamesRule
from graphql.validation.rules.unique_variable_names import duplicate_variable_message

from .harness import expect_fails_rule, expect_passes_rule


def duplicate_variable(name, l1, c1, l2, c2):
    return {
        "message": duplicate_variable_message(name),
        "locations": [(l1, c1), (l2, c2)],
    }


def describe_validate_unique_variable_names():
    def unique_variable_names():
        expect_passes_rule(
            UniqueVariableNamesRule,
            """
            query A($x: Int, $y: String) { __typename }
            query B($x: String, $y: Int) { __typename }
            """,
        )

    def duplicate_variable_names():
        expect_fails_rule(
            UniqueVariableNamesRule,
            """
            query A($x: Int, $x: Int, $x: String) { __typename }
            query B($x: String, $x: Int) { __typename }
            query C($x: Int, $x: Int) { __typename }
            """,
            [
                duplicate_variable("x", 2, 22, 2, 31),
                duplicate_variable("x", 2, 22, 2, 40),
                duplicate_variable("x", 3, 22, 3, 34),
                duplicate_variable("x", 4, 22, 4, 31),
            ],
        )
