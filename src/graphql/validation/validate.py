"""Validation"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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


# Per the specification, descriptions must not affect validation.
# See https://spec.graphql.org/draft/#sec-Descriptions
query_document_keys_to_validate: dict[str, tuple[str, ...]] = {
    kind: tuple(key for key in keys if key != "description")
    for kind, keys in QUERY_DOCUMENT_KEYS.items()
}


def get_selection_nesting(
    selection_set: SelectionSetNode,
) -> tuple[int, list[tuple[str, int]]]:
    """Get the nesting depth of a selection set, and its spreads with their depth.

    :meta private:
    """
    max_depth = 0
    spreads: list[tuple[str, int]] = []
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

    def __init__(self, fragments: dict[str, FragmentDefinitionNode]) -> None:
        super().__init__()
        self.depths: dict[str, int] = {}
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

    def get_depth(self, depth: int, spreads: list[tuple[str, int]]) -> int:
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
    rules: Collection[type[ASTValidationRule]] | None = None,
    max_errors: int | None = None,
    hide_suggestions: bool = False,
    allow_empty_selection_sets: bool = True,
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

    Validation is also aborted if the document nests fragments too deeply for the
    recursion limit of the interpreter. The errors found until then are kept, and an
    additional error reports the abort.

    :param schema: Schema to validate against.
    :param document_ast: Document AST to validate.
    :param rules: Validation rules to apply. Defaults to
        :data:`~graphql.validation.specified_rules`.
    :param max_errors: Maximum number of validation errors before validation stops.
        Defaults to 100.
    :param hide_suggestions: Whether suggestion text should be omitted from
        validation errors.
    :param allow_empty_selection_sets: If enabled (the default), a selection set on
        an object, interface or union type is only required to be present, rather
        than to be non-empty. Pair this with the ``allow_empty_selection_sets``
        parse option. See https://github.com/graphql/graphql-spec/pull/1227.
        Deprecated, since empty selection sets are now always allowed.
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
            # Unlike GraphQL.js, create a new error each time, because raising a
            # shared error would add the frames of every validation to its traceback.
            msg = "Too many validation errors, error limit reached. Validation aborted."
            raise ValidationAbortedError(msg)
        errors.append(error)

    context = ValidationContext(
        schema,
        document_ast,
        type_info,
        on_error,
        hide_suggestions,
        allow_empty_selection_sets,
    )

    # This uses a specialized visitor which runs multiple visitors in parallel,
    # while maintaining the visitor skip and break API.
    visitors: list[Visitor] = [rule(context) for rule in rules]
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
