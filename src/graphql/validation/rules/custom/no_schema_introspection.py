from typing import Any

from ....error import GraphQLError
from ....language import FieldNode
from ....type import get_named_type, is_introspection_type
from .. import ValidationRule

__all__ = ["NoSchemaIntrospectionCustomRule"]


class NoSchemaIntrospectionCustomRule(ValidationRule):
    """Prohibit introspection queries

    A GraphQL document is only valid if all fields selected are not fields that
    return an introspection type.

    Note: This rule is optional and is not part of the Validation section of the
    GraphQL Specification. This rule effectively disables introspection, which
    does not reflect best practices and should only be done if absolutely necessary.

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import NoSchemaIntrospectionCustomRule
    >>> schema = build_schema('type Query { name: String }')
    >>> document = parse('{ __schema { queryType { name } } }')
    >>> errors = validate(schema, document, [NoSchemaIntrospectionCustomRule])
    >>> for error in errors:
    ...     print(error.message)
    GraphQL introspection has been disabled, but the requested query contained the
    field '__schema'.
    GraphQL introspection has been disabled, but the requested query contained the
    field 'queryType'.
    >>> document = parse('{ name }')
    >>> validate(schema, document, [NoSchemaIntrospectionCustomRule])
    []
    """

    def enter_field(self, node: FieldNode, *_args: Any) -> None:
        """Called when entering a field node.

        :meta private:
        """
        type_ = get_named_type(self.context.get_type())
        if type_ and is_introspection_type(type_):
            self.report_error(
                GraphQLError(
                    "GraphQL introspection has been disabled, but the requested query"
                    f" contained the field '{node.name.value}'.",
                    node,
                )
            )
