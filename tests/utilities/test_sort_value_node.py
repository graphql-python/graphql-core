from graphql.language import parse_value, print_ast
from graphql.utilities.sort_value_node import sort_value_node


def describe_sort_value_node():
    def _expect_sorted_value(source: str, expected: str) -> None:
        assert print_ast(sort_value_node(parse_value(source))) == expected

    def do_not_change_non_object_values():
        _expect_sorted_value("1", "1")
        _expect_sorted_value("3.14", "3.14")
        _expect_sorted_value("null", "null")
        _expect_sorted_value("true", "true")
        _expect_sorted_value("false", "false")
        _expect_sorted_value('"cba"', '"cba"')
        _expect_sorted_value(
            '[1, 3.14, null, false, "cba"]', '[1, 3.14, null, false, "cba"]'
        )
        _expect_sorted_value(
            '[[1, 3.14, null, false, "cba"]]', '[[1, 3.14, null, false, "cba"]]'
        )

    def sort_input_object_fields():
        _expect_sorted_value("{ b: 2, a: 1 }", "{a: 1, b: 2}")
        _expect_sorted_value("{ a: { c: 3, b: 2 } }", "{a: {b: 2, c: 3}}")
        _expect_sorted_value(
            "[{ b: 2, a: 1 }, { d: 4, c: 3}]",
            "[{a: 1, b: 2}, {c: 3, d: 4}]",
        )
        _expect_sorted_value(
            "{ b: { g: 7, f: 6 }, c: 3 , a: { d: 4, e: 5 } }",
            "{a: {d: 4, e: 5}, b: {f: 6, g: 7}, c: 3}",
        )
