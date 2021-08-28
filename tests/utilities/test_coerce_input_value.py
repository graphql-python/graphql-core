from math import nan
from typing import Any, List, NamedTuple, Union

from pytest import raises

from graphql.error import GraphQLError
from graphql.pyutils import Undefined
from graphql.type import (
    GraphQLEnumType,
    GraphQLFloat,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInputType,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLScalarType,
)
from graphql.utilities import coerce_input_value


class CoercedValueError(NamedTuple):
    error: str
    path: List[Union[str, int]]
    value: Any


class CoercedValue(NamedTuple):
    errors: List[CoercedValueError]
    value: Any


def expect_value(result: CoercedValue) -> Any:
    assert result.errors == []
    return result.value


def expect_errors(result: CoercedValue) -> List[CoercedValueError]:
    return result.errors


def describe_coerce_input_value():
    def _coerce_value(input_value: Any, type_: GraphQLInputType):
        errors: List[CoercedValueError] = []
        append = errors.append

        def on_error(path, invalid_value, error):
            append(CoercedValueError(error.message, path, invalid_value))

        value = coerce_input_value(input_value, type_, on_error)
        return CoercedValue(errors, value)

    def describe_for_graphql_non_null():
        TestNonNull = GraphQLNonNull(GraphQLInt)

        def returns_non_error_for_non_null_value():
            result = _coerce_value(1, TestNonNull)
            assert expect_value(result) == 1

        def returns_an_error_for_undefined_value():
            result = _coerce_value(Undefined, TestNonNull)
            assert expect_errors(result) == [
                ("Expected non-nullable type 'Int!' not to be None.", [], Undefined)
            ]

        def returns_an_error_for_null_value():
            result = _coerce_value(None, TestNonNull)
            assert expect_errors(result) == [
                ("Expected non-nullable type 'Int!' not to be None.", [], None)
            ]

    def describe_for_graphql_scalar():
        def _parse_value(input_dict):
            assert isinstance(input_dict, dict)
            error = input_dict.get("error")
            if error:
                raise ValueError(error)
            return input_dict.get("value")

        TestScalar = GraphQLScalarType("TestScalar", parse_value=_parse_value)

        def returns_no_error_for_valid_input():
            result = _coerce_value({"value": 1}, TestScalar)
            assert expect_value(result) == 1

        def returns_no_error_for_null_result():
            result = _coerce_value({"value": None}, TestScalar)
            assert expect_value(result) is None

        def returns_no_error_for_nan_result():
            result = _coerce_value({"value": nan}, TestScalar)
            assert expect_value(result) is nan

        def returns_an_error_for_undefined_result():
            result = _coerce_value({"value": Undefined}, TestScalar)
            assert expect_errors(result) == [
                ("Expected type 'TestScalar'.", [], {"value": Undefined})
            ]

        def returns_an_error_for_undefined_result_with_some_error_message():
            input_value = {"error": "Some error message"}
            result = _coerce_value(input_value, TestScalar)
            assert expect_errors(result) == [
                (
                    "Expected type 'TestScalar'. Some error message",
                    [],
                    {"error": "Some error message"},
                )
            ]

    def describe_for_graphql_enum():
        TestEnum = GraphQLEnumType(
            "TestEnum", {"FOO": "InternalFoo", "BAR": 123_456_789}
        )

        def returns_no_error_for_a_known_enum_name():
            foo_result = _coerce_value("FOO", TestEnum)
            assert expect_value(foo_result) == "InternalFoo"

            bar_result = _coerce_value("BAR", TestEnum)
            assert expect_value(bar_result) == 123_456_789

        def returns_an_error_for_misspelled_enum_value():
            result = _coerce_value("foo", TestEnum)
            assert expect_errors(result) == [
                (
                    "Value 'foo' does not exist in 'TestEnum' enum."
                    " Did you mean the enum value 'FOO'?",
                    [],
                    "foo",
                )
            ]

        def returns_an_error_for_incorrect_value_type():
            result1 = _coerce_value(123, TestEnum)
            assert expect_errors(result1) == [
                ("Enum 'TestEnum' cannot represent non-string value: 123.", [], 123)
            ]

            result2 = _coerce_value({"field": "value"}, TestEnum)
            assert expect_errors(result2) == [
                (
                    "Enum 'TestEnum' cannot represent non-string value:"
                    " {'field': 'value'}.",
                    [],
                    {"field": "value"},
                )
            ]

    def describe_for_graphql_input_object():
        TestInputObject = GraphQLInputObjectType(
            "TestInputObject",
            {
                "foo": GraphQLInputField(GraphQLNonNull(GraphQLInt)),
                "bar": GraphQLInputField(GraphQLInt),
            },
        )

        def returns_no_error_for_a_valid_input():
            result = _coerce_value({"foo": 123}, TestInputObject)
            assert expect_value(result) == {"foo": 123}

        def returns_an_error_for_a_non_dict_value():
            result = _coerce_value(123, TestInputObject)
            assert expect_errors(result) == [
                ("Expected type 'TestInputObject' to be a mapping.", [], 123)
            ]

        def returns_an_error_for_an_invalid_field():
            result = _coerce_value({"foo": nan}, TestInputObject)
            assert expect_errors(result) == [
                (
                    "Int cannot represent non-integer value: nan",
                    ["foo"],
                    nan,
                )
            ]

        def returns_multiple_errors_for_multiple_invalid_fields():
            result = _coerce_value({"foo": "abc", "bar": "def"}, TestInputObject)
            assert expect_errors(result) == [
                (
                    "Int cannot represent non-integer value: 'abc'",
                    ["foo"],
                    "abc",
                ),
                (
                    "Int cannot represent non-integer value: 'def'",
                    ["bar"],
                    "def",
                ),
            ]

        def returns_error_for_a_missing_required_field():
            result = _coerce_value({"bar": 123}, TestInputObject)
            assert expect_errors(result) == [
                (
                    "Field 'foo' of required type 'Int!' was not provided.",
                    [],
                    {"bar": 123},
                )
            ]

        def returns_error_for_an_unknown_field():
            result = _coerce_value({"foo": 123, "unknownField": 123}, TestInputObject)
            assert expect_errors(result) == [
                (
                    "Field 'unknownField' is not defined by type 'TestInputObject'.",
                    [],
                    {"foo": 123, "unknownField": 123},
                )
            ]

        def returns_error_for_a_misspelled_field():
            result = _coerce_value({"foo": 123, "bart": 123}, TestInputObject)
            assert expect_errors(result) == [
                (
                    "Field 'bart' is not defined by type 'TestInputObject'."
                    " Did you mean 'bar'?",
                    [],
                    {"foo": 123, "bart": 123},
                )
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
            result = _coerce_value({"realPart": 1}, ComplexInputObject)
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
            result = _coerce_value({"real": 1, "imag": 2}, ComplexInputObject)
            assert expect_value(result) == 1 + 2j

    def describe_for_graphql_input_object_with_default_value():
        def _get_test_input_object(default_value):
            return GraphQLInputObjectType(
                "TestInputObject",
                {
                    "foo": GraphQLInputField(
                        GraphQLScalarType("TestScalar"), default_value=default_value
                    )
                },
            )

        def returns_no_errors_for_valid_input_value():
            result = _coerce_value({"foo": 5}, _get_test_input_object(7))
            assert expect_value(result) == {"foo": 5}

        def returns_object_with_default_value():
            result = _coerce_value({}, _get_test_input_object(7))
            assert expect_value(result) == {"foo": 7}

        def returns_null_as_value():
            result = _coerce_value({}, _get_test_input_object(None))
            assert expect_value(result) == {"foo": None}

        def returns_nan_as_value():
            result = _coerce_value({}, _get_test_input_object(nan))
            result_value = expect_value(result)
            assert "foo" in result_value
            assert result_value["foo"] is nan

    def describe_for_graphql_list():
        TestList = GraphQLList(GraphQLInt)

        def returns_no_error_for_a_valid_input():
            result = _coerce_value([1, 2, 3], TestList)
            assert expect_value(result) == [1, 2, 3]

        def returns_no_error_for_a_valid_iterable_input():
            def list_generator():
                yield 1
                yield 2
                yield 3

            result = _coerce_value(list_generator(), TestList)
            assert expect_value(result) == [1, 2, 3]

        def returns_an_error_for_an_invalid_input():
            result = _coerce_value([1, "b", True, 4], TestList)
            assert expect_errors(result) == [
                (
                    "Int cannot represent non-integer value: 'b'",
                    [1],
                    "b",
                ),
                (
                    "Int cannot represent non-integer value: True",
                    [2],
                    True,
                ),
            ]

        def returns_a_list_for_a_non_list_value():
            result = _coerce_value(42, TestList)
            assert expect_value(result) == [42]

        def returns_a_list_for_a_dictionary():
            test_list_of_objects = GraphQLList(
                GraphQLInputObjectType(
                    "TestObject", {"length": GraphQLInputField(GraphQLInt)}
                )
            )

            result = _coerce_value({"length": 100500}, test_list_of_objects)
            assert expect_value(result) == [{"length": 100500}]

        def returns_a_list_for_a_non_list_invalid_value():
            result = _coerce_value("Undefined", TestList)
            assert expect_errors(result) == [
                (
                    "Int cannot represent non-integer value: 'Undefined'",
                    [],
                    "Undefined",
                )
            ]

        def returns_null_for_a_null_value():
            result = _coerce_value(None, TestList)
            assert expect_value(result) is None

    def describe_for_nested_graphql_list():
        TestNestedList = GraphQLList(GraphQLList(GraphQLInt))

        def returns_no_error_for_a_valid_input():
            result = _coerce_value([[1], [2], [3]], TestNestedList)
            assert expect_value(result) == [[1], [2], [3]]

        def returns_a_list_for_a_non_list_value():
            result = _coerce_value(42, TestNestedList)
            assert expect_value(result) == [[42]]

        def returns_null_for_a_null_value():
            result = _coerce_value(None, TestNestedList)
            assert expect_value(result) is None

        def returns_nested_list_for_nested_non_list_values():
            result = _coerce_value([1, 2, 3], TestNestedList)
            assert expect_value(result) == [[1], [2], [3]]

        def returns_nested_null_for_nested_null_values():
            result = _coerce_value([42, [None], None], TestNestedList)
            assert expect_value(result) == [[42], [None], None]

    def describe_with_default_on_error():
        def throw_error_without_path():
            with raises(GraphQLError) as exc_info:
                assert coerce_input_value(None, GraphQLNonNull(GraphQLInt))
            assert exc_info.value.message == (
                "Invalid value None: Expected non-nullable type 'Int!' not to be None."
            )

        def throw_error_with_path():
            with raises(GraphQLError) as exc_info:
                assert coerce_input_value(
                    [None], GraphQLList(GraphQLNonNull(GraphQLInt))
                )
            assert exc_info.value.message == (
                "Invalid value None at 'value[0]':"
                " Expected non-nullable type 'Int!' not to be None."
            )
