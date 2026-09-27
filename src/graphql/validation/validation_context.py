"""Validation context"""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    NamedTuple,
    cast,
)

from ..language import (
    DocumentNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    OperationDefinitionNode,
    SelectionSetNode,
    VariableDefinitionNode,
    VariableNode,
    Visitor,
    VisitorAction,
    visit,
)
from ..pyutils import Undefined
from ..utilities import TypeInfo, TypeInfoVisitor

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..error import GraphQLError
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
    from ..utilities.type_info import FragmentSignature, FragmentSignatureByNameFn

from typing import TypeAlias

__all__ = [
    "ASTValidationContext",
    "SDLValidationContext",
    "ValidationContext",
    "VariableUsage",
    "VariableUsageVisitor",
]

NodeWithSelectionSet: TypeAlias = OperationDefinitionNode | FragmentDefinitionNode


class VariableUsage(NamedTuple):
    """Variable usage"""

    node: VariableNode
    type: GraphQLInputType | None
    parent_type: GraphQLInputType | None
    default_value: Any
    fragment_variable_definition: VariableDefinitionNode | None


class VariableUsageVisitor(Visitor):
    """Visitor adding all variable usages to a given list."""

    usages: list[VariableUsage]

    def __init__(
        self,
        type_info: TypeInfo,
        fragment_definition: FragmentDefinitionNode | None = None,
    ) -> None:
        super().__init__()
        self.usages = []
        self._append_usage = self.usages.append
        self._type_info = type_info
        self._fragment_definition = fragment_definition

    def enter_variable_definition(self, *_args: Any) -> VisitorAction:
        return self.SKIP

    def enter_variable(self, node: VariableNode, *_args: Any) -> VisitorAction:
        type_info = self._type_info
        fragment_definition = self._fragment_definition
        if fragment_definition:
            fragment_signature = type_info.get_fragment_signature_by_name()(
                fragment_definition.name.value
            )
            fragment_variable_definition = (
                fragment_signature.variable_definitions.get(node.name.value)
                if fragment_signature
                else None
            )
            # Fragment variables have a variable default but no location default,
            # which is what this default value represents.
            usage = VariableUsage(
                node,
                type_info.get_input_type(),
                type_info.get_parent_input_type(),
                Undefined,
                fragment_variable_definition,
            )
        else:
            usage = VariableUsage(
                node,
                type_info.get_input_type(),
                type_info.get_parent_input_type(),
                type_info.get_default_value(),
                None,
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

    _fragments: dict[str, FragmentDefinitionNode] | None
    _fragment_spreads: dict[SelectionSetNode, list[FragmentSpreadNode]]
    _recursively_referenced_fragments: dict[
        OperationDefinitionNode, list[FragmentDefinitionNode]
    ]

    def __init__(
        self, ast: DocumentNode, on_error: Callable[[GraphQLError], None]
    ) -> None:
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

    def get_fragment(self, name: str) -> FragmentDefinitionNode | None:
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

    def get_fragment_spreads(self, node: SelectionSetNode) -> list[FragmentSpreadNode]:
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
                            "NodeWithSelectionSet", selection
                        ).selection_set
                        if set_to_visit:
                            append_set(set_to_visit)
            self._fragment_spreads[node] = spreads
        return spreads

    def get_recursively_referenced_fragments(
        self, operation: OperationDefinitionNode
    ) -> list[FragmentDefinitionNode]:
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
        fragments = self._recursively_referenced_fragments.get(operation)
        if fragments is None:
            fragments = []
            append_fragment = fragments.append
            collected_names: set[str] = set()
            add_name = collected_names.add
            nodes_to_visit = [operation.selection_set]
            append_node = nodes_to_visit.append
            pop_node = nodes_to_visit.pop
            get_fragment = self.get_fragment
            get_fragment_spreads = self.get_fragment_spreads
            while nodes_to_visit:
                visited_node = pop_node()
                for spread in get_fragment_spreads(visited_node):
                    frag_name = spread.name.value
                    if frag_name not in collected_names:
                        add_name(frag_name)
                        if fragment := get_fragment(frag_name):
                            append_fragment(fragment)
                            append_node(fragment.selection_set)
            self._recursively_referenced_fragments[operation] = fragments
        return fragments


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

    schema: GraphQLSchema | None
    """The schema being extended, if any."""

    def __init__(
        self,
        ast: DocumentNode,
        schema: GraphQLSchema | None,
        on_error: Callable[[GraphQLError], None],
    ) -> None:
        super().__init__(ast, on_error)
        self.schema = schema

    @property
    def hide_suggestions(self) -> bool:
        """Whether validation error suggestions are hidden (always false for SDL)."""
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
    :param hide_suggestions: Whether suggestion text should be omitted from errors.

    >>> from graphql import GraphQLError, TypeInfo, build_schema, parse
    >>> from graphql.validation import ValidationContext
    >>> schema = build_schema('type Query { greeting: String }')
    >>> document = parse('{ greeting }')
    >>> errors = []
    >>> context = ValidationContext(schema, document, TypeInfo(schema), errors.append)
    >>> context.report_error(GraphQLError('Example validation error.'))
    >>> context.schema is schema
    True
    >>> errors[0].message
    'Example validation error.'
    """

    schema: GraphQLSchema
    """The schema being validated against."""

    _type_info: TypeInfo
    _variable_usages: dict[NodeWithSelectionSet, list[VariableUsage]]
    _recursive_variable_usages: dict[OperationDefinitionNode, list[VariableUsage]]
    _hide_suggestions: bool

    def __init__(
        self,
        schema: GraphQLSchema,
        ast: DocumentNode,
        type_info: TypeInfo,
        on_error: Callable[[GraphQLError], None],
        hide_suggestions: bool = False,
    ) -> None:
        super().__init__(ast, on_error)
        self.schema = schema
        self._type_info = type_info
        self._variable_usages = {}
        self._recursive_variable_usages = {}
        self._hide_suggestions = hide_suggestions

    @property
    def hide_suggestions(self) -> bool:
        """Whether validation error suggestions are hidden."""
        return self._hide_suggestions

    def get_variable_usages(self, node: NodeWithSelectionSet) -> list[VariableUsage]:
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
            fragment_definition = (
                node if isinstance(node, FragmentDefinitionNode) else None
            )
            usage_visitor = VariableUsageVisitor(self._type_info, fragment_definition)
            visit(node, TypeInfoVisitor(self._type_info, usage_visitor))
            usages = usage_visitor.usages
            self._variable_usages[node] = usages
        return usages

    def get_recursive_variable_usages(
        self, operation: OperationDefinitionNode
    ) -> list[VariableUsage]:
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
            usages = get_variable_usages(operation)
            for fragment in self.get_recursively_referenced_fragments(operation):
                usages.extend(get_variable_usages(fragment))
            self._recursive_variable_usages[operation] = usages
        return usages

    def get_type(self) -> GraphQLOutputType | None:
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

    def get_parent_type(self) -> GraphQLCompositeType | None:
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

    def get_input_type(self) -> GraphQLInputType | None:
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

    # Note: continues to expose the closest enclosing valid input type if
    # traversal descends into syntax with no corresponding GraphQL input type.
    def get_parent_input_type(self) -> GraphQLInputType | None:
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

    def get_field_def(self) -> GraphQLField | None:
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

    def get_directive(self) -> GraphQLDirective | None:
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

    def get_argument(self) -> GraphQLArgument | None:
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

    def get_fragment_signature(self) -> FragmentSignature | None:
        """Get the fragment signature at the current traversal position.

        :returns: The current fragment signature, if one is active.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> from graphql.validation import ValidationContext
        >>> schema = build_schema('type Query { greeting: String }')
        >>> document = parse(
        ...     '{ ...GreetingFields } fragment GreetingFields on Query { greeting }',
        ...     experimental_fragment_arguments=True,
        ... )
        >>> type_info = TypeInfo(schema)
        >>> context = ValidationContext(
        ...     schema, document, type_info, lambda error: None)
        >>> class PrintVisitor(Visitor):
        ...     def enter_fragment_spread(self, *_args):
        ...         print(context.get_fragment_signature().definition.name.value)
        >>> _ = visit(document, TypeInfoVisitor(type_info, PrintVisitor()))
        GreetingFields
        """
        return self._type_info.get_fragment_signature()

    def get_fragment_signature_by_name(self) -> FragmentSignatureByNameFn:
        """Get the function used to look up fragment signatures by name.

        :returns: A function that maps fragment names to fragment signatures.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> from graphql.validation import ValidationContext
        >>> schema = build_schema('type Query { greeting: String }')
        >>> document = parse(
        ...     '{ ...GreetingFields } fragment GreetingFields on Query { greeting }',
        ...     experimental_fragment_arguments=True,
        ... )
        >>> type_info = TypeInfo(schema)
        >>> context = ValidationContext(
        ...     schema, document, type_info, lambda error: None)
        >>> class PrintVisitor(Visitor):
        ...     def enter_document(self, *_args):
        ...         get_fragment_signature = context.get_fragment_signature_by_name()
        ...         signature = get_fragment_signature('GreetingFields')
        ...         print(signature.definition.name.value)
        >>> _ = visit(document, TypeInfoVisitor(type_info, PrintVisitor()))
        GreetingFields
        """
        return self._type_info.get_fragment_signature_by_name()

    def get_enum_value(self) -> GraphQLEnumValue | None:
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
