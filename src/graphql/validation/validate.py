from typing import List, Sequence

from ..error import GraphQLError
from ..language import DocumentNode, ParallelVisitor, TypeInfoVisitor, visit
from ..type import GraphQLSchema, assert_valid_schema
from ..pyutils import inspect
from ..utilities import TypeInfo
from .rules import RuleType
from .specified_rules import specified_rules, specified_sdl_rules
from .validation_context import SDLValidationContext, ValidationContext

__all__ = ["assert_valid_sdl", "assert_valid_sdl_extension", "validate", "validate_sdl"]


def validate(
    schema: GraphQLSchema,
    document_ast: DocumentNode,
    rules: Sequence[RuleType] = None,
    type_info: TypeInfo = None,
) -> List[GraphQLError]:
    """Implements the "Validation" section of the spec.

    Validation runs synchronously, returning a list of encountered errors, or an empty
    list if no errors were encountered and the document is valid.

    A list of specific validation rules may be provided. If not provided, the default
    list of rules defined by the GraphQL specification will be used.

    Each validation rule is a ValidationRule object which is a visitor object that holds
    a ValidationContext (see the language/visitor API). Visitor methods are expected to
    return GraphQLErrors, or lists of GraphQLErrors when invalid.

    Optionally a custom TypeInfo instance may be provided. If not provided, one will be
    created from the provided schema.
    """
    if not document_ast or not isinstance(document_ast, DocumentNode):
        raise TypeError("You must provide a document node.")
    # If the schema used for validation is invalid, throw an error.
    assert_valid_schema(schema)
    if type_info is None:
        type_info = TypeInfo(schema)
    elif not isinstance(type_info, TypeInfo):
        raise TypeError(f"Not a TypeInfo object: {inspect(type_info)}")
    if rules is None:
        rules = specified_rules
    elif not isinstance(rules, (list, tuple)):
        raise TypeError("Rules must be passed as a list/tuple.")
    context = ValidationContext(schema, document_ast, type_info)
    # This uses a specialized visitor which runs multiple visitors in parallel,
    # while maintaining the visitor skip and break API.
    visitors = [rule(context) for rule in rules]
    # Visit the whole document with each instance of all provided rules.
    visit(document_ast, TypeInfoVisitor(type_info, ParallelVisitor(visitors)))
    return context.errors


def validate_sdl(
    document_ast: DocumentNode,
    schema_to_extend: GraphQLSchema = None,
    rules: Sequence[RuleType] = None,
) -> List[GraphQLError]:
    """Validate an SDL document."""
    context = SDLValidationContext(document_ast, schema_to_extend)
    if rules is None:
        rules = specified_sdl_rules
    visitors = [rule(context) for rule in rules]
    visit(document_ast, ParallelVisitor(visitors))
    return context.errors


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
