from graphql.validation import VariablesInAllowedPositionRule
from graphql.validation.rules.variables_in_allowed_position import (
    bad_var_pos_message)

from .harness import expect_fails_rule, expect_passes_rule


def describe_validate_variables_are_in_allowed_positions():

    def boolean_to_boolean():
        expect_passes_rule(VariablesInAllowedPositionRule, """
            query Query($booleanArg: Boolean)
            {
              complicatedArgs {
                booleanArgField(booleanArg: $booleanArg)
              }
            }
            """)

    def boolean_to_boolean_in_fragment():
        expect_passes_rule(VariablesInAllowedPositionRule, """
            fragment booleanArgFrag on ComplicatedArgs {
              booleanArgField(booleanArg: $booleanArg)
            }
            query Query($booleanArg: Boolean)
            {
              complicatedArgs {
                ...booleanArgFrag
              }
            }
            """)

        expect_passes_rule(VariablesInAllowedPositionRule, """
            query Query($booleanArg: Boolean)
            {
              complicatedArgs {
                ...booleanArgFrag
              }
            }
            fragment booleanArgFrag on ComplicatedArgs {
              booleanArgField(booleanArg: $booleanArg)
            }
            """)

    def non_null_boolean_to_boolean():
        expect_passes_rule(VariablesInAllowedPositionRule, """
            query Query($nonNullBooleanArg: Boolean!)
            {
              complicatedArgs {
                booleanArgField(booleanArg: $nonNullBooleanArg)
              }
            }
            """)

    def non_null_boolean_to_boolean_within_fragment():
        expect_passes_rule(VariablesInAllowedPositionRule, """
            fragment booleanArgFrag on ComplicatedArgs {
              booleanArgField(booleanArg: $nonNullBooleanArg)
            }

            query Query($nonNullBooleanArg: Boolean!)
            {
              complicatedArgs {
                ...booleanArgFrag
              }
            }
            """)

    def array_of_string_to_array_of_string():
        expect_passes_rule(VariablesInAllowedPositionRule, """
            query Query($stringListVar: [String])
            {
              complicatedArgs {
                stringListArgField(stringListArg: $stringListVar)
              }
            }
            """)

    def array_of_non_null_string_to_array_of_string():
        expect_passes_rule(VariablesInAllowedPositionRule, """
            query Query($stringListVar: [String!])
            {
              complicatedArgs {
                stringListArgField(stringListArg: $stringListVar)
              }
            }
            """)

    def string_to_array_of_string_in_item_position():
        expect_passes_rule(VariablesInAllowedPositionRule, """
            query Query($stringVar: String)
            {
              complicatedArgs {
                stringListArgField(stringListArg: [$stringVar])
              }
            }
            """)

    def non_null_string_to_array_of_string_in_item_position():
        expect_passes_rule(VariablesInAllowedPositionRule, """
            query Query($stringVar: String!)
            {
              complicatedArgs {
                stringListArgField(stringListArg: [$stringVar])
              }
            }
            """)

    def complex_input_to_complex_input():
        expect_passes_rule(VariablesInAllowedPositionRule, """
            query Query($complexVar: ComplexInput)
            {
              complicatedArgs {
                complexArgField(complexArg: $complexVar)
              }
            }
            """)

    def complex_input_to_complex_input_in_field_position():
        expect_passes_rule(VariablesInAllowedPositionRule, """
            query Query($boolVar: Boolean = false)
            {
              complicatedArgs {
                complexArgField(complexArg: {requiredArg: $boolVar})
              }
            }
            """)

    def non_null_boolean_to_non_null_boolean_in_directive():
        expect_passes_rule(VariablesInAllowedPositionRule, """
            query Query($boolVar: Boolean!)
            {
              dog @include(if: $boolVar)
            }
            """)

    def int_to_non_null_int():
        expect_fails_rule(VariablesInAllowedPositionRule, """
            query Query($intArg: Int) {
              complicatedArgs {
                nonNullIntArgField(nonNullIntArg: $intArg)
              }
            }
            """, [{
            'message': bad_var_pos_message('intArg', 'Int', 'Int!'),
            'locations': [(2, 25), (4, 51)]
        }])

    def int_to_non_null_int_within_fragment():
        expect_fails_rule(VariablesInAllowedPositionRule, """
            fragment nonNullIntArgFieldFrag on ComplicatedArgs {
              nonNullIntArgField(nonNullIntArg: $intArg)
            }

            query Query($intArg: Int) {
              complicatedArgs {
                ...nonNullIntArgFieldFrag
              }
            }
            """, [{
            'message': bad_var_pos_message('intArg', 'Int', 'Int!'),
            'locations': [(6, 25), (3, 49)]
        }])

    def int_to_non_null_int_within_nested_fragment():
        expect_fails_rule(VariablesInAllowedPositionRule, """
            fragment outerFrag on ComplicatedArgs {
              ...nonNullIntArgFieldFrag
            }

            fragment nonNullIntArgFieldFrag on ComplicatedArgs {
              nonNullIntArgField(nonNullIntArg: $intArg)
            }

            query Query($intArg: Int) {
              complicatedArgs {
                ...outerFrag
              }
            }
            """, [{
            'message': bad_var_pos_message('intArg', 'Int', 'Int!'),
            'locations': [(10, 25), (7, 49)]
        }])

    def string_to_boolean():
        expect_fails_rule(VariablesInAllowedPositionRule, """
            query Query($stringVar: String) {
              complicatedArgs {
                booleanArgField(booleanArg: $stringVar)
              }
            }
            """, [{
            'message': bad_var_pos_message('stringVar', 'String', 'Boolean'),
            'locations': [(2, 25), (4, 45)]
        }])

    def string_to_array_of_string():
        expect_fails_rule(VariablesInAllowedPositionRule, """
            query Query($stringVar: String) {
              complicatedArgs {
                stringListArgField(stringListArg: $stringVar)
              }
            }
            """, [{
            'message': bad_var_pos_message('stringVar', 'String', '[String]'),
            'locations': [(2, 25), (4, 51)]
        }])

    def boolean_to_non_null_boolean_in_directive():
        expect_fails_rule(VariablesInAllowedPositionRule, """
            query Query($boolVar: Boolean) {
              dog @include(if: $boolVar)
            }
            """, [{
            'message': bad_var_pos_message('boolVar', 'Boolean', 'Boolean!'),
            'locations': [(2, 25), (3, 32)]
        }])

    def string_to_non_null_boolean_in_directive():
        expect_fails_rule(VariablesInAllowedPositionRule, """
            query Query($stringVar: String) {
              dog @include(if: $stringVar)
            }
            """, [{
            'message': bad_var_pos_message('stringVar', 'String', 'Boolean!'),
            'locations': [(2, 25), (3, 32)]
        }])

    def array_of_string_to_array_of_non_null_string():
        expect_fails_rule(VariablesInAllowedPositionRule, """
            query Query($stringListVar: [String])
            {
              complicatedArgs {
                stringListNonNullArgField(stringListNonNullArg: $stringListVar)
              }
            }
            """, [{
            'message': bad_var_pos_message(
                'stringListVar', '[String]', '[String!]'),
            'locations': [(2, 25), (5, 65)]
        }])

    def describe_allows_optional_nullable_variables_with_default_values():

        def int_to_non_null_int_fails_when_var_provides_null_default_value():
            expect_fails_rule(VariablesInAllowedPositionRule, """
                query Query($intVar: Int = null) {
                  complicatedArgs {
                    nonNullIntArgField(nonNullIntArg: $intVar)
                  }
                }
                """, [{
                'message': bad_var_pos_message('intVar', 'Int', 'Int!'),
                'locations': [(2, 29), (4, 55)]
                }])

    def int_to_non_null_int_when_var_provides_non_null_default_value():
        expect_passes_rule(VariablesInAllowedPositionRule, """
            query Query($intVar: Int = 1) {
              complicatedArgs {
                nonNullIntArgField(nonNullIntArg: $intVar)
              }
            }
            """)

    def int_to_non_null_int_when_optional_arg_provides_default_value():
        expect_passes_rule(VariablesInAllowedPositionRule, """
            query Query($intVar: Int) {
              complicatedArgs {
                nonNullFieldWithDefault(nonNullIntArg: $intVar)
              }
            }
            """)

    def bool_to_non_null_bool_in_directive_with_default_value_with_option():
        expect_passes_rule(VariablesInAllowedPositionRule, """
            query Query($boolVar: Boolean = false) {
              dog @include(if: $boolVar)
            }
            """)
