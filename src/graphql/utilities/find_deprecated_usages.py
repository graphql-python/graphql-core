from typing import List

from ..error import GraphQLError
from ..language import DocumentNode
from ..type import GraphQLSchema

__all__ = ["find_deprecated_usages"]


def find_deprecated_usages(
    schema: GraphQLSchema, ast: DocumentNode
) -> List[GraphQLError]:  # pragma: no cover
    """Get a list of GraphQLError instances describing each deprecated use.

    .. deprecated:: 3.1.3

    Please use ``validate`` with ``NoDeprecatedCustomRule`` instead::

        from graphql import validate, NoDeprecatedCustomRule

        errors = validate(schema, document, [NoDeprecatedCustomRule])
    """
    from ..validation import validate, NoDeprecatedCustomRule

    return validate(schema, ast, [NoDeprecatedCustomRule])
