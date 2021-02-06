from typing import Any

from ....error import GraphQLError
from ....language import FieldNode, EnumValueNode
from ....type import get_named_type
from .. import ValidationRule

__all__ = ["NoDeprecatedCustomRule"]


class NoDeprecatedCustomRule(ValidationRule):
    """No deprecated

    A GraphQL document is only valid if all selected fields and all used enum values
    have not been deprecated.

    Note: This rule is optional and is not part of the Validation section of the GraphQL
    Specification. The main purpose of this rule is detection of deprecated usages and
    not necessarily to forbid their use when querying a service.
    """

    def enter_field(self, node: FieldNode, *_args: Any) -> None:
        context = self.context
        field_def = context.get_field_def()
        parent_type = context.get_parent_type()
        if parent_type and field_def and field_def.deprecation_reason is not None:
            self.report_error(
                GraphQLError(
                    f"The field {parent_type.name}.{node.name.value}"
                    f" is deprecated. {field_def.deprecation_reason}",
                    node,
                )
            )

    def enter_enum_value(self, node: EnumValueNode, *_args: Any) -> None:
        context = self.context
        type_ = get_named_type(context.get_input_type())
        enum_val = context.get_enum_value()
        if type_ and enum_val and enum_val.deprecation_reason is not None:
            self.report_error(
                GraphQLError(
                    f"The enum value '{type_.name}.{node.value}'"
                    f" is deprecated. {enum_val.deprecation_reason}",
                    node,
                )
            )
