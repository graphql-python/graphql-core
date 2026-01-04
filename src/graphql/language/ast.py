"""GraphQL Abstract Syntax Tree"""

from __future__ import annotations

from copy import copy, deepcopy
from enum import Enum, IntEnum, auto
from typing import TYPE_CHECKING, Any, ClassVar

import msgspec

from ..pyutils import camel_to_snake

if TYPE_CHECKING:
    from .source import Source
    from .token_kind import TokenKind


__all__ = [
    "QUERY_DOCUMENT_KEYS",
    "ArgumentNode",
    "BooleanValueNode",
    "ConstArgumentNode",
    "ConstDirectiveNode",
    "ConstListValueNode",
    "ConstObjectFieldNode",
    "ConstObjectValueNode",
    "ConstValueNode",
    "DefinitionNode",
    "DirectiveDefinitionNode",
    "DirectiveNode",
    "DocumentNode",
    "EnumTypeDefinitionNode",
    "EnumTypeExtensionNode",
    "EnumValueDefinitionNode",
    "EnumValueNode",
    "ErrorBoundaryNode",
    "ExecutableDefinitionNode",
    "FieldDefinitionNode",
    "FieldNode",
    "FloatValueNode",
    "FragmentDefinitionNode",
    "FragmentSpreadNode",
    "InlineFragmentNode",
    "InputObjectTypeDefinitionNode",
    "InputObjectTypeExtensionNode",
    "InputValueDefinitionNode",
    "IntValueNode",
    "InterfaceTypeDefinitionNode",
    "InterfaceTypeExtensionNode",
    "ListNullabilityOperatorNode",
    "ListTypeNode",
    "ListValueNode",
    "Location",
    "NameNode",
    "NamedTypeNode",
    "Node",
    "NonNullAssertionNode",
    "NonNullTypeNode",
    "NullValueNode",
    "NullabilityAssertionNode",
    "ObjectFieldNode",
    "ObjectTypeDefinitionNode",
    "ObjectTypeExtensionNode",
    "ObjectValueNode",
    "OperationDefinitionNode",
    "OperationType",
    "OperationTypeDefinitionNode",
    "ScalarTypeDefinitionNode",
    "ScalarTypeExtensionNode",
    "SchemaDefinitionNode",
    "SchemaExtensionNode",
    "SelectionNode",
    "SelectionSetNode",
    "StringValueNode",
    "Token",
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
    """

    __slots__ = ("column", "end", "kind", "line", "next", "prev", "start", "value")

    kind: TokenKind  # the kind of token
    start: int  # the character offset at which this Node begins
    end: int  # the character offset at which this Node ends
    line: int  # the 1-indexed line number on which this Token appears
    column: int  # the 1-indexed column number at which this Token begins
    # for non-punctuation tokens, represents the interpreted value of the token:
    value: str | None
    # Tokens exist as nodes in a double-linked-list amongst all tokens including
    # ignored tokens. <SOF> is always the first node and <EOF> the last.
    prev: Token | None
    next: Token | None

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
        return copy(self)

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
    """

    __slots__ = (
        "end",
        "end_token",
        "source",
        "start",
        "start_token",
    )

    start: int  # character offset at which this Node begins
    end: int  # character offset at which this Node ends
    start_token: Token  # Token at which this Node begins
    end_token: Token  # Token at which this Node ends.
    source: Source  # Source document the AST represents

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
    QUERY = "query"
    MUTATION = "mutation"
    SUBSCRIPTION = "subscription"


# Default map from node kinds to their node attributes (internal)
QUERY_DOCUMENT_KEYS: dict[str, tuple[str, ...]] = {
    "name": (),
    "document": ("definitions",),
    "operation_definition": (
        "name",
        "variable_definitions",
        "directives",
        "selection_set",
    ),
    "variable_definition": ("variable", "type", "default_value", "directives"),
    "variable": ("name",),
    "selection_set": ("selections",),
    "field": (
        "alias",
        "name",
        "arguments",
        "directives",
        "selection_set",
        # note: Client controlled Nullability is experimental and may be changed
        # or removed in the future.
        "nullability_assertion",
    ),
    "argument": ("name", "value"),
    # note: Client controlled Nullability is experimental and may be changed
    # or removed in the future.
    "list_nullability_operator": ("nullability_assertion",),
    "non_null_assertion": ("nullability_assertion",),
    "error_boundary": ("nullability_assertion",),
    "fragment_spread": ("name", "directives"),
    "inline_fragment": ("type_condition", "directives", "selection_set"),
    "fragment_definition": (
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
    "directive_definition": ("description", "name", "arguments", "locations"),
    "schema_extension": ("directives", "operation_types"),
    "scalar_type_extension": ("name", "directives"),
    "object_type_extension": ("name", "interfaces", "directives", "fields"),
    "interface_type_extension": ("name", "interfaces", "directives", "fields"),
    "union_type_extension": ("name", "directives", "types"),
    "enum_type_extension": ("name", "directives", "values"),
    "input_object_type_extension": ("name", "directives", "fields"),
}


# Private IntEnum for compact serialization tags.
# This is an implementation detail - values may change between versions.
# May be expanded to a public Kind enum in the future.
class _NodeKind(IntEnum):
    UNKNOWN = 0
    NAME = auto()
    DOCUMENT = auto()
    OPERATION_DEFINITION = auto()
    VARIABLE_DEFINITION = auto()
    SELECTION_SET = auto()
    FIELD = auto()
    FRAGMENT_SPREAD = auto()
    INLINE_FRAGMENT = auto()
    LIST_NULLABILITY_OPERATOR = auto()
    NON_NULL_ASSERTION = auto()
    ERROR_BOUNDARY = auto()
    ARGUMENT = auto()
    CONST_ARGUMENT = auto()
    FRAGMENT_DEFINITION = auto()
    VARIABLE = auto()
    INT_VALUE = auto()
    FLOAT_VALUE = auto()
    STRING_VALUE = auto()
    BOOLEAN_VALUE = auto()
    NULL_VALUE = auto()
    ENUM_VALUE = auto()
    LIST_VALUE = auto()
    CONST_LIST_VALUE = auto()
    OBJECT_VALUE = auto()
    CONST_OBJECT_VALUE = auto()
    OBJECT_FIELD = auto()
    CONST_OBJECT_FIELD = auto()
    DIRECTIVE = auto()
    CONST_DIRECTIVE = auto()
    NAMED_TYPE = auto()
    LIST_TYPE = auto()
    NON_NULL_TYPE = auto()
    SCHEMA_DEFINITION = auto()
    OPERATION_TYPE_DEFINITION = auto()
    SCALAR_TYPE_DEFINITION = auto()
    OBJECT_TYPE_DEFINITION = auto()
    FIELD_DEFINITION = auto()
    INPUT_VALUE_DEFINITION = auto()
    INTERFACE_TYPE_DEFINITION = auto()
    UNION_TYPE_DEFINITION = auto()
    ENUM_TYPE_DEFINITION = auto()
    ENUM_VALUE_DEFINITION = auto()
    INPUT_OBJECT_TYPE_DEFINITION = auto()
    DIRECTIVE_DEFINITION = auto()
    SCHEMA_EXTENSION = auto()
    SCALAR_TYPE_EXTENSION = auto()
    OBJECT_TYPE_EXTENSION = auto()
    INTERFACE_TYPE_EXTENSION = auto()
    UNION_TYPE_EXTENSION = auto()
    ENUM_TYPE_EXTENSION = auto()
    INPUT_OBJECT_TYPE_EXTENSION = auto()
    # Test-only node kinds (used in tests)
    SAMPLE_TEST = auto()
    SAMPLE_NAMED = auto()
    FOO = auto()  # For testing class names without "Node" suffix
    CUSTOM_FIELD = auto()  # For testing custom node types in test_visitor.py


def _node_kind_tag(class_name: str) -> int:
    """Tag function for msgspec - returns int tag for class name.

    Computes the tag from the class name using the same logic as __init_subclass__
    uses to derive the kind string, then looks up the corresponding enum value.
    """
    if class_name == "Node":
        return 0  # Base class, not directly serializable
    # Derive enum name from class name (same logic as __init_subclass__)
    name = class_name.removeprefix("Const").removesuffix("Node")
    kind_enum_name = camel_to_snake(name).upper()
    try:
        return _NodeKind[kind_enum_name].value
    except KeyError:
        msg = f"No serialization tag for node class: {class_name}"
        raise ValueError(msg) from None


# Base AST Node


class Node(
    msgspec.Struct,
    frozen=True,
    kw_only=True,
    weakref=True,
    omit_defaults=True,
    array_like=True,
    tag=_node_kind_tag,
    tag_field="k",
):
    """AST nodes.

    All AST nodes are immutable msgspec.Struct instances with the following options:

    - frozen=True: Nodes cannot be modified after creation
    - kw_only=True: All fields must be passed as keyword arguments
    - weakref=True: Allow weak references to nodes
    - array_like=True: Compact array serialization (field order matters)
    - tag=_node_kind_tag: Integer tags for compact polymorphic serialization
    - omit_defaults=True: Default values are omitted in serialization

    Note: The serialization format is an implementation detail and may change
    between library versions. Use DocumentNode.to_bytes_unstable() for serialization.
    """

    loc: Location | None = None

    kind: ClassVar[str] = "ast"  # the kind of the node as a snake_case string

    @property
    def keys(self) -> tuple[str, ...]:
        """Get the names of all fields for this node type."""
        return tuple(f.name for f in msgspec.structs.fields(self.__class__))

    def __repr__(self) -> str:
        """Get a simple representation of the node."""
        rep = self.__class__.__name__
        if isinstance(self, NameNode):
            rep += f"({self.value!r})"
        else:
            name = getattr(self, "name", None)
            if name:
                rep += f"(name={name.value!r})"
        loc = getattr(self, "loc", None)
        if loc:
            rep += f" at {loc}"
        return rep

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        name = cls.__name__
        name = name.removeprefix("Const").removesuffix("Node")
        cls.kind = camel_to_snake(name)

    def __copy__(self) -> Node:
        """Create a shallow copy of the node."""
        return self.__class__(
            **{f.name: getattr(self, f.name) for f in msgspec.structs.fields(self)}
        )

    def __deepcopy__(self, memo: dict) -> Node:
        """Create a deep copy of the node"""
        return self.__class__(
            **{
                f.name: deepcopy(getattr(self, f.name), memo)
                for f in msgspec.structs.fields(self)
            }
        )

    def to_dict(self, locations: bool = False) -> dict:
        """Convert node to a dictionary."""
        from ..utilities import ast_to_dict

        return ast_to_dict(self, locations)


# Name


class NameNode(Node, frozen=True, kw_only=True):
    value: str


# Document


class DocumentNode(Node, frozen=True, kw_only=True):
    """A GraphQL Document AST node.

    This is the root node type returned by the parser.
    """

    definitions: tuple[DefinitionNode, ...] = ()

    def to_bytes_unstable(self) -> bytes:
        """Serialize the document to bytes using msgpack.

        .. warning::
            The serialization format is an implementation detail and may change
            between library versions. Do not use for long-term storage or
            cross-version communication. This is intended for short-lived caches
            or same-version IPC.

        Note:
            Documents must be parsed with ``no_location=True`` for serialization.
            Location objects contain Token linked lists and Source references
            that cannot be efficiently serialized.

        Returns:
            Compact msgpack-encoded bytes representation of the document.

        """
        return msgspec.msgpack.encode(self)

    _decoder: ClassVar[msgspec.msgpack.Decoder[DocumentNode] | None] = None

    @classmethod
    def from_bytes_unstable(cls, data: bytes) -> DocumentNode:
        """Deserialize a document from bytes.

        .. warning::
            The serialization format is an implementation detail and may change
            between library versions. Only use with data serialized by the same
            library version using :meth:`to_bytes_unstable`.

        Args:
            data: Bytes previously returned by :meth:`to_bytes_unstable`.

        Returns:
            The deserialized DocumentNode.

        Raises:
            msgspec.ValidationError: If the data is invalid or corrupted.

        """
        if cls._decoder is None:
            cls._decoder = msgspec.msgpack.Decoder(cls)
        return cls._decoder.decode(data)


# Operations


class OperationDefinitionNode(Node, frozen=True, kw_only=True):
    operation: OperationType
    selection_set: SelectionSetNode
    name: NameNode | None = None
    variable_definitions: tuple[VariableDefinitionNode, ...] = ()
    directives: tuple[DirectiveNode, ...] = ()


class VariableDefinitionNode(Node, frozen=True, kw_only=True):
    variable: VariableNode
    type: TypeNode
    default_value: ConstValueNode | None = None
    directives: tuple[ConstDirectiveNode, ...] = ()


class SelectionSetNode(Node, frozen=True, kw_only=True):
    selections: tuple[SelectionNode, ...] = ()


# Selections


class FieldNode(Node, frozen=True, kw_only=True):
    name: NameNode
    alias: NameNode | None = None
    arguments: tuple[ArgumentNode, ...] = ()
    directives: tuple[DirectiveNode, ...] = ()
    # Note: Client Controlled Nullability is experimental
    # and may be changed or removed in the future.
    nullability_assertion: NullabilityAssertionNode | None = None
    selection_set: SelectionSetNode | None = None


class FragmentSpreadNode(Node, frozen=True, kw_only=True):
    name: NameNode
    directives: tuple[DirectiveNode, ...] = ()


class InlineFragmentNode(Node, frozen=True, kw_only=True):
    type_condition: NamedTypeNode | None
    selection_set: SelectionSetNode
    directives: tuple[DirectiveNode, ...] = ()


SelectionNode = FieldNode | FragmentSpreadNode | InlineFragmentNode


# Nullability Assertions


class ListNullabilityOperatorNode(Node, frozen=True, kw_only=True):
    nullability_assertion: NullabilityAssertionNode | None = None


class NonNullAssertionNode(Node, frozen=True, kw_only=True):
    nullability_assertion: ListNullabilityOperatorNode | None = None


class ErrorBoundaryNode(Node, frozen=True, kw_only=True):
    nullability_assertion: ListNullabilityOperatorNode | None = None


NullabilityAssertionNode = (
    ListNullabilityOperatorNode | NonNullAssertionNode | ErrorBoundaryNode
)


class ArgumentNode(Node, frozen=True, kw_only=True):
    name: NameNode
    value: ValueNode


class ConstArgumentNode(ArgumentNode, frozen=True, kw_only=True):
    value: ConstValueNode


# Fragments


class FragmentDefinitionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    type_condition: NamedTypeNode
    selection_set: SelectionSetNode
    variable_definitions: tuple[VariableDefinitionNode, ...] = ()
    directives: tuple[DirectiveNode, ...] = ()


ExecutableDefinitionNode = OperationDefinitionNode | FragmentDefinitionNode


# Values


class VariableNode(Node, frozen=True, kw_only=True):
    name: NameNode


class IntValueNode(Node, frozen=True, kw_only=True):
    value: str


class FloatValueNode(Node, frozen=True, kw_only=True):
    value: str


class StringValueNode(Node, frozen=True, kw_only=True):
    value: str
    block: bool | None = None


class BooleanValueNode(Node, frozen=True, kw_only=True):
    value: bool


class NullValueNode(Node, frozen=True, kw_only=True):
    pass


class EnumValueNode(Node, frozen=True, kw_only=True):
    value: str


class ListValueNode(Node, frozen=True, kw_only=True):
    values: tuple[ValueNode, ...] = ()


class ConstListValueNode(ListValueNode, frozen=True, kw_only=True):
    values: tuple[ConstValueNode, ...] = ()


class ObjectValueNode(Node, frozen=True, kw_only=True):
    fields: tuple[ObjectFieldNode, ...] = ()


class ConstObjectValueNode(ObjectValueNode, frozen=True, kw_only=True):
    fields: tuple[ConstObjectFieldNode, ...] = ()


class ObjectFieldNode(Node, frozen=True, kw_only=True):
    name: NameNode
    value: ValueNode


class ConstObjectFieldNode(ObjectFieldNode, frozen=True, kw_only=True):
    value: ConstValueNode


ValueNode = (
    VariableNode
    | IntValueNode
    | FloatValueNode
    | StringValueNode
    | BooleanValueNode
    | NullValueNode
    | EnumValueNode
    | ListValueNode
    | ObjectValueNode
)

ConstValueNode = (
    IntValueNode
    | FloatValueNode
    | StringValueNode
    | BooleanValueNode
    | NullValueNode
    | EnumValueNode
    | ConstListValueNode
    | ConstObjectValueNode
)


# Directives


class DirectiveNode(Node, frozen=True, kw_only=True):
    name: NameNode
    arguments: tuple[ArgumentNode, ...] = ()


class ConstDirectiveNode(DirectiveNode, frozen=True, kw_only=True):
    arguments: tuple[ConstArgumentNode, ...] = ()


# Type Reference


class NamedTypeNode(Node, frozen=True, kw_only=True):
    name: NameNode


class ListTypeNode(Node, frozen=True, kw_only=True):
    type: TypeNode


class NonNullTypeNode(Node, frozen=True, kw_only=True):
    type: NamedTypeNode | ListTypeNode


TypeNode = NamedTypeNode | ListTypeNode | NonNullTypeNode


# Type System Definition


class SchemaDefinitionNode(Node, frozen=True, kw_only=True):
    description: StringValueNode | None = None
    directives: tuple[ConstDirectiveNode, ...] = ()
    operation_types: tuple[OperationTypeDefinitionNode, ...] = ()


class OperationTypeDefinitionNode(Node, frozen=True, kw_only=True):
    operation: OperationType
    type: NamedTypeNode


# Type Definitions


class ScalarTypeDefinitionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    description: StringValueNode | None = None
    directives: tuple[ConstDirectiveNode, ...] = ()


class ObjectTypeDefinitionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    description: StringValueNode | None = None
    interfaces: tuple[NamedTypeNode, ...] = ()
    directives: tuple[ConstDirectiveNode, ...] = ()
    fields: tuple[FieldDefinitionNode, ...] = ()


class FieldDefinitionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    type: TypeNode
    description: StringValueNode | None = None
    arguments: tuple[InputValueDefinitionNode, ...] = ()
    directives: tuple[ConstDirectiveNode, ...] = ()


class InputValueDefinitionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    type: TypeNode
    description: StringValueNode | None = None
    default_value: ConstValueNode | None = None
    directives: tuple[ConstDirectiveNode, ...] = ()


class InterfaceTypeDefinitionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    description: StringValueNode | None = None
    interfaces: tuple[NamedTypeNode, ...] = ()
    directives: tuple[ConstDirectiveNode, ...] = ()
    fields: tuple[FieldDefinitionNode, ...] = ()


class UnionTypeDefinitionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    description: StringValueNode | None = None
    directives: tuple[ConstDirectiveNode, ...] = ()
    types: tuple[NamedTypeNode, ...] = ()


class EnumTypeDefinitionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    description: StringValueNode | None = None
    directives: tuple[ConstDirectiveNode, ...] = ()
    values: tuple[EnumValueDefinitionNode, ...] = ()


class EnumValueDefinitionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    description: StringValueNode | None = None
    directives: tuple[ConstDirectiveNode, ...] = ()


class InputObjectTypeDefinitionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    description: StringValueNode | None = None
    directives: tuple[ConstDirectiveNode, ...] = ()
    fields: tuple[InputValueDefinitionNode, ...] = ()


TypeDefinitionNode = (
    ScalarTypeDefinitionNode
    | ObjectTypeDefinitionNode
    | InterfaceTypeDefinitionNode
    | UnionTypeDefinitionNode
    | EnumTypeDefinitionNode
    | InputObjectTypeDefinitionNode
)


# Directive Definitions


class DirectiveDefinitionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    locations: tuple[NameNode, ...]
    description: StringValueNode | None = None
    arguments: tuple[InputValueDefinitionNode, ...] = ()
    repeatable: bool = False


TypeSystemDefinitionNode = (
    SchemaDefinitionNode | TypeDefinitionNode | DirectiveDefinitionNode
)


# Type System Extensions


class SchemaExtensionNode(Node, frozen=True, kw_only=True):
    directives: tuple[ConstDirectiveNode, ...] = ()
    operation_types: tuple[OperationTypeDefinitionNode, ...] = ()


# Type Extensions


class ScalarTypeExtensionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    directives: tuple[ConstDirectiveNode, ...] = ()


class ObjectTypeExtensionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    interfaces: tuple[NamedTypeNode, ...] = ()
    directives: tuple[ConstDirectiveNode, ...] = ()
    fields: tuple[FieldDefinitionNode, ...] = ()


class InterfaceTypeExtensionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    interfaces: tuple[NamedTypeNode, ...] = ()
    directives: tuple[ConstDirectiveNode, ...] = ()
    fields: tuple[FieldDefinitionNode, ...] = ()


class UnionTypeExtensionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    directives: tuple[ConstDirectiveNode, ...] = ()
    types: tuple[NamedTypeNode, ...] = ()


class EnumTypeExtensionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    directives: tuple[ConstDirectiveNode, ...] = ()
    values: tuple[EnumValueDefinitionNode, ...] = ()


class InputObjectTypeExtensionNode(Node, frozen=True, kw_only=True):
    name: NameNode
    directives: tuple[ConstDirectiveNode, ...] = ()
    fields: tuple[InputValueDefinitionNode, ...] = ()


TypeExtensionNode = (
    ScalarTypeExtensionNode
    | ObjectTypeExtensionNode
    | InterfaceTypeExtensionNode
    | UnionTypeExtensionNode
    | EnumTypeExtensionNode
    | InputObjectTypeExtensionNode
)

TypeSystemExtensionNode = SchemaExtensionNode | TypeExtensionNode


DefinitionNode = (
    ExecutableDefinitionNode
    | TypeSystemDefinitionNode
    | TypeSystemExtensionNode
    | FieldDefinitionNode
    | InputValueDefinitionNode
    | EnumValueDefinitionNode
)
