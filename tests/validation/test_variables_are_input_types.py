from functools import partial

from graphql.validation import VariablesAreInputTypesRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, VariablesAreInputTypesRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_variables_are_input_types():
    def unknown_types_are_ignored():
        assert_valid(
            """
            query Foo($a: Unknown, $b: [[Unknown!]]!) {
              field(a: $a, b: $b)
            }
            """
        )

    def input_types_are_valid():
        assert_valid(
            """
            query Foo($a: String, $b: [Boolean!]!, $c: ComplexInput) {
              field(a: $a, b: $b, c: $c)
            }
            """
        )

    def output_types_are_invalid():
        assert_errors(
            """
            query Foo($a: Dog, $b: [[CatOrDog!]]!, $c: Pet) {
              field(a: $a, b: $b, c: $c)
            }
            """,
            [
                {
                    "locations": [(2, 27)],
                    "message": "Variable '$a' cannot be non-input type 'Dog'.",
                },
                {
                    "locations": [(2, 36)],
                    "message": "Variable '$b' cannot be"
                    " non-input type '[[CatOrDog!]]!'.",
                },
                {
                    "locations": [(2, 56)],
                    "message": "Variable '$c' cannot be non-input type 'Pet'.",
                },
            ],
        )
