from operator import attrgetter
from typing import Callable

from graphql.language import (
    ast,
    Node,
    is_definition_node,
    is_executable_definition_node,
    is_selection_node,
    is_value_node,
    is_type_node,
    is_type_system_definition_node,
    is_type_definition_node,
    is_type_system_extension_node,
    is_type_extension_node,
)

all_ast_nodes = sorted(
    [
        node_type()
        for node_type in vars(ast).values()
        if type(node_type) is type and issubclass(node_type, Node)
    ],
    key=attrgetter("kind"),
)


def filter_nodes(predicate: Callable[[Node], bool]):
    return [node.kind for node in all_ast_nodes if predicate(node)]


def describe_ast_node_predicates():
    def check_definition_node():
        assert filter_nodes(is_definition_node) == [
            "definition",
            "directive_definition",
            "enum_type_definition",
            "enum_type_extension",
            "enum_value_definition",
            "executable_definition",
            "field_definition",
            "fragment_definition",
            "input_object_type_definition",
            "input_object_type_extension",
            "input_value_definition",
            "interface_type_definition",
            "interface_type_extension",
            "object_type_definition",
            "object_type_extension",
            "operation_definition",
            "scalar_type_definition",
            "scalar_type_extension",
            "schema_definition",
            "type_definition",
            "type_extension",
            "type_system_definition",
            "union_type_definition",
            "union_type_extension",
        ]

    def check_executable_definition_node():
        assert filter_nodes(is_executable_definition_node) == [
            "executable_definition",
            "fragment_definition",
            "operation_definition",
        ]

    def check_selection_node():
        assert filter_nodes(is_selection_node) == [
            "field",
            "fragment_spread",
            "inline_fragment",
            "selection",
        ]

    def check_value_node():
        assert filter_nodes(is_value_node) == [
            "boolean_value",
            "enum_value",
            "float_value",
            "int_value",
            "list_value",
            "null_value",
            "object_value",
            "string_value",
            "value",
            "variable",
        ]

    def check_type_node():
        assert filter_nodes(is_type_node) == [
            "list_type",
            "named_type",
            "non_null_type",
            "type",
        ]

    def check_type_system_definition_node():
        assert filter_nodes(is_type_system_definition_node) == [
            "directive_definition",
            "enum_type_definition",
            "enum_type_extension",
            "enum_value_definition",
            "input_object_type_definition",
            "input_object_type_extension",
            "interface_type_definition",
            "interface_type_extension",
            "object_type_definition",
            "object_type_extension",
            "scalar_type_definition",
            "scalar_type_extension",
            "schema_definition",
            "type_definition",
            "type_extension",
            "type_system_definition",
            "union_type_definition",
            "union_type_extension",
        ]

    def check_type_definition_node():
        assert filter_nodes(is_type_definition_node) == [
            "enum_type_definition",
            "enum_value_definition",
            "input_object_type_definition",
            "interface_type_definition",
            "object_type_definition",
            "scalar_type_definition",
            "type_definition",
            "union_type_definition",
        ]

    def check_type_system_extension_node():
        assert filter_nodes(is_type_system_extension_node) == [
            "enum_type_extension",
            "input_object_type_extension",
            "interface_type_extension",
            "object_type_extension",
            "scalar_type_extension",
            "schema_extension",
            "type_extension",
            "union_type_extension",
        ]

    def check_type_extension_node():
        assert filter_nodes(is_type_extension_node) == [
            "enum_type_extension",
            "input_object_type_extension",
            "interface_type_extension",
            "object_type_extension",
            "scalar_type_extension",
            "type_extension",
            "union_type_extension",
        ]
