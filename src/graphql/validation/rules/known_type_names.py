"""Known type names rule"""

from __future__ import annotations

from typing import Any, Collection, cast

from ...error import GraphQLError
from ...language import (
    NamedTypeNode,
    Node,
    TypeSystemDefinitionNode,
    TypeSystemExtensionNode,
    is_type_definition_node,
    is_type_system_definition_node,
    is_type_system_extension_node,
)
from ...pyutils import did_you_mean, suggestion_list
from ...type import introspection_types, specified_scalar_types
from . import ASTValidationRule, SDLValidationContext, ValidationContext

try:
    from typing import TypeGuard
except ImportError:  # Python < 3.10
    from typing_extensions import TypeGuard


__all__ = ["KnownTypeNamesRule"]


class KnownTypeNamesRule(ASTValidationRule):
    """Known type names

    A GraphQL document is only valid if referenced types (specifically variable
    definitions and fragment conditions) are defined by the type schema.

    See https://spec.graphql.org/draft/#sec-Fragment-Spread-Type-Existence
    """

    def __init__(self, context: ValidationContext | SDLValidationContext) -> None:
        super().__init__(context)
        schema = context.schema
        self.existing_types_map = schema.type_map if schema else {}

        defined_types = []
        for def_ in context.document.definitions:
            if is_type_definition_node(def_):
                defined_types.append(def_.name.value)
        self.defined_types = set(defined_types)

        self.type_names = list(self.existing_types_map) + defined_types

    def enter_named_type(
        self,
        node: NamedTypeNode,
        _key: Any,
        parent: Node,
        _path: Any,
        ancestors: list[Node],
    ) -> None:
        type_name = node.name.value
        if (
            type_name not in self.existing_types_map
            and type_name not in self.defined_types
        ):
            try:
                definition_node = ancestors[2]
            except IndexError:
                definition_node = parent
            is_sdl = is_sdl_node(definition_node)
            if is_sdl and type_name in standard_type_names:
                return

            suggested_types = suggestion_list(
                type_name,
                list(standard_type_names) + self.type_names
                if is_sdl
                else self.type_names,
            )
            self.report_error(
                GraphQLError(
                    f"Unknown type '{type_name}'." + did_you_mean(suggested_types),
                    node,
                )
            )


standard_type_names = set(specified_scalar_types).union(introspection_types)


def is_sdl_node(
    value: Node | Collection[Node] | None,
) -> TypeGuard[TypeSystemDefinitionNode | TypeSystemExtensionNode]:
    return (
        value is not None
        and not isinstance(value, list)
        and (
            is_type_system_definition_node(cast("Node", value))
            or is_type_system_extension_node(cast("Node", value))
        )
    )
