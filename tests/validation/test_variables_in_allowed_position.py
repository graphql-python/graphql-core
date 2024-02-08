from functools import partial

from graphql.validation import VariablesInAllowedPositionRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, VariablesInAllowedPositionRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_variables_are_in_allowed_positions():
    def boolean_to_boolean():
        assert_valid(
            """
            query Query($booleanArg: Boolean)
            {
              complicatedArgs {
                booleanArgField(booleanArg: $booleanArg)
              }
            }
            """
        )

    def boolean_to_boolean_in_fragment():
        assert_valid(
            """
            fragment booleanArgFrag on ComplicatedArgs {
              booleanArgField(booleanArg: $booleanArg)
            }
            query Query($booleanArg: Boolean)
            {
              complicatedArgs {
                ...booleanArgFrag
              }
            }
            """
        )

        assert_valid(
            """
            query Query($booleanArg: Boolean)
            {
              complicatedArgs {
                ...booleanArgFrag
              }
            }
            fragment booleanArgFrag on ComplicatedArgs {
              booleanArgField(booleanArg: $booleanArg)
            }
            """
        )

    def non_null_boolean_to_boolean():
        assert_valid(
            """
            query Query($nonNullBooleanArg: Boolean!)
            {
              complicatedArgs {
                booleanArgField(booleanArg: $nonNullBooleanArg)
              }
            }
            """
        )

    def non_null_boolean_to_boolean_within_fragment():
        assert_valid(
            """
            fragment booleanArgFrag on ComplicatedArgs {
              booleanArgField(booleanArg: $nonNullBooleanArg)
            }

            query Query($nonNullBooleanArg: Boolean!)
            {
              complicatedArgs {
                ...booleanArgFrag
              }
            }
            """
        )

    def array_of_string_to_array_of_string():
        assert_valid(
            """
            query Query($stringListVar: [String])
            {
              complicatedArgs {
                stringListArgField(stringListArg: $stringListVar)
              }
            }
            """
        )

    def array_of_non_null_string_to_array_of_string():
        assert_valid(
            """
            query Query($stringListVar: [String!])
            {
              complicatedArgs {
                stringListArgField(stringListArg: $stringListVar)
              }
            }
            """
        )

    def string_to_array_of_string_in_item_position():
        assert_valid(
            """
            query Query($stringVar: String)
            {
              complicatedArgs {
                stringListArgField(stringListArg: [$stringVar])
              }
            }
            """
        )

    def non_null_string_to_array_of_string_in_item_position():
        assert_valid(
            """
            query Query($stringVar: String!)
            {
              complicatedArgs {
                stringListArgField(stringListArg: [$stringVar])
              }
            }
            """
        )

    def complex_input_to_complex_input():
        assert_valid(
            """
            query Query($complexVar: ComplexInput)
            {
              complicatedArgs {
                complexArgField(complexArg: $complexVar)
              }
            }
            """
        )

    def complex_input_to_complex_input_in_field_position():
        assert_valid(
            """
            query Query($boolVar: Boolean = false)
            {
              complicatedArgs {
                complexArgField(complexArg: {requiredArg: $boolVar})
              }
            }
            """
        )

    def non_null_boolean_to_non_null_boolean_in_directive():
        assert_valid(
            """
            query Query($boolVar: Boolean!)
            {
              dog @include(if: $boolVar)
            }
            """
        )

    def int_to_non_null_int():
        assert_errors(
            """
            query Query($intArg: Int) {
              complicatedArgs {
                nonNullIntArgField(nonNullIntArg: $intArg)
              }
            }
            """,
            [
                {
                    "message": "Variable '$intArg' of type 'Int'"
                    " used in position expecting type 'Int!'.",
                    "locations": [(2, 25), (4, 51)],
                }
            ],
        )

    def int_to_non_null_int_within_fragment():
        assert_errors(
            """
            fragment nonNullIntArgFieldFrag on ComplicatedArgs {
              nonNullIntArgField(nonNullIntArg: $intArg)
            }

            query Query($intArg: Int) {
              complicatedArgs {
                ...nonNullIntArgFieldFrag
              }
            }
            """,
            [
                {
                    "message": "Variable '$intArg' of type 'Int'"
                    " used in position expecting type 'Int!'.",
                    "locations": [(6, 25), (3, 49)],
                }
            ],
        )

    def int_to_non_null_int_within_nested_fragment():
        assert_errors(
            """
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
            """,
            [
                {
                    "message": "Variable '$intArg' of type 'Int'"
                    " used in position expecting type 'Int!'.",
                    "locations": [(10, 25), (7, 49)],
                }
            ],
        )

    def string_to_boolean():
        assert_errors(
            """
            query Query($stringVar: String) {
              complicatedArgs {
                booleanArgField(booleanArg: $stringVar)
              }
            }
            """,
            [
                {
                    "message": "Variable '$stringVar' of type 'String'"
                    " used in position expecting type 'Boolean'.",
                    "locations": [(2, 25), (4, 45)],
                }
            ],
        )

    def string_to_array_of_string():
        assert_errors(
            """
            query Query($stringVar: String) {
              complicatedArgs {
                stringListArgField(stringListArg: $stringVar)
              }
            }
            """,
            [
                {
                    "message": "Variable '$stringVar' of type 'String'"
                    " used in position expecting type '[String]'.",
                    "locations": [(2, 25), (4, 51)],
                }
            ],
        )

    def boolean_to_non_null_boolean_in_directive():
        assert_errors(
            """
            query Query($boolVar: Boolean) {
              dog @include(if: $boolVar)
            }
            """,
            [
                {
                    "message": "Variable '$boolVar' of type 'Boolean'"
                    " used in position expecting type 'Boolean!'.",
                    "locations": [(2, 25), (3, 32)],
                }
            ],
        )

    def string_to_non_null_boolean_in_directive():
        assert_errors(
            """
            query Query($stringVar: String) {
              dog @include(if: $stringVar)
            }
            """,
            [
                {
                    "message": "Variable '$stringVar' of type 'String'"
                    " used in position expecting type 'Boolean!'.",
                    "locations": [(2, 25), (3, 32)],
                }
            ],
        )

    def array_of_string_to_array_of_non_null_string():
        assert_errors(
            """
            query Query($stringListVar: [String])
            {
              complicatedArgs {
                stringListNonNullArgField(stringListNonNullArg: $stringListVar)
              }
            }
            """,
            [
                {
                    "message": "Variable '$stringListVar' of type '[String]'"
                    " used in position expecting type '[String!]'.",
                    "locations": [(2, 25), (5, 65)],
                }
            ],
        )

    def describe_allows_optional_nullable_variables_with_default_values():
        def int_to_non_null_int_fails_when_var_provides_null_default_value():
            assert_errors(
                """
                query Query($intVar: Int = null) {
                  complicatedArgs {
                    nonNullIntArgField(nonNullIntArg: $intVar)
                  }
                }
                """,
                [
                    {
                        "message": "Variable '$intVar' of type 'Int'"
                        " used in position expecting type 'Int!'.",
                        "locations": [(2, 29), (4, 55)],
                    }
                ],
            )

    def int_to_non_null_int_when_var_provides_non_null_default_value():
        assert_valid(
            """
            query Query($intVar: Int = 1) {
              complicatedArgs {
                nonNullIntArgField(nonNullIntArg: $intVar)
              }
            }
            """
        )

    def int_to_non_null_int_when_optional_arg_provides_default_value():
        assert_valid(
            """
            query Query($intVar: Int) {
              complicatedArgs {
                nonNullFieldWithDefault(nonNullIntArg: $intVar)
              }
            }
            """
        )

    def bool_to_non_null_bool_in_directive_with_default_value_with_option():
        assert_valid(
            """
            query Query($boolVar: Boolean = false) {
              dog @include(if: $boolVar)
            }
            """
        )
