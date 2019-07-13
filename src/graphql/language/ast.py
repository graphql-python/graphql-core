from copy import copy, deepcopy
from enum import Enum
from typing import List, NamedTuple, Optional, Union

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
    "FragmentSpreadNode",
    "InlineFragmentNode",
    "FragmentDefinitionNode",
    "ValueNode",
    "VariableNode",
    "IntValueNode",
    "FloatValueNode",
    "StringValueNode",
    "BooleanValueNode",
    "NullValueNode",
    "EnumValueNode",
    "ListValueNode",
    "ObjectValueNode",
    "ObjectFieldNode",
    "DirectiveNode",
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
]


class Token:
    __slots__ = ("kind", "start", "end", "line", "column", "prev", "next", "value")

    def __init__(
        self,
        kind: TokenKind,
        start: int,
        end: int,
        line: int,
        column: int,
        prev: "Token" = None,
        value: str = None,
    ) -> None:
        self.kind = kind
        self.start, self.end = start, end
        self.line, self.column = line, column
        self.prev: Optional[Token] = prev
        self.next: Optional[Token] = None
        self.value: Optional[str] = value

    def __str__(self):
        return self.desc

    def __repr__(self):
        """Print a simplified form when appearing in repr() or inspect()."""
        return f"<Token {self.desc} {self.line}/{self.column}>"

    def __inspect__(self):
        return repr(self)

    def __eq__(self, other):
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

    def __copy__(self):
        """Create a shallow copy of the token"""
        return self.__class__(
            self.kind,
            self.start,
            self.end,
            self.line,
            self.column,
            self.prev,
            self.value,
        )

    def __deepcopy__(self, memo):
        """Allow only shallow copies to avoid recursion."""
        return copy(self)

    @property
    def desc(self) -> str:
        """A helper property to describe a token as a string for debugging"""
        kind, value = self.kind.value, self.value
        return f"{kind} {value!r}" if value else kind


class Location(NamedTuple):
    """AST Location

    Contains a range of UTF-8 character offsets and token references that identify the
    region of the source from which the AST derived.
    """

    start: int  # character offset at which this Node begins
    end: int  # character offset at which this Node ends
    start_token: Token  # Token at which this Node begins
    end_token: Token  # Token at which this Node ends.
    source: Source  # Source document the AST represents

    def __str__(self):
        return f"{self.start}:{self.end}"

    def __repr__(self):
        """Print a simplified form when appearing in repr() or inspect()."""
        return f"<Location {self.start}:{self.end}>"

    def __inspect__(self):
        return repr(self)

    def __eq__(self, other):
        if isinstance(other, Location):
            return self.start == other.start and self.end == other.end
        elif isinstance(other, (list, tuple)) and len(other) == 2:
            return self.start == other[0] and self.end == other[1]
        return False

    def __ne__(self, other):
        return not self.__eq__(other)


class OperationType(Enum):

    QUERY = "query"
    MUTATION = "mutation"
    SUBSCRIPTION = "subscription"


# Base AST Node


class Node:
    """AST nodes"""

    __slots__ = ("loc",)

    loc: Optional[Location]

    kind: str = "ast"  # the kind of the node as a snake_case string
    keys = ["loc"]  # the names of the attributes of this node

    def __init__(self, **kwargs):
        """Initialize the node with the given keyword arguments."""
        for key in self.keys:
            setattr(self, key, kwargs.get(key))

    def __repr__(self):
        """Get a simple representation of the node."""
        name, loc = self.__class__.__name__, getattr(self, "loc", None)
        return f"{name} at {loc}" if loc else name

    def __eq__(self, other):
        """Test whether two nodes are equal (recursively)."""
        return (
            isinstance(other, Node)
            and self.__class__ == other.__class__
            and all(getattr(self, key) == getattr(other, key) for key in self.keys)
        )

    def __hash__(self):
        return id(self)

    def __copy__(self):
        """Create a shallow copy of the node."""
        return self.__class__(**{key: getattr(self, key) for key in self.keys})

    def __deepcopy__(self, memo):
        """Create a deep copy of the node"""
        # noinspection PyArgumentList
        return self.__class__(
            **{key: deepcopy(getattr(self, key), memo) for key in self.keys}
        )

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        name = cls.__name__
        if name.endswith("Node"):
            name = name[:-4]
        cls.kind = camel_to_snake(name)
        keys = []
        for base in cls.__bases__:
            # noinspection PyUnresolvedReferences
            keys.extend(base.keys)
        keys.extend(cls.__slots__)
        cls.keys = keys


# Name


class NameNode(Node):
    __slots__ = ("value",)

    value: str


# Document


class DocumentNode(Node):
    __slots__ = ("definitions",)

    definitions: List["DefinitionNode"]


class DefinitionNode(Node):
    __slots__ = ()


class ExecutableDefinitionNode(DefinitionNode):
    __slots__ = "name", "directives", "variable_definitions", "selection_set"

    name: Optional[NameNode]
    directives: Optional[List["DirectiveNode"]]
    variable_definitions: List["VariableDefinitionNode"]
    selection_set: "SelectionSetNode"


class OperationDefinitionNode(ExecutableDefinitionNode):
    __slots__ = ("operation",)

    operation: OperationType


class VariableDefinitionNode(Node):
    __slots__ = "variable", "type", "default_value", "directives"

    variable: "VariableNode"
    type: "TypeNode"
    default_value: Optional["ValueNode"]
    directives: Optional[List["DirectiveNode"]]


class SelectionSetNode(Node):
    __slots__ = ("selections",)

    selections: List["SelectionNode"]


class SelectionNode(Node):
    __slots__ = ("directives",)

    directives: Optional[List["DirectiveNode"]]


class FieldNode(SelectionNode):
    __slots__ = "alias", "name", "arguments", "selection_set"

    alias: Optional[NameNode]
    name: NameNode
    arguments: Optional[List["ArgumentNode"]]
    selection_set: Optional[SelectionSetNode]


class ArgumentNode(Node):
    __slots__ = "name", "value"

    name: NameNode
    value: "ValueNode"


# Fragments


class FragmentSpreadNode(SelectionNode):
    __slots__ = ("name",)

    name: NameNode


class InlineFragmentNode(SelectionNode):
    __slots__ = "type_condition", "selection_set"

    type_condition: "NamedTypeNode"
    selection_set: SelectionSetNode


class FragmentDefinitionNode(ExecutableDefinitionNode):
    __slots__ = ("type_condition",)

    name: NameNode
    type_condition: "NamedTypeNode"


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
    __slots__ = "value", "block"

    value: str
    block: Optional[bool]


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

    values: List[ValueNode]


class ObjectValueNode(ValueNode):
    __slots__ = ("fields",)

    fields: List["ObjectFieldNode"]


class ObjectFieldNode(Node):
    __slots__ = "name", "value"

    name: NameNode
    value: ValueNode


# Directives


class DirectiveNode(Node):
    __slots__ = "name", "arguments"

    name: NameNode
    arguments: List[ArgumentNode]


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

    type: Union[NamedTypeNode, ListTypeNode]


# Type System Definition


class TypeSystemDefinitionNode(DefinitionNode):
    __slots__ = ()


class SchemaDefinitionNode(TypeSystemDefinitionNode):
    __slots__ = "directives", "operation_types"

    directives: Optional[List[DirectiveNode]]
    operation_types: List["OperationTypeDefinitionNode"]


class OperationTypeDefinitionNode(Node):
    __slots__ = "operation", "type"

    operation: OperationType
    type: NamedTypeNode


# Type Definition


class TypeDefinitionNode(TypeSystemDefinitionNode):
    __slots__ = "description", "name", "directives"

    description: Optional[StringValueNode]
    name: NameNode
    directives: Optional[List[DirectiveNode]]


class ScalarTypeDefinitionNode(TypeDefinitionNode):
    __slots__ = ()


class ObjectTypeDefinitionNode(TypeDefinitionNode):
    __slots__ = "interfaces", "fields"

    interfaces: Optional[List[NamedTypeNode]]
    fields: Optional[List["FieldDefinitionNode"]]


class FieldDefinitionNode(TypeDefinitionNode):
    __slots__ = "arguments", "type"

    arguments: Optional[List["InputValueDefinitionNode"]]
    type: TypeNode


class InputValueDefinitionNode(TypeDefinitionNode):
    __slots__ = "type", "default_value"

    type: TypeNode
    default_value: Optional[ValueNode]


class InterfaceTypeDefinitionNode(TypeDefinitionNode):
    __slots__ = ("fields",)

    fields: Optional[List["FieldDefinitionNode"]]


class UnionTypeDefinitionNode(TypeDefinitionNode):
    __slots__ = ("types",)

    types: Optional[List[NamedTypeNode]]


class EnumTypeDefinitionNode(TypeDefinitionNode):
    __slots__ = ("values",)

    values: Optional[List["EnumValueDefinitionNode"]]


class EnumValueDefinitionNode(TypeDefinitionNode):
    __slots__ = ()


class InputObjectTypeDefinitionNode(TypeDefinitionNode):
    __slots__ = ("fields",)

    fields: Optional[List[InputValueDefinitionNode]]


# Directive Definitions


class DirectiveDefinitionNode(TypeSystemDefinitionNode):
    __slots__ = "description", "name", "arguments", "repeatable", "locations"

    description: Optional[StringValueNode]
    name: NameNode
    arguments: Optional[List[InputValueDefinitionNode]]
    repeatable: bool
    locations: List[NameNode]


# Type System Extensions


class SchemaExtensionNode(Node):
    __slots__ = "directives", "operation_types"

    directives: Optional[List[DirectiveNode]]
    operation_types: Optional[List[OperationTypeDefinitionNode]]


# Type Extensions


class TypeExtensionNode(TypeSystemDefinitionNode):
    __slots__ = "name", "directives"

    name: NameNode
    directives: Optional[List[DirectiveNode]]


TypeSystemExtensionNode = Union[SchemaExtensionNode, TypeExtensionNode]


class ScalarTypeExtensionNode(TypeExtensionNode):
    __slots__ = ()


class ObjectTypeExtensionNode(TypeExtensionNode):
    __slots__ = "interfaces", "fields"

    interfaces: Optional[List[NamedTypeNode]]
    fields: Optional[List[FieldDefinitionNode]]


class InterfaceTypeExtensionNode(TypeExtensionNode):
    __slots__ = ("fields",)

    fields: Optional[List[FieldDefinitionNode]]


class UnionTypeExtensionNode(TypeExtensionNode):
    __slots__ = ("types",)

    types: Optional[List[NamedTypeNode]]


class EnumTypeExtensionNode(TypeExtensionNode):
    __slots__ = ("values",)

    values: Optional[List[EnumValueDefinitionNode]]


class InputObjectTypeExtensionNode(TypeExtensionNode):
    __slots__ = ("fields",)

    fields: Optional[List[InputValueDefinitionNode]]
