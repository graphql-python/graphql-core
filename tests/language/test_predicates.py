from collections.abc import Callable
from operator import attrgetter

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


def _make_name() -> ast.NameNode:
    """Create a dummy NameNode."""
    return ast.NameNode(value="x")


def _make_named_type() -> ast.NamedTypeNode:
    """Create a dummy NamedTypeNode."""
    return ast.NamedTypeNode(name=_make_name())


def _make_selection_set() -> ast.SelectionSetNode:
    """Create a dummy SelectionSetNode."""
    return ast.SelectionSetNode()


def _create_node(node_class: type) -> Node:
    """Create a minimal valid instance of a node class."""
    name = _make_name()
    named_type = _make_named_type()
    selection_set = _make_selection_set()

    # Map node classes to their required constructor arguments
    constructors: dict[type, dict] = {
        # Nodes with required fields
        ast.NameNode: {"value": "x"},
        ast.FieldNode: {"name": name},
        ast.FragmentSpreadNode: {"name": name},
        ast.InlineFragmentNode: {"selection_set": selection_set},
        ast.ArgumentNode: {"name": name, "value": ast.NullValueNode()},
        ast.VariableNode: {"name": name},
        ast.IntValueNode: {"value": "0"},
        ast.FloatValueNode: {"value": "0.0"},
        ast.StringValueNode: {"value": ""},
        ast.BooleanValueNode: {"value": True},
        ast.EnumValueNode: {"value": "X"},
        ast.ObjectFieldNode: {"name": name, "value": ast.NullValueNode()},
        ast.ListTypeNode: {"type": named_type},
        ast.NonNullTypeNode: {"type": named_type},
        ast.NamedTypeNode: {"name": name},
        ast.OperationDefinitionNode: {
            "operation": ast.OperationType.QUERY,
            "selection_set": selection_set,
        },
        ast.VariableDefinitionNode: {
            "variable": ast.VariableNode(name=name),
            "type": named_type,
        },
        ast.FragmentDefinitionNode: {
            "name": name,
            "type_condition": named_type,
            "selection_set": selection_set,
        },
        ast.DirectiveNode: {"name": name},
        # Base classes with required fields
        ast.ExecutableDefinitionNode: {"selection_set": selection_set},
        ast.TypeDefinitionNode: {"name": name},
        ast.OperationTypeDefinitionNode: {
            "operation": ast.OperationType.QUERY,
            "type": named_type,
        },
        ast.ScalarTypeDefinitionNode: {"name": name},
        ast.ObjectTypeDefinitionNode: {"name": name},
        ast.FieldDefinitionNode: {"name": name, "type": named_type},
        ast.InputValueDefinitionNode: {"name": name, "type": named_type},
        ast.InterfaceTypeDefinitionNode: {"name": name},
        ast.UnionTypeDefinitionNode: {"name": name},
        ast.EnumTypeDefinitionNode: {"name": name},
        ast.EnumValueDefinitionNode: {"name": name},
        ast.InputObjectTypeDefinitionNode: {"name": name},
        ast.DirectiveDefinitionNode: {"name": name, "locations": ()},
        ast.TypeExtensionNode: {"name": name},
        ast.ScalarTypeExtensionNode: {"name": name},
        ast.ObjectTypeExtensionNode: {"name": name},
        ast.InterfaceTypeExtensionNode: {"name": name},
        ast.UnionTypeExtensionNode: {"name": name},
        ast.EnumTypeExtensionNode: {"name": name},
        ast.InputObjectTypeExtensionNode: {"name": name},
    }

    if node_class in constructors:
        return node_class(**constructors[node_class])
    # Node types with no required fields (base classes and simple nodes)
    return node_class()


# Build list of all concrete AST node types (excluding Const* variants)
all_ast_nodes = sorted(
    [
        _create_node(node_class)
        for node_class in vars(ast).values()
        if isinstance(node_class, type)
        and issubclass(node_class, Node)
        and node_class is not Node
        and not node_class.__name__.startswith("Const")
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

    def check_nullability_assertion_node():
        assert filter_nodes(is_nullability_assertion_node) == [
            "error_boundary",
            "list_nullability_operator",
            "non_null_assertion",
            "nullability_assertion",
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
            "type",
        ]

    def check_type_system_definition_node():
        assert filter_nodes(is_type_system_definition_node) == [
            "directive_definition",
            "enum_type_definition",
            "enum_type_extension",
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
