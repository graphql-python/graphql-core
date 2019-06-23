import re
from functools import partial
from typing import Any, List

from ...error import GraphQLError
from ...language import TypeDefinitionNode, TypeExtensionNode
from ...pyutils import did_you_mean, suggestion_list
from ...type import (
    is_enum_type,
    is_input_object_type,
    is_interface_type,
    is_object_type,
    is_scalar_type,
    is_union_type,
)
from . import SDLValidationContext, SDLValidationRule

__all__ = [
    "PossibleTypeExtensionsRule",
    "extending_unknown_type_message",
    "extending_different_type_kind_message",
]


def extending_unknown_type_message(type_name: str, suggested_types: List[str]) -> str:
    hint = did_you_mean([f"'{s}'" for s in suggested_types])
    return f"Cannot extend type '{type_name}' because it is not defined.{hint}"


def extending_different_type_kind_message(type_name: str, kind: str) -> str:
    return f"Cannot extend non-{kind} type {type_name}"


class PossibleTypeExtensionsRule(SDLValidationRule):
    """Possible type extension

     A type extension is only valid if the type is defined and has the same kind.
    """

    def __init__(self, context: SDLValidationContext) -> None:
        super().__init__(context)
        self.schema = context.schema
        self.defined_types = {
            def_.name.value: def_
            for def_ in context.document.definitions
            if isinstance(def_, TypeDefinitionNode)
        }

    def check_extension(self, node: TypeExtensionNode, *_args):
        schema = self.schema
        type_name = node.name.value
        def_node = self.defined_types.get(type_name)
        existing_type = schema.get_type(type_name) if schema else None

        if def_node:
            expected_kind = def_kind_to_ext_kind(def_node.kind)
            if expected_kind != node.kind:
                self.report_error(
                    GraphQLError(
                        extending_different_type_kind_message(
                            type_name, extension_kind_to_type_name(expected_kind)
                        ),
                        [def_node, node],
                    )
                )
        elif existing_type:
            expected_kind = type_to_ext_kind(existing_type)
            if expected_kind != node.kind:
                self.report_error(
                    GraphQLError(
                        extending_different_type_kind_message(
                            type_name, extension_kind_to_type_name(expected_kind)
                        ),
                        node,
                    )
                )
        else:
            all_type_names = list(self.defined_types)
            if self.schema:
                all_type_names.extend(self.schema.type_map)
            suggested_types = suggestion_list(type_name, all_type_names)
            self.report_error(
                GraphQLError(
                    extending_unknown_type_message(type_name, suggested_types),
                    node.name,
                )
            )

    enter_scalar_type_extension = enter_object_type_extension = check_extension
    enter_interface_type_extension = enter_union_type_extension = check_extension
    enter_enum_type_extension = enter_input_object_type_extension = check_extension


def_kind_to_ext_kind = partial(re.compile("(?<=_type_)definition$").sub, "extension")


def type_to_ext_kind(type_: Any) -> str:
    if is_scalar_type(type_):
        return "scalar_type_extension"
    elif is_object_type(type_):
        return "object_type_extension"
    elif is_interface_type(type_):
        return "interface_type_extension"
    elif is_union_type(type_):
        return "union_type_extension"
    elif is_enum_type(type_):
        return "enum_type_extension"
    elif is_input_object_type(type_):
        return "input_object_type_extension"
    else:
        return "unknown_type_extension"


_type_names_for_extension_kinds = {
    "scalar_type_extension": "scalar",
    "object_type_extension": "object",
    "interface_type_extension": "interface",
    "union_type_extension": "union",
    "enum_type_extension": "enum",
    "input_object_type_extension": "input object",
}


def extension_kind_to_type_name(kind: str) -> str:
    return _type_names_for_extension_kinds.get(kind, "unknown type")
