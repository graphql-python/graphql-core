from functools import partial

from graphql.validation import ValuesOfCorrectTypeRule
from graphql.validation.rules.values_of_correct_type import (
    bad_value_message,
    bad_enum_value_message,
    required_field_message,
    unknown_field_message,
)

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, ValuesOfCorrectTypeRule)

assert_valid = partial(assert_errors, errors=[])


def bad_value(type_name, value, line, column, message=None):
    return {
        "message": bad_value_message(type_name, value, message),
        "locations": [(line, column)],
    }


def bad_enum_value(type_name, value, line, column, message=None):
    return {
        "message": bad_enum_value_message(type_name, value, message),
        "locations": [(line, column)],
    }


def required_field(type_name, field_name, field_type_name, line, column):
    return {
        "message": required_field_message(type_name, field_name, field_type_name),
        "locations": [(line, column)],
    }


def unknown_field(type_name, field_name, line, column, suggested_fields):
    return {
        "message": unknown_field_message(type_name, field_name, suggested_fields),
        "locations": [(line, column)],
    }


def describe_validate_values_of_correct_type():
    def describe_valid_values():
        def good_int_value():
            assert_valid(
                """
                {
                  complicatedArgs {
                    intArgField(intArg: 2)
                  }
                }
                """
            )

        def good_negative_int_value():
            assert_valid(
                """
                {
                  complicatedArgs {
                    intArgField(intArg: -2)
                  }
                }
                """
            )

        def good_boolean_value():
            assert_valid(
                """
                {
                  complicatedArgs {
                    booleanArgField(intArg: true)
                  }
                }
                """
            )

        def good_string_value():
            assert_valid(
                """
                {
                  complicatedArgs {
                    stringArgField(intArg: "foo")
                  }
                }
                """
            )

        def good_float_value():
            assert_valid(
                """
                {
                  complicatedArgs {
                    floatArgField(intArg: 1.1)
                  }
                }
                """
            )

        def good_negative_float_value():
            assert_valid(
                """
                {
                  complicatedArgs {
                    floatArgField(intArg: -1.1)
                  }
                }
                """
            )

        def int_into_id():
            assert_valid(
                """
                {
                  complicatedArgs {
                    idArgField(idArg: 1)
                  }
                }
                """
            )

        def string_into_id():
            assert_valid(
                """
                {
                  complicatedArgs {
                    idArgField(idArg: "someIdString")
                  }
                }
                """
            )

        def good_enum_value():
            assert_valid(
                """
                {
                  dog {
                    doesKnowCommand(dogCommand: SIT)
                  }
                }
                """
            )

        def enum_with_undefined_value():
            assert_valid(
                """
                {
                  complicatedArgs {
                    enumArgField(enumArg: UNKNOWN)
                  }
                }
                """
            )

        def enum_with_null_value():
            assert_valid(
                """
                {
                  complicatedArgs {
                    enumArgField(enumArg: NO_FUR)
                  }
                }
                """
            )

        def null_into_nullable_type():
            assert_valid(
                """
                {
                  complicatedArgs {
                    intArgField(intArg: null)
                  }
                }
                """
            )

            assert_valid(
                """
                {
                  dog(a: null, b: null, c:{ requiredField: true, intField: null }) {
                    name
                  }
                }
                """
            )

    def describe_invalid_string_values():
        def int_into_string():
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
                """
                {
                  dog {
                    doesKnowCommand(dogCommand: "SIT")
                  }
                }
                """,
                [bad_enum_value("DogCommand", '"SIT"', 4, 49, ["SIT"])],
            )

        def boolean_into_enum():
            assert_errors(
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
            assert_errors(
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
            assert_errors(
                """
                {
                  dog {
                    doesKnowCommand(dogCommand: sit)
                  }
                }
                """,
                [bad_enum_value("DogCommand", "sit", 4, 49, ["SIT"])],
            )

    def describe_valid_list_value():
        def good_list_value():
            assert_valid(
                """
                {
                  complicatedArgs {
                    stringListArgField(stringListArg: ["one", null, "two"])
                  }
                }
                """
            )

        def empty_list_value():
            assert_valid(
                """
                {
                  complicatedArgs {
                    stringListArgField(stringListArg: [])
                  }
                }
                """
            )

        def null_value():
            assert_valid(
                """
                {
                  complicatedArgs {
                    stringListArgField(stringListArg: null)
                  }
                }
                """
            )

        def single_value_into_list():
            assert_valid(
                """
                {
                  complicatedArgs {
                    stringListArgField(stringListArg: "one")
                  }
                }
                """
            )

    def describe_invalid_list_value():
        def incorrect_item_type():
            assert_errors(
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
            assert_errors(
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
            assert_valid(
                """
                {
                  dog {
                    isHousetrained(atOtherHomes: true)
                  }
                }
                """
            )

        def no_arg_on_optional_arg():
            assert_valid(
                """
                {
                  dog {
                    isHousetrained
                  }
                }
                """
            )

        def multiple_args():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleReqs(req1: 1, req2: 2)
                  }
                }
                """
            )

        def multiple_args_reverse_order():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleReqs(req2: 2, req1: 1)
                  }
                }
                """
            )

        def no_args_on_multiple_optional():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleOpts
                  }
                }
                """
            )

        def one_arg_on_multiple_optional():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleOpts(opt1: 1)
                  }
                }
                """
            )

        def second_arg_on_multiple_optional():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleOpts(opt2: 1)
                  }
                }
                """
            )

        def multiple_reqs_on_mixed_list():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleOptAndReq(req1: 3, req2: 4)
                  }
                }
                """
            )

        def multiple_reqs_and_one_opt_on_mixed_list():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleOptAndReq(req1: 3, req2: 4, opt1: 5)
                  }
                }
                """
            )

        def all_reqs_and_and_opts_on_mixed_list():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleOptAndReq(req1: 3, req2: 4, opt1: 5, opt2: 6)
                  }
                }
                """
            )

    def describe_invalid_non_nullable_value():
        def incorrect_value_type():
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_valid(
                """
                {
                  complicatedArgs {
                    complexArgField
                  }
                }
                """
            )

        def partial_object_only_required():
            assert_valid(
                """
                {
                  complicatedArgs {
                    complexArgField(complexArg: { requiredField: true })
                  }
                }
                """
            )

        def partial_object_required_field_can_be_falsey():
            assert_valid(
                """
                {
                  complicatedArgs {
                    complexArgField(complexArg: { requiredField: false })
                  }
                }
                """
            )

        def partial_object_including_required():
            assert_valid(
                """
                {
                  complicatedArgs {
                    complexArgField(complexArg: { requiredField: true, intField: 4 })
                  }
                }
                """
            )

        def full_object():
            assert_valid(
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
                """
            )

        def full_object_with_fields_in_different_order():
            assert_valid(
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
                """
            )

    def describe_invalid_input_object_value():
        def partial_object_missing_required():
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
                        ["nonNullField", "intField", "booleanField"],
                    )
                ],
            )

        def reports_original_error_for_custom_scalar_which_throws():
            errors = assert_errors(
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
            assert_valid(
                """
                {
                  test1: anyArg(arg: 123)
                  test2: anyArg(arg: "abc")
                  test3: anyArg(arg: [123, "abc"])
                  test4: anyArg(arg: {deep: [123, "abc"]})
                }
                """
            )

    def describe_directive_arguments():
        def with_directives_of_valid_types():
            assert_valid(
                """
                {
                  dog @include(if: true) {
                    name
                  }
                  human @skip(if: false) {
                    name
                  }
                }
                """
            )

        def with_directives_with_incorrect_types():
            assert_errors(
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
            assert_valid(
                """
                query WithDefaultValues(
                  $a: Int = 1,
                  $b: String = "ok",
                  $c: ComplexInput = { requiredField: true, intField: 3 }
                  $d: Int! = 123
                ) {
                  dog { name }
                }
                """
            )

        def variables_with_valid_default_null_values():
            assert_valid(
                """
                query WithDefaultValues(
                  $a: Int = null,
                  $b: String = null,
                  $c: ComplexInput = { requiredField: true, intField: null }
                ) {
                  dog { name }
                }
                """
            )

        def variables_with_invalid_default_null_values():
            assert_errors(
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
            assert_errors(
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
            assert_errors(
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
            assert_errors(
                """
                query MissingRequiredField($a: ComplexInput = {intField: 3}) {
                  dog { name }
                }
                """,
                [required_field("ComplexInput", "requiredField", "Boolean!", 2, 63)],
            )

        def list_variables_with_invalid_item():
            assert_errors(
                """
                query InvalidItem($a: [String] = ["one", 2]) {
                  dog { name }
                }
                """,
                [bad_value("String", "2", 2, 58)],
            )
