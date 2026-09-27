"""Predicates for GraphQL nodes"""

from .ast import (
    ArgumentCoordinateNode,
    DirectiveArgumentCoordinateNode,
    DirectiveCoordinateNode,
    MemberCoordinateNode,
    Node,
    DefinitionNode,
    DirectiveExtensionNode,
    ExecutableDefinitionNode,
    ListValueNode,
    ObjectValueNode,
    SchemaExtensionNode,
    SelectionNode,
    TypeCoordinateNode,
    TypeDefinitionNode,
    TypeExtensionNode,
    TypeNode,
    TypeSystemDefinitionNode,
    ValueNode,
    VariableNode,
)

__all__ = [
    "is_definition_node",
    "is_executable_definition_node",
    "is_selection_node",
    "is_value_node",
    "is_const_value_node",
    "is_type_node",
    "is_type_system_definition_node",
    "is_type_definition_node",
    "is_type_system_extension_node",
    "is_type_extension_node",
    "is_schema_coordinate_node",
]


def is_definition_node(node: Node) -> bool:
    """Check whether the given node represents a definition.

    :param node: the AST node to test
    :returns: whether the AST node is a definition node

    >>> from graphql import parse, is_definition_node
    >>> document = parse('{ hello }')
    >>> is_definition_node(document.definitions[0])
    True
    >>> is_definition_node(document)
    False
    """
    return isinstance(node, DefinitionNode)


def is_executable_definition_node(node: Node) -> bool:
    """Check whether the given node represents an executable definition.

    :param node: the AST node to test
    :returns: whether the AST node is an executable definition node

    >>> from graphql import parse, is_executable_definition_node
    >>> query = parse('{ hello }')
    >>> schema = parse('type Query { hello: String }')
    >>> is_executable_definition_node(query.definitions[0])
    True
    >>> is_executable_definition_node(schema.definitions[0])
    False
    """
    return isinstance(node, ExecutableDefinitionNode)


def is_selection_node(node: Node) -> bool:
    """Check whether the given node represents a selection.

    :param node: the AST node to test
    :returns: whether the AST node is a selection node

    >>> from graphql import parse, is_selection_node
    >>> document = parse('{ hello }')
    >>> field = document.definitions[0].selection_set.selections[0]
    >>> is_selection_node(field)
    True
    >>> is_selection_node(document)
    False
    """
    return isinstance(node, SelectionNode)


def is_value_node(node: Node) -> bool:
    """Check whether the given node represents a value.

    :param node: the AST node to test
    :returns: whether the AST node is a value node

    >>> from graphql import parse_type, parse_value, is_value_node
    >>> value = parse_value('[42]')
    >>> type_ = parse_type('[String!]')
    >>> is_value_node(value)
    True
    >>> is_value_node(type_)
    False
    """
    return isinstance(node, ValueNode)


def is_const_value_node(node: Node) -> bool:
    """Check whether the given node represents a constant value.

    :param node: the AST node to test
    :returns: whether the AST node is a constant value node

    >>> from graphql import parse_const_value, parse_value, is_const_value_node
    >>> value = parse_const_value('[42]')
    >>> variable = parse_value('$id')
    >>> is_const_value_node(value)
    True
    >>> is_const_value_node(variable)
    False
    """
    return is_value_node(node) and (
        any(is_const_value_node(value) for value in node.values)
        if isinstance(node, ListValueNode)
        else (
            any(is_const_value_node(field.value) for field in node.fields)
            if isinstance(node, ObjectValueNode)
            else not isinstance(node, VariableNode)
        )
    )


def is_type_node(node: Node) -> bool:
    """Check whether the given node represents a type.

    :param node: the AST node to test
    :returns: whether the AST node is a type node

    >>> from graphql import parse_type, parse_value, is_type_node
    >>> type_ = parse_type('[String!]')
    >>> value = parse_value('[42]')
    >>> is_type_node(type_)
    True
    >>> is_type_node(value)
    False
    """
    return isinstance(node, TypeNode)


def is_type_system_definition_node(node: Node) -> bool:
    """Check whether the given node represents a type system definition.

    :param node: the AST node to test
    :returns: whether the AST node is a type system definition node

    >>> from graphql import parse, is_type_system_definition_node
    >>> schema = parse('type Query { hello: String }')
    >>> query = parse('{ hello }')
    >>> is_type_system_definition_node(schema.definitions[0])
    True
    >>> is_type_system_definition_node(query.definitions[0])
    False
    """
    return isinstance(node, TypeSystemDefinitionNode)


def is_type_definition_node(node: Node) -> bool:
    """Check whether the given node represents a type definition.

    :param node: the AST node to test
    :returns: whether the AST node is a type definition node

    >>> from graphql import parse, is_type_definition_node
    >>> type_definition = parse('type Query { hello: String }')
    >>> directive_definition = parse('directive @cache on FIELD')
    >>> is_type_definition_node(type_definition.definitions[0])
    True
    >>> is_type_definition_node(directive_definition.definitions[0])
    False
    """
    return isinstance(node, TypeDefinitionNode)


def is_type_system_extension_node(node: Node) -> bool:
    """Check whether the given node represents a type system extension.

    :param node: the AST node to test
    :returns: whether the AST node is a type system extension node

    >>> from graphql import parse, is_type_system_extension_node
    >>> extension = parse('extend type Query { hello: String }')
    >>> definition = parse('type Query { hello: String }')
    >>> is_type_system_extension_node(extension.definitions[0])
    True
    >>> is_type_system_extension_node(definition.definitions[0])
    False
    """
    return isinstance(
        node, (SchemaExtensionNode, DirectiveExtensionNode, TypeExtensionNode)
    )


def is_type_extension_node(node: Node) -> bool:
    """Check whether the given node represents a type extension.

    :param node: the AST node to test
    :returns: whether the AST node is a type extension node

    >>> from graphql import parse, is_type_extension_node
    >>> extension = parse('extend type Query { hello: String }')
    >>> schema_extension = parse('extend schema { query: Query }')
    >>> is_type_extension_node(extension.definitions[0])
    True
    >>> is_type_extension_node(schema_extension.definitions[0])
    False
    """
    return isinstance(node, TypeExtensionNode)


def is_schema_coordinate_node(node: Node) -> bool:
    """Check whether the given node represents a schema coordinate.

    :param node: the AST node to test
    :returns: whether the AST node is a schema coordinate node

    >>> from graphql import parse, parse_schema_coordinate, is_schema_coordinate_node
    >>> coordinate = parse_schema_coordinate('Query.hero')
    >>> document = parse('{ hero }')
    >>> is_schema_coordinate_node(coordinate)
    True
    >>> is_schema_coordinate_node(document)
    False
    """
    return isinstance(
        node,
        (
            TypeCoordinateNode,
            MemberCoordinateNode,
            ArgumentCoordinateNode,
            DirectiveCoordinateNode,
            DirectiveArgumentCoordinateNode,
        ),
    )
