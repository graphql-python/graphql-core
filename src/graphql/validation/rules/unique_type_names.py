from typing import Dict

from ...error import GraphQLError
from ...language import NameNode, TypeDefinitionNode
from . import SDLValidationContext, SDLValidationRule

__all__ = [
    "UniqueTypeNamesRule",
    "duplicate_type_name_message",
    "existed_type_name_message",
]


def duplicate_type_name_message(type_name: str) -> str:
    return f"There can be only one type named '{type_name}'."


def existed_type_name_message(type_name: str) -> str:
    return (
        f"Type '{type_name}' already exists in the schema."
        " It cannot also be defined in this type definition."
    )


class UniqueTypeNamesRule(SDLValidationRule):
    """Unique type names

    A GraphQL document is only valid if all defined types have unique names.
    """

    def __init__(self, context: SDLValidationContext) -> None:
        super().__init__(context)
        self.known_type_names: Dict[str, NameNode] = {}
        self.schema = context.schema

    def check_type_name(self, node: TypeDefinitionNode, *_args):
        type_name = node.name.value

        if self.schema and self.schema.get_type(type_name):
            self.report_error(
                GraphQLError(existed_type_name_message(type_name), node.name)
            )
        else:
            if type_name in self.known_type_names:
                self.report_error(
                    GraphQLError(
                        duplicate_type_name_message(type_name),
                        [self.known_type_names[type_name], node.name],
                    )
                )
            else:
                self.known_type_names[type_name] = node.name
            return self.SKIP

    enter_scalar_type_definition = enter_object_type_definition = check_type_name
    enter_interface_type_definition = enter_union_type_definition = check_type_name
    enter_enum_type_definition = enter_input_object_type_definition = check_type_name
