import json
from typing import Any, List

from pytest import mark, raises

from graphql.language import (
    ListTypeNode,
    NamedTypeNode,
    NameNode,
    parse,
    parse_value,
)
from graphql.language.reducer import reduce
from graphql.language.visitor import BREAK


def describe_reduce():
    def rejects_invalid_nodes():
        with raises(TypeError) as exc_info:
            reduce({}, {})  # type: ignore[arg-type]
        assert str(exc_info.value) == "Not an AST Node: {}."

    @mark.parametrize(
        "node",
        [None, {"kind": "Unknown"}, {"kind": "constructor"}, {"kind": ["Name"]}],
        ids=["none", "unknown", "constructor", "list"],
    )
    def rejects_missing_or_invalid_node_kinds(node):
        with raises(TypeError, match="Not an AST Node: "):
            reduce(node, {})

    def rejects_invalid_children():
        with raises(TypeError) as exc_info:
            reduce(NamedTypeNode(name="T"), {})
        assert str(exc_info.value) == "Invalid AST Node: 'T'."

    def reduces_children_before_their_parent():
        ast = parse("{ a b { c } }", no_location=True)
        snapshot = json.dumps(ast.to_dict())
        count = reduce(
            ast,
            {
                "field": lambda node: 1 + (node.selection_set or 0),
                "selection_set": lambda node: sum(
                    value or 0 for value in node.selections
                ),
                "operation_definition": lambda node: node.selection_set,
                "document": lambda node: node.definitions[0],
            },
        )
        assert count == 3
        assert json.dumps(ast.to_dict()) == snapshot

    def reduces_deeply_nested_nodes_without_recursion():
        type_: Any = NamedTypeNode(name=NameNode(value="T"))
        for _depth in range(10_000):
            type_ = ListTypeNode(type=type_)

        count = 0

        def count_list_type(_node):
            nonlocal count
            count += 1

        reduce(type_, {"list_type": count_list_type})
        assert count == 10_000

    def uses_none_for_missing_callbacks():
        assert reduce(parse_value("1"), {}) is None
        assert reduce(
            parse_value("[1, 2]"), {"list_value": lambda node: node.values}
        ) == [None, None]
        values: List[str] = []
        assert (
            reduce(
                parse_value("[1, 2]"),
                {"int_value": lambda node: values.append(node.value)},
            )
            is None
        )
        assert values == ["1", "2"]

    @mark.parametrize(
        "value",
        [False, None, BREAK, [1, 2], parse_value("3")],
        ids=["false", "none", "break", "list", "node"],
    )
    def retains_values_as_reduced_values(value):
        reducer = {
            "int_value": lambda _node: value,
            "list_value": lambda node: node.values,
        }
        assert reduce(parse_value("1"), reducer) is value
        assert reduce(parse_value("[1, 2]"), reducer) == [value, value]
        assert (
            reduce(
                parse_value("[1, 2]"),
                {**reducer, "list_value": lambda _node: value},
            )
            is value
        )
