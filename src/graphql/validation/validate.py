"""Validation"""

from typing import Any, Collection, Dict, List, Optional, Tuple, Type

from ..error import GraphQLError
from ..language import (
    SKIP,
    DocumentNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    OperationDefinitionNode,
    ParallelVisitor,
    SelectionSetNode,
    Visitor,
    VisitorAction,
    visit,
)
from ..language.ast import QUERY_DOCUMENT_KEYS
from ..language.parser import MAX_NESTING_DEPTH
from ..pyutils import inspect, is_collection
from ..type import GraphQLSchema, assert_valid_schema
from ..utilities import TypeInfo, TypeInfoVisitor
from .rules import ASTValidationRule
from .specified_rules import specified_rules, specified_sdl_rules
from .validation_context import SDLValidationContext, ValidationContext

__all__ = [
    "ValidationAbortedError",
    "assert_valid_sdl",
    "assert_valid_sdl_extension",
    "validate",
    "validate_sdl",
]


class ValidationAbortedError(GraphQLError):
    """Error when a validation has been aborted (error limit reached)."""


# Per the specification, descriptions must not affect validation.
# See https://spec.graphql.org/draft/#sec-Descriptions
query_document_keys_to_validate: Dict[str, Tuple[str, ...]] = {
    kind: tuple(key for key in keys if key != "description")
    for kind, keys in QUERY_DOCUMENT_KEYS.items()
}


def get_selection_nesting(
    selection_set: SelectionSetNode,
) -> Tuple[int, List[Tuple[str, int]]]:
    """Get the nesting depth of a selection set, and its spreads with their depth.

    :meta private:
    """
    max_depth = 0
    spreads: List[Tuple[str, int]] = []
    stack = [(selection_set, 1)]
    while stack:
        selection_set, depth = stack.pop()
        max_depth = max(max_depth, depth)
        for selection in selection_set.selections:
            if isinstance(selection, FragmentSpreadNode):
                spreads.append((selection.name.value, depth))
            else:
                nested = selection.selection_set  # type: ignore[attr-defined]
                if nested:
                    stack.append((nested, depth + 1))
    return max_depth, spreads


class FragmentNestingVisitor(Visitor):
    """Abort the validation before the rules recurse too deeply through fragments.

    The parser limits the nesting within a definition only. See ``MAX_NESTING_DEPTH``
    for why this is needed in addition to handling a stack overflow.

    :meta private:
    """

    def __init__(self, fragments: Dict[str, FragmentDefinitionNode]) -> None:
        super().__init__()
        self.depths: Dict[str, int] = {}
        depths = self.depths
        nestings = {
            name: get_selection_nesting(fragment.selection_set)
            for name, fragment in fragments.items()
        }
        # Walk the spreads without recursion. A spread closing a cycle adds nothing
        # here, since cycles are reported by the rules.
        for root in nestings:
            if root in depths:
                continue
            path = [(root, iter(nestings[root][1]))]
            on_path = {root}
            while path:
                name, spreads = path[-1]
                for spread, _depth in spreads:
                    if (
                        spread in nestings
                        and spread not in depths
                        and spread not in on_path
                    ):
                        path.append((spread, iter(nestings[spread][1])))
                        on_path.add(spread)
                        break
                else:
                    path.pop()
                    on_path.remove(name)
                    depths[name] = self.get_depth(*nestings[name])

    def get_depth(self, depth: int, spreads: List[Tuple[str, int]]) -> int:
        """Get the depth of a definition from its own depth and its spreads."""
        depths = self.depths
        for spread, spread_depth in spreads:
            depth = max(depth, spread_depth + depths.get(spread, 0))
        return depth

    def enter_operation_definition(
        self, node: OperationDefinitionNode, *_args: Any
    ) -> VisitorAction:
        """Check the depth of an operation.

        :meta private:
        """
        if self.get_depth(*get_selection_nesting(node.selection_set)) > (
            MAX_NESTING_DEPTH
        ):
            raise RecursionError
        return SKIP

    def enter_fragment_definition(
        self, node: FragmentDefinitionNode, *_args: Any
    ) -> VisitorAction:
        """Check the depth of a fragment.

        :meta private:
        """
        if self.depths[node.name.value] > MAX_NESTING_DEPTH:
            raise RecursionError
        return SKIP


def validate(
    schema: GraphQLSchema,
    document_ast: DocumentNode,
    rules: Optional[Collection[Type[ASTValidationRule]]] = None,
    max_errors: Optional[int] = None,
    type_info: Optional[TypeInfo] = None,
    hide_suggestions: bool = False,
) -> List[GraphQLError]:
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

    Validation is also aborted if the document nests fragments too deeply for the
    recursion limit of the interpreter. The errors found until then are kept, and an
    additional error reports the abort.

    Providing a custom TypeInfo instance is deprecated; omit the ``type_info``
    argument so that validate creates the TypeInfo instance. It will be removed in v3.3.

    :param schema: Schema to validate against.
    :param document_ast: Document AST to validate.
    :param rules: Validation rules to apply. Defaults to
        :data:`~graphql.validation.specified_rules`.
    :param max_errors: Maximum number of validation errors before validation stops.
        Defaults to 100.
    :param type_info: TypeInfo instance used to track traversal state during
        validation (deprecated, will be removed in v3.3).
    :param hide_suggestions: Omit suggestions from validation errors.
    :returns: Validation errors, or an empty list when the document is valid.

    Validate with the default specified rules:

    >>> from graphql import build_schema, parse, validate
    >>> schema = build_schema('type Query { greeting: String }')
    >>> validate(schema, parse('{ greeting }'))
    []
    >>> errors = validate(schema, parse('{ missing }'))
    >>> print(errors[0].message)
    Cannot query field 'missing' on type 'Query'.

    This variant uses a custom rule list and an error limit:

    >>> from graphql.validation import FieldsOnCorrectTypeRule
    >>> document = parse('{ missingOne missingTwo }')
    >>> errors = validate(
    ...     schema, document, [FieldsOnCorrectTypeRule], max_errors=1)
    >>> len(errors)
    2
    >>> print(errors[1].message)
    Too many validation errors, error limit reached. Validation aborted.
    """
    if not document_ast or not isinstance(document_ast, DocumentNode):
        raise TypeError("Must provide document.")
    # If the schema used for validation is invalid, throw an error.
    assert_valid_schema(schema)
    if max_errors is None:
        max_errors = 100
    elif not isinstance(max_errors, int):
        raise TypeError("The maximum number of errors must be passed as an int.")
    if type_info is None:
        type_info = TypeInfo(schema)
    elif not isinstance(type_info, TypeInfo):
        raise TypeError(f"Not a TypeInfo object: {inspect(type_info)}.")
    if rules is None:
        rules = specified_rules
    elif not is_collection(rules) or not all(
        isinstance(rule, type) and issubclass(rule, ASTValidationRule) for rule in rules
    ):
        raise TypeError(
            "Rules must be specified as a collection of ASTValidationRule subclasses."
        )

    errors: List[GraphQLError] = []

    def on_error(error: GraphQLError) -> None:
        if len(errors) >= max_errors:
            # Unlike GraphQL.js, create a new error each time, because raising a
            # shared error would add the frames of every validation to its traceback.
            raise ValidationAbortedError(
                "Too many validation errors, error limit reached. Validation aborted."
            )
        errors.append(error)

    context = ValidationContext(
        schema, document_ast, type_info, on_error, hide_suggestions
    )

    # This uses a specialized visitor which runs multiple visitors in parallel,
    # while maintaining the visitor skip and break API.
    visitors: List[Visitor] = [rule(context) for rule in rules]
    fragments = {
        definition.name.value: definition
        for definition in document_ast.definitions
        if isinstance(definition, FragmentDefinitionNode)
    }
    if fragments:
        visitors.insert(0, FragmentNestingVisitor(fragments))

    # Visit the whole document with each instance of all provided rules.
    try:
        visit(
            document_ast,
            TypeInfoVisitor(type_info, ParallelVisitor(visitors)),
            query_document_keys_to_validate,
        )
    except ValidationAbortedError as error:
        # Do not keep the frames of the validation alive with the returned error,
        # also not via the context of an error that was handled while aborting.
        error.__context__ = None
        errors.append(error.with_traceback(None))
    except RecursionError:
        # This error is never raised, so it has no traceback or context
        # that would keep all the frames of the recursion alive.
        errors.append(ValidationAbortedError("Validation aborted."))
    return errors


def validate_sdl(
    document_ast: DocumentNode,
    schema_to_extend: Optional[GraphQLSchema] = None,
    rules: Optional[Collection[Type[ASTValidationRule]]] = None,
) -> List[GraphQLError]:
    """Validate an SDL document.

    For internal use only.
    """
    errors: List[GraphQLError] = []
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
