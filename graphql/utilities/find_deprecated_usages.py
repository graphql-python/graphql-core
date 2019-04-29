from typing import List

from ..error import GraphQLError
from ..language import DocumentNode, TypeInfoVisitor, Visitor, visit
from ..type import GraphQLSchema, get_named_type
from .type_info import TypeInfo


__all__ = ["find_deprecated_usages"]


def find_deprecated_usages(
    schema: GraphQLSchema, ast: DocumentNode
) -> List[GraphQLError]:
    """Get a list of GraphQLError instances describing each deprecated use."""

    type_info = TypeInfo(schema)
    visitor = FindDeprecatedUsages(type_info)
    visit(ast, TypeInfoVisitor(type_info, visitor))
    return visitor.errors


class FindDeprecatedUsages(Visitor):
    """A validation rule which reports deprecated usages."""

    type_info: TypeInfo
    errors: List[GraphQLError]

    def __init__(self, type_info: TypeInfo) -> None:
        super().__init__()
        self.type_info = type_info
        self.errors = []

    def enter_field(self, node, *_args):
        field_def = self.type_info.get_field_def()
        if field_def and field_def.is_deprecated:
            parent_type = self.type_info.get_parent_type()
            if parent_type:
                field_name = node.name.value
                reason = field_def.deprecation_reason
                self.errors.append(
                    GraphQLError(
                        f"The field {parent_type.name}.{field_name}"
                        " is deprecated." + (f" {reason}" if reason else ""),
                        node,
                    )
                )

    def enter_enum_value(self, node, *_args):
        enum_val = self.type_info.get_enum_value()
        if enum_val and enum_val.is_deprecated:
            type_ = get_named_type(self.type_info.get_input_type())
            if type_:
                enum_val_name = node.value
                reason = enum_val.deprecation_reason
                self.errors.append(
                    GraphQLError(
                        f"The enum value {type_.name}.{enum_val_name}"
                        " is deprecated." + (f" {reason}" if reason else ""),
                        node,
                    )
                )
