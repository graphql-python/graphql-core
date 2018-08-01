from graphql.validation import VariablesAreInputTypesRule
from graphql.validation.rules.variables_are_input_types import (
    non_input_type_on_var_message)

from .harness import expect_fails_rule, expect_passes_rule


def describe_validate_variables_are_input_types():

    def input_types_are_valid():
        expect_passes_rule(VariablesAreInputTypesRule, """
            query Foo($a: String, $b: [Boolean!]!, $c: ComplexInput) {
              field(a: $a, b: $b, c: $c)
            }
            """)

    def output_types_are_invalid():
        expect_fails_rule(VariablesAreInputTypesRule, """
            query Foo($a: Dog, $b: [[CatOrDog!]]!, $c: Pet) {
              field(a: $a, b: $b, c: $c)
            }
            """, [{
            'locations': [(2, 27)],
            'message': non_input_type_on_var_message('a', 'Dog')
            }, {
            'locations': [(2, 36)],
            'message': non_input_type_on_var_message('b', '[[CatOrDog!]]!')
            }, {
            'locations': [(2, 56)],
            'message': non_input_type_on_var_message('c', 'Pet')
        }])
