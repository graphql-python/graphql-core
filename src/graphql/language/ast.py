from copy import copy, deepcopy
from enum import Enum
from typing import Any, Dict, List, Tuple, Optional, Union

from .source import Source
from .token_kind import TokenKind
from ..pyutils import camel_to_snake

__all__ = [
    "Location",
    "Token",
    "Node",
    "NameNode",
    "DocumentNode",
    "DefinitionNode",
    "ExecutableDefinitionNode",
    "OperationDefinitionNode",
    "VariableDefinitionNode",
    "SelectionSetNode",
    "SelectionNode",
    "FieldNode",
    "ArgumentNode",
    "ConstArgumentNode",
    "FragmentSpreadNode",
    "InlineFragmentNode",
    "FragmentDefinitionNode",
    "ValueNode",
    "ConstValueNode",
    "VariableNode",
    "IntValueNode",
    "FloatValueNode",
    "StringValueNode",
    "BooleanValueNode",
    "NullValueNode",
    "EnumValueNode",
    "ListValueNode",
    "ConstListValueNode",
    "ObjectValueNode",
    "ConstObjectValueNode",
    "ObjectFieldNode",
    "ConstObjectFieldNode",
    "DirectiveNode",
    "ConstDirectiveNode",
    "TypeNode",
    "NamedTypeNode",
    "ListTypeNode",
    "NonNullTypeNode",
    "TypeSystemDefinitionNode",
    "SchemaDefinitionNode",
    "OperationType",
    "OperationTypeDefinitionNode",
    "TypeDefinitionNode",
    "ScalarTypeDefinitionNode",
    "ObjectTypeDefinitionNode",
    "FieldDefinitionNode",
    "InputValueDefinitionNode",
    "InterfaceTypeDefinitionNode",
    "UnionTypeDefinitionNode",
    "EnumTypeDefinitionNode",
    "EnumValueDefinitionNode",
    "InputObjectTypeDefinitionNode",
    "DirectiveDefinitionNode",
    "SchemaExtensionNode",
    "TypeExtensionNode",
    "TypeSystemExtensionNode",
    "ScalarTypeExtensionNode",
    "ObjectTypeExtensionNode",
    "InterfaceTypeExtensionNode",
    "UnionTypeExtensionNode",
    "EnumTypeExtensionNode",
    "InputObjectTypeExtensionNode",
    "DirectiveExtensionNode",
    "SchemaCoordinateNode",
    "TypeCoordinateNode",
    "MemberCoordinateNode",
    "ArgumentCoordinateNode",
    "DirectiveCoordinateNode",
    "DirectiveArgumentCoordinateNode",
    "QUERY_DOCUMENT_KEYS",
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

    __slots__ = "kind", "start", "end", "line", "column", "prev", "next", "value"

    kind: TokenKind
    """The kind of Token."""
    start: int
    """The character offset at which this Node begins."""
    end: int
    """The character offset at which this Node ends."""
    line: int
    """The 1-indexed line number on which this Token appears."""
    column: int
    """The 1-indexed column number at which this Token begins."""
    value: Optional[str]
    """For non-punctuation tokens, represents the interpreted value of the token.

    Note: is ``None`` for punctuation tokens.
    """
    prev: Optional["Token"]
    """Previous token in the token stream, including ignored tokens.

    Tokens exist as nodes in a double-linked-list amongst all tokens including
    ignored tokens. <SOF> is always the first node and <EOF> the last.
    """
    next: Optional["Token"]
    """Next token in the token stream, including ignored tokens."""

    def __init__(
        self,
        kind: TokenKind,
        start: int,
        end: int,
        line: int,
        column: int,
        value: Optional[str] = None,
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

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Token):
            return (
                self.kind == other.kind
                and self.start == other.start
                and self.end == other.end
                and self.line == other.line
                and self.column == other.column
                and self.value == other.value
            )
        elif isinstance(other, str):
            return other == self.desc
        return False

    def __hash__(self) -> int:
        return hash(
            (self.kind, self.start, self.end, self.line, self.column, self.value)
        )

    def __copy__(self) -> "Token":
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

    def __deepcopy__(self, memo: Dict) -> "Token":
        """Allow only shallow copies to avoid recursion."""
        return copy(self)

    def __getstate__(self) -> Dict[str, Any]:
        """Remove the links when pickling.

        Keeping the links would make pickling a schema too expensive.
        """
        return {
            key: getattr(self, key)
            for key in self.__slots__
            if key not in {"prev", "next"}
        }

    def __setstate__(self, state: Dict[str, Any]) -> None:
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
        "start",
        "end",
        "start_token",
        "end_token",
        "source",
    )

    start: int
    """The character offset at which this Node begins."""
    end: int
    """The character offset at which this Node ends."""
    start_token: Token
    """The Token at which this Node begins."""
    end_token: Token
    """The Token at which this Node ends."""
    source: Source
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

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Location):
            return self.start == other.start and self.end == other.end
        elif isinstance(other, (list, tuple)) and len(other) == 2:
            return self.start == other[0] and self.end == other[1]
        return False

    def __ne__(self, other: Any) -> bool:
        return not self == other

    def __hash__(self) -> int:
        return hash((self.start, self.end))


class OperationType(Enum):
    """The operation types supported by GraphQL executable definitions."""

    QUERY = "query"
    """A query operation."""
    MUTATION = "mutation"
    """A mutation operation."""
    SUBSCRIPTION = "subscription"
    """A subscription operation."""


# Default map from node kinds to their node attributes (internal)
QUERY_DOCUMENT_KEYS: Dict[str, Tuple[str, ...]] = {
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
    "fragment_spread": ("name", "directives"),
    "inline_fragment": ("type_condition", "directives", "selection_set"),
    "fragment_definition": (
        "description",
        # Note: fragment variable definitions are deprecated and will be removed in v3.3
        "name",
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


class Node:
    """AST nodes

    Base class of all AST nodes. The attributes of a node are passed as keyword
    arguments; attributes that are not passed are set to ``None``.

    >>> from graphql.language import NameNode
    >>> node = NameNode(value='hello')
    >>> node.kind
    'name'
    >>> node.keys
    ('loc', 'value')
    >>> node.value
    'hello'
    >>> node.loc is None
    True
    """

    # allow custom attributes and weak references (not used internally)
    __slots__ = "__dict__", "__weakref__", "loc", "_hash"

    loc: Optional[Location]
    """The source location for this AST node, if location tracking was enabled."""

    kind: str = "ast"
    """The kind of the node as a snake_case string, identifying the concrete node."""
    keys: Tuple[str, ...] = ("loc",)
    """The names of the attributes of this node."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the node with the given keyword arguments."""
        for key in self.keys:
            value = kwargs.get(key)
            if isinstance(value, list):
                value = tuple(value)
            setattr(self, key, value)

    def __repr__(self) -> str:
        """Get a simple representation of the node."""
        name, loc = self.__class__.__name__, getattr(self, "loc", None)
        return f"{name} at {loc}" if loc else name

    def __eq__(self, other: Any) -> bool:
        """Test whether two nodes are equal (recursively)."""
        return (
            isinstance(other, Node)
            and self.__class__ == other.__class__
            and all(getattr(self, key) == getattr(other, key) for key in self.keys)
        )

    def __hash__(self) -> int:
        """Get a cached hash value for the node."""
        # Caching the hash values improves the performance of AST validators
        hashed = getattr(self, "_hash", None)
        if hashed is None:
            self._hash = id(self)  # avoid recursion
            hashed = hash(tuple(getattr(self, key) for key in self.keys))
            self._hash = hashed
        return hashed

    def __setattr__(self, key: str, value: Any) -> None:
        # reset cashed hash value if attributes are changed
        if hasattr(self, "_hash") and key in self.keys:
            del self._hash
        super().__setattr__(key, value)

    def __copy__(self) -> "Node":
        """Create a shallow copy of the node."""
        return self.__class__(**{key: getattr(self, key) for key in self.keys})

    def __deepcopy__(self, memo: Dict) -> "Node":
        """Create a deep copy of the node"""
        # noinspection PyArgumentList
        return self.__class__(
            **{key: deepcopy(getattr(self, key), memo) for key in self.keys}
        )

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        name = cls.__name__
        try:
            name = name.removeprefix("Const").removesuffix("Node")
        except AttributeError:  # pragma: no cover (Python < 3.9)
            if name.startswith("Const"):
                name = name[5:]
            if name.endswith("Node"):
                name = name[:-4]
        cls.kind = camel_to_snake(name)
        keys: List[str] = []
        for base in cls.__bases__:
            # noinspection PyUnresolvedReferences
            keys.extend(base.keys)  # type: ignore
        keys.extend(cls.__slots__)
        cls.keys = tuple(keys)

    def to_dict(self, locations: bool = False) -> Dict:
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


class NameNode(Node):
    """An identifier in a GraphQL document."""

    __slots__ = ("value",)

    value: str
    """Parsed value represented by this node."""


# Document


class DocumentNode(Node):
    """The root AST node for a parsed GraphQL document."""

    __slots__ = ("definitions",)

    definitions: Tuple["DefinitionNode", ...]
    """Top-level executable and type-system definitions in this document."""

    # The number of tokens in the parsed document. Set by the parser per instance
    # and deliberately kept out of ``__slots__`` (and therefore out of ``keys``) so
    # that it is not treated as a traversable attribute, the equivalent of the
    # non-enumerable ``tokenCount`` property in graphql-js.
    token_count: int = 0
    """The number of lexical tokens parsed for this document."""


class DefinitionNode(Node):
    """Any top-level definition that may appear in a GraphQL document."""

    __slots__ = ()


class ExecutableDefinitionNode(DefinitionNode):
    """Any executable definition that may appear in an operation document."""

    __slots__ = (
        "description",
        "name",
        "directives",
        "variable_definitions",
        "selection_set",
    )

    description: Optional["StringValueNode"]
    """The optional GraphQL description associated with this definition."""
    name: Optional[NameNode]
    """Name node identifying this AST node."""
    directives: Tuple["DirectiveNode", ...]
    """Directives available in this schema or applied to this AST node."""
    variable_definitions: Tuple["VariableDefinitionNode", ...]
    """Variable definitions declared by this operation or fragment.

    Note: variable definitions on fragment definitions are deprecated and will be
    removed in v3.3.
    """
    selection_set: "SelectionSetNode"
    """Selections made by this operation, field, or fragment."""


class OperationDefinitionNode(ExecutableDefinitionNode):
    """A query, mutation, or subscription operation definition."""

    __slots__ = ("operation",)

    operation: OperationType
    """The operation selected for execution."""


class VariableDefinitionNode(Node):
    """A variable declaration in an operation or legacy fragment definition."""

    __slots__ = "description", "variable", "type", "default_value", "directives"

    description: Optional["StringValueNode"]
    """The optional GraphQL description associated with this definition."""
    variable: "VariableNode"
    """The variable being defined or referenced."""
    type: "TypeNode"
    """The GraphQL type reference or runtime type for this element."""
    default_value: Optional["ConstValueNode"]
    """Default value used when no explicit value is supplied."""
    directives: Tuple["ConstDirectiveNode", ...]
    """Directives available in this schema or applied to this AST node."""


class SelectionSetNode(Node):
    """A set of fields and fragments selected from an object, interface, or union."""

    __slots__ = ("selections",)

    selections: Tuple["SelectionNode", ...]
    """Fields and fragments contained in this selection set."""


class SelectionNode(Node):
    """Any selection that may appear inside a selection set."""

    __slots__ = ("directives",)

    directives: Tuple["DirectiveNode", ...]
    """Directives available in this schema or applied to this AST node."""


class FieldNode(SelectionNode):
    """A field selected in an executable GraphQL document."""

    __slots__ = "alias", "name", "arguments", "selection_set"

    alias: Optional[NameNode]
    """The response-key alias for this field, if one was supplied."""
    name: NameNode
    """Name node identifying this AST node."""
    arguments: Tuple["ArgumentNode", ...]
    """Arguments supplied to this field, directive, or coordinate."""
    selection_set: Optional[SelectionSetNode]
    """Selections made by this operation, field, or fragment."""


class ArgumentNode(Node):
    """An argument supplied to a field or directive."""

    __slots__ = "name", "value"

    name: NameNode
    """Name node identifying this AST node."""
    value: "ValueNode"
    """Parsed value represented by this node."""


class ConstArgumentNode(ArgumentNode):
    """An argument node whose value is guaranteed to be constant."""

    value: "ConstValueNode"
    """Parsed value represented by this node."""


# Fragments


class FragmentSpreadNode(SelectionNode):
    """A named fragment spread, such as ``...userFields``."""

    __slots__ = ("name",)

    name: NameNode
    """Name node identifying this AST node."""


class InlineFragmentNode(SelectionNode):
    """An inline fragment spread with an optional type condition."""

    __slots__ = "type_condition", "selection_set"

    type_condition: "NamedTypeNode"
    """The type condition that limits where this fragment applies."""
    selection_set: SelectionSetNode
    """Selections made by this operation, field, or fragment."""


class FragmentDefinitionNode(ExecutableDefinitionNode):
    """A reusable fragment definition declared in an executable document."""

    __slots__ = ("type_condition",)

    name: NameNode
    """Name node identifying this AST node."""
    type_condition: "NamedTypeNode"
    """The type condition that limits where this fragment applies."""


# Values


class ValueNode(Node):
    """Any value literal that may appear in an executable GraphQL document."""

    __slots__ = ()


class VariableNode(ValueNode):
    """A variable reference, such as ``$id``."""

    __slots__ = ("name",)

    name: NameNode
    """Name node identifying this AST node."""


class IntValueNode(ValueNode):
    """An integer value literal."""

    __slots__ = ("value",)

    value: str
    """Parsed value represented by this node."""


class FloatValueNode(ValueNode):
    """A floating-point value literal."""

    __slots__ = ("value",)

    value: str
    """Parsed value represented by this node."""


class StringValueNode(ValueNode):
    """A string value literal."""

    __slots__ = "value", "block"

    value: str
    """Parsed value represented by this node."""
    block: Optional[bool]
    """Whether this string was parsed from block string syntax."""


class BooleanValueNode(ValueNode):
    """A boolean value literal."""

    __slots__ = ("value",)

    value: bool
    """Parsed value represented by this node."""


class NullValueNode(ValueNode):
    """A null value literal."""

    __slots__ = ()


class EnumValueNode(ValueNode):
    """An enum value literal."""

    __slots__ = ("value",)

    value: str
    """Parsed value represented by this node."""


class ListValueNode(ValueNode):
    """A list value literal."""

    __slots__ = ("values",)

    values: Tuple[ValueNode, ...]
    """Values contained in this enum, list, or input-object definition."""


class ConstListValueNode(ListValueNode):
    """A list value literal whose elements are all constant values."""

    values: Tuple["ConstValueNode", ...]
    """Values contained in this enum, list, or input-object definition."""


class ObjectValueNode(ValueNode):
    """An input object value literal."""

    __slots__ = ("fields",)

    fields: Tuple["ObjectFieldNode", ...]
    """Fields declared by this object, interface, input object, or literal."""


class ConstObjectValueNode(ObjectValueNode):
    """An input object value literal whose fields are all constant values."""

    fields: Tuple["ConstObjectFieldNode", ...]
    """Fields declared by this object, interface, input object, or literal."""


class ObjectFieldNode(Node):
    """A field inside an input object value literal."""

    __slots__ = "name", "value"

    name: NameNode
    """Name node identifying this AST node."""
    value: ValueNode
    """Parsed value represented by this node."""


class ConstObjectFieldNode(ObjectFieldNode):
    """A field inside a constant input object value literal."""

    value: "ConstValueNode"
    """Parsed value represented by this node."""


ConstValueNode = Union[
    IntValueNode,
    FloatValueNode,
    StringValueNode,
    BooleanValueNode,
    NullValueNode,
    EnumValueNode,
    ConstListValueNode,
    ConstObjectValueNode,
]
"""Any value literal that is guaranteed not to contain a variable reference."""


# Directives


class DirectiveNode(Node):
    """A directive applied to an executable or type-system location."""

    __slots__ = "name", "arguments"

    name: NameNode
    """Name node identifying this AST node."""
    arguments: Tuple[ArgumentNode, ...]
    """Arguments supplied to this field, directive, or coordinate."""


class ConstDirectiveNode(DirectiveNode):
    """A directive whose arguments are all constant values."""

    arguments: Tuple[ConstArgumentNode, ...]
    """Arguments supplied to this field, directive, or coordinate."""


# Type Reference


class TypeNode(Node):
    """Any GraphQL type reference AST node."""

    __slots__ = ()


class NamedTypeNode(TypeNode):
    """A named type reference."""

    __slots__ = ("name",)

    name: NameNode
    """Name node identifying this AST node."""


class ListTypeNode(TypeNode):
    """A list type reference."""

    __slots__ = ("type",)

    type: TypeNode
    """The GraphQL type reference or runtime type for this element."""


class NonNullTypeNode(TypeNode):
    """A non-null type reference."""

    __slots__ = ("type",)

    type: Union[NamedTypeNode, ListTypeNode]
    """The GraphQL type reference or runtime type for this element."""


# Type System Definition


class TypeSystemDefinitionNode(DefinitionNode):
    """Any type-system definition that may appear in a schema document."""

    __slots__ = ()


class SchemaDefinitionNode(TypeSystemDefinitionNode):
    """A schema definition in a type-system document."""

    __slots__ = "description", "directives", "operation_types"

    description: Optional[StringValueNode]
    """The optional GraphQL description associated with this definition."""
    directives: Tuple[ConstDirectiveNode, ...]
    """Directives available in this schema or applied to this AST node."""
    operation_types: Tuple["OperationTypeDefinitionNode", ...]
    """Root operation types declared by this schema definition or extension."""


class OperationTypeDefinitionNode(Node):
    """A root operation type declaration inside a schema definition or extension."""

    __slots__ = "operation", "type"

    operation: OperationType
    """The operation selected for execution."""
    type: NamedTypeNode
    """The GraphQL type reference or runtime type for this element."""


# Type Definition


class TypeDefinitionNode(TypeSystemDefinitionNode):
    """Any named type definition that may appear in a schema document."""

    __slots__ = "description", "name", "directives"

    description: Optional[StringValueNode]
    """The optional GraphQL description associated with this definition."""
    name: NameNode
    """Name node identifying this AST node."""
    directives: Tuple[DirectiveNode, ...]
    """Directives available in this schema or applied to this AST node."""


class ScalarTypeDefinitionNode(TypeDefinitionNode):
    """A scalar type definition in a type-system document."""

    __slots__ = ()

    directives: Tuple[ConstDirectiveNode, ...]
    """Directives available in this schema or applied to this AST node."""


class ObjectTypeDefinitionNode(TypeDefinitionNode):
    """An object type definition in a type-system document."""

    __slots__ = "interfaces", "fields"

    interfaces: Tuple[NamedTypeNode, ...]
    """Interfaces implemented by this object or interface type."""
    directives: Tuple[ConstDirectiveNode, ...]
    """Directives available in this schema or applied to this AST node."""
    fields: Tuple["FieldDefinitionNode", ...]
    """Fields declared by this object, interface, input object, or literal."""


class FieldDefinitionNode(DefinitionNode):
    """A field definition declared by an object or interface type."""

    __slots__ = "description", "name", "directives", "arguments", "type"

    description: Optional[StringValueNode]
    """The optional GraphQL description associated with this definition."""
    name: NameNode
    """Name node identifying this AST node."""
    directives: Tuple[ConstDirectiveNode, ...]
    """Directives available in this schema or applied to this AST node."""
    arguments: Tuple["InputValueDefinitionNode", ...]
    """Arguments supplied to this field, directive, or coordinate."""
    type: TypeNode
    """The GraphQL type reference or runtime type for this element."""


class InputValueDefinitionNode(DefinitionNode):
    """An argument or input-field definition."""

    __slots__ = "description", "name", "directives", "type", "default_value"

    description: Optional[StringValueNode]
    """The optional GraphQL description associated with this definition."""
    name: NameNode
    """Name node identifying this AST node."""
    directives: Tuple[ConstDirectiveNode, ...]
    """Directives available in this schema or applied to this AST node."""
    type: TypeNode
    """The GraphQL type reference or runtime type for this element."""
    default_value: Optional[ConstValueNode]
    """Default value used when no explicit value is supplied."""


class InterfaceTypeDefinitionNode(TypeDefinitionNode):
    """An interface type definition in a type-system document."""

    __slots__ = "fields", "interfaces"

    fields: Tuple["FieldDefinitionNode", ...]
    """Fields declared by this object, interface, input object, or literal."""
    directives: Tuple[ConstDirectiveNode, ...]
    """Directives available in this schema or applied to this AST node."""
    interfaces: Tuple[NamedTypeNode, ...]
    """Interfaces implemented by this object or interface type."""


class UnionTypeDefinitionNode(TypeDefinitionNode):
    """A union type definition in a type-system document."""

    __slots__ = ("types",)

    directives: Tuple[ConstDirectiveNode, ...]
    """Directives available in this schema or applied to this AST node."""
    types: Tuple[NamedTypeNode, ...]
    """Object types that belong to this union type."""


class EnumTypeDefinitionNode(TypeDefinitionNode):
    """An enum type definition in a type-system document."""

    __slots__ = ("values",)

    directives: Tuple[ConstDirectiveNode, ...]
    """Directives available in this schema or applied to this AST node."""
    values: Tuple["EnumValueDefinitionNode", ...]
    """Values contained in this enum, list, or input-object definition."""


class EnumValueDefinitionNode(DefinitionNode):
    """An enum value definition."""

    __slots__ = "description", "name", "directives"

    description: Optional[StringValueNode]
    """The optional GraphQL description associated with this definition."""
    name: NameNode
    """Name node identifying this AST node."""
    directives: Tuple[ConstDirectiveNode, ...]
    """Directives available in this schema or applied to this AST node."""


class InputObjectTypeDefinitionNode(TypeDefinitionNode):
    """An input object type definition in a type-system document."""

    __slots__ = ("fields",)

    directives: Tuple[ConstDirectiveNode, ...]
    """Directives available in this schema or applied to this AST node."""
    fields: Tuple[InputValueDefinitionNode, ...]
    """Fields declared by this object, interface, input object, or literal."""


# Directive Definitions


class DirectiveDefinitionNode(TypeSystemDefinitionNode):
    """A directive definition in a type-system document."""

    __slots__ = (
        "description",
        "name",
        "arguments",
        "directives",
        "repeatable",
        "locations",
    )

    description: Optional[StringValueNode]
    """The optional GraphQL description associated with this definition."""
    name: NameNode
    """Name node identifying this AST node."""
    arguments: Tuple[InputValueDefinitionNode, ...]
    """Arguments supplied to this field, directive, or coordinate."""
    directives: Tuple[ConstDirectiveNode, ...]
    """Directives available in this schema or applied to this AST node."""
    repeatable: bool
    """Whether this directive may appear more than once at the same location."""
    locations: Tuple[NameNode, ...]
    """Locations where this directive may be applied."""


# Type System Extensions


class SchemaExtensionNode(Node):
    """A schema extension in a type-system document."""

    __slots__ = "directives", "operation_types"

    directives: Tuple[ConstDirectiveNode, ...]
    """Directives available in this schema or applied to this AST node."""
    operation_types: Tuple[OperationTypeDefinitionNode, ...]
    """Root operation types declared by this schema definition or extension."""


class DirectiveExtensionNode(Node):
    """A directive extension."""

    __slots__ = "name", "directives"

    name: NameNode
    """Name node identifying this AST node."""
    directives: Tuple[ConstDirectiveNode, ...]
    """Directives available in this schema or applied to this AST node."""


# Type Extensions


class TypeExtensionNode(TypeSystemDefinitionNode):
    """Any named type extension that may appear in a schema extension document."""

    __slots__ = "name", "directives"

    name: NameNode
    """Name node identifying this AST node."""
    directives: Tuple[ConstDirectiveNode, ...]
    """Directives available in this schema or applied to this AST node."""


TypeSystemExtensionNode = Union[
    SchemaExtensionNode, TypeExtensionNode, DirectiveExtensionNode
]
"""Any type-system extension that may appear in a schema extension document."""


class ScalarTypeExtensionNode(TypeExtensionNode):
    """A scalar type extension."""

    __slots__ = ()


class ObjectTypeExtensionNode(TypeExtensionNode):
    """An object type extension."""

    __slots__ = "interfaces", "fields"

    interfaces: Tuple[NamedTypeNode, ...]
    """Interfaces implemented by this object or interface type."""
    fields: Tuple[FieldDefinitionNode, ...]
    """Fields declared by this object, interface, input object, or literal."""


class InterfaceTypeExtensionNode(TypeExtensionNode):
    """An interface type extension."""

    __slots__ = "interfaces", "fields"

    interfaces: Tuple[NamedTypeNode, ...]
    """Interfaces implemented by this object or interface type."""
    fields: Tuple[FieldDefinitionNode, ...]
    """Fields declared by this object, interface, input object, or literal."""


class UnionTypeExtensionNode(TypeExtensionNode):
    """A union type extension."""

    __slots__ = ("types",)

    types: Tuple[NamedTypeNode, ...]
    """Object types that belong to this union type."""


class EnumTypeExtensionNode(TypeExtensionNode):
    """An enum type extension."""

    __slots__ = ("values",)

    values: Tuple[EnumValueDefinitionNode, ...]
    """Values contained in this enum, list, or input-object definition."""


class InputObjectTypeExtensionNode(TypeExtensionNode):
    """An input object type extension."""

    __slots__ = ("fields",)

    fields: Tuple[InputValueDefinitionNode, ...]
    """Fields declared by this object, interface, input object, or literal."""


# Schema Coordinates


class TypeCoordinateNode(Node):
    """A schema coordinate that refers to a named type."""

    __slots__ = ("name",)

    name: NameNode
    """Name node identifying this AST node."""


class MemberCoordinateNode(Node):
    """A schema coordinate that refers to a member of a named type."""

    __slots__ = "name", "member_name"

    name: NameNode
    """Name node identifying this AST node."""
    member_name: NameNode
    """The member name referenced by this schema coordinate."""


class ArgumentCoordinateNode(Node):
    """A schema coordinate that refers to a field or directive argument."""

    __slots__ = "name", "field_name", "argument_name"

    name: NameNode
    """Name node identifying this AST node."""
    field_name: NameNode
    """The field name referenced by this schema coordinate."""
    argument_name: NameNode
    """The argument name referenced by this schema coordinate."""


class DirectiveCoordinateNode(Node):
    """A schema coordinate that refers to a directive."""

    __slots__ = ("name",)

    name: NameNode
    """Name node identifying this AST node."""


class DirectiveArgumentCoordinateNode(Node):
    """A schema coordinate that refers to a directive argument."""

    __slots__ = "name", "argument_name"

    name: NameNode
    """Name node identifying this AST node."""
    argument_name: NameNode
    """The argument name referenced by this schema coordinate."""


SchemaCoordinateNode = Union[
    TypeCoordinateNode,
    MemberCoordinateNode,
    ArgumentCoordinateNode,
    DirectiveCoordinateNode,
    DirectiveArgumentCoordinateNode,
]
"""Any AST node representing a GraphQL schema coordinate."""
