from typing import Any, List

from graphql.error import INVALID
from graphql.type import (
    GraphQLEnumType,
    GraphQLFloat,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLScalarType,
)
from graphql.utilities import coerce_value
from graphql.utilities.coerce_value import CoercedValue


def expect_value(result: CoercedValue) -> Any:
    assert result.errors is None
    return result.value


def expect_errors(result: CoercedValue) -> List[str]:
    errors = result.errors
    messages = [error.message for error in errors] if errors else []
    assert result.value is INVALID
    return messages


def describe_coerce_value():
    def describe_for_graphql_non_null():
        TestNonNull = GraphQLNonNull(GraphQLInt)

        def returns_non_error_for_non_null_value():
            result = coerce_value(1, TestNonNull)
            assert expect_value(result) == 1

        def returns_an_error_for_undefined_value():
            result = coerce_value(INVALID, TestNonNull)
            assert expect_errors(result) == [
                "Expected non-nullable type Int! not to be null."
            ]

        def returns_an_error_for_null_value():
            result = coerce_value(None, TestNonNull)
            assert expect_errors(result) == [
                "Expected non-nullable type Int! not to be null."
            ]

    def describe_for_graphql_scalar():
        def _parse_value(input_dict):
            assert isinstance(input_dict, dict)
            error = input_dict.get("error")
            if error:
                raise error
            return input_dict.get("value")

        TestScalar = GraphQLScalarType("TestScalar", parse_value=_parse_value)

        def returns_no_error_for_valid_input():
            result = coerce_value({"value": 1}, TestScalar)
            assert expect_value(result) == 1

        def returns_no_error_for_null_result():
            result = coerce_value({"value": None}, TestScalar)
            assert expect_value(result) is None

        def returns_an_error_for_undefined_result():
            error = ValueError("Some error message")
            result = coerce_value({"error": error}, TestScalar)
            assert expect_errors(result) == [
                "Expected type TestScalar. Some error message"
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

        def returns_an_error_for_misspelled_enum_value():
            result = coerce_value("foo", TestEnum)
            assert expect_errors(result) == [
                "Expected type TestEnum. Did you mean FOO?"
            ]

        def returns_an_error_for_incorrect_value_type():
            result1 = coerce_value(123, TestEnum)
            assert expect_errors(result1) == ["Expected type TestEnum."]

            result2 = coerce_value({"field": "value"}, TestEnum)
            assert expect_errors(result2) == ["Expected type TestEnum."]

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
            assert expect_errors(result) == [
                "Expected type TestInputObject to be a dict."
            ]

        def returns_an_error_for_an_invalid_field():
            result = coerce_value({"foo": "abc"}, TestInputObject)
            assert expect_errors(result) == [
                "Expected type Int at value.foo."
                " Int cannot represent non-integer value: 'abc'"
            ]

        def returns_multiple_errors_for_multiple_invalid_fields():
            result = coerce_value({"foo": "abc", "bar": "def"}, TestInputObject)
            assert expect_errors(result) == [
                "Expected type Int at value.foo."
                " Int cannot represent non-integer value: 'abc'",
                "Expected type Int at value.bar."
                " Int cannot represent non-integer value: 'def'",
            ]

        def returns_error_for_a_missing_required_field():
            result = coerce_value({"bar": 123}, TestInputObject)
            assert expect_errors(result) == [
                "Field value.foo of required type Int! was not provided."
            ]

        def returns_error_for_an_unknown_field():
            result = coerce_value({"foo": 123, "unknownField": 123}, TestInputObject)
            assert expect_errors(result) == [
                "Field 'unknownField' is not defined by type TestInputObject."
            ]

        def returns_error_for_a_misspelled_field():
            result = coerce_value({"foo": 123, "bart": 123}, TestInputObject)
            assert expect_errors(result) == [
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

    def describe_for_graphql_input_object_with_default_value():
        def _get_test_input_object(default_value):
            return GraphQLInputObjectType(
                "TestInputObject",
                {"foo": GraphQLInputField(GraphQLInt, default_value=default_value)},
            )

        def returns_no_errors_for_valid_input_value():
            result = coerce_value({"foo": 5}, _get_test_input_object(7))
            assert expect_value(result) == {"foo": 5}

        def returns_object_with_default_value():
            result = coerce_value({}, _get_test_input_object(7))
            assert expect_value(result) == {"foo": 7}

        def returns_null_as_value():
            result = coerce_value({}, _get_test_input_object(None))
            assert expect_value(result) == {"foo": None}

    def describe_for_graphql_list():
        TestList = GraphQLList(GraphQLInt)

        def returns_no_error_for_a_valid_input():
            result = coerce_value([1, 2, 3], TestList)
            assert expect_value(result) == [1, 2, 3]

        def returns_an_error_for_an_invalid_input():
            result = coerce_value([1, "b", True, 4], TestList)
            assert expect_errors(result) == [
                "Expected type Int at value[1]."
                " Int cannot represent non-integer value: 'b'",
                "Expected type Int at value[2]."
                " Int cannot represent non-integer value: True",
            ]

        def returns_a_list_for_a_non_list_value():
            result = coerce_value(42, TestList)
            assert expect_value(result) == [42]

        def returns_a_list_for_a_non_list_invalid_value():
            result = coerce_value("INVALID", TestList)
            assert expect_errors(result) == [
                "Expected type Int. Int cannot represent non-integer value: 'INVALID'"
            ]

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
