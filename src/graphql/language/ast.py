"""GraphQL Abstract Syntax Tree"""

from __future__ import annotations

from copy import copy, deepcopy
from enum import Enum
from typing import TYPE_CHECKING, Any, Union

try:
    from typing import TypeAlias
except ImportError:  # Python < 3.10
    from typing_extensions import TypeAlias

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

    __slots__ = "column", "end", "kind", "line", "next", "prev", "start", "value"

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


# Base AST Node


class Node:
    """AST nodes"""

    # allow custom attributes and weak references (not used internally)
    __slots__ = "__dict__", "__weakref__", "_hash", "loc"

    loc: Location | None

    kind: str = "ast"  # the kind of the node as a snake_case string
    keys: tuple[str, ...] = ("loc",)  # the names of the attributes of this node

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the node with the given keyword arguments."""
        for key in self.keys:
            value = kwargs.get(key)
            if isinstance(value, list):
                value = tuple(value)
            setattr(self, key, value)

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

    def __eq__(self, other: object) -> bool:
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

    def __copy__(self) -> Node:
        """Create a shallow copy of the node."""
        return self.__class__(**{key: getattr(self, key) for key in self.keys})

    def __deepcopy__(self, memo: dict) -> Node:
        """Create a deep copy of the node"""
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
        keys: list[str] = []
        for base in cls.__bases__:
            keys.extend(base.keys)  # type: ignore
        keys.extend(cls.__slots__)
        cls.keys = tuple(keys)

    def to_dict(self, locations: bool = False) -> dict:
        """Concert node to a dictionary."""
        from ..utilities import ast_to_dict

        return ast_to_dict(self, locations)


# Name


class NameNode(Node):
    __slots__ = ("value",)

    value: str


# Document


class DocumentNode(Node):
    __slots__ = ("definitions",)

    definitions: tuple[DefinitionNode, ...]


class DefinitionNode(Node):
    __slots__ = ()


class ExecutableDefinitionNode(DefinitionNode):
    __slots__ = "directives", "name", "selection_set", "variable_definitions"

    name: NameNode | None
    directives: tuple[DirectiveNode, ...]
    variable_definitions: tuple[VariableDefinitionNode, ...]
    selection_set: SelectionSetNode


class OperationDefinitionNode(ExecutableDefinitionNode):
    __slots__ = ("operation",)

    operation: OperationType


class VariableDefinitionNode(Node):
    __slots__ = "default_value", "directives", "type", "variable"

    variable: VariableNode
    type: TypeNode
    default_value: ConstValueNode | None
    directives: tuple[ConstDirectiveNode, ...]


class SelectionSetNode(Node):
    __slots__ = ("selections",)

    selections: tuple[SelectionNode, ...]


class SelectionNode(Node):
    __slots__ = ("directives",)

    directives: tuple[DirectiveNode, ...]


class FieldNode(SelectionNode):
    __slots__ = "alias", "arguments", "name", "nullability_assertion", "selection_set"

    alias: NameNode | None
    name: NameNode
    arguments: tuple[ArgumentNode, ...]
    # Note: Client Controlled Nullability is experimental
    # and may be changed or removed in the future.
    nullability_assertion: NullabilityAssertionNode
    selection_set: SelectionSetNode | None


class NullabilityAssertionNode(Node):
    __slots__ = ("nullability_assertion",)
    nullability_assertion: NullabilityAssertionNode | None


class ListNullabilityOperatorNode(NullabilityAssertionNode):
    pass


class NonNullAssertionNode(NullabilityAssertionNode):
    nullability_assertion: ListNullabilityOperatorNode


class ErrorBoundaryNode(NullabilityAssertionNode):
    nullability_assertion: ListNullabilityOperatorNode


class ArgumentNode(Node):
    __slots__ = "name", "value"

    name: NameNode
    value: ValueNode


class ConstArgumentNode(ArgumentNode):
    value: ConstValueNode


# Fragments


class FragmentSpreadNode(SelectionNode):
    __slots__ = ("name",)

    name: NameNode


class InlineFragmentNode(SelectionNode):
    __slots__ = "selection_set", "type_condition"

    type_condition: NamedTypeNode
    selection_set: SelectionSetNode


class FragmentDefinitionNode(ExecutableDefinitionNode):
    __slots__ = ("type_condition",)

    name: NameNode
    type_condition: NamedTypeNode


# Values


class ValueNode(Node):
    __slots__ = ()


class VariableNode(ValueNode):
    __slots__ = ("name",)

    name: NameNode


class IntValueNode(ValueNode):
    __slots__ = ("value",)

    value: str


class FloatValueNode(ValueNode):
    __slots__ = ("value",)

    value: str


class StringValueNode(ValueNode):
    __slots__ = "block", "value"

    value: str
    block: bool | None


class BooleanValueNode(ValueNode):
    __slots__ = ("value",)

    value: bool


class NullValueNode(ValueNode):
    __slots__ = ()


class EnumValueNode(ValueNode):
    __slots__ = ("value",)

    value: str


class ListValueNode(ValueNode):
    __slots__ = ("values",)

    values: tuple[ValueNode, ...]


class ConstListValueNode(ListValueNode):
    values: tuple[ConstValueNode, ...]


class ObjectValueNode(ValueNode):
    __slots__ = ("fields",)

    fields: tuple[ObjectFieldNode, ...]


class ConstObjectValueNode(ObjectValueNode):
    fields: tuple[ConstObjectFieldNode, ...]


class ObjectFieldNode(Node):
    __slots__ = "name", "value"

    name: NameNode
    value: ValueNode


class ConstObjectFieldNode(ObjectFieldNode):
    value: ConstValueNode


ConstValueNode: TypeAlias = Union[
    IntValueNode,
    FloatValueNode,
    StringValueNode,
    BooleanValueNode,
    NullValueNode,
    EnumValueNode,
    ConstListValueNode,
    ConstObjectValueNode,
]


# Directives


class DirectiveNode(Node):
    __slots__ = "arguments", "name"

    name: NameNode
    arguments: tuple[ArgumentNode, ...]


class ConstDirectiveNode(DirectiveNode):
    arguments: tuple[ConstArgumentNode, ...]


# Type Reference


class TypeNode(Node):
    __slots__ = ()


class NamedTypeNode(TypeNode):
    __slots__ = ("name",)

    name: NameNode


class ListTypeNode(TypeNode):
    __slots__ = ("type",)

    type: TypeNode


class NonNullTypeNode(TypeNode):
    __slots__ = ("type",)

    type: NamedTypeNode | ListTypeNode


# Type System Definition


class TypeSystemDefinitionNode(DefinitionNode):
    __slots__ = ()


class SchemaDefinitionNode(TypeSystemDefinitionNode):
    __slots__ = "description", "directives", "operation_types"

    description: StringValueNode | None
    directives: tuple[ConstDirectiveNode, ...]
    operation_types: tuple[OperationTypeDefinitionNode, ...]


class OperationTypeDefinitionNode(Node):
    __slots__ = "operation", "type"

    operation: OperationType
    type: NamedTypeNode


# Type Definition


class TypeDefinitionNode(TypeSystemDefinitionNode):
    __slots__ = "description", "directives", "name"

    description: StringValueNode | None
    name: NameNode
    directives: tuple[DirectiveNode, ...]


class ScalarTypeDefinitionNode(TypeDefinitionNode):
    __slots__ = ()

    directives: tuple[ConstDirectiveNode, ...]


class ObjectTypeDefinitionNode(TypeDefinitionNode):
    __slots__ = "fields", "interfaces"

    interfaces: tuple[NamedTypeNode, ...]
    directives: tuple[ConstDirectiveNode, ...]
    fields: tuple[FieldDefinitionNode, ...]


class FieldDefinitionNode(DefinitionNode):
    __slots__ = "arguments", "description", "directives", "name", "type"

    description: StringValueNode | None
    name: NameNode
    directives: tuple[ConstDirectiveNode, ...]
    arguments: tuple[InputValueDefinitionNode, ...]
    type: TypeNode


class InputValueDefinitionNode(DefinitionNode):
    __slots__ = "default_value", "description", "directives", "name", "type"

    description: StringValueNode | None
    name: NameNode
    directives: tuple[ConstDirectiveNode, ...]
    type: TypeNode
    default_value: ConstValueNode | None


class InterfaceTypeDefinitionNode(TypeDefinitionNode):
    __slots__ = "fields", "interfaces"

    fields: tuple[FieldDefinitionNode, ...]
    directives: tuple[ConstDirectiveNode, ...]
    interfaces: tuple[NamedTypeNode, ...]


class UnionTypeDefinitionNode(TypeDefinitionNode):
    __slots__ = ("types",)

    directives: tuple[ConstDirectiveNode, ...]
    types: tuple[NamedTypeNode, ...]


class EnumTypeDefinitionNode(TypeDefinitionNode):
    __slots__ = ("values",)

    directives: tuple[ConstDirectiveNode, ...]
    values: tuple[EnumValueDefinitionNode, ...]


class EnumValueDefinitionNode(DefinitionNode):
    __slots__ = "description", "directives", "name"

    description: StringValueNode | None
    name: NameNode
    directives: tuple[ConstDirectiveNode, ...]


class InputObjectTypeDefinitionNode(TypeDefinitionNode):
    __slots__ = ("fields",)

    directives: tuple[ConstDirectiveNode, ...]
    fields: tuple[InputValueDefinitionNode, ...]


# Directive Definitions


class DirectiveDefinitionNode(TypeSystemDefinitionNode):
    __slots__ = "arguments", "description", "locations", "name", "repeatable"

    description: StringValueNode | None
    name: NameNode
    arguments: tuple[InputValueDefinitionNode, ...]
    repeatable: bool
    locations: tuple[NameNode, ...]


# Type System Extensions


class SchemaExtensionNode(Node):
    __slots__ = "directives", "operation_types"

    directives: tuple[ConstDirectiveNode, ...]
    operation_types: tuple[OperationTypeDefinitionNode, ...]


# Type Extensions


class TypeExtensionNode(TypeSystemDefinitionNode):
    __slots__ = "directives", "name"

    name: NameNode
    directives: tuple[ConstDirectiveNode, ...]


TypeSystemExtensionNode: TypeAlias = Union[SchemaExtensionNode, TypeExtensionNode]


class ScalarTypeExtensionNode(TypeExtensionNode):
    __slots__ = ()


class ObjectTypeExtensionNode(TypeExtensionNode):
    __slots__ = "fields", "interfaces"

    interfaces: tuple[NamedTypeNode, ...]
    fields: tuple[FieldDefinitionNode, ...]


class InterfaceTypeExtensionNode(TypeExtensionNode):
    __slots__ = "fields", "interfaces"

    interfaces: tuple[NamedTypeNode, ...]
    fields: tuple[FieldDefinitionNode, ...]


class UnionTypeExtensionNode(TypeExtensionNode):
    __slots__ = ("types",)

    types: tuple[NamedTypeNode, ...]


class EnumTypeExtensionNode(TypeExtensionNode):
    __slots__ = ("values",)

    values: tuple[EnumValueDefinitionNode, ...]


class InputObjectTypeExtensionNode(TypeExtensionNode):
    __slots__ = ("fields",)

    fields: tuple[InputValueDefinitionNode, ...]
