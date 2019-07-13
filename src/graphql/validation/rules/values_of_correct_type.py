from typing import List, Sequence, cast

from ...error import GraphQLError
from ...language import (
    BooleanValueNode,
    EnumValueNode,
    FloatValueNode,
    IntValueNode,
    NullValueNode,
    ListValueNode,
    ObjectFieldNode,
    ObjectValueNode,
    StringValueNode,
    ValueNode,
    print_ast,
)
from ...pyutils import did_you_mean, is_invalid, suggestion_list
from ...type import (
    GraphQLEnumType,
    GraphQLScalarType,
    get_named_type,
    get_nullable_type,
    is_enum_type,
    is_input_object_type,
    is_list_type,
    is_non_null_type,
    is_required_input_field,
    is_scalar_type,
)
from . import ValidationRule

__all__ = [
    "ValuesOfCorrectTypeRule",
    "bad_value_message",
    "required_field_message",
    "unknown_field_message",
]


def bad_value_message(type_name: str, value_name: str, message: str = None) -> str:
    return f"Expected type {type_name}, found {value_name}" + (
        f"; {message}" if message else "."
    )


def bad_enum_value_message(
    type_name: str, value_name: str, suggested_values: Sequence[str]
) -> str:
    hint = did_you_mean(suggested_values, "the enum value")
    return f"Expected type {type_name}, found {value_name}.{hint}"


def required_field_message(
    type_name: str, field_name: str, field_type_name: str
) -> str:
    return (
        f"Field {type_name}.{field_name} of required type"
        f" {field_type_name} was not provided."
    )


def unknown_field_message(
    type_name: str, field_name: str, suggested_fields: Sequence[str]
) -> str:
    hint = did_you_mean(suggested_fields)
    return f"Field '{field_name}'' is not defined by type {type_name}.{hint}"


class ValuesOfCorrectTypeRule(ValidationRule):
    """Value literals of correct type

    A GraphQL document is only valid if all value literals are of the type expected at
    their position.
    """

    def enter_null_value(self, node: NullValueNode, *_args):
        type_ = self.context.get_input_type()
        if is_non_null_type(type_):
            self.report_error(
                GraphQLError(bad_value_message(type_, print_ast(node)), node)
            )

    def enter_list_value(self, node: ListValueNode, *_args):
        # Note: TypeInfo will traverse into a list's item type, so look to the parent
        # input type to check if it is a list.
        type_ = get_nullable_type(self.context.get_parent_input_type())
        if not is_list_type(type_):
            self.is_valid_scalar(node)
            return self.SKIP  # Don't traverse further.

    def enter_object_value(self, node: ObjectValueNode, *_args):
        type_ = get_named_type(self.context.get_input_type())
        if not is_input_object_type(type_):
            self.is_valid_scalar(node)
            return self.SKIP  # Don't traverse further.
        # Ensure every required field exists.
        field_node_map = {field.name.value: field for field in node.fields}
        for field_name, field_def in type_.fields.items():
            field_node = field_node_map.get(field_name)
            if not field_node and is_required_input_field(field_def):
                field_type = field_def.type
                self.report_error(
                    GraphQLError(
                        required_field_message(type_.name, field_name, str(field_type)),
                        node,
                    )
                )

    def enter_object_field(self, node: ObjectFieldNode, *_args):
        parent_type = get_named_type(self.context.get_parent_input_type())
        field_type = self.context.get_input_type()
        if not field_type and is_input_object_type(parent_type):
            suggestions = suggestion_list(node.name.value, list(parent_type.fields))
            self.report_error(
                GraphQLError(
                    unknown_field_message(
                        parent_type.name, node.name.value, suggestions
                    ),
                    node,
                )
            )

    def enter_enum_value(self, node: EnumValueNode, *_args):
        type_ = get_named_type(self.context.get_input_type())
        if not is_enum_type(type_):
            self.is_valid_scalar(node)
        elif node.value not in type_.values:
            self.report_error(
                GraphQLError(
                    bad_enum_value_message(
                        type_.name,
                        print_ast(node),
                        enum_type_suggestion(cast(GraphQLEnumType, type_), node),
                    ),
                    node,
                )
            )

    def enter_int_value(self, node: IntValueNode, *_args):
        self.is_valid_scalar(node)

    def enter_float_value(self, node: FloatValueNode, *_args):
        self.is_valid_scalar(node)

    def enter_string_value(self, node: StringValueNode, *_args):
        self.is_valid_scalar(node)

    def enter_boolean_value(self, node: BooleanValueNode, *_args):
        self.is_valid_scalar(node)

    def is_valid_scalar(self, node: ValueNode) -> None:
        """Check whether this is a valid scalar.

        Any value literal may be a valid representation of a Scalar, depending on that
        scalar type.
        """
        # Report any error at the full type expected by the location.
        location_type = self.context.get_input_type()
        if not location_type:
            return

        type_ = get_named_type(location_type)

        if not is_scalar_type(type_):
            message = (
                bad_enum_value_message(
                    location_type,
                    print_ast(node),
                    enum_type_suggestion(
                        cast(GraphQLEnumType, type_), cast(EnumValueNode, node)
                    ),
                )
                if is_enum_type(type_)
                else bad_value_message(location_type, print_ast(node))
            )

            self.report_error(GraphQLError(message, node))
            return

        # Scalars determine if a literal value is valid via `parse_literal()` which may
        # throw or return an invalid value to indicate failure.
        type_ = cast(GraphQLScalarType, type_)
        try:
            parse_result = type_.parse_literal(node)
            if is_invalid(parse_result):
                self.report_error(
                    GraphQLError(
                        bad_value_message(location_type, print_ast(node)), node
                    )
                )
        except Exception as error:
            # Ensure a reference to the original error is maintained.
            self.report_error(
                GraphQLError(
                    bad_value_message(location_type, print_ast(node), str(error)),
                    node,
                    original_error=error,
                )
            )


def enum_type_suggestion(type_: GraphQLEnumType, node: EnumValueNode) -> List[str]:
    return suggestion_list(print_ast(node), list(type_.values))
