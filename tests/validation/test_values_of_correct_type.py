from functools import partial

from graphql.pyutils import Undefined
from graphql.type import (
    GraphQLArgument,
    GraphQLField,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLScalarType,
    GraphQLString,
)
from graphql.validation import ValuesOfCorrectTypeRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, ValuesOfCorrectTypeRule)

assert_valid = partial(assert_errors, errors=[])


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
                [
                    {
                        "message": "String cannot represent a non string value: 1",
                        "locations": [(4, 47)],
                    },
                ],
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
                [
                    {
                        "message": "String cannot represent a non string value: 1.0",
                        "locations": [(4, 47)],
                    },
                ],
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
                [
                    {
                        "message": "String cannot represent a non string value: true",
                        "locations": [(4, 47)],
                    },
                ],
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
                [
                    {
                        "message": "String cannot represent a non string value: BAR",
                        "locations": [(4, 47)],
                    },
                ],
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
                [
                    {
                        "message": 'Int cannot represent non-integer value: "3"',
                        "locations": [(4, 41)],
                    },
                ],
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
                [
                    {
                        "message": "Int cannot represent non 32-bit signed integer"
                        " value: 829384293849283498239482938",
                        "locations": [(4, 41)],
                    },
                ],
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
                [
                    {
                        "message": "Int cannot represent non-integer value: FOO",
                        "locations": [(4, 41)],
                    },
                ],
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
                [
                    {
                        "message": "Int cannot represent non-integer value: 3.0",
                        "locations": [(4, 41)],
                    }
                ],
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
                [
                    {
                        "message": "Int cannot represent non-integer value: 3.333",
                        "locations": [(4, 41)],
                    },
                ],
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
                [
                    {
                        "message": 'Float cannot represent non numeric value: "3.333"',
                        "locations": [(4, 45)],
                    },
                ],
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
                [
                    {
                        "message": "Float cannot represent non numeric value: true",
                        "locations": [(4, 45)],
                    },
                ],
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
                [
                    {
                        "message": "Float cannot represent non numeric value: FOO",
                        "locations": [(4, 45)],
                    },
                ],
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
                [
                    {
                        "message": "Boolean cannot represent a non boolean value: 2",
                        "locations": [(4, 49)],
                    },
                ],
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
                [
                    {
                        "message": "Boolean cannot represent a non boolean value: 1.0",
                        "locations": [(4, 49)],
                    }
                ],
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
                [
                    {
                        "message": "Boolean cannot represent a non boolean value:"
                        ' "true"',
                        "locations": [(4, 49)],
                    }
                ],
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
                [
                    {
                        "message": "Boolean cannot represent a non boolean value: TRUE",
                        "locations": [(4, 49)],
                    },
                ],
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
                [
                    {
                        "message": "ID cannot represent a non-string"
                        " and non-integer value: 1.0",
                        "locations": [(4, 39)],
                    }
                ],
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
                [
                    {
                        "message": "ID cannot represent a non-string"
                        " and non-integer value: true",
                        "locations": [(4, 39)],
                    },
                ],
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
                [
                    {
                        "message": "ID cannot represent a non-string"
                        " and non-integer value: SOMETHING",
                        "locations": [(4, 39)],
                    },
                ],
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
                [
                    {
                        "message": "Enum 'DogCommand' cannot represent non-enum value:"
                        " 2.",
                        "locations": [(4, 49)],
                    },
                ],
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
                [
                    {
                        "message": "Enum 'DogCommand' cannot represent non-enum value:"
                        " 1.0.",
                        "locations": [(4, 49)],
                    },
                ],
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
                [
                    {
                        "message": "Enum 'DogCommand' cannot represent non-enum value:"
                        ' "SIT".'
                        " Did you mean the enum value 'SIT'?",
                        "locations": [(4, 49)],
                    },
                ],
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
                [
                    {
                        "message": "Enum 'DogCommand' cannot represent non-enum value:"
                        " true.",
                        "locations": [(4, 49)],
                    },
                ],
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
                [
                    {
                        "message": "Value 'JUGGLE'"
                        " does not exist in 'DogCommand' enum.",
                        "locations": [(4, 49)],
                    },
                ],
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
                [
                    {
                        "message": "Value 'sit' does not exist in 'DogCommand' enum."
                        " Did you mean the enum value 'SIT'?",
                        "locations": [(4, 49)],
                    },
                ],
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
                [
                    {
                        "message": "String cannot represent a non string value: 2",
                        "locations": [(4, 63)],
                    },
                ],
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
                [
                    {
                        "message": "String cannot represent a non string value: 1",
                        "locations": [(4, 55)],
                    },
                ],
            )

    def describe_valid_non_nullable_value():
        def arg_on_optional_arg():
            assert_valid(
                """
                {
                  dog {
                    isHouseTrained(atOtherHomes: true)
                  }
                }
                """
            )

        def no_arg_on_optional_arg():
            assert_valid(
                """
                {
                  dog {
                    isHouseTrained
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

        def multiple_required_args_on_mixed_list():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleOptAndReq(req1: 3, req2: 4)
                  }
                }
                """
            )

        def multiple_required_and_one_optional_arg_on_mixed_list():
            assert_valid(
                """
                {
                  complicatedArgs {
                    multipleOptAndReq(req1: 3, req2: 4, opt1: 5)
                  }
                }
                """
            )

        def all_required_and_optional_args_on_mixed_list():
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
                [
                    {
                        "message": 'Int cannot represent non-integer value: "two"',
                        "locations": [(4, 40)],
                    },
                    {
                        "message": 'Int cannot represent non-integer value: "one"',
                        "locations": [(4, 53)],
                    },
                ],
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
                [
                    {
                        "message": 'Int cannot represent non-integer value: "one"',
                        "locations": [(4, 40)],
                    },
                ],
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
                [
                    {
                        "message": "Expected value of type 'Int!', found null.",
                        "locations": [(4, 40)],
                    },
                ],
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

        def partial_object_required_field_can_be_falsy():
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
                [
                    {
                        "message": "Field 'ComplexInput.requiredField'"
                        " of required type 'Boolean!' was not provided.",
                        "locations": [(4, 49)],
                    },
                ],
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
                [
                    {
                        "message": "String cannot represent a non string value: 2",
                        "locations": [(5, 48)],
                    },
                ],
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
                [
                    {
                        "message": "Expected value of type 'Boolean!', found null.",
                        "locations": [(6, 37)],
                    }
                ],
            )

        def partial_object_unknown_field_arg():
            assert_errors(
                """
                {
                  complicatedArgs {
                    complexArgField(complexArg: {
                      requiredField: true,
                      invalidField: "value"
                    })
                  }
                }
                """,
                [
                    {
                        "message": "Field 'invalidField'"
                        " is not defined by type 'ComplexInput'."
                        " Did you mean 'intField'?",
                        "locations": [(6, 23)],
                    },
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
                    {
                        "message": "Expected value of type 'Invalid', found 123;"
                        " Invalid scalar is always invalid: 123",
                        "locations": [(3, 35)],
                    },
                ],
            )
            assert str(errors[0].original_error) == (
                "Invalid scalar is always invalid: 123"
            )

        def reports_error_for_custom_scalar_that_returns_undefined():
            custom_scalar = GraphQLScalarType(
                "CustomScalar", parse_value=lambda value: Undefined
            )

            schema = GraphQLSchema(
                GraphQLObjectType(
                    "Query",
                    {
                        "invalidArg": GraphQLField(
                            GraphQLString, args={"arg": GraphQLArgument(custom_scalar)}
                        )
                    },
                )
            )

            assert_errors(
                """
                {
                  invalidArg(arg: 123)
                }
                """,
                [
                    {
                        "message": "Expected value of type 'CustomScalar', found 123.",
                        "locations": [(3, 35)],
                    },
                ],
                schema=schema,
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
                    {
                        "message": "Boolean cannot represent a non boolean value:"
                        ' "yes"',
                        "locations": [(3, 36)],
                    },
                    {
                        "message": "Boolean cannot represent a non boolean value: ENUM",
                        "locations": [(4, 36)],
                    },
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
                    {
                        "message": "Expected value of type 'Int!', found null.",
                        "locations": [(3, 30)],
                    },
                    {
                        "message": "Expected value of type 'String!', found null.",
                        "locations": [(4, 33)],
                    },
                    {
                        "message": "Expected value of type 'Boolean!', found null.",
                        "locations": [(5, 55)],
                    },
                ],
            )

        def variables_with_invalid_default_values():
            assert_errors(
                """
                query InvalidDefaultValues(
                  $a: Int = "one",
                  $b: String = 4,
                  $c: ComplexInput = "NotVeryComplex"
                ) {
                  dog { name }
                }
                """,
                [
                    {
                        "message": 'Int cannot represent non-integer value: "one"',
                        "locations": [(3, 29)],
                    },
                    {
                        "message": "String cannot represent a non string value: 4",
                        "locations": [(4, 32)],
                    },
                    {
                        "message": "Expected value of type 'ComplexInput',"
                        ' found "NotVeryComplex".',
                        "locations": [(5, 38)],
                    },
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
                [
                    {
                        "message": "Boolean cannot represent a non boolean value: 123",
                        "locations": [(3, 55)],
                    },
                    {
                        "message": 'Int cannot represent non-integer value: "abc"',
                        "locations": [(3, 70)],
                    },
                ],
            )

        def complex_variables_missing_required_fields():
            assert_errors(
                """
                query MissingRequiredField($a: ComplexInput = {intField: 3}) {
                  dog { name }
                }
                """,
                [
                    {
                        "message": "Field 'ComplexInput.requiredField'"
                        " of required type 'Boolean!' was not provided.",
                        "locations": [(2, 63)],
                    },
                ],
            )

        def list_variables_with_invalid_item():
            assert_errors(
                """
                query InvalidItem($a: [String] = ["one", 2]) {
                  dog { name }
                }
                """,
                [
                    {
                        "message": "String cannot represent a non string value: 2",
                        "locations": [(2, 58)],
                    },
                ],
            )
