from __future__ import annotations

from math import isnan, nan
from typing import Any, NamedTuple

import pytest

from graphql.error import GraphQLError
from graphql.execution.values import (
    VariableValues,
    get_variable_values,
)
from graphql.language import (
    FloatValueNode,
    StringValueNode,
    TokenKind,
    parse_value,
    print_ast,
)
from graphql.language.parser import Parser
from graphql.pyutils import Undefined
from graphql.type import (
    GraphQLBoolean,
    GraphQLDefaultValueUsage,
    GraphQLEnumType,
    GraphQLFloat,
    GraphQLID,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInputType,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLString,
)
from graphql.utilities import coerce_input_literal, coerce_input_value
from graphql.utilities.coerce_input_value import coerce_default_value


class CoercedValueError(NamedTuple):
    error: str
    path: list[str | int]
    value: Any


class CoercedValue(NamedTuple):
    errors: list[CoercedValueError]
    value: Any


def expect_value(result: CoercedValue) -> Any:
    assert result.errors == []
    return result.value


def expect_errors(result: CoercedValue) -> list[CoercedValueError]:
    return result.errors


def describe_coerce_input_value():
    def _coerce_value(input_value: Any, type_: GraphQLInputType):
        errors: list[CoercedValueError] = []
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
            assert isnan(expect_value(result))

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
        DeepObject = GraphQLInputObjectType(
            "DeepObject",
            {
                "foo": GraphQLInputField(GraphQLNonNull(GraphQLInt)),
                "bar": GraphQLInputField(GraphQLInt),
            },
        )
        TestInputObject = GraphQLInputObjectType(
            "TestInputObject",
            {
                "foo": GraphQLInputField(GraphQLNonNull(GraphQLInt)),
                "bar": GraphQLInputField(GraphQLInt),
                "deepObject": GraphQLInputField(DeepObject),
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
                    "Field 'TestInputObject.foo' of required type 'Int!'"
                    " was not provided.",
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

        def returns_an_error_for_an_array_type():
            result = _coerce_value([{"foo": 1}, {"bar": 1}], TestInputObject)
            assert expect_errors(result) == [
                (
                    "Expected type 'TestInputObject' to be a mapping.",
                    [],
                    [{"foo": 1}, {"bar": 1}],
                )
            ]

        def returns_an_error_for_an_array_type_on_a_nested_field():
            result = _coerce_value({"foo": 1, "deepObject": [1, 2, 3]}, TestInputObject)
            assert expect_errors(result) == [
                (
                    "Expected type 'DeepObject' to be a mapping.",
                    ["deepObject"],
                    [1, 2, 3],
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

    def describe_for_graphql_input_object_that_is_one_of():
        TestInputObject = GraphQLInputObjectType(
            "TestInputObject",
            {
                "foo": GraphQLInputField(GraphQLInt),
                "bar": GraphQLInputField(GraphQLInt),
            },
            is_one_of=True,
        )

        def returns_no_error_for_a_valid_input():
            result = _coerce_value({"foo": 123}, TestInputObject)
            assert expect_value(result) == {"foo": 123}

        def returns_an_error_if_more_than_one_field_is_specified():
            result = _coerce_value({"foo": 123, "bar": None}, TestInputObject)
            assert expect_errors(result) == [
                (
                    "Exactly one key must be specified"
                    " for OneOf type 'TestInputObject'.",
                    [],
                    {"foo": 123, "bar": None},
                )
            ]

        def returns_an_error_if_the_one_field_is_null():
            result = _coerce_value({"bar": None}, TestInputObject)
            assert expect_errors(result) == [
                (
                    "Field 'bar' must be non-null.",
                    ["bar"],
                    None,
                )
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
                (
                    "Exactly one key must be specified"
                    " for OneOf type 'TestInputObject'.",
                    [],
                    {"foo": "abc", "bar": "def"},
                ),
            ]

        def returns_an_error_for_an_unknown_field():
            result = _coerce_value({"foo": 123, "unknownField": 123}, TestInputObject)
            assert expect_errors(result) == [
                (
                    "Field 'unknownField' is not defined by type 'TestInputObject'.",
                    [],
                    {"foo": 123, "unknownField": 123},
                )
            ]

        def returns_an_error_for_a_misspelled_field():
            result = _coerce_value({"bart": 123}, TestInputObject)
            assert expect_errors(result) == [
                (
                    "Field 'bart' is not defined by type 'TestInputObject'."
                    " Did you mean 'bar'?",
                    [],
                    {"bart": 123},
                ),
                (
                    "Exactly one key must be specified"
                    " for OneOf type 'TestInputObject'.",
                    [],
                    {"bart": 123},
                ),
            ]

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
            assert isnan(result_value["foo"])

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
            with pytest.raises(GraphQLError) as exc_info:
                assert coerce_input_value(None, GraphQLNonNull(GraphQLInt))
            assert exc_info.value.message == (
                "Invalid value None: Expected non-nullable type 'Int!' not to be None."
            )

        def throw_error_with_path():
            with pytest.raises(GraphQLError) as exc_info:
                assert coerce_input_value(
                    [None], GraphQLList(GraphQLNonNull(GraphQLInt))
                )
            assert exc_info.value.message == (
                "Invalid value None at 'value[0]':"
                " Expected non-nullable type 'Int!' not to be None."
            )


def describe_coerce_input_literal():
    def _test(
        value_text: str,
        type_: GraphQLInputType,
        expected: Any,
        variable_values: VariableValues | None = None,
    ):
        ast = parse_value(value_text)
        value = coerce_input_literal(ast, type_, variable_values)
        if expected is Undefined:
            assert value is Undefined
        elif isinstance(expected, float) and isnan(expected):
            assert isnan(value)
        else:
            assert value == expected

    def _test_with_variables(
        variable_defs: str,
        inputs: dict[str, Any],
        value_text: str,
        type_: GraphQLInputType,
        expected: Any,
    ):
        parser = Parser(variable_defs)
        parser.expect_token(TokenKind.SOF)
        variable_values = get_variable_values(
            GraphQLSchema(), parser.parse_variable_definitions(), inputs
        )
        assert not isinstance(variable_values, list)
        _test(value_text, type_, expected, variable_values)

    def converts_according_to_input_coercion_rules():
        _test("true", GraphQLBoolean, True)
        _test("false", GraphQLBoolean, False)
        _test("123", GraphQLInt, 123)
        _test("123", GraphQLFloat, 123)
        _test("123.456", GraphQLFloat, 123.456)
        _test('"abc123"', GraphQLString, "abc123")
        _test("123456", GraphQLID, "123456")
        _test('"123456"', GraphQLID, "123456")

    def does_not_convert_when_input_coercion_rules_reject_a_value():
        _test("123", GraphQLBoolean, Undefined)
        _test("123.456", GraphQLInt, Undefined)
        _test("true", GraphQLInt, Undefined)
        _test('"123"', GraphQLInt, Undefined)
        _test('"123"', GraphQLFloat, Undefined)
        _test("123", GraphQLString, Undefined)
        _test("true", GraphQLString, Undefined)
        _test("123.456", GraphQLString, Undefined)
        _test("123.456", GraphQLID, Undefined)

    def convert_using_parse_const_literal_from_a_custom_scalar_type():
        def pass_through_parse_const_literal(node):
            assert node.kind == "string_value"
            return node.value

        pass_through_scalar = GraphQLScalarType(
            "PassThroughScalar",
            parse_const_literal=pass_through_parse_const_literal,
            parse_value=lambda value: value,  # pragma: no cover
        )

        _test('"value"', pass_through_scalar, "value")

        def print_parse_const_literal(node):
            return f"~~~{print_ast(node)}~~~"

        print_scalar = GraphQLScalarType(
            "PrintScalar",
            parse_const_literal=print_parse_const_literal,
            parse_value=lambda value: value,  # pragma: no cover
        )

        _test('"value"', print_scalar, '~~~"value"~~~')
        _test_with_variables(
            "($var: String)",
            {"var": "value"},
            "{ field: $var }",
            print_scalar,
            '~~~{ field: "value" }~~~',
        )

        def throw_parse_const_literal(_node):
            raise RuntimeError("Test")

        throw_scalar = GraphQLScalarType(
            "ThrowScalar",
            parse_const_literal=throw_parse_const_literal,
            parse_value=lambda value: value,  # pragma: no cover
        )

        _test("value", throw_scalar, Undefined)

        def undefined_parse_const_literal(_node):
            return Undefined

        return_undefined_scalar = GraphQLScalarType(
            "ReturnUndefinedScalar",
            parse_const_literal=undefined_parse_const_literal,
            parse_value=lambda value: value,  # pragma: no cover
        )

        _test("value", return_undefined_scalar, Undefined)

    def converts_enum_values_according_to_input_coercion_rules():
        test_enum = GraphQLEnumType(
            "TestColor",
            {
                "RED": 1,
                "GREEN": 2,
                "BLUE": 3,
                "NULL": None,
                "NAN": nan,
                "NO_CUSTOM_VALUE": Undefined,
            },
        )

        _test("RED", test_enum, 1)
        _test("BLUE", test_enum, 3)
        _test("3", test_enum, Undefined)
        _test('"BLUE"', test_enum, Undefined)
        _test("null", test_enum, None)
        _test("NULL", test_enum, None)
        _test("NULL", GraphQLNonNull(test_enum), None)
        _test("NAN", test_enum, nan)
        # Note: differs from GraphQL.js, which returns the value name here.
        _test("NO_CUSTOM_VALUE", test_enum, Undefined)

    # make a Boolean!
    non_null_bool = GraphQLNonNull(GraphQLBoolean)
    # make a [Boolean]
    list_of_bool = GraphQLList(GraphQLBoolean)
    # make a [Boolean!]
    list_of_non_null_bool = GraphQLList(non_null_bool)
    # make a [Boolean]!
    non_null_list_of_bool = GraphQLNonNull(list_of_bool)
    # make a [Boolean!]!
    non_null_list_of_non_null_bool = GraphQLNonNull(list_of_non_null_bool)

    def coerces_to_null_unless_non_null():
        _test("null", GraphQLBoolean, None)
        _test("null", non_null_bool, Undefined)

    def coerces_lists_of_values():
        _test("true", list_of_bool, [True])
        _test("123", list_of_bool, Undefined)
        _test("null", list_of_bool, None)
        _test("[true, false]", list_of_bool, [True, False])
        _test("[true, 123]", list_of_bool, Undefined)
        _test("[true, null]", list_of_bool, [True, None])
        _test("{ true: true }", list_of_bool, Undefined)

    def coerces_non_null_lists_of_values():
        _test("true", non_null_list_of_bool, [True])
        _test("123", non_null_list_of_bool, Undefined)
        _test("null", non_null_list_of_bool, Undefined)
        _test("[true, false]", non_null_list_of_bool, [True, False])
        _test("[true, 123]", non_null_list_of_bool, Undefined)
        _test("[true, null]", non_null_list_of_bool, [True, None])

    def coerces_lists_of_non_null_values():
        _test("true", list_of_non_null_bool, [True])
        _test("123", list_of_non_null_bool, Undefined)
        _test("null", list_of_non_null_bool, None)
        _test("[true, false]", list_of_non_null_bool, [True, False])
        _test("[true, 123]", list_of_non_null_bool, Undefined)
        _test("[true, null]", list_of_non_null_bool, Undefined)

    def coerces_non_null_lists_of_non_null_values():
        _test("true", non_null_list_of_non_null_bool, [True])
        _test("123", non_null_list_of_non_null_bool, Undefined)
        _test("null", non_null_list_of_non_null_bool, Undefined)
        _test("[true, false]", non_null_list_of_non_null_bool, [True, False])
        _test("[true, 123]", non_null_list_of_non_null_bool, Undefined)
        _test("[true, null]", non_null_list_of_non_null_bool, Undefined)

    def uses_default_values_for_unprovided_fields():
        type_ = GraphQLInputObjectType(
            "TestInput",
            {
                "int": GraphQLInputField(GraphQLInt, default_value=42),
                "float": GraphQLInputField(
                    GraphQLFloat, default_value_literal=FloatValueNode(value="3.14")
                ),
            },
        )

        _test("{}", type_, {"int": 42, "float": 3.14})

    test_input_obj = GraphQLInputObjectType(
        "TestInput",
        {
            "int": GraphQLInputField(GraphQLInt, default_value=42),
            "bool": GraphQLInputField(GraphQLBoolean),
            "requiredBool": GraphQLInputField(non_null_bool),
        },
    )

    test_one_of_input_obj = GraphQLInputObjectType(
        "TestOneOfInput",
        {
            "a": GraphQLInputField(GraphQLString),
            "b": GraphQLInputField(GraphQLString),
        },
        is_one_of=True,
    )

    def coerces_input_objects_according_to_input_coercion_rules():
        _test("null", test_input_obj, None)
        _test("123", test_input_obj, Undefined)
        _test("[]", test_input_obj, Undefined)
        _test(
            "{ requiredBool: true }",
            test_input_obj,
            {"int": 42, "requiredBool": True},
        )
        _test(
            "{ int: null, requiredBool: true }",
            test_input_obj,
            {"int": None, "requiredBool": True},
        )
        _test(
            "{ int: 123, requiredBool: false }",
            test_input_obj,
            {"int": 123, "requiredBool": False},
        )
        _test(
            "{ bool: true, requiredBool: false }",
            test_input_obj,
            {"int": 42, "bool": True, "requiredBool": False},
        )
        _test("{ int: true, requiredBool: true }", test_input_obj, Undefined)
        _test("{ requiredBool: null }", test_input_obj, Undefined)
        _test("{ bool: true }", test_input_obj, Undefined)
        _test("{ requiredBool: true, unknown: 123 }", test_input_obj, Undefined)
        _test('{ a: "abc" }', test_one_of_input_obj, {"a": "abc"})
        _test('{ b: "def" }', test_one_of_input_obj, {"b": "def"})
        _test('{ a: "abc", b: null }', test_one_of_input_obj, Undefined)
        _test("{ a: null }", test_one_of_input_obj, Undefined)
        _test("{ a: 1 }", test_one_of_input_obj, Undefined)
        _test('{ a: "abc", b: "def" }', test_one_of_input_obj, Undefined)
        _test("{}", test_one_of_input_obj, Undefined)
        _test('{ c: "abc" }', test_one_of_input_obj, Undefined)

    def accepts_variable_values_assuming_already_coerced():
        _test("$var", GraphQLBoolean, Undefined)
        _test_with_variables(
            "($var: Boolean)", {"var": True}, "$var", GraphQLBoolean, True
        )
        _test_with_variables(
            "($var: Boolean)", {"var": None}, "$var", GraphQLBoolean, None
        )
        _test_with_variables(
            "($var: Boolean)", {"var": None}, "$var", non_null_bool, Undefined
        )

    def asserts_variables_are_provided_as_items_in_lists():
        _test("[ $foo ]", list_of_bool, [None])
        _test("[ $foo ]", list_of_non_null_bool, Undefined)
        _test_with_variables(
            "($foo: Boolean)", {"foo": True}, "[ $foo ]", list_of_non_null_bool, [True]
        )
        # Note: variables are expected to have already been coerced, so we
        # do not expect the singleton wrapping behavior for variables.
        _test_with_variables(
            "($foo: Boolean)", {"foo": True}, "$foo", list_of_non_null_bool, True
        )
        _test_with_variables(
            "($foo: [Boolean])", {"foo": [True]}, "$foo", list_of_non_null_bool, [True]
        )

    def omits_input_object_fields_for_unprovided_variables():
        _test(
            "{ int: $foo, bool: $foo, requiredBool: true }",
            test_input_obj,
            {"int": 42, "requiredBool": True},
        )
        _test("{ requiredBool: $foo }", test_input_obj, Undefined)
        _test_with_variables(
            "($foo: Boolean)",
            {"foo": True},
            "{ requiredBool: $foo }",
            test_input_obj,
            {"int": 42, "requiredBool": True},
        )

    def transforms_names_using_out_name():
        # This is an extension of GraphQL.js.
        complex_input_obj = GraphQLInputObjectType(
            "Complex",
            {
                "realPart": GraphQLInputField(GraphQLFloat, out_name="real_part"),
                "imagPart": GraphQLInputField(
                    GraphQLFloat, default_value=0, out_name="imag_part"
                ),
            },
        )
        _test(
            "{ realPart: 1 }",
            complex_input_obj,
            {"real_part": 1, "imag_part": 0},
        )

    def transforms_values_with_out_type():
        # This is an extension of GraphQL.js.
        complex_input_obj = GraphQLInputObjectType(
            "Complex",
            {
                "real": GraphQLInputField(GraphQLFloat),
                "imag": GraphQLInputField(GraphQLFloat),
            },
            out_type=lambda value: complex(value["real"], value["imag"]),
        )
        _test("{ real: 1, imag: 2 }", complex_input_obj, 1 + 2j)


def describe_coerce_default_value():
    def memoizes_coercion():
        parse_value_calls: list[Any] = []

        def parse_value(value):
            parse_value_calls.append(value)
            return value

        spy_scalar = GraphQLScalarType("SpyScalar", parse_value=parse_value)

        default_value_usage = GraphQLDefaultValueUsage(
            literal=StringValueNode(value="hello")
        )
        assert coerce_default_value(default_value_usage, spy_scalar) == "hello"

        # Call a second time
        assert coerce_default_value(default_value_usage, spy_scalar) == "hello"
        assert parse_value_calls == ["hello"]
