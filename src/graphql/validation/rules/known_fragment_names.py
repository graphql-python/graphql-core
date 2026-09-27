"""Known fragment names rule"""

from typing import Any

from ...error import GraphQLError
from ...language import FragmentSpreadNode
from . import ValidationRule

__all__ = ["KnownFragmentNamesRule"]


class KnownFragmentNamesRule(ValidationRule):
    """Known fragment names

    A GraphQL document is only valid if all ``...Fragment`` fragment spreads refer to
    fragments defined in the same document.

    See https://spec.graphql.org/draft/#sec-Fragment-spread-target-defined

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import KnownFragmentNamesRule
    >>> schema = build_schema('type Query { name: String }')
    >>> document = parse('{ ...Missing }')
    >>> errors = validate(schema, document, [KnownFragmentNamesRule])
    >>> print(errors[0].message)
    Unknown fragment 'Missing'.
    >>> document = parse(
    ...     'fragment NameFields on Query { name } query { ...NameFields }'
    ... )
    >>> validate(schema, document, [KnownFragmentNamesRule])
    []
    """

    def enter_fragment_spread(self, node: FragmentSpreadNode, *_args: Any) -> None:
        """Called when entering a fragment spread node.

        :meta private:
        """
        fragment_name = node.name.value
        fragment = self.context.get_fragment(fragment_name)
        if not fragment:
            self.report_error(
                GraphQLError(f"Unknown fragment '{fragment_name}'.", node.name)
            )
