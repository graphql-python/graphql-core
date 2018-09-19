from pytest import fixture

from graphql.error import INVALID
from graphql.language import parse_value
from graphql.utilities import value_from_ast_untyped


def describe_value_from_ast_untyped():
    @fixture
    def test_case(value_text, expected):
        value_node = parse_value(value_text)
        assert value_from_ast_untyped(value_node) == expected

    @fixture
    def test_case_with_vars(value_text, variables, expected):
        value_node = parse_value(value_text)
        assert value_from_ast_untyped(value_node, variables) == expected

    def parses_simple_values():
        test_case("null", None)
        test_case("true", True)
        test_case("false", False)
        test_case("123", 123)
        test_case("123.456", 123.456)
        test_case('"abc123"', "abc123")

    def parses_lists_of_values():
        test_case("[true, false]", [True, False])
        test_case("[true, 123.45]", [True, 123.45])
        test_case("[true, null]", [True, None])
        test_case('[true, ["foo", 1.2]]', [True, ["foo", 1.2]])

    def parses_input_objects():
        test_case("{ int: 123, bool: false }", {"int": 123, "bool": False})
        test_case('{ foo: [ { bar: "baz"} ] }', {"foo": [{"bar": "baz"}]})

    def parses_enum_values_as_plain_strings():
        test_case("TEST_ENUM_VALUE", "TEST_ENUM_VALUE")
        test_case("[TEST_ENUM_VALUE]", ["TEST_ENUM_VALUE"])

    def parses_variables():
        test_case_with_vars("$testVariable", {"testVariable": "foo"}, "foo")
        test_case_with_vars("[$testVariable]", {"testVariable": "foo"}, ["foo"])
        test_case_with_vars(
            "{a:[$testVariable]}", {"testVariable": "foo"}, {"a": ["foo"]}
        )
        test_case_with_vars("$testVariable", {"testVariable": None}, None)
        test_case_with_vars("$testVariable", {}, INVALID)
