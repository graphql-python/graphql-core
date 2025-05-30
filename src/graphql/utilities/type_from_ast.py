"""Generating GraphQL types from AST nodes"""

from __future__ import annotations

from typing import cast, overload

from ..language import ListTypeNode, NamedTypeNode, NonNullTypeNode, TypeNode
from ..pyutils import inspect
from ..type import (
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLNullableType,
    GraphQLSchema,
    GraphQLType,
)

__all__ = ["type_from_ast"]


@overload
def type_from_ast(
    schema: GraphQLSchema, type_node: NamedTypeNode
) -> GraphQLNamedType | None: ...


@overload
def type_from_ast(
    schema: GraphQLSchema, type_node: ListTypeNode
) -> GraphQLList | None: ...


@overload
def type_from_ast(
    schema: GraphQLSchema, type_node: NonNullTypeNode
) -> GraphQLNonNull | None: ...


@overload
def type_from_ast(schema: GraphQLSchema, type_node: TypeNode) -> GraphQLType | None: ...


def type_from_ast(
    schema: GraphQLSchema,
    type_node: TypeNode,
) -> GraphQLType | None:
    """Get the GraphQL type definition from an AST node.

    Given a Schema and an AST node describing a type, return a GraphQLType definition
    which applies to that type. For example, if provided the parsed AST node for
    ``[User]``, a GraphQLList instance will be returned, containing the type called
    "User" found in the schema. If a type called "User" is not found in the schema,
    then None will be returned.
    """
    inner_type: GraphQLType | None
    if isinstance(type_node, ListTypeNode):
        inner_type = type_from_ast(schema, type_node.type)
        return GraphQLList(inner_type) if inner_type else None
    if isinstance(type_node, NonNullTypeNode):
        inner_type = type_from_ast(schema, type_node.type)
        inner_type = cast("GraphQLNullableType", inner_type)
        return GraphQLNonNull(inner_type) if inner_type else None
    if isinstance(type_node, NamedTypeNode):
        return schema.get_type(type_node.name.value)

    # Not reachable. All possible type nodes have been considered.
    msg = f"Unexpected type node: {inspect(type_node)}."  # pragma: no cover
    raise TypeError(msg)  # pragma: no cover
