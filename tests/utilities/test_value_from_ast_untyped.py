from math import nan

from graphql.language import parse_value, FloatValueNode, IntValueNode
from graphql.pyutils import Undefined
from graphql.utilities import value_from_ast_untyped


def describe_value_from_ast_untyped():
    def _compare_value(value, expected):
        if expected is None:
            assert value is None
        elif expected is Undefined:
            assert value is Undefined
        elif expected is nan:
            assert value is nan
        else:
            assert value == expected

    def _test_case(value_text, expected):
        value_node = parse_value(value_text)
        _compare_value(value_from_ast_untyped(value_node), expected)

    def _test_case_with_vars(value_text, variables, expected):
        value_node = parse_value(value_text)
        _compare_value(value_from_ast_untyped(value_node, variables), expected)

    def parses_simple_values():
        _test_case("null", None)
        _test_case("true", True)
        _test_case("false", False)
        _test_case("123", 123)
        _test_case("123.456", 123.456)
        _test_case('"abc123"', "abc123")

    def parses_lists_of_values():
        _test_case("[true, false]", [True, False])
        _test_case("[true, 123.45]", [True, 123.45])
        _test_case("[true, null]", [True, None])
        _test_case('[true, ["foo", 1.2]]', [True, ["foo", 1.2]])

    def parses_input_objects():
        _test_case("{ int: 123, bool: false }", {"int": 123, "bool": False})
        _test_case('{ foo: [ { bar: "baz"} ] }', {"foo": [{"bar": "baz"}]})

    def parses_enum_values_as_plain_strings():
        _test_case("TEST_ENUM_VALUE", "TEST_ENUM_VALUE")
        _test_case("[TEST_ENUM_VALUE]", ["TEST_ENUM_VALUE"])

    def parses_variables():
        _test_case_with_vars("$testVariable", {"testVariable": "foo"}, "foo")
        _test_case_with_vars("[$testVariable]", {"testVariable": "foo"}, ["foo"])
        _test_case_with_vars(
            "{a:[$testVariable]}", {"testVariable": "foo"}, {"a": ["foo"]}
        )
        _test_case_with_vars("$testVariable", {"testVariable": None}, None)
        _test_case_with_vars("$testVariable", {"testVariable": nan}, nan)
        _test_case_with_vars("$testVariable", {}, Undefined)
        _test_case_with_vars("$testVariable", None, Undefined)

    def parse_invalid_int_as_nan():
        assert value_from_ast_untyped(IntValueNode(value="invalid")) is nan

    def parse_invalid_float_as_nan():
        assert value_from_ast_untyped(FloatValueNode(value="invalid")) is nan
