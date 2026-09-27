"""Validation"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..error import GraphQLError
from ..language import DocumentNode, ParallelVisitor, visit
from ..language.ast import QUERY_DOCUMENT_KEYS
from ..type import GraphQLSchema, assert_valid_schema
from ..utilities import TypeInfo, TypeInfoVisitor
from .specified_rules import specified_rules, specified_sdl_rules
from .validation_context import SDLValidationContext, ValidationContext

if TYPE_CHECKING:
    from collections.abc import Collection

    from .rules import ASTValidationRule

__all__ = [
    "ValidationAbortedError",
    "assert_valid_sdl",
    "assert_valid_sdl_extension",
    "validate",
    "validate_sdl",
]


class ValidationAbortedError(GraphQLError):
    """Error when a validation has been aborted (error limit reached)."""


validation_aborted_error = ValidationAbortedError(
    "Too many validation errors, error limit reached. Validation aborted."
)


# Per the specification, descriptions must not affect validation.
# See https://spec.graphql.org/draft/#sec-Descriptions
query_document_keys_to_validate: dict[str, tuple[str, ...]] = {
    kind: tuple(key for key in keys if key != "description")
    for kind, keys in QUERY_DOCUMENT_KEYS.items()
}


def validate(
    schema: GraphQLSchema,
    document_ast: DocumentNode,
    rules: Collection[type[ASTValidationRule]] | None = None,
    max_errors: int | None = None,
    hide_suggestions: bool = False,
) -> list[GraphQLError]:
    """Implements the "Validation" section of the spec.

    Validation runs synchronously, returning a list of encountered errors, or an empty
    list if no errors were encountered and the document is valid.

    A list of specific validation rules may be provided. If not provided, the default
    list of rules defined by the GraphQL specification will be used.

    Each validation rule is a ValidationRule object which is a visitor object that holds
    a ValidationContext (see the language/visitor API). Visitor methods are expected to
    return GraphQLErrors, or lists of GraphQLErrors when invalid.

    Validate will stop validation after a ``max_errors`` limit has been reached.
    Attackers can send pathologically invalid queries to induce a DoS attack,
    so ``max_errors`` defaults to 100 errors.

    :param schema: Schema to validate against.
    :param document_ast: Document AST to validate.
    :param rules: Validation rules to apply. Defaults to
        :data:`~graphql.validation.specified_rules`.
    :param max_errors: Maximum number of validation errors before validation stops.
        Defaults to 100.
    :param hide_suggestions: Whether suggestion text should be omitted from
        validation errors.
    :returns: Validation errors, or an empty list when the document is valid.

    Validate with the default specified rules:

    >>> from graphql import build_schema, parse, validate
    >>> schema = build_schema('type Query { greeting: String }')
    >>> validate(schema, parse('{ greeting }'))
    []
    >>> errors = validate(schema, parse('{ missing }'))
    >>> print(errors[0].message)
    Cannot query field 'missing' on type 'Query'.

    This variant uses a custom rule list and validation options:

    >>> from graphql.validation import FieldsOnCorrectTypeRule
    >>> document = parse('{ missingOne missingTwo }')
    >>> errors = validate(schema, document, [FieldsOnCorrectTypeRule], max_errors=1)
    >>> len(errors)
    2
    >>> print(errors[1].message)
    Too many validation errors, error limit reached. Validation aborted.
    >>> errors = validate(
    ...     schema, parse('{ name }'), [FieldsOnCorrectTypeRule], hide_suggestions=True
    ... )
    >>> print(errors[0].message)
    Cannot query field 'name' on type 'Query'.
    """
    # If the schema used for validation is invalid, throw an error.
    assert_valid_schema(schema)
    if max_errors is None:
        max_errors = 100
    if rules is None:
        rules = specified_rules

    errors: list[GraphQLError] = []
    type_info = TypeInfo(schema)

    def on_error(error: GraphQLError) -> None:
        if len(errors) >= max_errors:
            raise validation_aborted_error
        errors.append(error)

    context = ValidationContext(
        schema, document_ast, type_info, on_error, hide_suggestions
    )

    # This uses a specialized visitor which runs multiple visitors in parallel,
    # while maintaining the visitor skip and break API.
    visitors = [rule(context) for rule in rules]

    # Visit the whole document with each instance of all provided rules.
    try:
        visit(
            document_ast,
            TypeInfoVisitor(type_info, ParallelVisitor(visitors)),
            query_document_keys_to_validate,
        )
    except ValidationAbortedError:
        errors.append(validation_aborted_error)
    return errors


def validate_sdl(
    document_ast: DocumentNode,
    schema_to_extend: GraphQLSchema | None = None,
    rules: Collection[type[ASTValidationRule]] | None = None,
) -> list[GraphQLError]:
    """Validate an SDL document.

    For internal use only.
    """
    errors: list[GraphQLError] = []
    context = SDLValidationContext(document_ast, schema_to_extend, errors.append)
    if rules is None:
        rules = specified_sdl_rules
    visitors = [rule(context) for rule in rules]
    visit(document_ast, ParallelVisitor(visitors))
    return errors


def assert_valid_sdl(document_ast: DocumentNode) -> None:
    """Assert document is valid SDL.

    Utility function which asserts a SDL document is valid by throwing an error if it
    is invalid.
    """
    errors = validate_sdl(document_ast)
    if errors:
        raise TypeError("\n\n".join(error.message for error in errors))


def assert_valid_sdl_extension(
    document_ast: DocumentNode, schema: GraphQLSchema
) -> None:
    """Assert document is a valid SDL extension.

    Utility function which asserts a SDL document is valid by throwing an error if it
    is invalid.
    """
    errors = validate_sdl(document_ast, schema)
    if errors:
        raise TypeError("\n\n".join(error.message for error in errors))
