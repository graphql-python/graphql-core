from typing import List

from ..error import GraphQLError
from ..language import DocumentNode, Visitor, visit
from ..type import GraphQLSchema, get_named_type
from .type_info import TypeInfo, TypeInfoVisitor


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

    def __init__(self, type_info: TypeInfo):
        super().__init__()
        self.type_info = type_info
        self.errors = []

    def enter_field(self, node, *_args):
        parent_type = self.type_info.get_parent_type()
        field_def = self.type_info.get_field_def()
        if parent_type and field_def and field_def.deprecation_reason is not None:
            self.errors.append(
                GraphQLError(
                    f"The field '{parent_type.name}.{node.name.value}'"
                    " is deprecated. " + field_def.deprecation_reason,
                    node,
                )
            )

    def enter_enum_value(self, node, *_args):
        type_ = get_named_type(self.type_info.get_input_type())
        enum_val = self.type_info.get_enum_value()
        if type_ and enum_val and enum_val.deprecation_reason is not None:
            self.errors.append(
                GraphQLError(
                    f"The enum value '{type_.name}.{node.value}'"
                    " is deprecated. " + enum_val.deprecation_reason,
                    node,
                )
            )
