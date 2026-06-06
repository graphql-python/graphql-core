"""Value literals of correct type rule"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...language import (
    SKIP,
    BooleanValueNode,
    EnumValueNode,
    FloatValueNode,
    IntValueNode,
    ListValueNode,
    NullValueNode,
    ObjectValueNode,
    StringValueNode,
    ValueNode,
    VisitorAction,
)
from ...utilities.validate_input_value import validate_input_literal
from . import ValidationRule

if TYPE_CHECKING:
    from ...error import GraphQLError
    from ...type import GraphQLInputType

__all__ = ["ValuesOfCorrectTypeRule"]


class ValuesOfCorrectTypeRule(ValidationRule):
    """Value literals of correct type

    A GraphQL document is only valid if all value literals are of the type expected at
    their position.

    See https://spec.graphql.org/draft/#sec-Values-of-Correct-Type
    """

    def enter_null_value(self, node: NullValueNode, *_args: Any) -> VisitorAction:
        return self.is_valid_value_node(node, self.context.get_input_type())

    def enter_list_value(self, node: ListValueNode, *_args: Any) -> VisitorAction:
        # Note: TypeInfo will traverse into a list's item type, so look to the parent
        # input type to check if it is a list.
        return self.is_valid_value_node(node, self.context.get_parent_input_type())

    def enter_object_value(self, node: ObjectValueNode, *_args: Any) -> VisitorAction:
        return self.is_valid_value_node(node, self.context.get_input_type())

    def enter_enum_value(self, node: EnumValueNode, *_args: Any) -> VisitorAction:
        return self.is_valid_value_node(node, self.context.get_input_type())

    def enter_int_value(self, node: IntValueNode, *_args: Any) -> VisitorAction:
        return self.is_valid_value_node(node, self.context.get_input_type())

    def enter_float_value(self, node: FloatValueNode, *_args: Any) -> VisitorAction:
        return self.is_valid_value_node(node, self.context.get_input_type())

    # Descriptions are string values that would not validate according
    # to the below logic, but since (per the specification) descriptions must
    # not affect validation, they are ignored entirely when visiting the AST
    # and do not require special handling.
    # See https://spec.graphql.org/draft/#sec-Descriptions
    def enter_string_value(self, node: StringValueNode, *_args: Any) -> VisitorAction:
        return self.is_valid_value_node(node, self.context.get_input_type())

    def enter_boolean_value(self, node: BooleanValueNode, *_args: Any) -> VisitorAction:
        return self.is_valid_value_node(node, self.context.get_input_type())

    def is_valid_value_node(
        self, node: ValueNode, input_type: GraphQLInputType | None
    ) -> VisitorAction:
        """Check whether this is a valid value node.

        Any value literal may be a valid representation of a Scalar, depending on that
        scalar type.
        """
        if input_type:

            def on_error(error: GraphQLError, _path: list[str | int]) -> None:
                self.report_error(error)

            validate_input_literal(
                node,
                input_type,
                on_error,
                None,
                None,
                self.context.hide_suggestions,
            )
        return SKIP  # Don't traverse further.
