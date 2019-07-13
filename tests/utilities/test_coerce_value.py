from math import inf, nan
from typing import Any, List

from graphql.error import INVALID
from graphql.type import (
    GraphQLEnumType,
    GraphQLFloat,
    GraphQLID,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLString,
)
from graphql.utilities import coerce_value
from graphql.utilities.coerce_value import CoercedValue


def expect_value(result: CoercedValue) -> Any:
    assert result.errors is None
    return result.value


def expect_error(result: CoercedValue) -> List[str]:
    errors = result.errors
    messages = [error.message for error in errors] if errors else []
    assert result.value is INVALID
    return messages


def describe_coerce_value():
    def describe_for_graphql_string():
        def returns_error_for_array_input_as_string():
            result = coerce_value([1, 2, 3], GraphQLString)
            assert expect_error(result) == [
                f"Expected type String."
                " String cannot represent a non string value: [1, 2, 3]"
            ]

    def describe_for_graphql_id():
        def returns_error_for_array_input_as_string():
            result = coerce_value([1, 2, 3], GraphQLID)
            assert expect_error(result) == [
                f"Expected type ID. ID cannot represent value: [1, 2, 3]"
            ]

    def describe_for_graphql_int():
        def returns_value_for_integer():
            result = coerce_value(1, GraphQLInt)
            assert expect_value(result) == 1

        def returns_no_error_for_numeric_looking_string():
            result = coerce_value("1", GraphQLInt)
            assert expect_error(result) == [
                f"Expected type Int. Int cannot represent non-integer value: '1'"
            ]

        def returns_value_for_negative_int_input():
            result = coerce_value(-1, GraphQLInt)
            assert expect_value(result) == -1

        def returns_value_for_exponent_input():
            result = coerce_value(1e3, GraphQLInt)
            assert expect_value(result) == 1000

        def returns_null_for_null_value():
            result = coerce_value(None, GraphQLInt)
            assert expect_value(result) is None

        def returns_a_single_error_for_empty_string_as_value():
            result = coerce_value("", GraphQLInt)
            assert expect_error(result) == [
                "Expected type Int. Int cannot represent non-integer value: ''"
            ]

        def returns_a_single_error_for_2_32_input_as_int():
            result = coerce_value(1 << 32, GraphQLInt)
            assert expect_error(result) == [
                "Expected type Int. Int cannot represent"
                " non 32-bit signed integer value: 4294967296"
            ]

        def returns_a_single_error_for_float_input_as_int():
            result = coerce_value(1.5, GraphQLInt)
            assert expect_error(result) == [
                "Expected type Int. Int cannot represent non-integer value: 1.5"
            ]

        def returns_a_single_error_for_nan_input_as_int():
            result = coerce_value(nan, GraphQLInt)
            assert expect_error(result) == [
                "Expected type Int. Int cannot represent non-integer value: nan"
            ]

        def returns_a_single_error_for_infinity_input_as_int():
            result = coerce_value(inf, GraphQLInt)
            assert expect_error(result) == [
                "Expected type Int. Int cannot represent non-integer value: inf"
            ]

        def returns_a_single_error_for_char_input():
            result = coerce_value("a", GraphQLInt)
            assert expect_error(result) == [
                "Expected type Int. Int cannot represent non-integer value: 'a'"
            ]

        def returns_a_single_error_for_string_input():
            result = coerce_value("meow", GraphQLInt)
            assert expect_error(result) == [
                "Expected type Int. Int cannot represent non-integer value: 'meow'"
            ]

    def describe_for_graphql_float():
        def returns_value_for_integer():
            result = coerce_value(1, GraphQLFloat)
            assert expect_value(result) == 1

        def returns_value_for_decimal():
            result = coerce_value(1.1, GraphQLFloat)
            assert expect_value(result) == 1.1

        def returns_no_error_for_exponent_input():
            result = coerce_value(1e3, GraphQLFloat)
            assert expect_value(result) == 1000

        def returns_error_for_numeric_looking_string():
            result = coerce_value("1", GraphQLFloat)
            assert expect_error(result) == [
                "Expected type Float. Float cannot represent non numeric value: '1'"
            ]

        def returns_null_for_null_value():
            result = coerce_value(None, GraphQLFloat)
            assert expect_value(result) is None

        def returns_a_single_error_for_empty_string_input():
            result = coerce_value("", GraphQLFloat)
            assert expect_error(result) == [
                "Expected type Float. Float cannot represent non numeric value: ''"
            ]

        def returns_a_single_error_for_nan_input():
            result = coerce_value(nan, GraphQLFloat)
            assert expect_error(result) == [
                "Expected type Float. Float cannot represent non numeric value: nan"
            ]

        def returns_a_single_error_for_infinity_input():
            result = coerce_value(inf, GraphQLFloat)
            assert expect_error(result) == [
                "Expected type Float. Float cannot represent non numeric value: inf"
            ]

        def returns_a_single_error_for_char_input():
            result = coerce_value("a", GraphQLFloat)
            assert expect_error(result) == [
                "Expected type Float. Float cannot represent non numeric value: 'a'"
            ]

        def returns_a_single_error_for_string_input():
            result = coerce_value("meow", GraphQLFloat)
            assert expect_error(result) == [
                "Expected type Float. Float cannot represent non numeric value: 'meow'"
            ]

    def describe_for_graphql_enum():
        TestEnum = GraphQLEnumType(
            "TestEnum", {"FOO": "InternalFoo", "BAR": 123_456_789}
        )

        def returns_no_error_for_a_known_enum_name():
            foo_result = coerce_value("FOO", TestEnum)
            assert expect_value(foo_result) == "InternalFoo"

            bar_result = coerce_value("BAR", TestEnum)
            assert expect_value(bar_result) == 123_456_789

        def results_error_for_misspelled_enum_value():
            result = coerce_value("foo", TestEnum)
            assert expect_error(result) == ["Expected type TestEnum. Did you mean FOO?"]

        def results_error_for_incorrect_value_type():
            result1 = coerce_value(123, TestEnum)
            assert expect_error(result1) == ["Expected type TestEnum."]

            result2 = coerce_value({"field": "value"}, TestEnum)
            assert expect_error(result2) == ["Expected type TestEnum."]

    def describe_for_graphql_input_object():
        TestInputObject = GraphQLInputObjectType(
            "TestInputObject",
            {
                "foo": GraphQLInputField(GraphQLNonNull(GraphQLInt)),
                "bar": GraphQLInputField(GraphQLInt),
            },
        )

        def returns_no_error_for_a_valid_input():
            result = coerce_value({"foo": 123}, TestInputObject)
            assert expect_value(result) == {"foo": 123}

        def returns_an_error_for_a_non_dict_value():
            result = coerce_value(123, TestInputObject)
            assert expect_error(result) == [
                "Expected type TestInputObject to be a dict."
            ]

        def returns_an_error_for_an_invalid_field():
            result = coerce_value({"foo": "abc"}, TestInputObject)
            assert expect_error(result) == [
                "Expected type Int at value.foo."
                " Int cannot represent non-integer value: 'abc'"
            ]

        def returns_multiple_errors_for_multiple_invalid_fields():
            result = coerce_value({"foo": "abc", "bar": "def"}, TestInputObject)
            assert expect_error(result) == [
                "Expected type Int at value.foo."
                " Int cannot represent non-integer value: 'abc'",
                "Expected type Int at value.bar."
                " Int cannot represent non-integer value: 'def'",
            ]

        def returns_error_for_a_missing_required_field():
            result = coerce_value({"bar": 123}, TestInputObject)
            assert expect_error(result) == [
                "Field value.foo of required type Int! was not provided."
            ]

        def returns_error_for_an_unknown_field():
            result = coerce_value({"foo": 123, "unknownField": 123}, TestInputObject)
            assert expect_error(result) == [
                "Field 'unknownField' is not defined by type TestInputObject."
            ]

        def returns_error_for_a_misspelled_field():
            result = coerce_value({"foo": 123, "bart": 123}, TestInputObject)
            assert expect_error(result) == [
                "Field 'bart' is not defined by type TestInputObject."
                " Did you mean bar?"
            ]

        def transforms_names_using_out_name():
            # This is an extension of GraphQL.js.
            ComplexInputObject = GraphQLInputObjectType(
                "Complex",
                {
                    "realPart": GraphQLInputField(GraphQLFloat, out_name="real_part"),
                    "imagPart": GraphQLInputField(
                        GraphQLFloat, default_value=0, out_name="imag_part"
                    ),
                },
            )
            result = coerce_value({"realPart": 1}, ComplexInputObject)
            assert expect_value(result) == {"real_part": 1, "imag_part": 0}

        def transforms_values_with_out_type():
            # This is an extension of GraphQL.js.
            ComplexInputObject = GraphQLInputObjectType(
                "Complex",
                {
                    "real": GraphQLInputField(GraphQLFloat),
                    "imag": GraphQLInputField(GraphQLFloat),
                },
                out_type=lambda value: complex(value["real"], value["imag"]),
            )
            result = coerce_value({"real": 1, "imag": 2}, ComplexInputObject)
            assert expect_value(result) == 1 + 2j

    def describe_for_graphql_list():
        TestList = GraphQLList(GraphQLInt)

        def returns_no_error_for_a_valid_input():
            result = coerce_value([1, 2, 3], TestList)
            assert expect_value(result) == [1, 2, 3]

        def returns_an_error_for_an_invalid_input():
            result = coerce_value([1, "b", True], TestList)
            assert expect_error(result) == [
                "Expected type Int at value[1]."
                " Int cannot represent non-integer value: 'b'",
                "Expected type Int at value[2]."
                " Int cannot represent non-integer value: True",
            ]

        def returns_a_list_for_a_non_list_value():
            result = coerce_value(42, TestList)
            assert expect_value(result) == [42]

        def returns_null_for_a_null_value():
            result = coerce_value(None, TestList)
            assert expect_value(result) is None

    def describe_for_nested_graphql_list():
        TestNestedList = GraphQLList(GraphQLList(GraphQLInt))

        def returns_no_error_for_a_valid_input():
            result = coerce_value([[1], [2], [3]], TestNestedList)
            assert expect_value(result) == [[1], [2], [3]]

        def returns_a_list_for_a_non_list_value():
            result = coerce_value(42, TestNestedList)
            assert expect_value(result) == [[42]]

        def returns_null_for_a_null_value():
            result = coerce_value(None, TestNestedList)
            assert expect_value(result) is None

        def returns_nested_list_for_nested_non_list_values():
            result = coerce_value([1, 2, 3], TestNestedList)
            assert expect_value(result) == [[1], [2], [3]]

        def returns_nested_null_for_nested_null_values():
            result = coerce_value([42, [None], None], TestNestedList)
            assert expect_value(result) == [[42], [None], None]
