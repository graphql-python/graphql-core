from typing import List, Sequence, Type

from ..error import GraphQLError
from ..language import DocumentNode, ParallelVisitor, TypeInfoVisitor, visit
from ..type import GraphQLSchema, assert_valid_schema
from ..utilities import TypeInfo
from .rules import ValidationRule
from .specified_rules import specified_rules
from .validation_context import ValidationContext

__all__ = ['validate']

RuleType = Type[ValidationRule]


def validate(schema: GraphQLSchema, document_ast: DocumentNode,
             rules: Sequence[RuleType]=None,
             type_info: TypeInfo=None) -> List[GraphQLError]:
    """Implements the "Validation" section of the spec.

    Validation runs synchronously, returning a list of encountered errors, or
    an empty list if no errors were encountered and the document is valid.

    A list of specific validation rules may be provided. If not provided, the
    default list of rules defined by the GraphQL specification will be used.

    Each validation rule is a ValidationRule object which is a visitor object
    that holds a ValidationContext (see the language/visitor API).
    Visitor methods are expected to return GraphQLErrors, or lists of
    GraphQLErrors when invalid.

    Optionally a custom TypeInfo instance may be provided. If not provided, one
    will be created from the provided schema.
    """
    if not document_ast or not isinstance(document_ast, DocumentNode):
        raise TypeError('You must provide a document node.')
    # If the schema used for validation is invalid, throw an error.
    assert_valid_schema(schema)
    if type_info is None:
        type_info = TypeInfo(schema)
    elif not isinstance(type_info, TypeInfo):
        raise TypeError(f'Not a TypeInfo object: {type_info!r}')
    if rules is None:
        rules = specified_rules
    elif not isinstance(rules, (list, tuple)):
        raise TypeError('Rules must be passed as a list/tuple.')
    context = ValidationContext(schema, document_ast, type_info)
    # This uses a specialized visitor which runs multiple visitors in parallel,
    # while maintaining the visitor skip and break API.
    visitors = [rule(context) for rule in rules]
    # Visit the whole document with each instance of all provided rules.
    visit(document_ast, TypeInfoVisitor(type_info, ParallelVisitor(visitors)))
    return context.errors
