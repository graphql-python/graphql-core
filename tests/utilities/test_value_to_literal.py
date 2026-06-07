from math import inf, nan
from typing import Any

import pytest

from graphql.language import EnumValueNode, parse_const_value
from graphql.pyutils import Undefined
from graphql.type import (
    GraphQLBoolean,
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
    GraphQLString,
)
from graphql.utilities.value_to_literal import (
    default_scalar_value_to_literal,
    value_to_literal,
)


def describe_value_to_literal():
    def _test(value: Any, type_: GraphQLInputType, expected: str | None) -> None:
        assert value_to_literal(value, type_) == (
            None if expected is None else parse_const_value(expected, no_location=True)
        )

    def converts_null_values_to_null_ast():
        _test(None, GraphQLString, "null")
        _test(Undefined, GraphQLString, "null")
        _test(None, GraphQLNonNull(GraphQLString), None)

    def converts_boolean_values_to_boolean_asts():
        _test(True, GraphQLBoolean, "true")
        _test(False, GraphQLBoolean, "false")
        _test("false", GraphQLBoolean, None)

    def converts_int_number_values_to_int_asts():
        _test(0, GraphQLInt, "0")
        _test(-1, GraphQLInt, "-1")
        _test(2147483647, GraphQLInt, "2147483647")
        _test(2147483648, GraphQLInt, None)
        _test(0.5, GraphQLInt, None)

    def converts_float_number_values_to_float_asts():
        _test(123.5, GraphQLFloat, "123.5")
        _test(2e40, GraphQLFloat, "2e+40")
        _test(1099511627776, GraphQLFloat, "1099511627776")
        _test("0.5", GraphQLFloat, None)
        # Non-finite
        _test(nan, GraphQLFloat, None)
        _test(inf, GraphQLFloat, None)

    def converts_string_values_to_string_asts():
        _test("hello world", GraphQLString, '"hello world"')
        _test(123, GraphQLString, None)

    def converts_id_values_to_int_or_string_asts():
        _test("hello world", GraphQLID, '"hello world"')
        _test("123", GraphQLID, "123")
        _test(123, GraphQLID, "123")
        _test(
            "123456789123456789123456789123456789",
            GraphQLID,
            "123456789123456789123456789123456789",
        )
        _test(123.5, GraphQLID, None)
        _test(True, GraphQLID, None)

    my_enum = GraphQLEnumType(
        "MyEnum",
        {
            "HELLO": None,
            "COMPLEX": {"someArbitrary": "complexValue"},
        },
    )

    def converts_enum_names_to_enum_asts():
        _test("HELLO", my_enum, "HELLO")
        _test("COMPLEX", my_enum, "COMPLEX")
        # Undefined Enum
        _test("GOODBYE", my_enum, None)
        _test(123, my_enum, None)

    def converts_list_values_to_list_asts():
        _test(["FOO", "BAR"], GraphQLList(GraphQLString), '["FOO", "BAR"]')
        _test(["123", 123], GraphQLList(GraphQLID), "[123, 123]")
        # Invalid items create an invalid result
        _test(["FOO", 123], GraphQLList(GraphQLString), None)
        # Does not coerce items to list singletons
        _test("FOO", GraphQLList(GraphQLString), '"FOO"')

    input_obj = GraphQLInputObjectType(
        "MyInputObj",
        {
            "foo": GraphQLInputField(GraphQLNonNull(GraphQLFloat)),
            "bar": GraphQLInputField(GraphQLID),
        },
    )

    def converts_input_objects():
        _test({"foo": 3, "bar": "3"}, input_obj, "{ foo: 3, bar: 3 }")
        _test({"foo": 3}, input_obj, "{ foo: 3 }")

        # Non-object is invalid
        _test("123", input_obj, None)

        # Invalid fields create an invalid result
        _test({"foo": "3"}, input_obj, None)

        # Missing required fields create an invalid result
        _test({"bar": 3}, input_obj, None)

        # Additional fields create an invalid result
        _test({"foo": 3, "unknown": 3}, input_obj, None)

    def custom_scalar_types_may_define_value_to_literal():
        def value_to_literal_fn(value: Any) -> Any:
            if isinstance(value, str) and value.startswith("#"):
                return EnumValueNode(value=value[1:])
            return None

        custom_scalar = GraphQLScalarType(
            "CustomScalar", value_to_literal=value_to_literal_fn
        )

        _test("#FOO", custom_scalar, "FOO")
        _test("FOO", custom_scalar, None)

    def custom_scalar_types_may_throw_errors_from_value_to_literal():
        def value_to_literal_fn(_value: Any) -> Any:
            raise RuntimeError

        custom_scalar = GraphQLScalarType(
            "CustomScalar", value_to_literal=value_to_literal_fn
        )

        _test("FOO", custom_scalar, None)

    def custom_scalar_types_may_fall_back_on_default_value_to_literal():
        custom_scalar = GraphQLScalarType("CustomScalar")

        _test({"foo": "bar"}, custom_scalar, '{ foo: "bar" }')

    def describe_default_scalar_value_to_literal():
        def _test_default(value: Any, expected: str) -> None:
            assert default_scalar_value_to_literal(value) == parse_const_value(
                expected, no_location=True
            )

        def converts_null_values_to_null_asts():
            _test_default(None, "null")
            _test_default(Undefined, "null")

        def converts_boolean_values_to_boolean_asts():
            _test_default(True, "true")
            _test_default(False, "false")

        def converts_number_values_to_int_or_float_asts():
            _test_default(0, "0")
            _test_default(-1, "-1")
            _test_default(1099511627776, "1099511627776")
            _test_default(123.5, "123.5")
            _test_default(2e40, "2e+40")

        def converts_non_finite_number_values_to_null_asts():
            _test_default(nan, "null")
            _test_default(inf, "null")

        def converts_string_values_to_string_asts():
            _test_default("hello world", '"hello world"')

        def converts_list_values_to_list_asts():
            _test_default(["abc", 123], '["abc", 123]')

        def converts_object_values_to_object_asts():
            _test_default(
                {"foo": "abc", "bar": None, "baz": Undefined},
                '{ foo: "abc", bar: null }',
            )

        def throws_on_values_it_cannot_convert():
            with pytest.raises(TypeError, match="Cannot convert value to AST:"):
                default_scalar_value_to_literal(object())
