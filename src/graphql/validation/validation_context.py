"""Validation context"""

from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    FrozenSet,
    List,
    NamedTuple,
    Optional,
    Union,
    cast,
)

from ..error import GraphQLError
from ..language import (
    DocumentNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    OperationDefinitionNode,
    SelectionSetNode,
    VariableNode,
    Visitor,
    VisitorAction,
    visit,
)
from ..type import (
    GraphQLArgument,
    GraphQLCompositeType,
    GraphQLDirective,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInputType,
    GraphQLOutputType,
    GraphQLSchema,
)
from ..utilities import TypeInfo, TypeInfoVisitor

__all__ = [
    "MAX_FRAGMENT_WORK",
    "ASTValidationContext",
    "SDLValidationContext",
    "ValidationContext",
    "VariableUsage",
    "VariableUsageVisitor",
]

NodeWithSelectionSet = Union[OperationDefinitionNode, FragmentDefinitionNode]

# The maximum amount of work spent on fragments shared by the operations of a single
# document, counted in fragment spreads and variable usages. Once it is exhausted,
# validation is aborted with a "Validation aborted." error. Unlike GraphQL.js, the
# budget can be raised or lowered by assigning to
# ``graphql.validation.validation_context.MAX_FRAGMENT_WORK``.
MAX_FRAGMENT_WORK = 50_000


class VariableUsage(NamedTuple):
    """A usage of a variable together with the expected input type."""

    node: VariableNode
    type: Optional[GraphQLInputType]
    default_value: Any
    parent_type: Optional[GraphQLInputType]


class VariableUsageVisitor(Visitor):
    """Visitor adding all variable usages to a given list."""

    usages: List[VariableUsage]

    def __init__(self, type_info: TypeInfo):
        super().__init__()
        self.usages = []
        self._append_usage = self.usages.append
        self._type_info = type_info

    def enter_variable_definition(self, *_args: Any) -> VisitorAction:
        return self.SKIP

    def enter_variable(self, node: VariableNode, *_args: Any) -> VisitorAction:
        type_info = self._type_info
        usage = VariableUsage(
            node,
            type_info.get_input_type(),
            type_info.get_default_value(),
            type_info.get_parent_input_type(),
        )
        self._append_usage(usage)
        return None


class ASTValidationContext:
    """Utility class providing a context for validation of an AST.

    An instance of this class is passed as the context attribute to all Validators,
    allowing access to commonly useful contextual information from within a validation
    rule.

    :param ast: Document AST being validated.
    :param on_error: Callback invoked for each validation error.

    >>> from graphql import GraphQLError, parse
    >>> from graphql.validation import ASTValidationContext
    >>> errors = []
    >>> context = ASTValidationContext(parse('{ greeting }'), errors.append)
    >>> context.document.kind
    'document'
    >>> context.report_error(GraphQLError('Example validation error.'))
    >>> errors[0].message
    'Example validation error.'
    """

    document: DocumentNode
    """The document AST being validated."""

    _remaining_fragment_work: int
    _fragments: Optional[Dict[str, FragmentDefinitionNode]]
    _fragment_spreads: Dict[SelectionSetNode, List[FragmentSpreadNode]]
    _recursively_referenced_fragments: Dict[
        FrozenSet[str], List[FragmentDefinitionNode]
    ]

    def __init__(
        self, ast: DocumentNode, on_error: Callable[[GraphQLError], None]
    ) -> None:
        self._remaining_fragment_work = MAX_FRAGMENT_WORK
        self.document = ast
        self.on_error = on_error  # type: ignore
        self._fragments = None
        self._fragment_spreads = {}
        self._recursively_referenced_fragments = {}

    def on_error(self, error: GraphQLError) -> None:
        """Handle a validation error.

        This method is replaced with the ``on_error`` callback passed to the
        constructor.

        :param error: The validation error.

        >>> from graphql import GraphQLError, parse
        >>> from graphql.validation import ASTValidationContext
        >>> context = ASTValidationContext(parse('{ greeting }'), print)
        >>> context.on_error(GraphQLError('Example validation error.'))
        Example validation error.
        """

    def report_error(self, error: GraphQLError) -> None:
        """Report a validation error.

        :param error: The validation error to report.

        >>> from graphql import GraphQLError, parse
        >>> from graphql.validation import ASTValidationContext
        >>> errors = []
        >>> context = ASTValidationContext(parse('{ greeting }'), errors.append)
        >>> context.report_error(GraphQLError('Example validation error.'))
        >>> errors[0].message
        'Example validation error.'
        """
        self.on_error(error)

    def get_fragment(self, name: str) -> Optional[FragmentDefinitionNode]:
        """Get the fragment definition with the given name from the document.

        :param name: The name of the fragment.
        :returns: The fragment definition, or ``None`` if there is no such fragment.

        >>> from graphql import parse
        >>> from graphql.validation import ASTValidationContext
        >>> document = parse('{ ...Greeting } fragment Greeting on Query { greeting }')
        >>> context = ASTValidationContext(document, print)
        >>> context.get_fragment('Greeting').type_condition.name.value
        'Query'
        >>> context.get_fragment('Missing') is None
        True
        """
        fragments = self._fragments
        if fragments is None:
            fragments = {
                statement.name.value: statement
                for statement in self.document.definitions
                if isinstance(statement, FragmentDefinitionNode)
            }

            self._fragments = fragments
        return fragments.get(name)

    def get_fragment_spreads(self, node: SelectionSetNode) -> List[FragmentSpreadNode]:
        """Get all fragment spreads contained in the given selection set.

        This includes fragment spreads in nested selection sets, but not the ones
        inside the spread fragments themselves.

        :param node: The selection set node to inspect.
        :returns: The fragment spreads found in the selection set.

        >>> from graphql import parse
        >>> from graphql.validation import ASTValidationContext
        >>> document = parse('{ ...A viewer { ...B } }')
        >>> context = ASTValidationContext(document, print)
        >>> selection_set = document.definitions[0].selection_set
        >>> spreads = context.get_fragment_spreads(selection_set)
        >>> [spread.name.value for spread in spreads]
        ['A', 'B']
        """
        spreads = self._fragment_spreads.get(node)
        if spreads is None:
            spreads = []
            append_spread = spreads.append
            sets_to_visit = [node]
            append_set = sets_to_visit.append
            pop_set = sets_to_visit.pop
            while sets_to_visit:
                visited_set = pop_set()
                for selection in visited_set.selections:
                    if isinstance(selection, FragmentSpreadNode):
                        append_spread(selection)
                    else:
                        set_to_visit = cast(
                            NodeWithSelectionSet, selection
                        ).selection_set
                        if set_to_visit:
                            append_set(set_to_visit)
            self._fragment_spreads[node] = spreads
        return spreads

    # TODO: In the next major version, accept multiple operations here and
    # remove get_recursively_referenced_fragments_for_operations.
    def get_recursively_referenced_fragments(
        self, operation: OperationDefinitionNode
    ) -> List[FragmentDefinitionNode]:
        """Get all fragments referenced by the operation, directly or indirectly.

        :param operation: The operation definition to inspect.
        :returns: The fragment definitions reachable from the operation.

        >>> from graphql import parse
        >>> from graphql.validation import ASTValidationContext
        >>> document = parse('''
        ...     { ...A }
        ...     fragment A on Query { ...B }
        ...     fragment B on Query { greeting }
        ... ''')
        >>> context = ASTValidationContext(document, print)
        >>> operation = document.definitions[0]
        >>> fragments = context.get_recursively_referenced_fragments(operation)
        >>> [fragment.name.value for fragment in fragments]
        ['A', 'B']
        """
        return self.get_recursively_referenced_fragments_for_operations([operation])

    def get_recursively_referenced_fragments_for_operations(
        self, operations: Collection[OperationDefinitionNode]
    ) -> List[FragmentDefinitionNode]:
        """Get all fragments referenced by the operations, directly or indirectly.

        :param operations: The operation definitions to inspect.
        :returns: The fragment definitions reachable from any of the operations.

        >>> from graphql import parse
        >>> from graphql.validation import ASTValidationContext
        >>> document = parse('''
        ...     query One { ...A }
        ...     query Two { ...B }
        ...     fragment A on Query { greeting }
        ...     fragment B on Query { farewell }
        ...     fragment C on Query { greeting }
        ... ''')
        >>> context = ASTValidationContext(document, print)
        >>> operations = document.definitions[:2]
        >>> fragments = context.get_recursively_referenced_fragments_for_operations(
        ...     operations)
        >>> sorted(fragment.name.value for fragment in fragments)
        ['A', 'B']
        """
        get_fragment_spreads = self.get_fragment_spreads
        # keep the names in the order in which they are spread
        fragment_names = list(
            dict.fromkeys(
                spread.name.value
                for operation in operations
                for spread in get_fragment_spreads(operation.selection_set)
            )
        )
        key = frozenset(fragment_names)
        fragments = self._recursively_referenced_fragments.get(key)
        if fragments is None:
            fragments = []
            append_fragment = fragments.append
            spend_fragment_work = self.spend_fragment_work
            spend_fragment_work(len(fragment_names))
            collected_names = set(fragment_names)
            add_name = collected_names.add
            # the list grows while it is iterated, like a set in JavaScript
            append_name = fragment_names.append
            get_fragment = self.get_fragment
            for frag_name in fragment_names:
                fragment = get_fragment(frag_name)
                if fragment:
                    append_fragment(fragment)
                    spreads = get_fragment_spreads(fragment.selection_set)
                    spend_fragment_work(len(spreads))
                    for spread in spreads:
                        spread_name = spread.name.value
                        if spread_name not in collected_names:
                            add_name(spread_name)
                            append_name(spread_name)
            self._recursively_referenced_fragments[key] = fragments
        return fragments

    def spend_fragment_work(self, cost: int) -> None:
        """Spend work on shared fragments and abort validation when exhausted.

        :param cost: The amount of work to spend.
        :raises ValidationAbortedError: If the budget for fragment work is exhausted.

        :meta private:
        """
        self._remaining_fragment_work -= cost
        if self._remaining_fragment_work < 0:
            from .validate import ValidationAbortedError

            raise ValidationAbortedError("Validation aborted.")


class SDLValidationContext(ASTValidationContext):
    """Utility class providing a context for validation of an SDL AST.

    An instance of this class is passed as the context attribute to all Validators,
    allowing access to commonly useful contextual information from within a validation
    rule.

    :param ast: SDL document AST being validated.
    :param schema: Schema being extended, if any.
    :param on_error: Callback invoked for each validation error.

    >>> from graphql import build_schema, parse
    >>> from graphql.validation import SDLValidationContext
    >>> schema = build_schema('type Query { greeting: String }')
    >>> document = parse('extend type Query { farewell: String }')
    >>> context = SDLValidationContext(document, schema, print)
    >>> context.schema is schema
    True
    >>> SDLValidationContext(document, None, print).schema is None
    True
    """

    schema: Optional[GraphQLSchema]
    """The schema being extended, if any."""

    def __init__(
        self,
        ast: DocumentNode,
        schema: Optional[GraphQLSchema],
        on_error: Callable[[GraphQLError], None],
    ) -> None:
        super().__init__(ast, on_error)
        self.schema = schema

    @property
    def hide_suggestions(self) -> bool:
        """Whether suggestions should be omitted from validation errors."""
        return False


class ValidationContext(ASTValidationContext):
    """Utility class providing a context for validation using a GraphQL schema.

    An instance of this class is passed as the context attribute to all Validators,
    allowing access to commonly useful contextual information from within a validation
    rule.

    :param schema: Schema used to validate the document.
    :param ast: Document AST being validated.
    :param type_info: TypeInfo instance used to track traversal state.
    :param on_error: Callback invoked for each validation error.
    :param hide_suggestions: Omit suggestions from error messages.

    >>> from graphql import GraphQLError, TypeInfo, build_schema, parse
    >>> from graphql.validation import ValidationContext
    >>> schema = build_schema('type Query { greeting: String }')
    >>> document = parse('{ greeting }')
    >>> errors = []
    >>> context = ValidationContext(
    ...     schema, document, TypeInfo(schema), errors.append)
    >>> context.report_error(GraphQLError('Example validation error.'))
    >>> context.schema is schema
    True
    >>> context.schema.query_type.name
    'Query'
    >>> errors[0].message
    'Example validation error.'
    """

    schema: GraphQLSchema
    """The schema being validated against."""

    _type_info: TypeInfo
    _variable_usages: Dict[NodeWithSelectionSet, List[VariableUsage]]
    _recursive_variable_usages: Dict[OperationDefinitionNode, List[VariableUsage]]
    # keyed by the id of the fragment lists cached (and so kept alive) in the context
    _fragment_variable_usages: Dict[int, List[VariableUsage]]

    def __init__(
        self,
        schema: GraphQLSchema,
        ast: DocumentNode,
        type_info: TypeInfo,
        on_error: Callable[[GraphQLError], None],
        hide_suggestions: bool = False,
    ) -> None:
        super().__init__(ast, on_error)
        self._hide_suggestions = hide_suggestions
        self.schema = schema
        self._type_info = type_info
        self._variable_usages = {}
        self._recursive_variable_usages = {}
        self._fragment_variable_usages = {}

    @property
    def hide_suggestions(self) -> bool:
        """Whether suggestions should be omitted from validation errors."""
        return self._hide_suggestions

    def get_variable_usages(self, node: NodeWithSelectionSet) -> List[VariableUsage]:
        """Get variable usages found directly within the given node.

        :param node: The operation or fragment definition to inspect.
        :returns: Variable usages found directly within this node.

        >>> from graphql import TypeInfo, build_schema, parse
        >>> from graphql.validation import ValidationContext
        >>> schema = build_schema('type Query { greeting(name: String): String }')
        >>> document = parse('query ($name: String) { greeting(name: $name) }')
        >>> operation = document.definitions[0]
        >>> context = ValidationContext(
        ...     schema, document, TypeInfo(schema), lambda error: None)
        >>> usages = context.get_variable_usages(operation)
        >>> usages[0].node.name.value
        'name'
        >>> str(usages[0].type)
        'String'
        """
        usages = self._variable_usages.get(node)
        if usages is None:
            usage_visitor = VariableUsageVisitor(self._type_info)
            visit(node, TypeInfoVisitor(self._type_info, usage_visitor))
            usages = usage_visitor.usages
            self._variable_usages[node] = usages
        return usages

    def get_recursive_variable_usages(
        self, operation: OperationDefinitionNode
    ) -> List[VariableUsage]:
        """Get variable usages for an operation, including referenced fragments.

        :param operation: Operation definition to inspect.
        :returns: Variable usages reachable from the operation.

        >>> from graphql import TypeInfo, build_schema, parse
        >>> from graphql.validation import ValidationContext
        >>> schema = build_schema('''
        ...     type Query { viewer: User }
        ...     type User { name(prefix: String): String }
        ... ''')
        >>> document = parse('''
        ...     query ($prefix: String) { viewer { ...UserName } }
        ...     fragment UserName on User { name(prefix: $prefix) }
        ... ''')
        >>> operation = document.definitions[0]
        >>> context = ValidationContext(
        ...     schema, document, TypeInfo(schema), lambda error: None)
        >>> usages = context.get_recursive_variable_usages(operation)
        >>> [usage.node.name.value for usage in usages]
        ['prefix']
        """
        usages = self._recursive_variable_usages.get(operation)
        if usages is None:
            get_variable_usages = self.get_variable_usages
            fragments = self.get_recursively_referenced_fragments(operation)
            fragment_usages = self._fragment_variable_usages.get(id(fragments))
            spend_fragment_work = self.spend_fragment_work
            if fragment_usages is None:
                spend_fragment_work(len(fragments))
                fragment_usages = []
                extend_usages = fragment_usages.extend
                for fragment in fragments:
                    local_usages = get_variable_usages(fragment)
                    spend_fragment_work(len(local_usages))
                    extend_usages(local_usages)
                self._fragment_variable_usages[id(fragments)] = fragment_usages
            spend_fragment_work(len(fragment_usages))
            usages = [*get_variable_usages(operation), *fragment_usages]
            self._recursive_variable_usages[operation] = usages
        return usages

    def get_type(self) -> Optional[GraphQLOutputType]:
        """Get the current output type at this point in traversal.

        :returns: The current output type, if known.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> from graphql.validation import ValidationContext
        >>> schema = build_schema('type Query { greeting: String }')
        >>> document = parse('{ greeting }')
        >>> type_info = TypeInfo(schema)
        >>> context = ValidationContext(
        ...     schema, document, type_info, lambda error: None)
        >>> class PrintVisitor(Visitor):
        ...     def enter_field(self, *_args):
        ...         print(context.get_type())
        >>> _ = visit(document, TypeInfoVisitor(type_info, PrintVisitor()))
        String
        """
        return self._type_info.get_type()

    def get_parent_type(self) -> Optional[GraphQLCompositeType]:
        """Get the current parent composite type.

        :returns: The current parent composite type, if known.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> from graphql.validation import ValidationContext
        >>> schema = build_schema('type Query { greeting: String }')
        >>> document = parse('{ greeting }')
        >>> type_info = TypeInfo(schema)
        >>> context = ValidationContext(
        ...     schema, document, type_info, lambda error: None)
        >>> class PrintVisitor(Visitor):
        ...     def enter_field(self, *_args):
        ...         print(context.get_parent_type().name)
        >>> _ = visit(document, TypeInfoVisitor(type_info, PrintVisitor()))
        Query
        """
        return self._type_info.get_parent_type()

    def get_input_type(self) -> Optional[GraphQLInputType]:
        """Get the current input type at this point in traversal.

        :returns: The current input type, if known.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> from graphql.validation import ValidationContext
        >>> schema = build_schema('type Query { reviews(limit: Int): [String] }')
        >>> document = parse('{ reviews(limit: 5) }')
        >>> type_info = TypeInfo(schema)
        >>> context = ValidationContext(
        ...     schema, document, type_info, lambda error: None)
        >>> class PrintVisitor(Visitor):
        ...     def enter_argument(self, *_args):
        ...         print(context.get_input_type())
        >>> _ = visit(document, TypeInfoVisitor(type_info, PrintVisitor()))
        Int
        """
        return self._type_info.get_input_type()

    def get_parent_input_type(self) -> Optional[GraphQLInputType]:
        """Get the parent input type for the current input position.

        :returns: The parent input type, if known.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> from graphql.validation import ValidationContext
        >>> schema = build_schema('''
        ...     input ReviewFilter { stars: Int }
        ...     type Query { reviews(filter: ReviewFilter): [String] }
        ... ''')
        >>> document = parse('{ reviews(filter: { stars: 5 }) }')
        >>> type_info = TypeInfo(schema)
        >>> context = ValidationContext(
        ...     schema, document, type_info, lambda error: None)
        >>> class PrintVisitor(Visitor):
        ...     def enter_object_field(self, *_args):
        ...         print(context.get_parent_input_type())
        >>> _ = visit(document, TypeInfoVisitor(type_info, PrintVisitor()))
        ReviewFilter
        """
        return self._type_info.get_parent_input_type()

    def get_field_def(self) -> Optional[GraphQLField]:
        """Get the current field definition.

        :returns: The current field definition, if known.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> from graphql.validation import ValidationContext
        >>> schema = build_schema('type Query { greeting: String }')
        >>> document = parse('{ greeting }')
        >>> type_info = TypeInfo(schema)
        >>> context = ValidationContext(
        ...     schema, document, type_info, lambda error: None)
        >>> class PrintVisitor(Visitor):
        ...     def enter_field(self, *_args):
        ...         print(context.get_field_def().type)
        >>> _ = visit(document, TypeInfoVisitor(type_info, PrintVisitor()))
        String
        """
        return self._type_info.get_field_def()

    def get_directive(self) -> Optional[GraphQLDirective]:
        """Get the current directive definition.

        :returns: The current directive definition, if known.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> from graphql.validation import ValidationContext
        >>> schema = build_schema('type Query { greeting: String }')
        >>> document = parse('{ greeting @include(if: true) }')
        >>> type_info = TypeInfo(schema)
        >>> context = ValidationContext(
        ...     schema, document, type_info, lambda error: None)
        >>> class PrintVisitor(Visitor):
        ...     def enter_directive(self, *_args):
        ...         print(context.get_directive().name)
        >>> _ = visit(document, TypeInfoVisitor(type_info, PrintVisitor()))
        include
        """
        return self._type_info.get_directive()

    def get_argument(self) -> Optional[GraphQLArgument]:
        """Get the current argument definition.

        :returns: The current argument definition, if known.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> from graphql.validation import ValidationContext
        >>> schema = build_schema('type Query { reviews(limit: Int): [String] }')
        >>> document = parse('{ reviews(limit: 5) }')
        >>> type_info = TypeInfo(schema)
        >>> context = ValidationContext(
        ...     schema, document, type_info, lambda error: None)
        >>> class PrintVisitor(Visitor):
        ...     def enter_argument(self, *_args):
        ...         print(context.get_argument().type)
        >>> _ = visit(document, TypeInfoVisitor(type_info, PrintVisitor()))
        Int
        """
        return self._type_info.get_argument()

    def get_enum_value(self) -> Optional[GraphQLEnumValue]:
        """Get the current enum value definition.

        :returns: The current enum value definition, if known.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> from graphql.validation import ValidationContext
        >>> schema = build_schema('''
        ...     enum Sort { NEWEST OLDEST }
        ...     type Query { reviews(sort: Sort): [String] }
        ... ''')
        >>> document = parse('{ reviews(sort: OLDEST) }')
        >>> type_info = TypeInfo(schema)
        >>> context = ValidationContext(
        ...     schema, document, type_info, lambda error: None)
        >>> class PrintVisitor(Visitor):
        ...     def enter_enum_value(self, *_args):
        ...         print(context.get_enum_value().value)
        >>> _ = visit(document, TypeInfoVisitor(type_info, PrintVisitor()))
        OLDEST
        """
        return self._type_info.get_enum_value()
