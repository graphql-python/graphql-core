"""Validation"""

from __future__ import annotations

from typing import TYPE_CHECKING, Collection

from ..error import GraphQLError
from ..language import DocumentNode, ParallelVisitor, visit
from ..type import GraphQLSchema, assert_valid_schema
from ..utilities import TypeInfo, TypeInfoVisitor
from .specified_rules import specified_rules, specified_sdl_rules
from .validation_context import SDLValidationContext, ValidationContext

if TYPE_CHECKING:
    from .rules import ASTValidationRule

__all__ = [
    "assert_valid_sdl",
    "assert_valid_sdl_extension",
    "validate",
    "validate_sdl",
    "ValidationAbortedError",
]


class ValidationAbortedError(GraphQLError):
    """Error when a validation has been aborted (error limit reached)."""


validation_aborted_error = ValidationAbortedError(
    "Too many validation errors, error limit reached. Validation aborted."
)


def validate(
    schema: GraphQLSchema,
    document_ast: DocumentNode,
    rules: Collection[type[ASTValidationRule]] | None = None,
    max_errors: int | None = None,
    type_info: TypeInfo | None = None,
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
    so by default ``max_errors`` set to 100 errors.

    Providing a custom TypeInfo instance is deprecated and will be removed in v3.3.
    """
    # If the schema used for validation is invalid, throw an error.
    assert_valid_schema(schema)
    if max_errors is None:
        max_errors = 100
    if type_info is None:
        type_info = TypeInfo(schema)
    if rules is None:
        rules = specified_rules

    errors: list[GraphQLError] = []

    def on_error(error: GraphQLError) -> None:
        if len(errors) >= max_errors:
            raise validation_aborted_error
        errors.append(error)

    context = ValidationContext(schema, document_ast, type_info, on_error)

    # This uses a specialized visitor which runs multiple visitors in parallel,
    # while maintaining the visitor skip and break API.
    visitors = [rule(context) for rule in rules]

    # Visit the whole document with each instance of all provided rules.
    try:
        visit(document_ast, TypeInfoVisitor(type_info, ParallelVisitor(visitors)))
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
