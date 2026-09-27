"""Fragments on composite type rule"""

from __future__ import annotations

from typing import Any

from ...error import GraphQLError
from ...language import FragmentDefinitionNode, InlineFragmentNode, print_ast
from ...type import is_composite_type
from ...utilities import type_from_ast
from . import ValidationRule

__all__ = ["FragmentsOnCompositeTypesRule"]


class FragmentsOnCompositeTypesRule(ValidationRule):
    """Fragments on composite type

    Fragments use a type condition to determine if they apply, since fragments can only
    be spread into a composite type (object, interface, or union), the type condition
    must also be a composite type.

    See https://spec.graphql.org/draft/#sec-Fragments-On-Composite-Types

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import FragmentsOnCompositeTypesRule
    >>> schema = build_schema('type Query { name: String }')
    >>> document = parse('fragment Bad on String { length }')
    >>> errors = validate(schema, document, [FragmentsOnCompositeTypesRule])
    >>> print(errors[0].message)
    Fragment 'Bad' cannot condition on non composite type 'String'.
    >>> document = parse('fragment Good on Query { name }')
    >>> validate(schema, document, [FragmentsOnCompositeTypesRule])
    []
    """

    def enter_inline_fragment(self, node: InlineFragmentNode, *_args: Any) -> None:
        """Called when entering an inline fragment node.

        :meta private:
        """
        type_condition = node.type_condition
        if (
            type_condition
            and (type_ := type_from_ast(self.context.schema, type_condition))
            and not is_composite_type(type_)
        ):
            type_str = print_ast(type_condition)
            self.report_error(
                GraphQLError(
                    f"Fragment cannot condition on non composite type '{type_str}'.",
                    type_condition,
                )
            )

    def enter_fragment_definition(
        self, node: FragmentDefinitionNode, *_args: Any
    ) -> None:
        """Called when entering a fragment definition node.

        :meta private:
        """
        type_condition = node.type_condition
        if (
            type_ := type_from_ast(self.context.schema, type_condition)
        ) and not is_composite_type(type_):
            type_str = print_ast(type_condition)
            self.report_error(
                GraphQLError(
                    f"Fragment '{node.name.value}' cannot condition"
                    f" on non composite type '{type_str}'.",
                    type_condition,
                )
            )
