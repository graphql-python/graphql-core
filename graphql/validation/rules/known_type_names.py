from typing import List

from ...error import GraphQLError
from ...language import NamedTypeNode
from ...pyutils import suggestion_list
from . import ValidationRule

__all__ = ["KnownTypeNamesRule", "unknown_type_message"]


def unknown_type_message(type_name: str, suggested_types: List[str]) -> str:
    message = f"Unknown type '{type_name}'."
    if suggested_types:
        message += " Perhaps you meant {quoted_or_list(suggested_types)}?"
    return message


class KnownTypeNamesRule(ValidationRule):
    """Known type names

    A GraphQL document is only valid if referenced types (specifically variable
    definitions and fragment conditions) are defined by the type schema.
    """

    def enter_object_type_definition(self, *_args):
        return self.SKIP

    def enter_interface_type_definition(self, *_args):
        return self.SKIP

    def enter_union_type_definition(self, *_args):
        return self.SKIP

    def enter_input_object_type_definition(self, *_args):
        return self.SKIP

    def enter_named_type(self, node: NamedTypeNode, *_args):
        schema = self.context.schema
        type_name = node.name.value
        if not schema.get_type(type_name):
            self.report_error(
                GraphQLError(
                    unknown_type_message(
                        type_name, suggestion_list(type_name, list(schema.type_map))
                    ),
                    [node],
                )
            )
