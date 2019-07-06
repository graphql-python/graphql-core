from collections import defaultdict
from typing import Any, Dict

from ...error import GraphQLError
from ...language import NameNode, ObjectTypeDefinitionNode
from ...type import is_object_type, is_interface_type, is_input_object_type
from . import SDLValidationContext, SDLValidationRule

__all__ = [
    "UniqueFieldDefinitionNamesRule",
    "duplicate_field_definition_name_message",
    "existed_field_definition_name_message",
]


def duplicate_field_definition_name_message(type_name: str, field_name: str) -> str:
    return f"Field '{type_name}.{field_name}' can only be defined once."


def existed_field_definition_name_message(type_name: str, field_name: str) -> str:
    return (
        f"Field '{type_name}.{field_name}' already exists in the schema."
        " It cannot also be defined in this type extension."
    )


class UniqueFieldDefinitionNamesRule(SDLValidationRule):
    """Unique field definition names

    A GraphQL complex type is only valid if all its fields are uniquely named.
    """

    def __init__(self, context: SDLValidationContext) -> None:
        super().__init__(context)
        schema = context.schema
        self.existing_type_map = schema.type_map if schema else {}
        self.known_field_names: Dict[str, Dict[str, NameNode]] = defaultdict(dict)

    def check_field_uniqueness(self, node: ObjectTypeDefinitionNode, *_args):
        if node.fields:
            type_name = node.name.value
            field_names = self.known_field_names[type_name]
            existing_type_map = self.existing_type_map

            for field_def in node.fields:
                field_name = field_def.name.value

                if has_field(existing_type_map.get(type_name), field_name):
                    self.report_error(
                        GraphQLError(
                            existed_field_definition_name_message(
                                type_name, field_name
                            ),
                            field_def.name,
                        )
                    )
                elif field_name in field_names:
                    self.report_error(
                        GraphQLError(
                            duplicate_field_definition_name_message(
                                type_name, field_name
                            ),
                            [field_names[field_name], field_def.name],
                        )
                    )
                else:
                    field_names[field_name] = field_def.name

        return self.SKIP

    enter_input_object_type_definition = check_field_uniqueness
    enter_input_object_type_extension = check_field_uniqueness
    enter_interface_type_definition = check_field_uniqueness
    enter_interface_type_extension = check_field_uniqueness
    enter_object_type_definition = check_field_uniqueness
    enter_object_type_extension = check_field_uniqueness


def has_field(type_: Any, field_name: str) -> bool:
    if is_object_type(type_) or is_interface_type(type_) or is_input_object_type(type_):
        return field_name in type_.fields
    return False
