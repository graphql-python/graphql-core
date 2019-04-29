from collections import defaultdict
from typing import cast, Dict

from ...error import GraphQLError
from ...language import NameNode, EnumTypeDefinitionNode
from ...type import is_enum_type, GraphQLEnumType
from . import SDLValidationContext, SDLValidationRule

__all__ = [
    "UniqueEnumValueNamesRule",
    "duplicate_enum_value_name_message",
    "existed_enum_value_name_message",
]


def duplicate_enum_value_name_message(type_name: str, value_name: str) -> str:
    return f"Enum value '{type_name}.{value_name}' can only be defined once."


def existed_enum_value_name_message(type_name: str, value_name: str) -> str:
    return (
        f"Enum value '{type_name}.{value_name}' already exists in the schema."
        " It cannot also be defined in this type extension."
    )


class UniqueEnumValueNamesRule(SDLValidationRule):
    """Unique enum value names

    A GraphQL enum type is only valid if all its values are uniquely named.
    """

    def __init__(self, context: SDLValidationContext) -> None:
        super().__init__(context)
        schema = context.schema
        self.existing_type_map = schema.type_map if schema else {}
        self.known_value_names: Dict[str, Dict[str, NameNode]] = defaultdict(dict)

    def check_value_uniqueness(self, node: EnumTypeDefinitionNode, *_args):
        if node.values:
            type_name = node.name.value
            value_names = self.known_value_names[type_name]
            existing_type_map = self.existing_type_map

            for value_def in node.values:
                value_name = value_def.name.value

                existing_type = existing_type_map.get(type_name)
                if (
                    is_enum_type(existing_type)
                    and value_name in cast(GraphQLEnumType, existing_type).values
                ):
                    self.report_error(
                        GraphQLError(
                            existed_enum_value_name_message(type_name, value_name),
                            value_def.name,
                        )
                    )
                elif value_name in value_names:
                    self.report_error(
                        GraphQLError(
                            duplicate_enum_value_name_message(type_name, value_name),
                            [value_names[value_name], value_def.name],
                        )
                    )
                else:
                    value_names[value_name] = value_def.name

        return self.SKIP

    enter_enum_type_definition = check_value_uniqueness
    enter_enum_type_extension = check_value_uniqueness
