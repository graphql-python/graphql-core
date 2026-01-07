"""GraphQL Abstract Syntax Tree"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Union

from ..pyutils import camel_to_snake

try:
    from typing import TypeAlias
except ImportError:  # Python < 3.10
    from typing_extensions import TypeAlias

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


class _KeysProperty:
    """Descriptor providing .keys at both class and instance level.

    For backwards compatibility only. Prefer using dataclasses.fields() instead.
    """

    def __get__(self, obj: object, cls: type) -> tuple[str, ...]:
        if not hasattr(cls, "__dataclass_fields__"):
            return ()  # During class construction
        return tuple(f.name for f in fields(cls))


@dataclass(frozen=True, repr=False, kw_only=True)
class Node:
    """AST nodes"""

    kind: ClassVar[str] = "ast"
    keys: ClassVar[tuple[str, ...]] = _KeysProperty()  # type: ignore[assignment]
    loc: Location | None = None

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
        """Convert node to a dictionary."""
        from ..utilities import ast_to_dict

        return ast_to_dict(self, locations)


# Name


@dataclass(frozen=True, repr=False, kw_only=True)
class NameNode(Node):
    value: str


# Base classes for node categories


@dataclass(frozen=True, repr=False, kw_only=True)
class DefinitionNode(Node):
    """Base class for all definition nodes."""


@dataclass(frozen=True, repr=False, kw_only=True)
class ExecutableDefinitionNode(DefinitionNode):
    """Base class for executable definition nodes."""

    selection_set: SelectionSetNode
    name: NameNode | None = None
    variable_definitions: tuple[VariableDefinitionNode, ...] = ()
    directives: tuple[DirectiveNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class SelectionNode(Node):
    """Base class for selection nodes."""

    directives: tuple[DirectiveNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class NullabilityAssertionNode(Node):
    """Base class for nullability assertion nodes."""


@dataclass(frozen=True, repr=False, kw_only=True)
class ValueNode(Node):
    """Base class for value nodes."""


@dataclass(frozen=True, repr=False, kw_only=True)
class TypeNode(Node):
    """Base class for type nodes."""


@dataclass(frozen=True, repr=False, kw_only=True)
class TypeSystemDefinitionNode(DefinitionNode):
    """Base class for type system definition nodes."""


@dataclass(frozen=True, repr=False, kw_only=True)
class TypeDefinitionNode(TypeSystemDefinitionNode):
    """Base class for type definition nodes."""

    name: NameNode
    description: StringValueNode | None = None
    directives: tuple[ConstDirectiveNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class TypeExtensionNode(TypeSystemDefinitionNode):
    """Base class for type extension nodes."""

    name: NameNode
    directives: tuple[ConstDirectiveNode, ...] = ()


# Type Reference nodes


@dataclass(frozen=True, repr=False, kw_only=True)
class NamedTypeNode(TypeNode):
    name: NameNode


@dataclass(frozen=True, repr=False, kw_only=True)
class ListTypeNode(TypeNode):
    type: TypeNode


@dataclass(frozen=True, repr=False, kw_only=True)
class NonNullTypeNode(TypeNode):
    type: NamedTypeNode | ListTypeNode


# Value nodes


@dataclass(frozen=True, repr=False, kw_only=True)
class VariableNode(ValueNode):
    name: NameNode


@dataclass(frozen=True, repr=False, kw_only=True)
class IntValueNode(ValueNode):
    value: str


@dataclass(frozen=True, repr=False, kw_only=True)
class FloatValueNode(ValueNode):
    value: str


@dataclass(frozen=True, repr=False, kw_only=True)
class StringValueNode(ValueNode):
    value: str
    block: bool | None = None


@dataclass(frozen=True, repr=False, kw_only=True)
class BooleanValueNode(ValueNode):
    value: bool


@dataclass(frozen=True, repr=False, kw_only=True)
class NullValueNode(ValueNode):
    """A null value node has no fields."""


@dataclass(frozen=True, repr=False, kw_only=True)
class EnumValueNode(ValueNode):
    value: str


@dataclass(frozen=True, repr=False, kw_only=True)
class ListValueNode(ValueNode):
    values: tuple[ValueNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class ConstListValueNode(ListValueNode):
    values: tuple[ConstValueNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class ObjectFieldNode(Node):
    name: NameNode
    value: ValueNode


@dataclass(frozen=True, repr=False, kw_only=True)
class ConstObjectFieldNode(ObjectFieldNode):
    value: ConstValueNode


@dataclass(frozen=True, repr=False, kw_only=True)
class ObjectValueNode(ValueNode):
    fields: tuple[ObjectFieldNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class ConstObjectValueNode(ObjectValueNode):
    fields: tuple[ConstObjectFieldNode, ...] = ()


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


# Directive nodes


@dataclass(frozen=True, repr=False, kw_only=True)
class DirectiveNode(Node):
    name: NameNode
    arguments: tuple[ArgumentNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class ConstDirectiveNode(DirectiveNode):
    arguments: tuple[ConstArgumentNode, ...] = ()


# Nullability Assertion nodes


@dataclass(frozen=True, repr=False, kw_only=True)
class ListNullabilityOperatorNode(NullabilityAssertionNode):
    nullability_assertion: NullabilityAssertionNode | None = None


@dataclass(frozen=True, repr=False, kw_only=True)
class NonNullAssertionNode(NullabilityAssertionNode):
    nullability_assertion: ListNullabilityOperatorNode | None = None


@dataclass(frozen=True, repr=False, kw_only=True)
class ErrorBoundaryNode(NullabilityAssertionNode):
    nullability_assertion: ListNullabilityOperatorNode | None = None


# Selection nodes


@dataclass(frozen=True, repr=False, kw_only=True)
class FieldNode(SelectionNode):
    name: NameNode
    alias: NameNode | None = None
    arguments: tuple[ArgumentNode, ...] = ()
    directives: tuple[DirectiveNode, ...] = ()
    nullability_assertion: NullabilityAssertionNode | None = None
    selection_set: SelectionSetNode | None = None


@dataclass(frozen=True, repr=False, kw_only=True)
class FragmentSpreadNode(SelectionNode):
    name: NameNode
    directives: tuple[DirectiveNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class InlineFragmentNode(SelectionNode):
    selection_set: SelectionSetNode
    type_condition: NamedTypeNode | None = None
    directives: tuple[DirectiveNode, ...] = ()


# Argument nodes


@dataclass(frozen=True, repr=False, kw_only=True)
class ArgumentNode(Node):
    name: NameNode
    value: ValueNode


@dataclass(frozen=True, repr=False, kw_only=True)
class ConstArgumentNode(ArgumentNode):
    value: ConstValueNode


# Selection Set


@dataclass(frozen=True, repr=False, kw_only=True)
class SelectionSetNode(Node):
    selections: tuple[SelectionNode, ...] = ()


# Variable Definition


@dataclass(frozen=True, repr=False, kw_only=True)
class VariableDefinitionNode(Node):
    variable: VariableNode
    type: TypeNode
    default_value: ConstValueNode | None = None
    directives: tuple[ConstDirectiveNode, ...] = ()


# Executable Definition nodes


@dataclass(frozen=True, repr=False, kw_only=True)
class OperationDefinitionNode(ExecutableDefinitionNode):
    operation: OperationType


@dataclass(frozen=True, repr=False, kw_only=True)
class FragmentDefinitionNode(ExecutableDefinitionNode):
    name: NameNode  # Required (overrides optional in parent)
    type_condition: NamedTypeNode


# Document


@dataclass(frozen=True, repr=False, kw_only=True)
class DocumentNode(Node):
    definitions: tuple[DefinitionNode, ...] = ()


# Type System Definition nodes


@dataclass(frozen=True, repr=False, kw_only=True)
class SchemaDefinitionNode(TypeSystemDefinitionNode):
    description: StringValueNode | None = None
    directives: tuple[ConstDirectiveNode, ...] = ()
    operation_types: tuple[OperationTypeDefinitionNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class OperationTypeDefinitionNode(Node):
    operation: OperationType
    type: NamedTypeNode


# Type Definition nodes


@dataclass(frozen=True, repr=False, kw_only=True)
class ScalarTypeDefinitionNode(TypeDefinitionNode):
    """Scalar type definition node - inherits name, description, directives."""


@dataclass(frozen=True, repr=False, kw_only=True)
class ObjectTypeDefinitionNode(TypeDefinitionNode):
    interfaces: tuple[NamedTypeNode, ...] = ()
    fields: tuple[FieldDefinitionNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class FieldDefinitionNode(DefinitionNode):
    name: NameNode
    type: TypeNode
    description: StringValueNode | None = None
    arguments: tuple[InputValueDefinitionNode, ...] = ()
    directives: tuple[ConstDirectiveNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class InputValueDefinitionNode(DefinitionNode):
    name: NameNode
    type: TypeNode
    description: StringValueNode | None = None
    default_value: ConstValueNode | None = None
    directives: tuple[ConstDirectiveNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class InterfaceTypeDefinitionNode(TypeDefinitionNode):
    interfaces: tuple[NamedTypeNode, ...] = ()
    fields: tuple[FieldDefinitionNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class UnionTypeDefinitionNode(TypeDefinitionNode):
    types: tuple[NamedTypeNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class EnumTypeDefinitionNode(TypeDefinitionNode):
    values: tuple[EnumValueDefinitionNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class EnumValueDefinitionNode(DefinitionNode):
    name: NameNode
    description: StringValueNode | None = None
    directives: tuple[ConstDirectiveNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class InputObjectTypeDefinitionNode(TypeDefinitionNode):
    fields: tuple[InputValueDefinitionNode, ...] = ()


# Directive Definition


@dataclass(frozen=True, repr=False, kw_only=True)
class DirectiveDefinitionNode(TypeSystemDefinitionNode):
    name: NameNode
    locations: tuple[NameNode, ...]
    description: StringValueNode | None = None
    arguments: tuple[InputValueDefinitionNode, ...] = ()
    repeatable: bool = False


# Type System Extension nodes


@dataclass(frozen=True, repr=False, kw_only=True)
class SchemaExtensionNode(Node):
    directives: tuple[ConstDirectiveNode, ...] = ()
    operation_types: tuple[OperationTypeDefinitionNode, ...] = ()


TypeSystemExtensionNode: TypeAlias = Union[SchemaExtensionNode, TypeExtensionNode]


# Type Extension nodes


@dataclass(frozen=True, repr=False, kw_only=True)
class ScalarTypeExtensionNode(TypeExtensionNode):
    """Scalar type extension node - inherits name, directives."""


@dataclass(frozen=True, repr=False, kw_only=True)
class ObjectTypeExtensionNode(TypeExtensionNode):
    interfaces: tuple[NamedTypeNode, ...] = ()
    fields: tuple[FieldDefinitionNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class InterfaceTypeExtensionNode(TypeExtensionNode):
    interfaces: tuple[NamedTypeNode, ...] = ()
    fields: tuple[FieldDefinitionNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class UnionTypeExtensionNode(TypeExtensionNode):
    types: tuple[NamedTypeNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class EnumTypeExtensionNode(TypeExtensionNode):
    values: tuple[EnumValueDefinitionNode, ...] = ()


@dataclass(frozen=True, repr=False, kw_only=True)
class InputObjectTypeExtensionNode(TypeExtensionNode):
    fields: tuple[InputValueDefinitionNode, ...] = ()
