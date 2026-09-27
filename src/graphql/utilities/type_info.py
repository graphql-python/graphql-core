"""Managing type information"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, NamedTuple, TypeAlias

from ..language import (
    ArgumentNode,
    DirectiveNode,
    DocumentNode,
    EnumValueNode,
    FieldNode,
    FragmentArgumentNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    ListValueNode,
    Node,
    ObjectFieldNode,
    OperationDefinitionNode,
    SelectionSetNode,
    VariableDefinitionNode,
    Visitor,
)
from ..pyutils import Undefined
from ..type import (
    GraphQLArgument,
    GraphQLCompositeType,
    GraphQLDirective,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInputType,
    GraphQLOutputType,
    GraphQLSchema,
    GraphQLType,
    get_named_type,
    get_nullable_type,
    is_composite_type,
    is_enum_type,
    is_input_object_type,
    is_input_type,
    is_list_type,
    is_object_type,
    is_output_type,
)
from .type_from_ast import type_from_ast

__all__ = ["FragmentSignature", "TypeInfo", "TypeInfoVisitor"]


FragmentSignatureByNameFn: TypeAlias = Callable[[str], "FragmentSignature | None"]


class FragmentSignature(NamedTuple):
    """A fragment definition with the variable definitions of its arguments."""

    definition: FragmentDefinitionNode
    variable_definitions: dict[str, VariableDefinitionNode]


class TypeInfo:
    """Utility class for keeping track of type definitions.

    TypeInfo is a utility class which, given a GraphQL schema, can keep track of the
    current field and type definitions at any point in a GraphQL document AST during
    a recursive descent by calling :meth:`enter(node) <.TypeInfo.enter>` and
    :meth:`leave(node) <.TypeInfo.leave>`.

    :param schema: Schema used for type lookups.
    :param initial_type: Optional type to use at the start of traversal. It may be
        provided in rare cases to facilitate traversals beginning somewhere other
        than documents.
    :param fragment_signatures: Optional function returning the signatures of the
        fragments available during traversal by fragment name.

    Track field types during a traversal with a :class:`TypeInfoVisitor`:

    >>> from graphql import (
    ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
    >>> schema = build_schema('''
    ...     type Query {
    ...       greeting: String
    ...     }
    ... ''')
    >>> type_info = TypeInfo(schema)
    >>> seen_types = []
    >>> class FieldVisitor(Visitor):
    ...     def enter_field(self, *_args):
    ...         seen_types.append(str(type_info.get_type()))
    >>> _ = visit(parse('{ greeting }'), TypeInfoVisitor(type_info, FieldVisitor()))
    >>> seen_types
    ['String']

    This variant starts from an initial type and supplies fragment signatures:

    >>> from graphql import FragmentSpreadNode, NameNode, SelectionSetNode
    >>> from graphql.utilities.type_info import FragmentSignature
    >>> schema = build_schema('''
    ...     type Query {
    ...       greeting(name: String): String
    ...     }
    ... ''')
    >>> fragment_document = parse(
    ...     'fragment GreetingFields($name: String) on Query { greeting(name: $name) }',
    ...     experimental_fragment_arguments=True,
    ... )
    >>> fragment_definition = fragment_document.definitions[0]
    >>> variable_definition = fragment_definition.variable_definitions[0]
    >>> type_info = TypeInfo(
    ...     schema,
    ...     schema.query_type,
    ...     lambda name: FragmentSignature(
    ...         fragment_definition, {'name': variable_definition}
    ...     )
    ...     if name == 'GreetingFields'
    ...     else None,
    ... )
    >>> type_info.enter(SelectionSetNode(selections=()))
    >>> type_info.enter(
    ...     FragmentSpreadNode(
    ...         name=NameNode(value='GreetingFields'), arguments=(), directives=()
    ...     )
    ... )
    >>> str(type_info.get_parent_type())
    'Query'
    >>> type_info.get_fragment_signature().definition.name.value
    'GreetingFields'
    """

    def __init__(
        self,
        schema: GraphQLSchema,
        initial_type: GraphQLType | None = None,
        fragment_signatures: FragmentSignatureByNameFn | None = None,
    ) -> None:
        """Initialize the TypeInfo for the given GraphQL schema.

        Initial type may be provided in rare cases to facilitate traversals beginning
        somewhere other than documents.
        """
        self._schema = schema
        self._type_stack: list[GraphQLOutputType | None] = []
        self._parent_type_stack: list[GraphQLCompositeType | None] = []
        self._input_type_stack: list[GraphQLInputType | None] = []
        self._field_def_stack: list[GraphQLField | None] = []
        self._default_value_stack: list[Any] = []
        self._directive: GraphQLDirective | None = None
        self._argument: GraphQLArgument | None = None
        self._enum_value: GraphQLEnumValue | None = None
        self._fragment_signatures_by_name: FragmentSignatureByNameFn = (
            fragment_signatures or (lambda _fragment_name: None)
        )
        self._fragment_signature: FragmentSignature | None = None
        self._fragment_argument: VariableDefinitionNode | None = None
        if initial_type:
            if is_input_type(initial_type):
                self._input_type_stack.append(initial_type)
            if is_composite_type(initial_type):
                self._parent_type_stack.append(initial_type)
            if is_output_type(initial_type):
                self._type_stack.append(initial_type)

    def get_type(self) -> GraphQLOutputType | None:
        """Get the current output type at this point in traversal.

        :returns: The current output type, if known.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> schema = build_schema('''
        ...     type Query {
        ...       viewer: User
        ...     }
        ...
        ...     type User {
        ...       name: String
        ...     }
        ... ''')
        >>> type_info = TypeInfo(schema)
        >>> field_types = {}
        >>> class FieldVisitor(Visitor):
        ...     def enter_field(self, node, *_args):
        ...         field_types[node.name.value] = str(type_info.get_type())
        >>> document = parse('{ viewer { name } }')
        >>> _ = visit(document, TypeInfoVisitor(type_info, FieldVisitor()))
        >>> field_types
        {'viewer': 'User', 'name': 'String'}
        """
        if self._type_stack:
            return self._type_stack[-1]
        return None

    def get_parent_type(self) -> GraphQLCompositeType | None:
        """Get the current parent composite type.

        :returns: The current parent composite type, if known.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> schema = build_schema('''
        ...     type Query {
        ...       viewer: User
        ...     }
        ...
        ...     type User {
        ...       name: String
        ...     }
        ... ''')
        >>> type_info = TypeInfo(schema)
        >>> parent_types = {}
        >>> class FieldVisitor(Visitor):
        ...     def enter_field(self, node, *_args):
        ...         parent_types[node.name.value] = str(type_info.get_parent_type())
        >>> document = parse('{ viewer { name } }')
        >>> _ = visit(document, TypeInfoVisitor(type_info, FieldVisitor()))
        >>> parent_types
        {'viewer': 'Query', 'name': 'User'}
        """
        if self._parent_type_stack:
            return self._parent_type_stack[-1]
        return None

    def get_input_type(self) -> GraphQLInputType | None:
        """Get the current input type at this point in traversal.

        :returns: The current input type, if known.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> schema = build_schema('''
        ...     type Query {
        ...       reviews(stars: Int!, sort: Sort = NEWEST): [String]
        ...     }
        ...
        ...     enum Sort {
        ...       NEWEST
        ...       OLDEST
        ...     }
        ... ''')
        >>> type_info = TypeInfo(schema)
        >>> input_types = {}
        >>> class ArgumentVisitor(Visitor):
        ...     def enter_argument(self, node, *_args):
        ...         input_types[node.name.value] = str(type_info.get_input_type())
        >>> document = parse('{ reviews(stars: 5, sort: OLDEST) }')
        >>> _ = visit(document, TypeInfoVisitor(type_info, ArgumentVisitor()))
        >>> input_types
        {'stars': 'Int!', 'sort': 'Sort'}
        """
        if self._input_type_stack:
            return self._input_type_stack[-1]
        return None

    # Note: continues to expose the closest enclosing valid input type if
    # traversal descends into syntax with no corresponding GraphQL input type.
    def get_parent_input_type(self) -> GraphQLInputType | None:
        """Get the parent input type for the current input position.

        :returns: The parent input type, if known.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> schema = build_schema('''
        ...     input ReviewFilter {
        ...       stars: Int!
        ...     }
        ...
        ...     type Query {
        ...       reviews(filter: ReviewFilter): [String]
        ...     }
        ... ''')
        >>> type_info = TypeInfo(schema)
        >>> parent_input_types = {}
        >>> class ObjectFieldVisitor(Visitor):
        ...     def enter_object_field(self, node, *_args):
        ...         parent_input_types[node.name.value] = str(
        ...             type_info.get_parent_input_type())
        >>> document = parse('{ reviews(filter: { stars: 5 }) }')
        >>> _ = visit(document, TypeInfoVisitor(type_info, ObjectFieldVisitor()))
        >>> parent_input_types
        {'stars': 'ReviewFilter'}
        """
        if len(self._input_type_stack) > 1:
            return self._input_type_stack[-2]
        return None

    def get_field_def(self) -> GraphQLField | None:
        """Get the current field definition.

        :returns: The current field definition, if known.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> schema = build_schema('''
        ...     type Query {
        ...       greeting: String
        ...     }
        ... ''')
        >>> type_info = TypeInfo(schema)
        >>> field_defs = []
        >>> class FieldVisitor(Visitor):
        ...     def enter_field(self, node, *_args):
        ...         field_defs.append(type_info.get_field_def())
        >>> document = parse('{ greeting }')
        >>> _ = visit(document, TypeInfoVisitor(type_info, FieldVisitor()))
        >>> field_defs == [schema.query_type.fields['greeting']]
        True
        """
        if self._field_def_stack:
            return self._field_def_stack[-1]
        return None

    def get_default_value(self) -> Any:
        """Get the default value for the current input position.

        :returns: The current default value, if one is available.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> schema = build_schema('''
        ...     type Query {
        ...       reviews(limit: Int = 10): [String]
        ...     }
        ... ''')
        >>> type_info = TypeInfo(schema)
        >>> default_values = []
        >>> class ArgumentVisitor(Visitor):
        ...     def enter_argument(self, node, *_args):
        ...         default_values.append(type_info.get_default_value())
        >>> document = parse('{ reviews(limit: 5) }')
        >>> _ = visit(document, TypeInfoVisitor(type_info, ArgumentVisitor()))
        >>> from graphql import print_ast
        >>> [print_ast(default.literal) for default in default_values]
        ['10']
        """
        if self._default_value_stack:
            return self._default_value_stack[-1]
        return None

    def get_directive(self) -> GraphQLDirective | None:
        """Get the current directive definition.

        :returns: The current directive definition, if known.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> schema = build_schema('''
        ...     type Query {
        ...       greeting: String
        ...     }
        ... ''')
        >>> type_info = TypeInfo(schema)
        >>> directive_names = []
        >>> class DirectiveVisitor(Visitor):
        ...     def enter_directive(self, node, *_args):
        ...         directive_names.append(type_info.get_directive().name)
        >>> document = parse('{ greeting @include(if: true) }')
        >>> _ = visit(document, TypeInfoVisitor(type_info, DirectiveVisitor()))
        >>> directive_names
        ['include']
        """
        return self._directive

    def get_argument(self) -> GraphQLArgument | None:
        """Get the current argument definition.

        :returns: The current argument definition, if known.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> schema = build_schema('''
        ...     type Query {
        ...       reviews(limit: Int = 10): [String]
        ...     }
        ... ''')
        >>> type_info = TypeInfo(schema)
        >>> arguments = []
        >>> class ArgumentVisitor(Visitor):
        ...     def enter_argument(self, node, *_args):
        ...         arguments.append(type_info.get_argument())
        >>> document = parse('{ reviews(limit: 5) }')
        >>> _ = visit(document, TypeInfoVisitor(type_info, ArgumentVisitor()))
        >>> arguments == [schema.query_type.fields['reviews'].args['limit']]
        True
        """
        return self._argument

    def get_fragment_signature(self) -> FragmentSignature | None:
        """Get the current fragment signature.

        :returns: The fragment signature for the current fragment spread.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> schema = build_schema('''
        ...     type Query {
        ...       greeting: String
        ...     }
        ... ''')
        >>> document = parse('''
        ...     {
        ...       ...GreetingFields
        ...     }
        ...
        ...     fragment GreetingFields on Query {
        ...       greeting
        ...     }
        ... ''', experimental_fragment_arguments=True)
        >>> type_info = TypeInfo(schema)
        >>> fragment_names = []
        >>> class FragmentSpreadVisitor(Visitor):
        ...     def enter_fragment_spread(self, *_args):
        ...         signature = type_info.get_fragment_signature()
        ...         fragment_names.append(signature.definition.name.value)
        >>> _ = visit(document, TypeInfoVisitor(type_info, FragmentSpreadVisitor()))
        >>> fragment_names
        ['GreetingFields']
        """
        return self._fragment_signature

    def get_fragment_signature_by_name(self) -> FragmentSignatureByNameFn:
        """Get the function used to look up fragment signatures by name.

        :returns: A function that maps fragment names to fragment signatures.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> schema = build_schema('''
        ...     type Query {
        ...       greeting: String
        ...     }
        ... ''')
        >>> document = parse('''
        ...     {
        ...       ...GreetingFields
        ...     }
        ...
        ...     fragment GreetingFields on Query {
        ...       greeting
        ...     }
        ... ''', experimental_fragment_arguments=True)
        >>> type_info = TypeInfo(schema)
        >>> fragment_names = []
        >>> class DocumentVisitor(Visitor):
        ...     def enter_document(self, *_args):
        ...         get_fragment_signature = type_info.get_fragment_signature_by_name()
        ...         signature = get_fragment_signature('GreetingFields')
        ...         fragment_names.append(signature.definition.name.value)
        >>> _ = visit(document, TypeInfoVisitor(type_info, DocumentVisitor()))
        >>> fragment_names
        ['GreetingFields']
        """
        return self._fragment_signatures_by_name

    def get_fragment_argument(self) -> VariableDefinitionNode | None:
        """Get the current fragment argument definition.

        :returns: The variable definition for the current fragment argument.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> schema = build_schema('''
        ...     type Query {
        ...       greeting(name: String): String
        ...     }
        ... ''')
        >>> document = parse('''
        ...     {
        ...       ...GreetingFields(name: "Ada")
        ...     }
        ...
        ...     fragment GreetingFields($name: String) on Query {
        ...       greeting(name: $name)
        ...     }
        ... ''', experimental_fragment_arguments=True)
        >>> type_info = TypeInfo(schema)
        >>> argument_names = []
        >>> class FragmentArgumentVisitor(Visitor):
        ...     def enter_fragment_argument(self, *_args):
        ...         argument = type_info.get_fragment_argument()
        ...         argument_names.append(argument.variable.name.value)
        >>> _ = visit(
        ...     document, TypeInfoVisitor(type_info, FragmentArgumentVisitor())
        ... )
        >>> argument_names
        ['name']
        """
        return self._fragment_argument

    def get_enum_value(self) -> GraphQLEnumValue | None:
        """Get the current enum value definition.

        :returns: The current enum value definition, if known.

        >>> from graphql import (
        ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
        >>> schema = build_schema('''
        ...     enum Sort {
        ...       NEWEST
        ...       OLDEST
        ...     }
        ...
        ...     type Query {
        ...       reviews(sort: Sort = NEWEST): [String]
        ...     }
        ... ''')
        >>> type_info = TypeInfo(schema)
        >>> enum_values = []
        >>> class EnumValueVisitor(Visitor):
        ...     def enter_enum_value(self, node, *_args):
        ...         enum_values.append(type_info.get_enum_value().value)
        >>> document = parse('{ reviews(sort: OLDEST) }')
        >>> _ = visit(document, TypeInfoVisitor(type_info, EnumValueVisitor()))
        >>> enum_values
        ['OLDEST']
        """
        return self._enum_value

    def enter(self, node: Node) -> None:
        """Update this TypeInfo instance for an entered AST node.

        :param node: AST node being entered.

        >>> from graphql import TypeInfo, build_schema, parse
        >>> schema = build_schema('''
        ...     type Query {
        ...       greeting: String
        ...     }
        ... ''')
        >>> document = parse('{ greeting }')
        >>> operation = document.definitions[0]
        >>> selection_set = operation.selection_set
        >>> field = selection_set.selections[0]
        >>> type_info = TypeInfo(schema)
        >>> type_info.enter(operation)
        >>> type_info.enter(selection_set)
        >>> type_info.enter(field)
        >>> field.kind
        'field'
        >>> type_info.get_parent_type().name
        'Query'
        >>> str(type_info.get_type())
        'String'
        """
        method = getattr(self, "enter_" + node.kind, None)
        if method:
            method(node)

    def leave(self, node: Node) -> None:
        """Update this TypeInfo instance for a left AST node.

        :param node: AST node being left.

        >>> from graphql import TypeInfo, build_schema, parse
        >>> schema = build_schema('''
        ...     type Query {
        ...       greeting: String
        ...     }
        ... ''')
        >>> document = parse('{ greeting }')
        >>> operation = document.definitions[0]
        >>> selection_set = operation.selection_set
        >>> field = selection_set.selections[0]
        >>> type_info = TypeInfo(schema)
        >>> type_info.enter(operation)
        >>> type_info.enter(selection_set)
        >>> type_info.enter(field)
        >>> str(type_info.get_type())
        'String'
        >>> type_info.leave(field)
        >>> str(type_info.get_type())
        'Query'
        """
        method = getattr(self, "leave_" + node.kind, None)
        if method:
            method()

    def enter_document(self, node: DocumentNode) -> None:
        """Update this TypeInfo instance for an entered document node.

        :meta private:
        """
        self._fragment_signatures_by_name = get_fragment_signatures(node).get

    def enter_selection_set(self, _node: SelectionSetNode) -> None:
        """Update this TypeInfo instance for an entered selection set node.

        :meta private:
        """
        named_type = get_named_type(self.get_type())
        self._parent_type_stack.append(
            named_type if is_composite_type(named_type) else None
        )

    def enter_field(self, node: FieldNode) -> None:
        """Update this TypeInfo instance for an entered field node.

        :meta private:
        """
        parent_type = self.get_parent_type()
        if parent_type:
            field_def = self._schema.get_field(parent_type, node.name.value)
            field_type = field_def.type if field_def else None
        else:
            field_def = field_type = None
        self._field_def_stack.append(field_def)
        self._type_stack.append(field_type if is_output_type(field_type) else None)

    def enter_directive(self, node: DirectiveNode) -> None:
        """Update this TypeInfo instance for an entered directive node.

        :meta private:
        """
        self._directive = self._schema.get_directive(node.name.value)

    def enter_operation_definition(self, node: OperationDefinitionNode) -> None:
        """Update this TypeInfo instance for an entered operation definition node.

        :meta private:
        """
        root_type = self._schema.get_root_type(node.operation)
        self._type_stack.append(root_type if is_object_type(root_type) else None)

    def enter_fragment_spread(self, node: FragmentSpreadNode) -> None:
        """Update this TypeInfo instance for an entered fragment spread node.

        :meta private:
        """
        self._fragment_signature = self.get_fragment_signature_by_name()(
            node.name.value
        )

    def enter_inline_fragment(self, node: InlineFragmentNode) -> None:
        """Update this TypeInfo instance for an entered (inline) fragment.

        :meta private:
        """
        type_condition_ast = node.type_condition
        output_type = (
            type_from_ast(self._schema, type_condition_ast)
            if type_condition_ast
            else get_named_type(self.get_type())
        )
        self._type_stack.append(output_type if is_output_type(output_type) else None)

    enter_fragment_definition = enter_inline_fragment

    def enter_variable_definition(self, node: VariableDefinitionNode) -> None:
        """Update this TypeInfo instance for an entered variable definition node.

        :meta private:
        """
        input_type = type_from_ast(self._schema, node.type)
        self._input_type_stack.append(input_type if is_input_type(input_type) else None)

    def enter_fragment_argument(self, node: FragmentArgumentNode) -> None:
        """Update this TypeInfo instance for an entered fragment argument node.

        :meta private:
        """
        fragment_signature = self.get_fragment_signature()
        arg_def = (
            fragment_signature.variable_definitions.get(node.name.value)
            if fragment_signature
            else None
        )
        self._fragment_argument = arg_def
        arg_type = type_from_ast(self._schema, arg_def.type) if arg_def else None
        # Fragment arguments have a variable default but no location default;
        # push Undefined so get_default_value() reports "no default" here and the
        # leave handler's default-value pop stays balanced (unlike GraphQL.js,
        # which relies on an empty-stack read returning undefined).
        self._default_value_stack.append(Undefined)
        self._input_type_stack.append(arg_type if is_input_type(arg_type) else None)

    def enter_argument(self, node: ArgumentNode) -> None:
        """Update this TypeInfo instance for an entered argument node.

        :meta private:
        """
        field_or_directive = self.get_directive() or self.get_field_def()
        if field_or_directive:
            arg_def = field_or_directive.args.get(node.name.value)
            arg_type = arg_def.type if arg_def else None
        else:
            arg_def = arg_type = None
        self._argument = arg_def
        self._default_value_stack.append(
            (arg_def.default if arg_def.default is not None else arg_def.default_value)
            if arg_def
            else Undefined
        )
        self._input_type_stack.append(arg_type if is_input_type(arg_type) else None)

    def enter_list_value(self, _node: ListValueNode) -> None:
        """Update this TypeInfo instance for an entered list value node.

        :meta private:
        """
        list_type = get_nullable_type(self.get_input_type())
        item_type = list_type.of_type if is_list_type(list_type) else None
        # List positions never have a default value.
        self._default_value_stack.append(Undefined)
        self._input_type_stack.append(item_type if is_input_type(item_type) else None)

    def enter_object_field(self, node: ObjectFieldNode) -> None:
        """Update this TypeInfo instance for an entered object field node.

        :meta private:
        """
        object_type = get_named_type(self.get_input_type())
        if is_input_object_type(object_type):
            input_field = object_type.fields.get(node.name.value)
            input_field_type = input_field.type if input_field else None
        else:
            input_field = input_field_type = None
        self._default_value_stack.append(
            (
                input_field.default
                if input_field.default is not None
                else input_field.default_value
            )
            if input_field
            else Undefined
        )
        self._input_type_stack.append(
            input_field_type if is_input_type(input_field_type) else None
        )

    def enter_enum_value(self, node: EnumValueNode) -> None:
        """Update this TypeInfo instance for an entered enum value node.

        :meta private:
        """
        enum_type = get_named_type(self.get_input_type())
        if is_enum_type(enum_type):
            enum_value = enum_type.values.get(node.value)
        else:
            enum_value = None
        self._enum_value = enum_value

    def leave_document(self) -> None:
        """Update this TypeInfo instance for a left document node.

        :meta private:
        """
        self._fragment_signatures_by_name = (
            lambda _fragment_name: None  # pragma: no cover
        )

    def leave_selection_set(self) -> None:
        """Update this TypeInfo instance for a left selection set node.

        :meta private:
        """
        del self._parent_type_stack[-1:]

    def leave_field(self) -> None:
        """Update this TypeInfo instance for a left field node.

        :meta private:
        """
        del self._field_def_stack[-1:]
        del self._type_stack[-1:]

    def leave_directive(self) -> None:
        """Update this TypeInfo instance for a left directive node.

        :meta private:
        """
        self._directive = None

    def leave_operation_definition(self) -> None:
        """Update this TypeInfo instance for a left operation or (inline) fragment.

        :meta private:
        """
        del self._type_stack[-1:]

    leave_inline_fragment = leave_operation_definition
    leave_fragment_definition = leave_operation_definition

    def leave_fragment_spread(self) -> None:
        """Update this TypeInfo instance for a left fragment spread node.

        :meta private:
        """
        self._fragment_signature = None

    def leave_variable_definition(self) -> None:
        """Update this TypeInfo instance for a left variable definition node.

        :meta private:
        """
        del self._input_type_stack[-1:]

    def leave_fragment_argument(self) -> None:
        """Update this TypeInfo instance for a left fragment argument node.

        :meta private:
        """
        self._fragment_argument = None
        del self._default_value_stack[-1:]
        del self._input_type_stack[-1:]

    def leave_argument(self) -> None:
        """Update this TypeInfo instance for a left argument node.

        :meta private:
        """
        self._argument = None
        del self._default_value_stack[-1:]
        del self._input_type_stack[-1:]

    def leave_list_value(self) -> None:
        """Update this TypeInfo instance for a left list value or object field node.

        :meta private:
        """
        del self._default_value_stack[-1:]
        del self._input_type_stack[-1:]

    leave_object_field = leave_list_value

    def leave_enum_value(self) -> None:
        """Update this TypeInfo instance for a left enum value node.

        :meta private:
        """
        self._enum_value = None


def get_fragment_signatures(document: DocumentNode) -> dict[str, FragmentSignature]:
    """Collect the fragment signatures of all fragment definitions in a document."""
    fragment_signatures: dict[str, FragmentSignature] = {}
    for definition in document.definitions:
        if isinstance(definition, FragmentDefinitionNode):
            variable_definitions: dict[str, VariableDefinitionNode] = {}
            if definition.variable_definitions:
                for var_def in definition.variable_definitions:
                    variable_definitions[var_def.variable.name.value] = var_def
            fragment_signatures[definition.name.value] = FragmentSignature(
                definition, variable_definitions
            )
    return fragment_signatures


class TypeInfoVisitor(Visitor):
    """A visitor which maintains a provided TypeInfo.

    Creates a new visitor instance which maintains a provided TypeInfo instance along
    with visiting the wrapped visitor.

    :param type_info: TypeInfo instance to update during traversal.
    :param visitor: Visitor to wrap with TypeInfo updates.

    >>> from graphql import (
    ...     TypeInfo, TypeInfoVisitor, Visitor, build_schema, parse, visit)
    >>> schema = build_schema('''
    ...     type Query {
    ...       greeting: String
    ...     }
    ... ''')
    >>> type_info = TypeInfo(schema)
    >>> fields = []
    >>> class FieldVisitor(Visitor):
    ...     def enter_field(self, node, *_args):
    ...         fields.append({
    ...             'name': node.name.value,
    ...             'parent_type': str(type_info.get_parent_type()),
    ...             'type': str(type_info.get_type()),
    ...         })
    >>> _ = visit(parse('{ greeting }'), TypeInfoVisitor(type_info, FieldVisitor()))
    >>> fields
    [{'name': 'greeting', 'parent_type': 'Query', 'type': 'String'}]
    """

    def __init__(self, type_info: TypeInfo, visitor: Visitor) -> None:
        super().__init__()
        self.type_info = type_info
        self.visitor = visitor

    def enter(self, node: Node, *args: Any) -> Any:
        """Update the TypeInfo and call the enter function of the wrapped visitor.

        :meta private:
        """
        self.type_info.enter(node)
        fn = self.visitor.get_enter_leave_for_kind(node.kind).enter
        if not fn:
            return None
        result = fn(node, *args)
        if result is not None:
            self.type_info.leave(node)
            if isinstance(result, Node):
                self.type_info.enter(result)
        return result

    def leave(self, node: Node, *args: Any) -> Any:
        """Call the leave function of the wrapped visitor and update the TypeInfo.

        :meta private:
        """
        fn = self.visitor.get_enter_leave_for_kind(node.kind).leave
        result = fn(node, *args) if fn else None
        self.type_info.leave(node)
        return result
