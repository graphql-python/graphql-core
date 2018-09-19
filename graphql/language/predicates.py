from .ast import (
    Node,
    DefinitionNode,
    ExecutableDefinitionNode,
    SchemaExtensionNode,
    SelectionNode,
    TypeDefinitionNode,
    TypeExtensionNode,
    TypeNode,
    TypeSystemDefinitionNode,
    ValueNode,
)

__all__ = [
    "is_definition_node",
    "is_executable_definition_node",
    "is_selection_node",
    "is_value_node",
    "is_type_node",
    "is_type_system_definition_node",
    "is_type_definition_node",
    "is_type_system_extension_node",
    "is_type_extension_node",
]


def is_definition_node(node: Node) -> bool:
    return isinstance(node, DefinitionNode)


def is_executable_definition_node(node: Node) -> bool:
    return isinstance(node, ExecutableDefinitionNode)


def is_selection_node(node: Node) -> bool:
    return isinstance(node, SelectionNode)


def is_value_node(node: Node) -> bool:
    return isinstance(node, ValueNode)


def is_type_node(node: Node) -> bool:
    return isinstance(node, TypeNode)


def is_type_system_definition_node(node: Node) -> bool:
    return isinstance(node, TypeSystemDefinitionNode)


def is_type_definition_node(node: Node) -> bool:
    return isinstance(node, TypeDefinitionNode)


def is_type_system_extension_node(node: Node) -> bool:
    return isinstance(node, (SchemaExtensionNode, TypeExtensionNode))


def is_type_extension_node(node: Node) -> bool:
    return isinstance(node, TypeExtensionNode)
