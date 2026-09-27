"""Unique input field names rule"""

from typing import Any, Dict, List

from ...error import GraphQLError
from ...language import NameNode, ObjectFieldNode
from . import ASTValidationContext, ASTValidationRule

__all__ = ["UniqueInputFieldNamesRule"]


class UniqueInputFieldNamesRule(ASTValidationRule):
    """Unique input field names

    A GraphQL input object value is only valid if all supplied fields are uniquely
    named.

    See https://spec.graphql.org/draft/#sec-Input-Object-Field-Uniqueness

    :param context: The validation context used while checking the document.

    >>> from graphql import build_schema, parse, validate
    >>> from graphql.validation import UniqueInputFieldNamesRule
    >>> sdl = (
    ...     'input Filter { name: String }'
    ...     ' type Query { search(filter: Filter): String }'
    ... )
    >>> schema = build_schema(sdl)
    >>> document = parse('{ search(filter: { name: "a", name: "b" }) }')
    >>> errors = validate(schema, document, [UniqueInputFieldNamesRule])
    >>> print(errors[0].message)
    There can be only one input field named 'name'.
    >>> document = parse('{ search(filter: { name: "a" }) }')
    >>> validate(schema, document, [UniqueInputFieldNamesRule])
    []
    """

    def __init__(self, context: ASTValidationContext):
        super().__init__(context)
        self.known_names_stack: List[Dict[str, NameNode]] = []
        self.known_names: Dict[str, NameNode] = {}

    def enter_object_value(self, *_args: Any) -> None:
        """Called when entering an object value node.

        :meta private:
        """
        self.known_names_stack.append(self.known_names)
        self.known_names = {}

    def leave_object_value(self, *_args: Any) -> None:
        """Called when leaving an object value node.

        :meta private:
        """
        self.known_names = self.known_names_stack.pop()

    def enter_object_field(self, node: ObjectFieldNode, *_args: Any) -> None:
        """Called when entering an object field node.

        :meta private:
        """
        known_names = self.known_names
        field_name = node.name.value
        if field_name in known_names:
            self.report_error(
                GraphQLError(
                    f"There can be only one input field named '{field_name}'.",
                    [known_names[field_name], node.name],
                )
            )
        else:
            known_names[field_name] = node.name
