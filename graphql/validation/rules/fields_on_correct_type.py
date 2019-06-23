from collections import defaultdict
from typing import Dict, List, cast

from ...type import (
    GraphQLAbstractType,
    GraphQLSchema,
    GraphQLOutputType,
    is_abstract_type,
    is_interface_type,
    is_object_type,
)
from ...error import GraphQLError
from ...language import FieldNode
from ...pyutils import did_you_mean, suggestion_list
from . import ValidationRule

__all__ = ["FieldsOnCorrectTypeRule", "undefined_field_message"]


def undefined_field_message(
    field_name: str,
    type_: str,
    suggested_type_names: List[str],
    suggested_field_names: List[str],
) -> str:
    hint = did_you_mean(
        [f"'{s}'" for s in suggested_type_names], "to use an inline fragment on"
    ) or did_you_mean([f"'{s}'" for s in suggested_field_names])
    return f"Cannot query field '{field_name}' on type '{type_}'.{hint}"


class FieldsOnCorrectTypeRule(ValidationRule):
    """Fields on correct type

    A GraphQL document is only valid if all fields selected are defined by the parent
    type, or are an allowed meta field such as `__typename`.
    """

    def enter_field(self, node: FieldNode, *_args):
        type_ = self.context.get_parent_type()
        if not type_:
            return
        field_def = self.context.get_field_def()
        if field_def:
            return
        # This field doesn't exist, lets look for suggestions.
        schema = self.context.schema
        field_name = node.name.value
        # First determine if there are any suggested types to condition on.
        suggested_type_names = get_suggested_type_names(schema, type_, field_name)
        # If there are no suggested types, then perhaps this was a typo?
        suggested_field_names = (
            [] if suggested_type_names else get_suggested_field_names(type_, field_name)
        )

        # Report an error, including helpful suggestions.
        self.report_error(
            GraphQLError(
                undefined_field_message(
                    field_name, type_.name, suggested_type_names, suggested_field_names
                ),
                node,
            )
        )


def get_suggested_type_names(
    schema: GraphQLSchema, type_: GraphQLOutputType, field_name: str
) -> List[str]:
    """
    Get a list of suggested type names.

    Go through all of the implementations of type, as well as the interfaces
    that they implement. If any of those types include the provided field,
    suggest them, sorted by how often the type is referenced, starting with
    Interfaces.
    """
    if is_abstract_type(type_):
        type_ = cast(GraphQLAbstractType, type_)
        suggested_object_types = []
        interface_usage_count: Dict[str, int] = defaultdict(int)
        for possible_type in schema.get_possible_types(type_):
            if field_name not in possible_type.fields:
                continue
            # This object type defines this field.
            suggested_object_types.append(possible_type.name)
            for possible_interface in possible_type.interfaces:
                if field_name not in possible_interface.fields:
                    continue
                # This interface type defines this field.
                interface_usage_count[possible_interface.name] += 1

        # Suggest interface types based on how common they are.
        suggested_interface_types = sorted(
            interface_usage_count, key=lambda k: -interface_usage_count[k]
        )

        # Suggest both interface and object types.
        return suggested_interface_types + suggested_object_types

    # Otherwise, must be an Object type, which does not have possible fields.
    return []


def get_suggested_field_names(type_: GraphQLOutputType, field_name: str) -> List[str]:
    """Get a list of suggested field names.

    For the field name provided, determine if there are any similar field names that may
    be the result of a typo.
    """
    if is_object_type(type_) or is_interface_type(type_):
        possible_field_names = list(type_.fields)  # type: ignore
        return suggestion_list(field_name, possible_field_names)
    # Otherwise, must be a Union type, which does not define fields.
    return []
