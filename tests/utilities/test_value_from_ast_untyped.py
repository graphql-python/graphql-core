from __future__ import annotations

from math import isnan, nan
from typing import Any

from graphql.language import FloatValueNode, IntValueNode, parse_value
from graphql.pyutils import Undefined
from graphql.utilities import value_from_ast_untyped


def describe_value_from_ast_untyped():
    def _compare_value(value: Any, expected: Any):
        if expected is None:
            assert value is None
        elif expected is Undefined:
            assert value is Undefined
        elif isinstance(expected, float) and isnan(expected):
            assert isnan(value)
        else:
            assert value == expected

    def _expect_value_from(value_text: str, expected: Any):
        ast = parse_value(value_text)
        value = value_from_ast_untyped(ast)
        _compare_value(value, expected)

    def _expect_value_from_vars(
        value_text: str, variables: dict[str, Any] | None, expected: Any
    ):
        ast = parse_value(value_text)
        value = value_from_ast_untyped(ast, variables)
        _compare_value(value, expected)

    def parses_simple_values():
        _expect_value_from("null", None)
        _expect_value_from("true", True)
        _expect_value_from("false", False)
        _expect_value_from("123", 123)
        _expect_value_from("123.456", 123.456)
        _expect_value_from('"abc123"', "abc123")

    def parses_lists_of_values():
        _expect_value_from("[true, false]", [True, False])
        _expect_value_from("[true, 123.45]", [True, 123.45])
        _expect_value_from("[true, null]", [True, None])
        _expect_value_from('[true, ["foo", 1.2]]', [True, ["foo", 1.2]])

    def parses_input_objects():
        _expect_value_from("{ int: 123, bool: false }", {"int": 123, "bool": False})
        _expect_value_from('{ foo: [ { bar: "baz"} ] }', {"foo": [{"bar": "baz"}]})

    def parses_enum_values_as_plain_strings():
        _expect_value_from("TEST_ENUM_VALUE", "TEST_ENUM_VALUE")
        _expect_value_from("[TEST_ENUM_VALUE]", ["TEST_ENUM_VALUE"])

    def parses_variables():
        _expect_value_from_vars("$testVariable", {"testVariable": "foo"}, "foo")
        _expect_value_from_vars("[$testVariable]", {"testVariable": "foo"}, ["foo"])
        _expect_value_from_vars(
            "{a:[$testVariable]}", {"testVariable": "foo"}, {"a": ["foo"]}
        )
        _expect_value_from_vars("$testVariable", {"testVariable": None}, None)
        _expect_value_from_vars("$testVariable", {"testVariable": nan}, nan)
        _expect_value_from_vars("$testVariable", {}, Undefined)
        _expect_value_from_vars("$testVariable", None, Undefined)

    def parse_invalid_int_as_nan():
        assert isnan(value_from_ast_untyped(IntValueNode(value="invalid")))

    def parse_invalid_float_as_nan():
        assert isnan(value_from_ast_untyped(FloatValueNode(value="invalid")))
