"""graphql.validation.rules package"""

from ...error import GraphQLError
from ...language.visitor import Visitor
from ..validation_context import (
    ASTValidationContext,
    SDLValidationContext,
    ValidationContext,
)

__all__ = ["ASTValidationRule", "SDLValidationRule", "ValidationRule"]


class ASTValidationRule(Visitor):
    """Visitor for validation of an AST.

    This is the base class of all validation rules.

    :param context: The validation context used while checking the document.

    >>> from graphql import GraphQLError, parse, visit
    >>> from graphql.validation import ASTValidationContext, ASTValidationRule
    >>> class NoAnonymousOperationsRule(ASTValidationRule):
    ...     def enter_operation_definition(self, node, *_args):
    ...         if not node.name:
    ...             self.report_error(GraphQLError('Name all operations.', node))
    >>> document = parse('{ greeting }')
    >>> errors = []
    >>> context = ASTValidationContext(document, errors.append)
    >>> _ = visit(document, NoAnonymousOperationsRule(context))
    >>> print(errors[0].message)
    Name all operations.
    """

    context: ASTValidationContext
    """The validation context used while checking the document."""

    def __init__(self, context: ASTValidationContext):
        super().__init__()
        self.context = context

    def report_error(self, error: GraphQLError) -> None:
        """Report a validation error to the validation context.

        :param error: The validation error to report.

        >>> from graphql import GraphQLError, parse
        >>> from graphql.validation import ASTValidationContext, ASTValidationRule
        >>> context = ASTValidationContext(parse('{ greeting }'), print)
        >>> rule = ASTValidationRule(context)
        >>> rule.report_error(GraphQLError('Example validation error.'))
        Example validation error.
        """
        self.context.report_error(error)


class SDLValidationRule(ASTValidationRule):
    """Visitor for validation of an SDL AST.

    :param context: The validation context used while checking the SDL document.

    >>> from graphql import GraphQLError, parse, visit
    >>> from graphql.validation import SDLValidationContext, SDLValidationRule
    >>> class NoInterfacesRule(SDLValidationRule):
    ...     def enter_interface_type_definition(self, node, *_args):
    ...         self.report_error(GraphQLError('No interfaces allowed.', node))
    >>> document = parse('interface Node { id: ID } type Query { node: Node }')
    >>> errors = []
    >>> context = SDLValidationContext(document, None, errors.append)
    >>> _ = visit(document, NoInterfacesRule(context))
    >>> print(errors[0].message)
    No interfaces allowed.
    """

    context: SDLValidationContext
    """The validation context used while checking the SDL document."""

    def __init__(self, context: SDLValidationContext) -> None:
        super().__init__(context)


class ValidationRule(ASTValidationRule):
    """Visitor for validation using a GraphQL schema.

    A validation rule creates an AST visitor for validating a GraphQL document.
    Custom validation rules can be created by subclassing this class and reporting
    errors with its ``report_error()`` method.

    :param context: The validation context used while checking the document.

    >>> from graphql import GraphQLError, build_schema, parse, validate
    >>> from graphql.validation import ValidationRule
    >>> class NoAliasesRule(ValidationRule):
    ...     def enter_field(self, node, *_args):
    ...         if node.alias:
    ...             self.report_error(GraphQLError('Aliases are not allowed.', node))
    >>> schema = build_schema('type Query { name: String }')
    >>> document = parse('{ alias: name }')
    >>> errors = validate(schema, document, [NoAliasesRule])
    >>> print(errors[0].message)
    Aliases are not allowed.
    >>> document = parse('{ name }')
    >>> validate(schema, document, [NoAliasesRule])
    []
    """

    context: ValidationContext
    """The validation context used while checking the document."""

    def __init__(self, context: ValidationContext) -> None:
        super().__init__(context)
