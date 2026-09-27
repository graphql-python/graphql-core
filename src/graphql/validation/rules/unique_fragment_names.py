"""Unique fragment names rule"""

from typing import Any, Dict

from ...error import GraphQLError
from ...language import NameNode, FragmentDefinitionNode, VisitorAction, SKIP
from . import ASTValidationContext, ASTValidationRule

__all__ = ["UniqueFragmentNamesRule"]


class UniqueFragmentNamesRule(ASTValidationRule):
    """Unique fragment names

    A GraphQL document is only valid if all defined fragments have unique names.

    See https://spec.graphql.org/draft/#sec-Fragment-Name-Uniqueness

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import UniqueFragmentNamesRule
    >>> schema = build_schema('type Query { name: String }')
    >>> document = parse(
    ...     'fragment A on Query { name } fragment A on Query { name } query { ...A }'
    ... )
    >>> errors = validate(schema, document, [UniqueFragmentNamesRule])
    >>> print(errors[0].message)
    There can be only one fragment named 'A'.
    >>> document = parse('fragment A on Query { name } query { ...A }')
    >>> validate(schema, document, [UniqueFragmentNamesRule])
    []
    """

    def __init__(self, context: ASTValidationContext):
        super().__init__(context)
        self.known_fragment_names: Dict[str, NameNode] = {}

    @staticmethod
    def enter_operation_definition(*_args: Any) -> VisitorAction:
        return SKIP

    def enter_fragment_definition(
        self, node: FragmentDefinitionNode, *_args: Any
    ) -> VisitorAction:
        """Called when entering a fragment definition node.

        :meta private:
        """
        known_fragment_names = self.known_fragment_names
        fragment_name = node.name.value
        if fragment_name in known_fragment_names:
            self.report_error(
                GraphQLError(
                    f"There can be only one fragment named '{fragment_name}'.",
                    [known_fragment_names[fragment_name], node.name],
                )
            )
        else:
            known_fragment_names[fragment_name] = node.name
        return SKIP
