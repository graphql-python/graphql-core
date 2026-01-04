import inspect
from collections.abc import Callable
from operator import attrgetter

import msgspec

from graphql.language import (
    Node,
    ast,
    is_const_value_node,
    is_definition_node,
    is_executable_definition_node,
    is_nullability_assertion_node,
    is_selection_node,
    is_type_definition_node,
    is_type_extension_node,
    is_type_node,
    is_type_system_definition_node,
    is_type_system_extension_node,
    is_value_node,
    parse_value,
)


def _create_node_instance(node_type: type[Node]) -> Node:
    """Create a node instance with dummy values for required fields."""
    # Default values for required fields by field name
    _dummy_name = ast.NameNode(value="")
    _dummy_type = ast.NamedTypeNode(name=_dummy_name)
    defaults = {
        "value": "",
        "name": _dummy_name,
        "type": _dummy_type,
        "operation": ast.OperationType.QUERY,
        "selection_set": ast.SelectionSetNode(selections=()),
        "selections": (),
        "definitions": (),
        "variable": ast.VariableNode(name=_dummy_name),
        "type_condition": _dummy_type,
        "fields": (),
        "arguments": (),
        "values": (),
        "directives": (),
        "variable_definitions": (),
        "interfaces": (),
        "types": (),
        "locations": (),
    }
    kwargs = {}
    for field in msgspec.structs.fields(node_type):
        if field.required and field.name in defaults:
            kwargs[field.name] = defaults[field.name]
    return node_type(**kwargs)


all_ast_nodes = sorted(
    [
        _create_node_instance(node_type)
        for node_type in vars(ast).values()
        if inspect.isclass(node_type)
        and issubclass(node_type, Node)
        and not node_type.__name__.startswith("Const")
    ],
    key=attrgetter("kind"),
)


def filter_nodes(predicate: Callable[[Node], bool]):
    return [node.kind for node in all_ast_nodes if predicate(node)]


def describe_ast_node_predicates():
    def check_definition_node():
        # With flattened hierarchy, only concrete definition nodes are matched
        assert filter_nodes(is_definition_node) == [
            "directive_definition",
            "enum_type_definition",
            "enum_type_extension",
            "enum_value_definition",
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
            "schema_extension",
            "union_type_definition",
            "union_type_extension",
        ]

    def check_executable_definition_node():
        assert filter_nodes(is_executable_definition_node) == [
            "fragment_definition",
            "operation_definition",
        ]

    def check_selection_node():
        assert filter_nodes(is_selection_node) == [
            "field",
            "fragment_spread",
            "inline_fragment",
        ]

    def check_nullability_assertion_node():
        assert filter_nodes(is_nullability_assertion_node) == [
            "error_boundary",
            "list_nullability_operator",
            "non_null_assertion",
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
            "variable",
        ]

    def check_const_value_node():
        assert is_const_value_node(parse_value('"value"')) is True
        assert is_const_value_node(parse_value("$var")) is False

        assert is_const_value_node(parse_value('{ field: "value" }')) is True
        assert is_const_value_node(parse_value("{ field: $var }")) is False

        assert is_const_value_node(parse_value('[ "value" ]')) is True
        assert is_const_value_node(parse_value("[ $var ]")) is False

    def check_type_node():
        assert filter_nodes(is_type_node) == [
            "list_type",
            "named_type",
            "non_null_type",
        ]

    def check_type_system_definition_node():
        assert filter_nodes(is_type_system_definition_node) == [
            "directive_definition",
            "enum_type_definition",
            "input_object_type_definition",
            "interface_type_definition",
            "object_type_definition",
            "scalar_type_definition",
            "schema_definition",
            "union_type_definition",
        ]

    def check_type_definition_node():
        assert filter_nodes(is_type_definition_node) == [
            "enum_type_definition",
            "input_object_type_definition",
            "interface_type_definition",
            "object_type_definition",
            "scalar_type_definition",
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
            "union_type_extension",
        ]

    def check_type_extension_node():
        assert filter_nodes(is_type_extension_node) == [
            "enum_type_extension",
            "input_object_type_extension",
            "interface_type_extension",
            "object_type_extension",
            "scalar_type_extension",
            "union_type_extension",
        ]
