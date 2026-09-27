"""Scalar leafs rule"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...error import GraphQLError
from ...type import get_named_type, is_leaf_type
from . import ValidationRule

if TYPE_CHECKING:
    from ...language import FieldNode

__all__ = ["ScalarLeafsRule"]


class ScalarLeafsRule(ValidationRule):
    """Scalar leafs

    A GraphQL document is valid only if all leaf fields (fields without sub selections)
    are of scalar or enum types.

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import ScalarLeafsRule
    >>> schema = build_schema('type Query { name: String }')
    >>> document = parse('{ name { length } }')
    >>> errors = validate(schema, document, [ScalarLeafsRule])
    >>> print(errors[0].message)
    Field 'name' must not have a selection since type 'String' has no subfields.
    >>> document = parse('{ name }')
    >>> validate(schema, document, [ScalarLeafsRule])
    []
    """

    def enter_field(self, node: FieldNode, *_args: Any) -> None:
        """Called when entering a field node.

        :meta private:
        """
        type_ = self.context.get_type()
        if type_:
            selection_set = node.selection_set
            if is_leaf_type(get_named_type(type_)):
                if selection_set:
                    field_name = node.name.value
                    self.report_error(
                        GraphQLError(
                            f"Field '{field_name}' must not have a selection"
                            f" since type '{type_}' has no subfields.",
                            selection_set,
                        )
                    )
            elif not selection_set:
                field_name = node.name.value
                self.report_error(
                    GraphQLError(
                        f"Field '{field_name}' of type '{type_}'"
                        " must have a selection of subfields."
                        f" Did you mean '{field_name} {{ ... }}'?",
                        node,
                    )
                )
            elif not selection_set.selections:
                field_name = node.name.value
                self.report_error(
                    GraphQLError(
                        f"Field '{field_name}' of type '{type_}'"
                        " must have at least one field selected.",
                        node,
                    )
                )
