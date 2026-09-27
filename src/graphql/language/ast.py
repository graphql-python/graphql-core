"""GraphQL Abstract Syntax Tree"""

from __future__ import annotations

import sys
from dataclasses import dataclass, fields
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, TypeAlias, TypeVar

from ..pyutils import camel_to_snake

if sys.version_info < (3, 11):
    if TYPE_CHECKING:
        from typing_extensions import dataclass_transform
    else:
        # typing_extensions is not a runtime dependency, and the decorator is
        # only a hint for static type checkers, so we can do without it here
        def dataclass_transform(**_kwargs: Any) -> Any:
            return lambda cls: cls

else:
    from typing import dataclass_transform

if TYPE_CHECKING:
    from .source import Source
    from .token_kind import TokenKind

__all__ = [
    "QUERY_DOCUMENT_KEYS",
    "ArgumentCoordinateNode",
    "ArgumentNode",
    "BooleanValueNode",
    "ConstArgumentNode",
    "ConstDirectiveNode",
    "ConstListValueNode",
    "ConstObjectFieldNode",
    "ConstObjectValueNode",
    "ConstValueNode",
    "DefinitionNode",
    "DirectiveArgumentCoordinateNode",
    "DirectiveCoordinateNode",
    "DirectiveDefinitionNode",
    "DirectiveExtensionNode",
    "DirectiveNode",
    "DocumentNode",
    "EnumTypeDefinitionNode",
    "EnumTypeExtensionNode",
    "EnumValueDefinitionNode",
    "EnumValueNode",
    "ExecutableDefinitionNode",
    "FieldDefinitionNode",
    "FieldNode",
    "FloatValueNode",
    "FragmentArgumentNode",
    "FragmentDefinitionNode",
    "FragmentSpreadNode",
    "InlineFragmentNode",
    "InputObjectTypeDefinitionNode",
    "InputObjectTypeExtensionNode",
    "InputValueDefinitionNode",
    "IntValueNode",
    "InterfaceTypeDefinitionNode",
    "InterfaceTypeExtensionNode",
    "ListTypeNode",
    "ListValueNode",
    "Location",
    "MemberCoordinateNode",
    "NameNode",
    "NamedTypeNode",
    "Node",
    "NonNullTypeNode",
    "NullValueNode",
    "ObjectFieldNode",
    "ObjectTypeDefinitionNode",
    "ObjectTypeExtensionNode",
    "ObjectValueNode",
    "OperationDefinitionNode",
    "OperationType",
    "OperationTypeDefinitionNode",
    "ScalarTypeDefinitionNode",
    "ScalarTypeExtensionNode",
    "SchemaCoordinateNode",
    "SchemaDefinitionNode",
    "SchemaExtensionNode",
    "SelectionNode",
    "SelectionSetNode",
    "StringValueNode",
    "Token",
    "TypeCoordinateNode",
    "TypeDefinitionNode",
    "TypeExtensionNode",
    "TypeNode",
    "TypeSystemDefinitionNode",
    "TypeSystemExtensionNode",
    "UnionTypeDefinitionNode",
    "UnionTypeExtensionNode",
    "ValueNode",
    "VariableDefinitionNode",
    "VariableNode",
]


class Token:
    """AST Token

    Represents a range of characters represented by a lexical token within a Source.

    :param kind: Token kind produced by lexical analysis.
    :param start: Character offset where this token begins.
    :param end: Character offset where this token ends.
    :param line: One-indexed line number where this token begins.
    :param column: One-indexed column number where this token begins.
    :param value: Interpreted value for non-punctuation tokens.

    >>> from graphql.language import Token, TokenKind
    >>> token = Token(TokenKind.NAME, 2, 7, 1, 3, 'hello')
    >>> token.kind
    <TokenKind.NAME: 'Name'>
    >>> token.value
    'hello'
    >>> token
    <Token Name 'hello' 1:3>
    """

    __slots__ = "column", "end", "kind", "line", "next", "prev", "start", "value"

    kind: TokenKind  # the kind of token
    """The kind of Token."""
    start: int  # the character offset at which this Node begins
    """The character offset at which this Node begins."""
    end: int  # the character offset at which this Node ends
    """The character offset at which this Node ends."""
    line: int  # the 1-indexed line number on which this Token appears
    """The 1-indexed line number on which this Token appears."""
    column: int  # the 1-indexed column number at which this Token begins
    """The 1-indexed column number at which this Token begins."""
    # for non-punctuation tokens, represents the interpreted value of the token:
    value: str | None
    """For non-punctuation tokens, represents the interpreted value of the token.

    Note: is ``None`` for punctuation tokens.
    """
    # Tokens exist as nodes in a double-linked-list amongst all tokens including
    # ignored tokens. <SOF> is always the first node and <EOF> the last.
    prev: Token | None
    """Previous token in the token stream, including ignored tokens.

    Tokens exist as nodes in a double-linked-list amongst all tokens including
    ignored tokens. <SOF> is always the first node and <EOF> the last.
    """
    next: Token | None
    """Next token in the token stream, including ignored tokens."""

    def __init__(
        self,
        kind: TokenKind,
        start: int,
        end: int,
        line: int,
        column: int,
        value: str | None = None,
    ) -> None:
        self.kind = kind
        self.start, self.end = start, end
        self.line, self.column = line, column
        self.value = value
        self.prev = self.next = None

    def __str__(self) -> str:
        return self.desc

    def __repr__(self) -> str:
        """Print a simplified form when appearing in repr() or inspect()."""
        return f"<Token {self.desc} {self.line}:{self.column}>"

    def __inspect__(self) -> str:
        return repr(self)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Token):
            return (
                self.kind == other.kind
                and self.start == other.start
                and self.end == other.end
                and self.line == other.line
                and self.column == other.column
                and self.value == other.value
            )
        if isinstance(other, str):
            return other == self.desc
        return False

    def __hash__(self) -> int:
        return hash(
            (self.kind, self.start, self.end, self.line, self.column, self.value)
        )

    def __copy__(self) -> Token:
        """Create a shallow copy of the token"""
        token = self.__class__(
            self.kind,
            self.start,
            self.end,
            self.line,
            self.column,
            self.value,
        )
        token.prev = self.prev
        return token

    def __deepcopy__(self, memo: dict) -> Token:
        """Allow only shallow copies to avoid recursion."""
        return self.__copy__()

    def __getstate__(self) -> dict[str, Any]:
        """Remove the links when pickling.

        Keeping the links would make pickling a schema too expensive.
        """
        return {
            key: getattr(self, key)
            for key in self.__slots__
            if key not in {"prev", "next"}
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Reset the links when un-pickling."""
        for key, value in state.items():
            setattr(self, key, value)
        self.prev = self.next = None

    @property
    def desc(self) -> str:
        """A helper property to describe a token as a string for debugging"""
        kind, value = self.kind.value, self.value
        return f"{kind} {value!r}" if value else kind


class Location:
    """AST Location

    Contains a range of UTF-8 character offsets and token references that identify the
    region of the source from which the AST derived.

    :param start_token: The start token.
    :param end_token: The end token.
    :param source: Source document used to derive error locations.

    >>> from graphql.language import Location, Source, Token, TokenKind
    >>> source = Source('{ hello }')
    >>> start_token = Token(TokenKind.BRACE_L, 0, 1, 1, 1)
    >>> end_token = Token(TokenKind.BRACE_R, 8, 9, 1, 9)
    >>> location = Location(start_token, end_token, source)
    >>> location.start
    0
    >>> location.end
    9
    >>> location.source.body
    '{ hello }'

    The location of a parsed document:

    >>> from graphql import parse
    >>> parse('{ hello }').loc
    <Location 0:9>
    """

    __slots__ = (
        "end",
        "end_token",
        "source",
        "start",
        "start_token",
    )

    start: int  # character offset at which this Node begins
    """The character offset at which this Node begins."""
    end: int  # character offset at which this Node ends
    """The character offset at which this Node ends."""
    start_token: Token  # Token at which this Node begins
    """The Token at which this Node begins."""
    end_token: Token  # Token at which this Node ends.
    """The Token at which this Node ends."""
    source: Source  # Source document the AST represents
    """The Source document the AST represents."""

    def __init__(self, start_token: Token, end_token: Token, source: Source) -> None:
        self.start = start_token.start
        self.end = end_token.end
        self.start_token = start_token
        self.end_token = end_token
        self.source = source

    def __str__(self) -> str:
        return f"{self.start}:{self.end}"

    def __repr__(self) -> str:
        """Print a simplified form when appearing in repr() or inspect()."""
        return f"<Location {self.start}:{self.end}>"

    def __inspect__(self) -> str:
        return repr(self)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Location):
            return self.start == other.start and self.end == other.end
        if isinstance(other, (list, tuple)) and len(other) == 2:
            return self.start == other[0] and self.end == other[1]
        return False

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __hash__(self) -> int:
        return hash((self.start, self.end))


class OperationType(Enum):
    """The operation types supported by GraphQL executable definitions."""

    QUERY = "query"
    MUTATION = "mutation"
    SUBSCRIPTION = "subscription"


# Default map from node kinds to their node attributes (internal)
QUERY_DOCUMENT_KEYS: dict[str, tuple[str, ...]] = {
    "name": (),
    "document": ("definitions",),
    "operation_definition": (
        "description",
        "name",
        "variable_definitions",
        "directives",
        "selection_set",
    ),
    "variable_definition": (
        "description",
        "variable",
        "type",
        "default_value",
        "directives",
    ),
    "variable": ("name",),
    "selection_set": ("selections",),
    "field": ("alias", "name", "arguments", "directives", "selection_set"),
    "argument": ("name", "value"),
    "fragment_argument": ("name", "value"),
    "fragment_spread": (
        "name",
        # note: Fragment arguments are experimental and may be changed
        # or removed in the future.
        "arguments",
        "directives",
    ),
    "inline_fragment": ("type_condition", "directives", "selection_set"),
    "fragment_definition": (
        "description",
        "name",
        # note: Fragment variables are experimental and may be changed
        # or removed in the future.
        "variable_definitions",
        "type_condition",
        "directives",
        "selection_set",
    ),
    "list_value": ("values",),
    "object_value": ("fields",),
    "object_field": ("name", "value"),
    "directive": ("name", "arguments"),
    "named_type": ("name",),
    "list_type": ("type",),
    "non_null_type": ("type",),
    "schema_definition": ("description", "directives", "operation_types"),
    "operation_type_definition": ("type",),
    "scalar_type_definition": ("description", "name", "directives"),
    "object_type_definition": (
        "description",
        "name",
        "interfaces",
        "directives",
        "fields",
    ),
    "field_definition": ("description", "name", "arguments", "type", "directives"),
    "input_value_definition": (
        "description",
        "name",
        "type",
        "default_value",
        "directives",
    ),
    "interface_type_definition": (
        "description",
        "name",
        "interfaces",
        "directives",
        "fields",
    ),
    "union_type_definition": ("description", "name", "directives", "types"),
    "enum_type_definition": ("description", "name", "directives", "values"),
    "enum_value_definition": ("description", "name", "directives"),
    "input_object_type_definition": ("description", "name", "directives", "fields"),
    "directive_definition": (
        "description",
        "name",
        "arguments",
        "directives",
        "locations",
    ),
    "schema_extension": ("directives", "operation_types"),
    "directive_extension": ("name", "directives"),
    "scalar_type_extension": ("name", "directives"),
    "object_type_extension": ("name", "interfaces", "directives", "fields"),
    "interface_type_extension": ("name", "interfaces", "directives", "fields"),
    "union_type_extension": ("name", "directives", "types"),
    "enum_type_extension": ("name", "directives", "values"),
    "input_object_type_extension": ("name", "directives", "fields"),
    "type_coordinate": ("name",),
    "member_coordinate": ("name", "member_name"),
    "argument_coordinate": ("name", "field_name", "argument_name"),
    "directive_coordinate": ("name",),
    "directive_argument_coordinate": ("name", "argument_name"),
}


# Base AST Node


class _KeysProperty:
    """Descriptor providing .keys at both class and instance level.

    For backwards compatibility only. Prefer using dataclasses.fields() instead.
    """

    def __get__(self, obj: object, cls: type) -> tuple[str, ...]:
        if not hasattr(cls, "__dataclass_fields__"):
            return ()  # During class construction
        return tuple(f.name for f in fields(cls))


T_Instance = TypeVar("T_Instance")


@dataclass_transform(frozen_default=True, kw_only_default=True)
def node_class(cls: type[T_Instance]) -> type[T_Instance]:
    """Decorator to define a GraphQL AST Node class.

    We use default dict-based dataclass instances for faster pickling/unpickling.
    """
    return dataclass(frozen=True, kw_only=True, repr=False)(cls)


@node_class
class Node:
    """Base class for all AST nodes.

    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import NameNode
    >>> node = NameNode(value='hello')
    >>> node.kind
    'name'
    >>> node.keys
    ('loc', 'value')
    """

    kind: ClassVar[str] = "ast"
    """The kind of the node as a snake_case string, identifying the concrete node."""
    keys: ClassVar[tuple[str, ...]] = _KeysProperty()  # type: ignore[assignment]
    """The names of the attributes of this node."""
    loc: Location | None = None
    """The source location for this AST node, if location tracking was enabled."""

    def __repr__(self) -> str:
        """Get a simple representation of the node."""
        rep = self.__class__.__name__
        if isinstance(self, NameNode):
            rep += f"({self.value!r})"
        else:
            name = getattr(self, "name", None)
            if name:
                rep += f"(name={name.value!r})"
        if self.loc:
            rep += f" at {self.loc}"
        return rep

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        name = cls.__name__.removeprefix("Const").removesuffix("Node")
        cls.kind = camel_to_snake(name)

    def to_dict(self, locations: bool = False) -> dict:
        """Convert this node to a nested dictionary.

        :param locations: whether the dictionaries should include the locations
        :returns: a JSON-compatible dictionary representing this AST node

        >>> from graphql import parse_value
        >>> value = parse_value('42')
        >>> value.to_dict()
        {'kind': 'int_value', 'value': '42'}
        >>> value.to_dict(locations=True)
        {'kind': 'int_value', 'value': '42', 'loc': {'start': 0, 'end': 2}}
        """
        from ..utilities import ast_to_dict

        return ast_to_dict(self, locations)


# Name


@node_class
class NameNode(Node):
    """An identifier in a GraphQL document.

    :param value: Parsed value represented by this node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import NameNode, print_ast
    >>> print_ast(NameNode(value='hello'))
    'hello'
    """

    value: str
    """Parsed value represented by this node."""


# Base classes for node categories


@node_class
class DefinitionNode(Node):
    """Base class for all definition nodes.

    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import DefinitionNode, parse
    >>> document = parse('{ hello } type Query { hello: String }')
    >>> [isinstance(node, DefinitionNode) for node in document.definitions]
    [True, True]
    """


@node_class
class ExecutableDefinitionNode(DefinitionNode):
    """Base class for executable definition nodes.

    :param selection_set: Selections made by this operation, field, or fragment.
    :param description: The optional GraphQL description associated with this
        definition.
    :param name: Name node identifying this AST node.
    :param variable_definitions: Variable definitions declared by this operation or
        fragment.
    :param directives: Directives available in this schema or applied to this AST node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import ExecutableDefinitionNode, parse
    >>> document = parse('{ hello } type Query { hello: String }')
    >>> [isinstance(node, ExecutableDefinitionNode) for node in document.definitions]
    [True, False]
    """

    selection_set: SelectionSetNode
    """Selections made by this operation, field, or fragment."""
    description: StringValueNode | None = None
    """The optional GraphQL description associated with this definition."""
    name: NameNode | None = None
    """Name node identifying this AST node."""
    variable_definitions: tuple[VariableDefinitionNode, ...] | None = None
    """Variable definitions declared by this operation or fragment.

    Note: variable definitions on fragment definitions are experimental and may be
    changed or removed in the future.
    """
    directives: tuple[DirectiveNode, ...] | None = None
    """Directives available in this schema or applied to this AST node."""


@node_class
class SelectionNode(Node):
    """Base class for selection nodes.

    :param directives: Directives available in this schema or applied to this AST node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import SelectionNode, parse
    >>> operation = parse('{ hello ...Hi ... on Query { hi } }').definitions[0]
    >>> [isinstance(node, SelectionNode) for node in operation.selection_set.selections]
    [True, True, True]
    """

    directives: tuple[DirectiveNode, ...] | None = None
    """Directives available in this schema or applied to this AST node."""


@node_class
class ValueNode(Node):
    """Base class for value nodes.

    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import ValueNode, parse_value
    >>> isinstance(parse_value('[1, "two", $three]'), ValueNode)
    True
    """


@node_class
class TypeNode(Node):
    """Base class for type nodes.

    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import TypeNode, parse_type
    >>> isinstance(parse_type('[String!]'), TypeNode)
    True
    """


@node_class
class TypeSystemDefinitionNode(DefinitionNode):
    """Base class for type system definition nodes.

    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import TypeSystemDefinitionNode, parse
    >>> document = parse('schema { query: Query } scalar Date directive @a on FIELD')
    >>> [isinstance(node, TypeSystemDefinitionNode) for node in document.definitions]
    [True, True, True]
    """


@node_class
class TypeDefinitionNode(TypeSystemDefinitionNode):
    """Base class for type definition nodes.

    :param name: Name node identifying this AST node.
    :param description: The optional GraphQL description associated with this
        definition.
    :param directives: Directives available in this schema or applied to this AST node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import TypeDefinitionNode, parse
    >>> document = parse('scalar Date directive @a on FIELD')
    >>> [isinstance(node, TypeDefinitionNode) for node in document.definitions]
    [True, False]
    """

    name: NameNode
    """Name node identifying this AST node."""
    description: StringValueNode | None = None
    """The optional GraphQL description associated with this definition."""
    directives: tuple[ConstDirectiveNode, ...] | None = None
    """Directives available in this schema or applied to this AST node."""


@node_class
class TypeExtensionNode(TypeSystemDefinitionNode):
    """Base class for type extension nodes.

    :param name: Name node identifying this AST node.
    :param directives: Directives available in this schema or applied to this AST node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import TypeExtensionNode, parse
    >>> document = parse('extend scalar Date @a extend schema @a')
    >>> [isinstance(node, TypeExtensionNode) for node in document.definitions]
    [True, False]
    """

    name: NameNode
    """Name node identifying this AST node."""
    directives: tuple[ConstDirectiveNode, ...] | None = None
    """Directives available in this schema or applied to this AST node."""


# Type Reference nodes


@node_class
class NamedTypeNode(TypeNode):
    """A named type reference.

    :param name: Name node identifying this AST node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import NameNode, NamedTypeNode, print_ast
    >>> print_ast(NamedTypeNode(name=NameNode(value='String')))
    'String'
    """

    name: NameNode
    """Name node identifying this AST node."""


@node_class
class ListTypeNode(TypeNode):
    """A list type reference.

    :param type: The GraphQL type reference or runtime type for this element.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import ListTypeNode, NameNode, NamedTypeNode, print_ast
    >>> print_ast(ListTypeNode(type=NamedTypeNode(name=NameNode(value='String'))))
    '[String]'
    """

    type: TypeNode
    """The GraphQL type reference or runtime type for this element."""


@node_class
class NonNullTypeNode(TypeNode):
    """A non-null type reference.

    :param type: The GraphQL type reference or runtime type for this element.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import NameNode, NamedTypeNode, NonNullTypeNode, print_ast
    >>> print_ast(NonNullTypeNode(type=NamedTypeNode(name=NameNode(value='String'))))
    'String!'
    """

    type: NamedTypeNode | ListTypeNode
    """The GraphQL type reference or runtime type for this element."""


# Value nodes


@node_class
class VariableNode(ValueNode):
    """A variable reference, such as ``$id``.

    :param name: Name node identifying this AST node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import NameNode, VariableNode, print_ast
    >>> print_ast(VariableNode(name=NameNode(value='id')))
    '$id'
    """

    name: NameNode
    """Name node identifying this AST node."""


@node_class
class IntValueNode(ValueNode):
    """An integer value literal.

    :param value: Parsed value represented by this node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import IntValueNode, print_ast
    >>> print_ast(IntValueNode(value='42'))
    '42'
    """

    value: str
    """Parsed value represented by this node."""


@node_class
class FloatValueNode(ValueNode):
    """A floating-point value literal.

    :param value: Parsed value represented by this node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import FloatValueNode, print_ast
    >>> print_ast(FloatValueNode(value='3.14'))
    '3.14'
    """

    value: str
    """Parsed value represented by this node."""


@node_class
class StringValueNode(ValueNode):
    """A string value literal.

    :param value: Parsed value represented by this node.
    :param block: Whether this string was parsed from block string syntax.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import StringValueNode, print_ast
    >>> print_ast(StringValueNode(value='hello'))
    '"hello"'
    """

    value: str
    """Parsed value represented by this node."""
    block: bool | None = None
    """Whether this string was parsed from block string syntax."""


@node_class
class BooleanValueNode(ValueNode):
    """A boolean value literal.

    :param value: Parsed value represented by this node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import BooleanValueNode, print_ast
    >>> print_ast(BooleanValueNode(value=True))
    'true'
    """

    value: bool
    """Parsed value represented by this node."""


@node_class
class NullValueNode(ValueNode):
    """A null value literal.

    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import NullValueNode, print_ast
    >>> print_ast(NullValueNode())
    'null'
    """


@node_class
class EnumValueNode(ValueNode):
    """An enum value literal.

    :param value: Parsed value represented by this node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import EnumValueNode, print_ast
    >>> print_ast(EnumValueNode(value='RED'))
    'RED'
    """

    value: str
    """Parsed value represented by this node."""


@node_class
class ListValueNode(ValueNode):
    """A list value literal.

    :param values: Values contained in this enum, list, or input-object definition.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     IntValueNode, ListValueNode, NameNode, VariableNode, print_ast,
    ... )
    >>> values = (IntValueNode(value='1'), VariableNode(name=NameNode(value='two')))
    >>> print_ast(ListValueNode(values=values))
    '[1, $two]'
    """

    values: tuple[ValueNode, ...] = ()
    """Values contained in this enum, list, or input-object definition."""


@node_class
class ConstListValueNode(ListValueNode):
    """A list value literal whose elements are all constant values.

    :param values: Values contained in this enum, list, or input-object definition.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import ConstListValueNode, IntValueNode, print_ast
    >>> print_ast(ConstListValueNode(values=(IntValueNode(value='1'),)))
    '[1]'
    """

    values: tuple[ConstValueNode, ...] = ()
    """Values contained in this enum, list, or input-object definition."""


@node_class
class ObjectFieldNode(Node):
    """A field inside an input object value literal.

    :param name: Name node identifying this AST node.
    :param value: Parsed value represented by this node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import NameNode, ObjectFieldNode, VariableNode, print_ast
    >>> value = VariableNode(name=NameNode(value='a'))
    >>> print_ast(ObjectFieldNode(name=NameNode(value='a'), value=value))
    'a: $a'
    """

    name: NameNode
    """Name node identifying this AST node."""
    value: ValueNode
    """Parsed value represented by this node."""


@node_class
class ConstObjectFieldNode(ObjectFieldNode):
    """A field inside a constant input object value literal.

    :param name: Name node identifying this AST node.
    :param value: Parsed value represented by this node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     ConstObjectFieldNode, IntValueNode, NameNode, print_ast,
    ... )
    >>> value = IntValueNode(value='1')
    >>> print_ast(ConstObjectFieldNode(name=NameNode(value='a'), value=value))
    'a: 1'
    """

    value: ConstValueNode
    """Parsed value represented by this node."""


@node_class
class ObjectValueNode(ValueNode):
    """An input object value literal.

    :param fields: Fields declared by this object, interface, input object, or literal.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     NameNode, ObjectFieldNode, ObjectValueNode, VariableNode, print_ast
    ... )
    >>> value = VariableNode(name=NameNode(value='a'))
    >>> field = ObjectFieldNode(name=NameNode(value='a'), value=value)
    >>> print_ast(ObjectValueNode(fields=(field,)))
    '{ a: $a }'
    """

    fields: tuple[ObjectFieldNode, ...] = ()
    """Fields declared by this object, interface, input object, or literal."""


@node_class
class ConstObjectValueNode(ObjectValueNode):
    """An input object value literal whose fields are all constant values.

    :param fields: Fields declared by this object, interface, input object, or literal.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     ConstObjectFieldNode, ConstObjectValueNode, IntValueNode, NameNode,
    ...     print_ast,
    ... )
    >>> value = IntValueNode(value='1')
    >>> field = ConstObjectFieldNode(name=NameNode(value='a'), value=value)
    >>> print_ast(ConstObjectValueNode(fields=(field,)))
    '{ a: 1 }'
    """

    fields: tuple[ConstObjectFieldNode, ...] = ()
    """Fields declared by this object, interface, input object, or literal."""


ConstValueNode: TypeAlias = (
    IntValueNode
    | FloatValueNode
    | StringValueNode
    | BooleanValueNode
    | NullValueNode
    | EnumValueNode
    | ConstListValueNode
    | ConstObjectValueNode
)


# Directive nodes


@node_class
class DirectiveNode(Node):
    """A directive applied to an executable or type-system location.

    :param name: Name node identifying this AST node.
    :param arguments: Arguments supplied to this field, directive, or coordinate.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     ArgumentNode, DirectiveNode, NameNode, VariableNode, print_ast,
    ... )
    >>> value = VariableNode(name=NameNode(value='skip'))
    >>> argument = ArgumentNode(name=NameNode(value='if'), value=value)
    >>> print_ast(DirectiveNode(name=NameNode(value='skip'), arguments=(argument,)))
    '@skip(if: $skip)'
    """

    name: NameNode
    """Name node identifying this AST node."""
    arguments: tuple[ArgumentNode, ...] | None = None
    """Arguments supplied to this field, directive, or coordinate."""


@node_class
class ConstDirectiveNode(DirectiveNode):
    """A directive whose arguments are all constant values.

    :param name: Name node identifying this AST node.
    :param arguments: Arguments supplied to this field, directive, or coordinate.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     ConstArgumentNode, ConstDirectiveNode, NameNode, StringValueNode, print_ast
    ... )
    >>> value = StringValueNode(value='Use other')
    >>> argument = ConstArgumentNode(name=NameNode(value='reason'), value=value)
    >>> name = NameNode(value='deprecated')
    >>> print_ast(ConstDirectiveNode(name=name, arguments=(argument,)))
    '@deprecated(reason: "Use other")'
    """

    arguments: tuple[ConstArgumentNode, ...] | None = None
    """Arguments supplied to this field, directive, or coordinate."""


# Selection nodes


@node_class
class FieldNode(SelectionNode):
    """A field selected in an executable GraphQL document.

    :param alias: The response-key alias for this field, if one was supplied.
    :param name: Name node identifying this AST node.
    :param arguments: Arguments supplied to this field, directive, or coordinate.
    :param directives: Directives available in this schema or applied to this AST node.
    :param selection_set: Selections made by this operation, field, or fragment.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import FieldNode, NameNode, print_ast
    >>> node = FieldNode(name=NameNode(value='hello'), alias=NameNode(value='greeting'))
    >>> print_ast(node)
    'greeting: hello'
    """

    name: NameNode
    """Name node identifying this AST node."""
    alias: NameNode | None = None
    """The response-key alias for this field, if one was supplied."""
    arguments: tuple[ArgumentNode, ...] | None = None
    """Arguments supplied to this field, directive, or coordinate."""
    directives: tuple[DirectiveNode, ...] | None = None
    """Directives available in this schema or applied to this AST node."""
    selection_set: SelectionSetNode | None = None
    """Selections made by this operation, field, or fragment."""


@node_class
class FragmentSpreadNode(SelectionNode):
    """A named fragment spread, such as ``...userFields``.

    :param name: Name node identifying this AST node.
    :param arguments: Argument values supplied to the referenced fragment.
    :param directives: Directives available in this schema or applied to this AST node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import FragmentSpreadNode, NameNode, print_ast
    >>> print_ast(FragmentSpreadNode(name=NameNode(value='userFields')))
    '...userFields'
    """

    name: NameNode
    """Name node identifying this AST node."""
    arguments: tuple[FragmentArgumentNode, ...] | None = None
    """Argument values supplied to the referenced fragment."""
    directives: tuple[DirectiveNode, ...] | None = None
    """Directives available in this schema or applied to this AST node."""


@node_class
class InlineFragmentNode(SelectionNode):
    """An inline fragment spread with an optional type condition.

    :param type_condition: The type condition that limits where this fragment applies.
    :param directives: Directives available in this schema or applied to this AST node.
    :param selection_set: Selections made by this operation, field, or fragment.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     FieldNode, InlineFragmentNode, NamedTypeNode, NameNode, SelectionSetNode,
    ...     print_ast,
    ... )
    >>> field = FieldNode(name=NameNode(value='a'))
    >>> selection_set = SelectionSetNode(selections=(field,))
    >>> type_condition = NamedTypeNode(name=NameNode(value='User'))
    >>> node = InlineFragmentNode(
    ...     type_condition=type_condition, selection_set=selection_set
    ... )
    >>> print_ast(node).splitlines()
    ['... on User {', '  a', '}']
    """

    selection_set: SelectionSetNode
    """Selections made by this operation, field, or fragment."""
    type_condition: NamedTypeNode | None = None
    """The type condition that limits where this fragment applies."""
    directives: tuple[DirectiveNode, ...] | None = None
    """Directives available in this schema or applied to this AST node."""


# Argument nodes


@node_class
class ArgumentNode(Node):
    """An argument supplied to a field or directive.

    :param name: Name node identifying this AST node.
    :param value: Parsed value represented by this node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import ArgumentNode, NameNode, VariableNode, print_ast
    >>> value = VariableNode(name=NameNode(value='id'))
    >>> print_ast(ArgumentNode(name=NameNode(value='id'), value=value))
    'id: $id'
    """

    name: NameNode
    """Name node identifying this AST node."""
    value: ValueNode
    """Parsed value represented by this node."""


@node_class
class ConstArgumentNode(ArgumentNode):
    """An argument node whose value is guaranteed to be constant.

    :param name: Name node identifying this AST node.
    :param value: Parsed value represented by this node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     ConstArgumentNode, IntValueNode, NameNode, print_ast,
    ... )
    >>> value = IntValueNode(value='4')
    >>> print_ast(ConstArgumentNode(name=NameNode(value='id'), value=value))
    'id: 4'
    """

    value: ConstValueNode
    """Parsed value represented by this node."""


@node_class
class FragmentArgumentNode(Node):
    """An argument supplied to a fragment spread (experimental).

    :param name: Name of the fragment variable this argument is supplied for.
    :param value: Parsed value represented by this node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     BooleanValueNode, FragmentArgumentNode, NameNode, print_ast,
    ... )
    >>> value = BooleanValueNode(value=True)
    >>> print_ast(FragmentArgumentNode(name=NameNode(value='var'), value=value))
    'var: true'
    """

    name: NameNode
    """Name of the fragment variable this argument is supplied for."""
    value: ValueNode
    """Parsed value represented by this node."""


# Selection Set


@node_class
class SelectionSetNode(Node):
    """A set of fields and fragments selected from an object, interface, or union.

    :param selections: Fields and fragments contained in this selection set.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import FieldNode, NameNode, SelectionSetNode, print_ast
    >>> field = FieldNode(name=NameNode(value='hello'))
    >>> print(print_ast(SelectionSetNode(selections=(field,))))
    {
      hello
    }
    """

    selections: tuple[SelectionNode, ...] = ()
    """Fields and fragments contained in this selection set."""


# Variable Definition


@node_class
class VariableDefinitionNode(Node):
    """A variable declaration in an operation or experimental fragment definition.

    :param description: The optional GraphQL description associated with this
        definition.
    :param variable: The variable being defined or referenced.
    :param type: The GraphQL type reference or runtime type for this element.
    :param default_value: Default value used when no explicit value is supplied.
    :param directives: Directives available in this schema or applied to this AST node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     IntValueNode, NamedTypeNode, NameNode, VariableDefinitionNode, VariableNode,
    ...     print_ast,
    ... )
    >>> node = VariableDefinitionNode(
    ...     variable=VariableNode(name=NameNode(value='id')),
    ...     type=NamedTypeNode(name=NameNode(value='ID')),
    ...     default_value=IntValueNode(value='4'),
    ... )
    >>> print_ast(node)
    '$id: ID = 4'
    """

    description: StringValueNode | None = None
    """The optional GraphQL description associated with this definition."""
    variable: VariableNode
    """The variable being defined or referenced."""
    type: TypeNode
    """The GraphQL type reference or runtime type for this element."""
    default_value: ConstValueNode | None = None
    """Default value used when no explicit value is supplied."""
    directives: tuple[ConstDirectiveNode, ...] | None = None
    """Directives available in this schema or applied to this AST node."""


# Executable Definition nodes


@node_class
class OperationDefinitionNode(ExecutableDefinitionNode):
    """A query, mutation, or subscription operation definition.

    :param operation: The operation selected for execution.
    :param description: The optional GraphQL description associated with this
        definition.
    :param name: Name node identifying this AST node.
    :param variable_definitions: Variable definitions declared by this operation or
        fragment.
    :param directives: Directives available in this schema or applied to this AST node.
    :param selection_set: Selections made by this operation, field, or fragment.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     FieldNode, NameNode, OperationDefinitionNode, OperationType,
    ...     SelectionSetNode, print_ast,
    ... )
    >>> field = FieldNode(name=NameNode(value='hello'))
    >>> node = OperationDefinitionNode(
    ...     operation=OperationType.QUERY,
    ...     name=NameNode(value='Hello'),
    ...     selection_set=SelectionSetNode(selections=(field,)),
    ... )
    >>> print(print_ast(node))
    query Hello {
      hello
    }
    """

    operation: OperationType
    """The operation selected for execution."""


@node_class
class FragmentDefinitionNode(ExecutableDefinitionNode):
    """A reusable fragment definition declared in an executable document.

    :param description: The optional GraphQL description associated with this
        definition.
    :param name: Name node identifying this AST node.
    :param variable_definitions: Variable definitions declared by this operation or
        fragment.
    :param type_condition: The type condition that limits where this fragment applies.
    :param directives: Directives available in this schema or applied to this AST node.
    :param selection_set: Selections made by this operation, field, or fragment.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     FieldNode, FragmentDefinitionNode, NamedTypeNode, NameNode,
    ...     SelectionSetNode, print_ast,
    ... )
    >>> field = FieldNode(name=NameNode(value='name'))
    >>> node = FragmentDefinitionNode(
    ...     name=NameNode(value='userFields'),
    ...     type_condition=NamedTypeNode(name=NameNode(value='User')),
    ...     selection_set=SelectionSetNode(selections=(field,)),
    ... )
    >>> print(print_ast(node))
    fragment userFields on User {
      name
    }
    """

    name: NameNode  # Required (overrides optional in parent)
    """Name node identifying this AST node."""
    type_condition: NamedTypeNode
    """The type condition that limits where this fragment applies."""


# Document


@node_class
class DocumentNode(Node):
    """The root AST node for a parsed GraphQL document.

    :param definitions: Top-level executable and type-system definitions in this
        document.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import DocumentNode, parse, print_ast
    >>> document = parse('{ hello }')
    >>> document.token_count
    3
    >>> print(print_ast(DocumentNode(definitions=document.definitions)))
    {
      hello
    }
    """

    definitions: tuple[DefinitionNode, ...] = ()
    """Top-level executable and type-system definitions in this document."""

    # The number of tokens in the parsed document. Set by the parser per instance
    # (declared as a ClassVar so it is not treated as a traversable child key, the
    # equivalent of the non-enumerable ``tokenCount`` property in graphql-js).
    token_count: ClassVar[int] = 0
    """The number of lexical tokens parsed for this document."""


# Type System Definition nodes


@node_class
class SchemaDefinitionNode(TypeSystemDefinitionNode):
    """A schema definition in a type-system document.

    :param description: The optional GraphQL description associated with this
        definition.
    :param directives: Directives available in this schema or applied to this AST node.
    :param operation_types: Root operation types declared by this schema definition or
        extension.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     NamedTypeNode, NameNode, OperationType, OperationTypeDefinitionNode,
    ...     SchemaDefinitionNode, print_ast,
    ... )
    >>> operation_type = OperationTypeDefinitionNode(
    ...     operation=OperationType.QUERY,
    ...     type=NamedTypeNode(name=NameNode(value='Root')),
    ... )
    >>> print(print_ast(SchemaDefinitionNode(operation_types=(operation_type,))))
    schema {
      query: Root
    }
    """

    description: StringValueNode | None = None
    """The optional GraphQL description associated with this definition."""
    directives: tuple[ConstDirectiveNode, ...] | None = None
    """Directives available in this schema or applied to this AST node."""
    operation_types: tuple[OperationTypeDefinitionNode, ...] = ()
    """Root operation types declared by this schema definition or extension."""


@node_class
class OperationTypeDefinitionNode(Node):
    """A root operation type declaration inside a schema definition or extension.

    :param operation: The operation selected for execution.
    :param type: The GraphQL type reference or runtime type for this element.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     NamedTypeNode, NameNode, OperationType, OperationTypeDefinitionNode,
    ...     print_ast,
    ... )
    >>> node = OperationTypeDefinitionNode(
    ...     operation=OperationType.QUERY,
    ...     type=NamedTypeNode(name=NameNode(value='Root')),
    ... )
    >>> print_ast(node)
    'query: Root'
    """

    operation: OperationType
    """The operation selected for execution."""
    type: NamedTypeNode
    """The GraphQL type reference or runtime type for this element."""


# Type Definition nodes


@node_class
class ScalarTypeDefinitionNode(TypeDefinitionNode):
    """A scalar type definition in a type-system document.

    :param description: The optional GraphQL description associated with this
        definition.
    :param name: Name node identifying this AST node.
    :param directives: Directives available in this schema or applied to this AST node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     NameNode, ScalarTypeDefinitionNode, StringValueNode, print_ast,
    ... )
    >>> node = ScalarTypeDefinitionNode(
    ...     name=NameNode(value='Date'), description=StringValueNode(value='A date')
    ... )
    >>> print(print_ast(node))
    "A date"
    scalar Date
    """


@node_class
class ObjectTypeDefinitionNode(TypeDefinitionNode):
    """An object type definition in a type-system document.

    :param description: The optional GraphQL description associated with this
        definition.
    :param name: Name node identifying this AST node.
    :param interfaces: Interfaces implemented by this object or interface type.
    :param directives: Directives available in this schema or applied to this AST node.
    :param fields: Fields declared by this object, interface, input object, or literal.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     FieldDefinitionNode, NamedTypeNode, NameNode, ObjectTypeDefinitionNode,
    ...     print_ast,
    ... )
    >>> field = FieldDefinitionNode(
    ...     name=NameNode(value='hello'),
    ...     type=NamedTypeNode(name=NameNode(value='String')),
    ... )
    >>> node = ObjectTypeDefinitionNode(name=NameNode(value='Query'), fields=(field,))
    >>> print(print_ast(node))
    type Query {
      hello: String
    }
    """

    interfaces: tuple[NamedTypeNode, ...] | None = None
    """Interfaces implemented by this object or interface type."""
    fields: tuple[FieldDefinitionNode, ...] | None = None
    """Fields declared by this object, interface, input object, or literal."""


@node_class
class FieldDefinitionNode(DefinitionNode):
    """A field definition declared by an object or interface type.

    :param description: The optional GraphQL description associated with this
        definition.
    :param name: Name node identifying this AST node.
    :param arguments: Arguments supplied to this field, directive, or coordinate.
    :param type: The GraphQL type reference or runtime type for this element.
    :param directives: Directives available in this schema or applied to this AST node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     FieldDefinitionNode, InputValueDefinitionNode, NamedTypeNode, NameNode,
    ...     print_ast,
    ... )
    >>> argument = InputValueDefinitionNode(
    ...     name=NameNode(value='id'), type=NamedTypeNode(name=NameNode(value='ID'))
    ... )
    >>> node = FieldDefinitionNode(
    ...     name=NameNode(value='user'),
    ...     arguments=(argument,),
    ...     type=NamedTypeNode(name=NameNode(value='User')),
    ... )
    >>> print_ast(node)
    'user(id: ID): User'
    """

    name: NameNode
    """Name node identifying this AST node."""
    type: TypeNode
    """The GraphQL type reference or runtime type for this element."""
    description: StringValueNode | None = None
    """The optional GraphQL description associated with this definition."""
    arguments: tuple[InputValueDefinitionNode, ...] | None = None
    """Arguments supplied to this field, directive, or coordinate."""
    directives: tuple[ConstDirectiveNode, ...] | None = None
    """Directives available in this schema or applied to this AST node."""


@node_class
class InputValueDefinitionNode(DefinitionNode):
    """An argument or input-field definition.

    :param description: The optional GraphQL description associated with this
        definition.
    :param name: Name node identifying this AST node.
    :param type: The GraphQL type reference or runtime type for this element.
    :param default_value: Default value used when no explicit value is supplied.
    :param directives: Directives available in this schema or applied to this AST node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     InputValueDefinitionNode, IntValueNode, NamedTypeNode, NameNode, print_ast
    ... )
    >>> node = InputValueDefinitionNode(
    ...     name=NameNode(value='first'),
    ...     type=NamedTypeNode(name=NameNode(value='Int')),
    ...     default_value=IntValueNode(value='10'),
    ... )
    >>> print_ast(node)
    'first: Int = 10'
    """

    name: NameNode
    """Name node identifying this AST node."""
    type: TypeNode
    """The GraphQL type reference or runtime type for this element."""
    description: StringValueNode | None = None
    """The optional GraphQL description associated with this definition."""
    default_value: ConstValueNode | None = None
    """Default value used when no explicit value is supplied."""
    directives: tuple[ConstDirectiveNode, ...] | None = None
    """Directives available in this schema or applied to this AST node."""


@node_class
class InterfaceTypeDefinitionNode(TypeDefinitionNode):
    """An interface type definition in a type-system document.

    :param description: The optional GraphQL description associated with this
        definition.
    :param name: Name node identifying this AST node.
    :param interfaces: Interfaces implemented by this object or interface type.
    :param directives: Directives available in this schema or applied to this AST node.
    :param fields: Fields declared by this object, interface, input object, or literal.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     FieldDefinitionNode, InterfaceTypeDefinitionNode, NamedTypeNode, NameNode,
    ...     NonNullTypeNode, print_ast,
    ... )
    >>> field = FieldDefinitionNode(
    ...     name=NameNode(value='id'),
    ...     type=NonNullTypeNode(type=NamedTypeNode(name=NameNode(value='ID'))),
    ... )
    >>> node = InterfaceTypeDefinitionNode(name=NameNode(value='Node'), fields=(field,))
    >>> print(print_ast(node))
    interface Node {
      id: ID!
    }
    """

    interfaces: tuple[NamedTypeNode, ...] | None = None
    """Interfaces implemented by this object or interface type."""
    fields: tuple[FieldDefinitionNode, ...] | None = None
    """Fields declared by this object, interface, input object, or literal."""


@node_class
class UnionTypeDefinitionNode(TypeDefinitionNode):
    """A union type definition in a type-system document.

    :param description: The optional GraphQL description associated with this
        definition.
    :param name: Name node identifying this AST node.
    :param directives: Directives available in this schema or applied to this AST node.
    :param types: Object types that belong to this union type.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     NamedTypeNode, NameNode, UnionTypeDefinitionNode, print_ast,
    ... )
    >>> types = tuple(NamedTypeNode(name=NameNode(value=name)) for name in ('A', 'B'))
    >>> print_ast(UnionTypeDefinitionNode(name=NameNode(value='AOrB'), types=types))
    'union AOrB = A | B'
    """

    types: tuple[NamedTypeNode, ...] | None = None
    """Object types that belong to this union type."""


@node_class
class EnumTypeDefinitionNode(TypeDefinitionNode):
    """An enum type definition in a type-system document.

    :param description: The optional GraphQL description associated with this
        definition.
    :param name: Name node identifying this AST node.
    :param directives: Directives available in this schema or applied to this AST node.
    :param values: Values contained in this enum, list, or input-object definition.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     EnumTypeDefinitionNode, EnumValueDefinitionNode, NameNode, print_ast
    ... )
    >>> values = tuple(
    ...     EnumValueDefinitionNode(name=NameNode(value=name))
    ...     for name in ('RED', 'BLUE')
    ... )
    >>> node = EnumTypeDefinitionNode(name=NameNode(value='Color'), values=values)
    >>> print(print_ast(node))
    enum Color {
      RED
      BLUE
    }
    """

    values: tuple[EnumValueDefinitionNode, ...] | None = None
    """Values contained in this enum, list, or input-object definition."""


@node_class
class EnumValueDefinitionNode(DefinitionNode):
    """An enum value definition.

    :param description: The optional GraphQL description associated with this
        definition.
    :param name: Name node identifying this AST node.
    :param directives: Directives available in this schema or applied to this AST node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     ConstDirectiveNode, EnumValueDefinitionNode, NameNode, print_ast
    ... )
    >>> directive = ConstDirectiveNode(name=NameNode(value='deprecated'))
    >>> node = EnumValueDefinitionNode(
    ...     name=NameNode(value='RED'), directives=(directive,)
    ... )
    >>> print_ast(node)
    'RED @deprecated'
    """

    name: NameNode
    """Name node identifying this AST node."""
    description: StringValueNode | None = None
    """The optional GraphQL description associated with this definition."""
    directives: tuple[ConstDirectiveNode, ...] | None = None
    """Directives available in this schema or applied to this AST node."""


@node_class
class InputObjectTypeDefinitionNode(TypeDefinitionNode):
    """An input object type definition in a type-system document.

    :param description: The optional GraphQL description associated with this
        definition.
    :param name: Name node identifying this AST node.
    :param directives: Directives available in this schema or applied to this AST node.
    :param fields: Fields declared by this object, interface, input object, or literal.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     InputObjectTypeDefinitionNode, InputValueDefinitionNode, NamedTypeNode,
    ...     NameNode, print_ast,
    ... )
    >>> field = InputValueDefinitionNode(
    ...     name=NameNode(value='name'),
    ...     type=NamedTypeNode(name=NameNode(value='String')),
    ... )
    >>> node = InputObjectTypeDefinitionNode(
    ...     name=NameNode(value='UserInput'), fields=(field,)
    ... )
    >>> print(print_ast(node))
    input UserInput {
      name: String
    }
    """

    fields: tuple[InputValueDefinitionNode, ...] | None = None
    """Fields declared by this object, interface, input object, or literal."""


# Directive Definition


@node_class
class DirectiveDefinitionNode(TypeSystemDefinitionNode):
    """A directive definition in a type-system document.

    :param description: The optional GraphQL description associated with this
        definition.
    :param name: Name node identifying this AST node.
    :param arguments: Arguments supplied to this field, directive, or coordinate.
    :param directives: Directives available in this schema or applied to this AST node.
    :param locations: Locations where this directive may be applied.
    :param repeatable: Whether this directive may appear more than once at the same
        location.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import DirectiveDefinitionNode, NameNode, print_ast
    >>> node = DirectiveDefinitionNode(
    ...     name=NameNode(value='tag'),
    ...     locations=(NameNode(value='FIELD'), NameNode(value='OBJECT')),
    ...     repeatable=True,
    ... )
    >>> print_ast(node)
    'directive @tag repeatable on FIELD | OBJECT'
    """

    name: NameNode
    """Name node identifying this AST node."""
    locations: tuple[NameNode, ...]
    """Locations where this directive may be applied."""
    description: StringValueNode | None = None
    """The optional GraphQL description associated with this definition."""
    arguments: tuple[InputValueDefinitionNode, ...] | None = None
    """Arguments supplied to this field, directive, or coordinate."""
    directives: tuple[ConstDirectiveNode, ...] | None = None
    """Directives available in this schema or applied to this AST node."""
    repeatable: bool = False
    """Whether this directive may appear more than once at the same location."""


# Type System Extension nodes


@node_class
class SchemaExtensionNode(Node):
    """A schema extension in a type-system document.

    :param directives: Directives available in this schema or applied to this AST node.
    :param operation_types: Root operation types declared by this schema definition or
        extension.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     ConstDirectiveNode, NameNode, SchemaExtensionNode, print_ast,
    ... )
    >>> directive = ConstDirectiveNode(name=NameNode(value='link'))
    >>> print_ast(SchemaExtensionNode(directives=(directive,)))
    'extend schema @link'
    """

    directives: tuple[ConstDirectiveNode, ...] | None = None
    """Directives available in this schema or applied to this AST node."""
    operation_types: tuple[OperationTypeDefinitionNode, ...] | None = None
    """Root operation types declared by this schema definition or extension."""


@node_class
class DirectiveExtensionNode(Node):
    """A directive extension.

    :param name: Name node identifying this AST node.
    :param directives: Directives available in this schema or applied to this AST node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     ConstDirectiveNode, DirectiveExtensionNode, NameNode, print_ast,
    ... )
    >>> directive = ConstDirectiveNode(name=NameNode(value='deprecated'))
    >>> node = DirectiveExtensionNode(
    ...     name=NameNode(value='tag'), directives=(directive,)
    ... )
    >>> print_ast(node)
    'extend directive @tag @deprecated'
    """

    name: NameNode
    """Name node identifying this AST node."""
    directives: tuple[ConstDirectiveNode, ...] | None = None
    """Directives available in this schema or applied to this AST node."""


TypeSystemExtensionNode: TypeAlias = (
    SchemaExtensionNode | TypeExtensionNode | DirectiveExtensionNode
)


# Type Extension nodes


@node_class
class ScalarTypeExtensionNode(TypeExtensionNode):
    """A scalar type extension.

    :param name: Name node identifying this AST node.
    :param directives: Directives available in this schema or applied to this AST node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     ConstDirectiveNode, NameNode, ScalarTypeExtensionNode, print_ast,
    ... )
    >>> directive = ConstDirectiveNode(name=NameNode(value='deprecated'))
    >>> node = ScalarTypeExtensionNode(
    ...     name=NameNode(value='Date'), directives=(directive,)
    ... )
    >>> print_ast(node)
    'extend scalar Date @deprecated'
    """


@node_class
class ObjectTypeExtensionNode(TypeExtensionNode):
    """An object type extension.

    :param name: Name node identifying this AST node.
    :param interfaces: Interfaces implemented by this object or interface type.
    :param directives: Directives available in this schema or applied to this AST node.
    :param fields: Fields declared by this object, interface, input object, or literal.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     NamedTypeNode, NameNode, ObjectTypeExtensionNode, print_ast,
    ... )
    >>> interface = NamedTypeNode(name=NameNode(value='Node'))
    >>> node = ObjectTypeExtensionNode(
    ...     name=NameNode(value='User'), interfaces=(interface,)
    ... )
    >>> print_ast(node)
    'extend type User implements Node'
    """

    interfaces: tuple[NamedTypeNode, ...] | None = None
    """Interfaces implemented by this object or interface type."""
    fields: tuple[FieldDefinitionNode, ...] | None = None
    """Fields declared by this object, interface, input object, or literal."""


@node_class
class InterfaceTypeExtensionNode(TypeExtensionNode):
    """An interface type extension.

    :param name: Name node identifying this AST node.
    :param interfaces: Interfaces implemented by this object or interface type.
    :param directives: Directives available in this schema or applied to this AST node.
    :param fields: Fields declared by this object, interface, input object, or literal.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     InterfaceTypeExtensionNode, NamedTypeNode, NameNode, print_ast,
    ... )
    >>> interface = NamedTypeNode(name=NameNode(value='Node'))
    >>> node = InterfaceTypeExtensionNode(
    ...     name=NameNode(value='Entity'), interfaces=(interface,)
    ... )
    >>> print_ast(node)
    'extend interface Entity implements Node'
    """

    interfaces: tuple[NamedTypeNode, ...] | None = None
    """Interfaces implemented by this object or interface type."""
    fields: tuple[FieldDefinitionNode, ...] | None = None
    """Fields declared by this object, interface, input object, or literal."""


@node_class
class UnionTypeExtensionNode(TypeExtensionNode):
    """A union type extension.

    :param name: Name node identifying this AST node.
    :param directives: Directives available in this schema or applied to this AST node.
    :param types: Object types that belong to this union type.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     NamedTypeNode, NameNode, UnionTypeExtensionNode, print_ast,
    ... )
    >>> types = (NamedTypeNode(name=NameNode(value='C')),)
    >>> print_ast(UnionTypeExtensionNode(name=NameNode(value='AOrB'), types=types))
    'extend union AOrB = C'
    """

    types: tuple[NamedTypeNode, ...] | None = None
    """Object types that belong to this union type."""


@node_class
class EnumTypeExtensionNode(TypeExtensionNode):
    """An enum type extension.

    :param name: Name node identifying this AST node.
    :param directives: Directives available in this schema or applied to this AST node.
    :param values: Values contained in this enum, list, or input-object definition.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     EnumTypeExtensionNode, EnumValueDefinitionNode, NameNode, print_ast
    ... )
    >>> values = (EnumValueDefinitionNode(name=NameNode(value='GREEN')),)
    >>> node = EnumTypeExtensionNode(name=NameNode(value='Color'), values=values)
    >>> print(print_ast(node))
    extend enum Color {
      GREEN
    }
    """

    values: tuple[EnumValueDefinitionNode, ...] | None = None
    """Values contained in this enum, list, or input-object definition."""


@node_class
class InputObjectTypeExtensionNode(TypeExtensionNode):
    """An input object type extension.

    :param name: Name node identifying this AST node.
    :param directives: Directives available in this schema or applied to this AST node.
    :param fields: Fields declared by this object, interface, input object, or literal.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     InputObjectTypeExtensionNode, InputValueDefinitionNode, NamedTypeNode,
    ...     NameNode, print_ast,
    ... )
    >>> field = InputValueDefinitionNode(
    ...     name=NameNode(value='age'), type=NamedTypeNode(name=NameNode(value='Int'))
    ... )
    >>> node = InputObjectTypeExtensionNode(
    ...     name=NameNode(value='UserInput'), fields=(field,)
    ... )
    >>> print(print_ast(node))
    extend input UserInput {
      age: Int
    }
    """

    fields: tuple[InputValueDefinitionNode, ...] | None = None
    """Fields declared by this object, interface, input object, or literal."""


# Schema Coordinates


@node_class
class TypeCoordinateNode(Node):
    """A schema coordinate that refers to a named type.

    :param name: Name node identifying this AST node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import NameNode, TypeCoordinateNode, print_ast
    >>> print_ast(TypeCoordinateNode(name=NameNode(value='User')))
    'User'
    """

    name: NameNode
    """Name node identifying this AST node."""


@node_class
class MemberCoordinateNode(Node):
    """A schema coordinate that refers to a member of a named type.

    :param name: Name node identifying this AST node.
    :param member_name: The member name referenced by this schema coordinate.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import MemberCoordinateNode, NameNode, print_ast
    >>> node = MemberCoordinateNode(
    ...     name=NameNode(value='User'), member_name=NameNode(value='name')
    ... )
    >>> print_ast(node)
    'User.name'
    """

    name: NameNode
    """Name node identifying this AST node."""
    member_name: NameNode
    """The member name referenced by this schema coordinate."""


@node_class
class ArgumentCoordinateNode(Node):
    """A schema coordinate that refers to a field or directive argument.

    :param name: Name node identifying this AST node.
    :param field_name: The field name referenced by this schema coordinate.
    :param argument_name: The argument name referenced by this schema coordinate.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import ArgumentCoordinateNode, NameNode, print_ast
    >>> node = ArgumentCoordinateNode(
    ...     name=NameNode(value='Query'),
    ...     field_name=NameNode(value='user'),
    ...     argument_name=NameNode(value='id'),
    ... )
    >>> print_ast(node)
    'Query.user(id:)'
    """

    name: NameNode
    """Name node identifying this AST node."""
    field_name: NameNode
    """The field name referenced by this schema coordinate."""
    argument_name: NameNode
    """The argument name referenced by this schema coordinate."""


@node_class
class DirectiveCoordinateNode(Node):
    """A schema coordinate that refers to a directive.

    :param name: Name node identifying this AST node.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import DirectiveCoordinateNode, NameNode, print_ast
    >>> print_ast(DirectiveCoordinateNode(name=NameNode(value='deprecated')))
    '@deprecated'
    """

    name: NameNode
    """Name node identifying this AST node."""


@node_class
class DirectiveArgumentCoordinateNode(Node):
    """A schema coordinate that refers to a directive argument.

    :param name: Name node identifying this AST node.
    :param argument_name: The argument name referenced by this schema coordinate.
    :param loc: The source location for this AST node, if location tracking was enabled.

    >>> from graphql.language import (
    ...     DirectiveArgumentCoordinateNode, NameNode, print_ast,
    ... )
    >>> node = DirectiveArgumentCoordinateNode(
    ...     name=NameNode(value='deprecated'), argument_name=NameNode(value='reason')
    ... )
    >>> print_ast(node)
    '@deprecated(reason:)'
    """

    name: NameNode
    """Name node identifying this AST node."""
    argument_name: NameNode
    """The argument name referenced by this schema coordinate."""


SchemaCoordinateNode: TypeAlias = (
    TypeCoordinateNode
    | MemberCoordinateNode
    | ArgumentCoordinateNode
    | DirectiveCoordinateNode
    | DirectiveArgumentCoordinateNode
)
