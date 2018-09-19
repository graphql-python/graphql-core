from graphql.validation import ValuesOfCorrectTypeRule
from graphql.validation.rules.values_of_correct_type import (
    bad_value_message,
    required_field_message,
    unknown_field_message,
)

from .harness import expect_fails_rule, expect_passes_rule


def bad_value(type_name, value, line, column, message=None):
    return {
        "message": bad_value_message(type_name, value, message),
        "locations": [(line, column)],
    }


def required_field(type_name, field_name, field_type_name, line, column):
    return {
        "message": required_field_message(type_name, field_name, field_type_name),
        "locations": [(line, column)],
    }


def unknown_field(type_name, field_name, line, column, message=None):
    return {
        "message": unknown_field_message(type_name, field_name, message),
        "locations": [(line, column)],
    }


def describe_validate_values_of_correct_type():
    def describe_valid_values():
        def good_int_value():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    intArgField(intArg: 2)
                  }
                }
                """,
            )

        def good_negative_int_value():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    intArgField(intArg: -2)
                  }
                }
                """,
            )

        def good_boolean_value():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    booleanArgField(intArg: true)
                  }
                }
                """,
            )

        def good_string_value():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    stringArgField(intArg: "foo")
                  }
                }
                """,
            )

        def good_float_value():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    floatArgField(intArg: 1.1)
                  }
                }
                """,
            )

        def good_negative_float_value():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    floatArgField(intArg: -1.1)
                  }
                }
                """,
            )

        def int_into_id():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    idArgField(idArg: 1)
                  }
                }
                """,
            )

        def string_into_id():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    idArgField(idArg: "someIdString")
                  }
                }
                """,
            )

        def good_enum_value():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  dog {
                    doesKnowCommand(dogCommand: SIT)
                  }
                }
                """,
            )

        def enum_with_undefined_value():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    enumArgField(enumArg: UNKNOWN)
                  }
                }
                """,
            )

        def enum_with_null_value():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    enumArgField(enumArg: NO_FUR)
                  }
                }
                """,
            )

        def null_into_nullable_type():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    intArgField(intArg: null)
                  }
                }
                """,
            )

            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  dog(a: null, b: null, c:{ requiredField: true, intField: null }) {
                    name
                  }
                }
                """,
            )

    def describe_invalid_string_values():
        def int_into_string():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    stringArgField(stringArg: 1)
                  }
                }
                """,
                [bad_value("String", "1", 4, 47)],
            )

        def float_into_string():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    stringArgField(stringArg: 1.0)
                  }
                }
                """,
                [bad_value("String", "1.0", 4, 47)],
            )

        def boolean_into_string():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    stringArgField(stringArg: true)
                  }
                }
                """,
                [bad_value("String", "true", 4, 47)],
            )

        def unquoted_string_into_string():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    stringArgField(stringArg: BAR)
                  }
                }
                """,
                [bad_value("String", "BAR", 4, 47)],
            )

    def describe_invalid_int_values():
        def string_into_int():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    intArgField(intArg: "3")
                  }
                }
                """,
                [bad_value("Int", '"3"', 4, 41)],
            )

        def big_int_into_int():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    intArgField(intArg: 829384293849283498239482938)
                  }
                }
                """,
                [bad_value("Int", "829384293849283498239482938", 4, 41)],
            )

        def unquoted_string_into_int():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    intArgField(intArg: FOO)
                  }
                }
                """,
                [bad_value("Int", "FOO", 4, 41)],
            )

        def simple_float_into_int():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    intArgField(intArg: 3.0)
                  }
                }
                """,
                [bad_value("Int", "3.0", 4, 41)],
            )

        def float_into_int():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    intArgField(intArg: 3.333)
                  }
                }
                """,
                [bad_value("Int", "3.333", 4, 41)],
            )

    def describe_invalid_float_values():
        def string_into_float():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    floatArgField(floatArg: "3.333")
                  }
                }
                """,
                [bad_value("Float", '"3.333"', 4, 45)],
            )

        def boolean_into_float():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    floatArgField(floatArg: true)
                  }
                }
                """,
                [bad_value("Float", "true", 4, 45)],
            )

        def unquoted_into_float():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    floatArgField(floatArg: FOO)
                  }
                }
                """,
                [bad_value("Float", "FOO", 4, 45)],
            )

    def describe_invalid_boolean_value():
        def int_into_boolean():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    booleanArgField(booleanArg: 2)
                  }
                }
                """,
                [bad_value("Boolean", "2", 4, 49)],
            )

        def float_into_boolean():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    booleanArgField(booleanArg: 1.0)
                  }
                }
                """,
                [bad_value("Boolean", "1.0", 4, 49)],
            )

        def string_into_boolean():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    booleanArgField(booleanArg: "true")
                  }
                }
                """,
                [bad_value("Boolean", '"true"', 4, 49)],
            )

        def unquoted_into_boolean():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    booleanArgField(booleanArg: TRUE)
                  }
                }
                """,
                [bad_value("Boolean", "TRUE", 4, 49)],
            )

    def describe_invalid_id_value():
        def float_into_id():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    idArgField(idArg: 1.0)
                  }
                }
                """,
                [bad_value("ID", "1.0", 4, 39)],
            )

        def boolean_into_id():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    idArgField(idArg: true)
                  }
                }
                """,
                [bad_value("ID", "true", 4, 39)],
            )

        def unquoted_into_id():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    idArgField(idArg: SOMETHING)
                  }
                }
                """,
                [bad_value("ID", "SOMETHING", 4, 39)],
            )

    def describe_invalid_enum_value():
        def int_into_enum():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  dog {
                    doesKnowCommand(dogCommand: 2)
                  }
                }
                """,
                [bad_value("DogCommand", "2", 4, 49)],
            )

        def float_into_enum():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  dog {
                    doesKnowCommand(dogCommand: 1.0)
                  }
                }
                """,
                [bad_value("DogCommand", "1.0", 4, 49)],
            )

        def string_into_enum():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  dog {
                    doesKnowCommand(dogCommand: "SIT")
                  }
                }
                """,
                [
                    bad_value(
                        "DogCommand", '"SIT"', 4, 49, "Did you mean the enum value SIT?"
                    )
                ],
            )

        def boolean_into_enum():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  dog {
                    doesKnowCommand(dogCommand: true)
                  }
                }
                """,
                [bad_value("DogCommand", "true", 4, 49)],
            )

        def unknown_enum_value_into_enum():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  dog {
                    doesKnowCommand(dogCommand: JUGGLE)
                  }
                }
                """,
                [bad_value("DogCommand", "JUGGLE", 4, 49)],
            )

        def different_case_enum_value_into_enum():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  dog {
                    doesKnowCommand(dogCommand: sit)
                  }
                }
                """,
                [
                    bad_value(
                        "DogCommand", "sit", 4, 49, "Did you mean the enum value SIT?"
                    )
                ],
            )

    def describe_valid_list_value():
        def good_list_value():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    stringListArgField(stringListArg: ["one", null, "two"])
                  }
                }
                """,
            )

        def empty_list_value():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    stringListArgField(stringListArg: [])
                  }
                }
                """,
            )

        def null_value():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    stringListArgField(stringListArg: null)
                  }
                }
                """,
            )

        def single_value_into_list():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    stringListArgField(stringListArg: "one")
                  }
                }
                """,
            )

    def describe_invalid_list_value():
        def incorrect_item_type():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    stringListArgField(stringListArg: ["one", 2])
                  }
                }
                """,
                [bad_value("String", "2", 4, 63)],
            )

        def single_value_of_incorrect_type():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    stringListArgField(stringListArg: 1)
                  }
                }
                """,
                [bad_value("[String]", "1", 4, 55)],
            )

    def describe_valid_non_nullable_value():
        def arg_on_optional_arg():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  dog {
                    isHousetrained(atOtherHomes: true)
                  }
                }
                """,
            )

        def no_arg_on_optional_arg():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  dog {
                    isHousetrained
                  }
                }
                """,
            )

        def multiple_args():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    multipleReqs(req1: 1, req2: 2)
                  }
                }
                """,
            )

        def multiple_args_reverse_order():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    multipleReqs(req2: 2, req1: 1)
                  }
                }
                """,
            )

        def no_args_on_multiple_optional():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    multipleOpts
                  }
                }
                """,
            )

        def one_arg_on_multiple_optional():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    multipleOpts(opt1: 1)
                  }
                }
                """,
            )

        def second_arg_on_multiple_optional():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    multipleOpts(opt2: 1)
                  }
                }
                """,
            )

        def multiple_reqs_on_mixed_list():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    multipleOptAndReq(req1: 3, req2: 4)
                  }
                }
                """,
            )

        def multiple_reqs_and_one_opt_on_mixed_list():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    multipleOptAndReq(req1: 3, req2: 4, opt1: 5)
                  }
                }
                """,
            )

        def all_reqs_and_and_opts_on_mixed_list():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    multipleOptAndReq(req1: 3, req2: 4, opt1: 5, opt2: 6)
                  }
                }
                """,
            )

    def describe_invalid_non_nullable_value():
        def incorrect_value_type():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    multipleReqs(req2: "two", req1: "one")
                  }
                }
                """,
                [bad_value("Int!", '"two"', 4, 40), bad_value("Int!", '"one"', 4, 53)],
            )

        def incorrect_value_and_missing_argument_provided_required_arguments():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    multipleReqs(req1: "one")
                  }
                }
                """,
                [bad_value("Int!", '"one"', 4, 40)],
            )

        def null_value():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    multipleReqs(req1: null)
                  }
                }
                """,
                [bad_value("Int!", "null", 4, 40)],
            )

    def describe_valid_input_object_value():
        def optional_arg_despite_required_field_in_type():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    complexArgField
                  }
                }
                """,
            )

        def partial_object_only_required():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    complexArgField(complexArg: { requiredField: true })
                  }
                }
                """,
            )

        def partial_object_required_field_can_be_falsey():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    complexArgField(complexArg: { requiredField: false })
                  }
                }
                """,
            )

        def partial_object_including_required():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    complexArgField(complexArg: { requiredField: true, intField: 4 })
                  }
                }
                """,
            )

        def full_object():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    complexArgField(complexArg: {
                      requiredField: true,
                      intField: 4,
                      stringField: "foo",
                      booleanField: false,
                      stringListField: ["one", "two"]
                    })
                  }
                }
                """,
            )

        def full_object_with_fields_in_different_order():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    complexArgField(complexArg: {
                      stringListField: ["one", "two"],
                      booleanField: false,
                      requiredField: true,
                      stringField: "foo",
                      intField: 4,
                    })
                  }
                }
                """,
            )

    def describe_invalid_input_object_value():
        def partial_object_missing_required():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    complexArgField(complexArg: { intField: 4 })
                  }
                }
                """,
                [required_field("ComplexInput", "requiredField", "Boolean!", 4, 49)],
            )

        def partial_object_invalid_field_type():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    complexArgField(complexArg: {
                      stringListField: ["one", 2],
                      requiredField: true,
                    })
                  }
                }
                """,
                [bad_value("String", "2", 5, 48)],
            )

        def partial_object_null_to_non_null_field():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    complexArgField(complexArg: {
                      requiredField: true,
                      nonNullField: null,
                    })
                  }
                }
                """,
                [bad_value("Boolean!", "null", 6, 37)],
            )

        def partial_object_unknown_field_arg():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  complicatedArgs {
                    complexArgField(complexArg: {
                      requiredField: true,
                      unknownField: "value"
                    })
                  }
                }
                """,
                [
                    unknown_field(
                        "ComplexInput",
                        "unknownField",
                        6,
                        23,
                        "Did you mean nonNullField, intField or booleanField?",
                    )
                ],
            )

        def reports_original_error_for_custom_scalar_which_throws():
            errors = expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  invalidArg(arg: 123)
                }
                """,
                [
                    bad_value(
                        "Invalid", "123", 3, 35, "Invalid scalar is always invalid: 123"
                    )
                ],
            )
            assert str(errors[0].original_error) == (
                "Invalid scalar is always invalid: 123"
            )

        def allows_custom_scalar_to_accept_complex_literals():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  test1: anyArg(arg: 123)
                  test2: anyArg(arg: "abc")
                  test3: anyArg(arg: [123, "abc"])
                  test4: anyArg(arg: {deep: [123, "abc"]})
                }
                """,
            )

    def describe_directive_arguments():
        def with_directives_of_valid_types():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  dog @include(if: true) {
                    name
                  }
                  human @skip(if: false) {
                    name
                  }
                }
                """,
            )

        def with_directives_with_incorrect_types():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                {
                  dog @include(if: "yes") {
                    name @skip(if: ENUM)
                  }
                }
                """,
                [
                    bad_value("Boolean!", '"yes"', 3, 36),
                    bad_value("Boolean!", "ENUM", 4, 36),
                ],
            )

    def describe_variable_default_values():
        def variables_with_valid_default_values():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                query WithDefaultValues(
                  $a: Int = 1,
                  $b: String = "ok",
                  $c: ComplexInput = { requiredField: true, intField: 3 }
                  $d: Int! = 123
                ) {
                  dog { name }
                }
                """,
            )

        def variables_with_valid_default_null_values():
            expect_passes_rule(
                ValuesOfCorrectTypeRule,
                """
                query WithDefaultValues(
                  $a: Int = null,
                  $b: String = null,
                  $c: ComplexInput = { requiredField: true, intField: null }
                ) {
                  dog { name }
                }
                """,
            )

        def variables_with_invalid_default_null_values():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                query WithDefaultValues(
                  $a: Int! = null,
                  $b: String! = null,
                  $c: ComplexInput = { requiredField: null, intField: null }
                ) {
                  dog { name }
                }
                """,
                [
                    bad_value("Int!", "null", 3, 30),
                    bad_value("String!", "null", 4, 33),
                    bad_value("Boolean!", "null", 5, 55),
                ],
            )

        def variables_with_invalid_default_values():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                query InvalidDefaultValues(
                  $a: Int = "one",
                  $b: String = 4,
                  $c: ComplexInput = "notverycomplex"
                ) {
                  dog { name }
                }
                """,
                [
                    bad_value("Int", '"one"', 3, 29),
                    bad_value("String", "4", 4, 32),
                    bad_value("ComplexInput", '"notverycomplex"', 5, 38),
                ],
            )

        def variables_with_complex_invalid_default_values():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                query WithDefaultValues(
                  $a: ComplexInput = { requiredField: 123, intField: "abc" }
                ) {
                  dog { name }
                }
                """,
                [bad_value("Boolean!", "123", 3, 55), bad_value("Int", '"abc"', 3, 70)],
            )

        def complex_variables_missing_required_fields():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                query MissingRequiredField($a: ComplexInput = {intField: 3}) {
                  dog { name }
                }
                """,
                [required_field("ComplexInput", "requiredField", "Boolean!", 2, 63)],
            )

        def list_variables_with_invalid_item():
            expect_fails_rule(
                ValuesOfCorrectTypeRule,
                """
                query InvalidItem($a: [String] = ["one", 2]) {
                  dog { name }
                }
                """,
                [bad_value("String", "2", 2, 58)],
            )
