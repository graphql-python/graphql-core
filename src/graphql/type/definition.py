from collections.abc import Sequence as AbstractSequence
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    NamedTuple,
    Optional,
    Sequence,
    TYPE_CHECKING,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from ..error import INVALID, InvalidType
from ..language import (
    EnumTypeDefinitionNode,
    EnumValueDefinitionNode,
    EnumTypeExtensionNode,
    EnumValueNode,
    FieldDefinitionNode,
    FieldNode,
    FragmentDefinitionNode,
    InputObjectTypeDefinitionNode,
    InputObjectTypeExtensionNode,
    InputValueDefinitionNode,
    InterfaceTypeDefinitionNode,
    InterfaceTypeExtensionNode,
    ObjectTypeDefinitionNode,
    ObjectTypeExtensionNode,
    OperationDefinitionNode,
    ScalarTypeDefinitionNode,
    ScalarTypeExtensionNode,
    TypeDefinitionNode,
    TypeExtensionNode,
    UnionTypeDefinitionNode,
    UnionTypeExtensionNode,
    ValueNode,
)
from ..pyutils import AwaitableOrValue, FrozenList, cached_property, inspect
from ..utilities.value_from_ast_untyped import value_from_ast_untyped

if TYPE_CHECKING:  # pragma: no cover
    from .schema import GraphQLSchema  # noqa: F401

__all__ = [
    "is_type",
    "is_scalar_type",
    "is_object_type",
    "is_interface_type",
    "is_union_type",
    "is_enum_type",
    "is_input_object_type",
    "is_list_type",
    "is_non_null_type",
    "is_input_type",
    "is_output_type",
    "is_leaf_type",
    "is_composite_type",
    "is_abstract_type",
    "is_wrapping_type",
    "is_nullable_type",
    "is_named_type",
    "is_required_argument",
    "is_required_input_field",
    "assert_type",
    "assert_scalar_type",
    "assert_object_type",
    "assert_interface_type",
    "assert_union_type",
    "assert_enum_type",
    "assert_input_object_type",
    "assert_list_type",
    "assert_non_null_type",
    "assert_input_type",
    "assert_output_type",
    "assert_leaf_type",
    "assert_composite_type",
    "assert_abstract_type",
    "assert_wrapping_type",
    "assert_nullable_type",
    "assert_named_type",
    "get_nullable_type",
    "get_named_type",
    "GraphQLAbstractType",
    "GraphQLArgument",
    "GraphQLArgumentMap",
    "GraphQLCompositeType",
    "GraphQLEnumType",
    "GraphQLEnumValue",
    "GraphQLEnumValueMap",
    "GraphQLField",
    "GraphQLFieldMap",
    "GraphQLFieldResolver",
    "GraphQLInputField",
    "GraphQLInputFieldMap",
    "GraphQLInputObjectType",
    "GraphQLInputType",
    "GraphQLInterfaceType",
    "GraphQLIsTypeOfFn",
    "GraphQLLeafType",
    "GraphQLList",
    "GraphQLNamedType",
    "GraphQLNullableType",
    "GraphQLNonNull",
    "GraphQLResolveInfo",
    "GraphQLScalarType",
    "GraphQLScalarSerializer",
    "GraphQLScalarValueParser",
    "GraphQLScalarLiteralParser",
    "GraphQLObjectType",
    "GraphQLOutputType",
    "GraphQLType",
    "GraphQLTypeResolver",
    "GraphQLUnionType",
    "GraphQLWrappingType",
    "ResponsePath",
    "Thunk",
]


class GraphQLType:
    """Base class for all GraphQL types"""

    # Note: We don't use slots for GraphQLType objects because memory considerations
    # are not really important for the schema definition and it would make caching
    # properties slower or more complicated.


# There are predicates for each kind of GraphQL type.


def is_type(type_: Any) -> bool:
    return isinstance(type_, GraphQLType)


def assert_type(type_: Any) -> GraphQLType:
    if not is_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL type.")
    return cast(GraphQLType, type_)


# These types wrap and modify other types

GT = TypeVar("GT", bound=GraphQLType)


class GraphQLWrappingType(GraphQLType, Generic[GT]):
    """Base class for all GraphQL wrapping types"""

    of_type: GT

    def __init__(self, type_: GT) -> None:
        if not is_type(type_):
            raise TypeError(
                f"Can only create a wrapper for a GraphQLType, but got: {type_}."
            )
        self.of_type = type_

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.of_type!r}>"


def is_wrapping_type(type_: Any) -> bool:
    return isinstance(type_, GraphQLWrappingType)


def assert_wrapping_type(type_: Any) -> GraphQLWrappingType:
    if not is_wrapping_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL wrapping type.")
    return cast(GraphQLWrappingType, type_)


# These named types do not include modifiers like List or NonNull.


class GraphQLNamedType(GraphQLType):
    """Base class for all GraphQL named types"""

    name: str
    description: Optional[str]
    ast_node: Optional[TypeDefinitionNode]
    extension_ast_nodes: Optional[FrozenList[TypeExtensionNode]]

    def __init__(
        self,
        name: str,
        description: str = None,
        ast_node: TypeDefinitionNode = None,
        extension_ast_nodes: Sequence[TypeExtensionNode] = None,
    ) -> None:
        if not name:
            raise TypeError("Must provide name.")
        if not isinstance(name, str):
            raise TypeError("The name must be a string.")
        if description is not None and not isinstance(description, str):
            raise TypeError("The description must be a string.")
        if ast_node and not isinstance(ast_node, TypeDefinitionNode):
            raise TypeError(f"{name} AST node must be a TypeDefinitionNode.")
        if extension_ast_nodes:
            if not isinstance(extension_ast_nodes, AbstractSequence) or not all(
                isinstance(node, TypeExtensionNode) for node in extension_ast_nodes
            ):
                raise TypeError(
                    f"{name} extension AST nodes must be specified"
                    " as a sequence of TypeExtensionNode instances."
                )
            if not isinstance(extension_ast_nodes, FrozenList):
                extension_ast_nodes = FrozenList(extension_ast_nodes)
        else:
            extension_ast_nodes = None
        self.name = name
        self.description = description
        self.ast_node = ast_node
        self.extension_ast_nodes = extension_ast_nodes

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name!r}>"

    def __str__(self):
        return self.name

    def to_kwargs(self) -> Dict[str, Any]:
        return dict(
            name=self.name,
            description=self.description,
            ast_node=self.ast_node,
            extension_ast_nodes=self.extension_ast_nodes or FrozenList(),
        )


def is_named_type(type_: Any) -> bool:
    return isinstance(type_, GraphQLNamedType)


def assert_named_type(type_: Any) -> GraphQLNamedType:
    if not is_named_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL named type.")
    return cast(GraphQLNamedType, type_)


@overload
def get_named_type(type_: None) -> None:
    ...  # pragma: no cover


@overload  # noqa: F811 (pycqa/flake8#423)
def get_named_type(type_: GraphQLType) -> GraphQLNamedType:
    ...  # pragma: no cover


def get_named_type(type_):  # noqa: F811
    """Unwrap possible wrapping type"""
    if type_:
        unwrapped_type = type_
        while is_wrapping_type(unwrapped_type):
            unwrapped_type = cast(GraphQLWrappingType, unwrapped_type)
            unwrapped_type = unwrapped_type.of_type
        return cast(GraphQLNamedType, unwrapped_type)
    return None


def resolve_thunk(thunk: Any) -> Any:
    """Resolve the given thunk.

    Used while defining GraphQL types to allow for circular references in otherwise
    immutable type definitions.
    """
    return thunk() if callable(thunk) else thunk


# Unfortunately these types cannot be specified any better in Python:
GraphQLScalarSerializer = Callable
GraphQLScalarValueParser = Callable
GraphQLScalarLiteralParser = Callable


class GraphQLScalarType(GraphQLNamedType):
    """Scalar Type Definition

    The leaf values of any request and input values to arguments are Scalars (or Enums)
    and are defined with a name and a series of functions used to parse input from ast
    or variables and to ensure validity.

    If a type's serialize function does not return a value (i.e. it returns `None`),
    then no error will be included in the response.

    Example:

        def serialize_odd(value):
            if value % 2 == 1:
                return value

        odd_type = GraphQLScalarType('Odd', serialize=serialize_odd)

    """

    ast_node: Optional[ScalarTypeDefinitionNode]
    extension_ast_nodes: Optional[FrozenList[ScalarTypeExtensionNode]]

    def __init__(
        self,
        name: str,
        serialize: GraphQLScalarSerializer = None,
        description: str = None,
        parse_value: GraphQLScalarValueParser = None,
        parse_literal: GraphQLScalarLiteralParser = None,
        ast_node: ScalarTypeDefinitionNode = None,
        extension_ast_nodes: Sequence[ScalarTypeExtensionNode] = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        if serialize is not None and not callable(serialize):
            raise TypeError(
                f"{name} must provide 'serialize' as a function."
                " If this custom Scalar is also used as an input type,"
                " ensure 'parse_value' and 'parse_literal' functions"
                " are also provided."
            )
        if parse_literal is not None and (
            not callable(parse_literal)
            or (parse_value is None or not callable(parse_value))
        ):
            raise TypeError(
                f"{name} must provide"
                " both 'parse_value' and 'parse_literal' as functions."
            )
        if ast_node and not isinstance(ast_node, ScalarTypeDefinitionNode):
            raise TypeError(f"{name} AST node must be a ScalarTypeDefinitionNode.")
        if extension_ast_nodes and not all(
            isinstance(node, ScalarTypeExtensionNode) for node in extension_ast_nodes
        ):
            raise TypeError(
                f"{name} extension AST nodes must be specified"
                " as a sequence of ScalarTypeExtensionNode instances."
            )
        if serialize is not None:
            self.serialize = serialize
        if parse_value is not None:
            self.parse_value = parse_value
        if parse_literal is not None:
            self.parse_literal = parse_literal

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name!r}>"

    def __str__(self):
        return self.name

    @staticmethod
    def serialize(value: Any) -> Any:
        """Serializes an internal value to include in a response.

        This default method just passes the value through and should be replaced
        with a more specific version when creating a scalar type.
        """
        return value

    @staticmethod
    def parse_value(value: Any) -> Any:
        """Parses an externally provided value to use as an input.

        This default method just passes the value through and should be replaced
        with a more specific version when creating a scalar type.
        """
        return value

    def parse_literal(  # type: ignore
        self, node: ValueNode, _variables: Dict[str, Any] = None
    ) -> Any:
        """Parses an externally provided literal value to use as an input.

        This default method uses the parse_value method and should be replaced
        with a more specific version when creating a scalar type.
        """
        return self.parse_value(value_from_ast_untyped(node))

    def to_kwargs(self) -> Dict[str, Any]:
        return dict(
            **super().to_kwargs(),
            serialize=None
            if self.serialize is GraphQLScalarType.serialize
            else self.serialize,
            parse_value=None
            if self.parse_value is GraphQLScalarType.parse_value
            else self.parse_value,
            parse_literal=None
            if getattr(self.parse_literal, "__func__")
            is GraphQLScalarType.parse_literal
            else self.parse_literal,
        )


def is_scalar_type(type_: Any) -> bool:
    return isinstance(type_, GraphQLScalarType)


def assert_scalar_type(type_: Any) -> GraphQLScalarType:
    if not is_scalar_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Scalar type.")
    return cast(GraphQLScalarType, type_)


GraphQLArgumentMap = Dict[str, "GraphQLArgument"]


class GraphQLField:
    """Definition of a GraphQL field"""

    type: "GraphQLOutputType"
    args: GraphQLArgumentMap
    resolve: Optional["GraphQLFieldResolver"]
    subscribe: Optional["GraphQLFieldResolver"]
    description: Optional[str]
    deprecation_reason: Optional[str]
    ast_node: Optional[FieldDefinitionNode]

    def __init__(
        self,
        type_: "GraphQLOutputType",
        args: GraphQLArgumentMap = None,
        resolve: "GraphQLFieldResolver" = None,
        subscribe: "GraphQLFieldResolver" = None,
        description: str = None,
        deprecation_reason: str = None,
        ast_node: FieldDefinitionNode = None,
    ) -> None:
        if not is_output_type(type_):
            raise TypeError("Field type must be an output type.")
        if args is None:
            args = {}
        elif not isinstance(args, dict):
            raise TypeError("Field args must be a dict with argument names as keys.")
        elif not all(
            isinstance(value, GraphQLArgument) or is_input_type(value)
            for value in args.values()
        ):
            raise TypeError(
                "Field args must be GraphQLArguments or input type objects."
            )
        else:
            args = {
                name: value
                if isinstance(value, GraphQLArgument)
                else GraphQLArgument(cast(GraphQLInputType, value))
                for name, value in args.items()
            }
        if resolve is not None and not callable(resolve):
            raise TypeError(
                "Field resolver must be a function if provided, "
                f" but got: {inspect(resolve)}."
            )
        if description is not None and not isinstance(description, str):
            raise TypeError("The description must be a string.")
        if deprecation_reason is not None and not isinstance(deprecation_reason, str):
            raise TypeError("The deprecation reason must be a string.")
        if ast_node and not isinstance(ast_node, FieldDefinitionNode):
            raise TypeError("Field AST node must be a FieldDefinitionNode.")
        self.type = type_
        self.args = args or {}
        self.resolve = resolve
        self.subscribe = subscribe
        self.deprecation_reason = deprecation_reason
        self.description = description
        self.ast_node = ast_node

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.type!r}>"

    def __str__(self):
        return f"Field: {self.type}"

    def __eq__(self, other):
        return self is other or (
            isinstance(other, GraphQLField)
            and self.type == other.type
            and self.args == other.args
            and self.resolve == other.resolve
            and self.description == other.description
            and self.deprecation_reason == other.deprecation_reason
        )

    def to_kwargs(self) -> Dict[str, Any]:
        return dict(
            type_=self.type,
            args=self.args.copy() if self.args else None,
            resolve=self.resolve,
            subscribe=self.subscribe,
            description=self.description,
            deprecation_reason=self.deprecation_reason,
            ast_node=self.ast_node,
        )

    @property
    def is_deprecated(self) -> bool:
        return bool(self.deprecation_reason)


class ResponsePath(NamedTuple):

    prev: Any  # Optional['ResponsePath'] (python/mypy/issues/731))
    key: Union[str, int]


class GraphQLResolveInfo(NamedTuple):
    """Collection of information passed to the resolvers.

    This is always passed as the first argument to the resolvers.

    Note that contrary to the JavaScript implementation, the context (commonly used to
    represent an authenticated user, or request-specific caches) is included here and
    not passed as an additional argument.
    """

    field_name: str
    field_nodes: List[FieldNode]
    return_type: "GraphQLOutputType"
    parent_type: "GraphQLObjectType"
    path: ResponsePath
    schema: "GraphQLSchema"
    fragments: Dict[str, FragmentDefinitionNode]
    root_value: Any
    operation: OperationDefinitionNode
    variable_values: Dict[str, Any]
    context: Any


# Note: Contrary to the Javascript implementation of GraphQLFieldResolver,
# the context is passed as part of the GraphQLResolveInfo and any arguments
# are passed individually as keyword arguments.
GraphQLFieldResolverWithoutArgs = Callable[[Any, GraphQLResolveInfo], Any]
# Unfortunately there is currently no syntax to indicate optional or keyword
# arguments in Python, so we also allow any other Callable as a workaround:
GraphQLFieldResolver = Callable[..., Any]

# Note: Contrary to the Javascript implementation of GraphQLTypeResolver,
# the context is passed as part of the GraphQLResolveInfo:
GraphQLTypeResolver = Callable[
    [Any, GraphQLResolveInfo, "GraphQLAbstractType"],
    AwaitableOrValue[Optional[Union["GraphQLObjectType", str]]],
]

# Note: Contrary to the Javascript implementation of GraphQLIsTypeOfFn,
# the context is passed as part of the GraphQLResolveInfo:
GraphQLIsTypeOfFn = Callable[[Any, GraphQLResolveInfo], AwaitableOrValue[bool]]


class GraphQLArgument:
    """Definition of a GraphQL argument"""

    type: "GraphQLInputType"
    default_value: Any
    description: Optional[str]
    out_name: Optional[str]  # for transforming names (extension of GraphQL.js)
    ast_node: Optional[InputValueDefinitionNode]

    def __init__(
        self,
        type_: "GraphQLInputType",
        default_value: Any = INVALID,
        description: str = None,
        out_name: str = None,
        ast_node: InputValueDefinitionNode = None,
    ) -> None:
        if not is_input_type(type_):
            raise TypeError(f"Argument type must be a GraphQL input type.")
        if description is not None and not isinstance(description, str):
            raise TypeError("Argument description must be a string.")
        if out_name is not None and not isinstance(out_name, str):
            raise TypeError("Argument out name must be a string.")
        if ast_node and not isinstance(ast_node, InputValueDefinitionNode):
            raise TypeError("Argument AST node must be an InputValueDefinitionNode.")
        self.type = type_
        self.default_value = default_value
        self.description = description
        self.out_name = out_name
        self.ast_node = ast_node

    def __eq__(self, other):
        return self is other or (
            isinstance(other, GraphQLArgument)
            and self.type == other.type
            and self.default_value == other.default_value
            and self.description == other.description
            and self.out_name == other.out_name
        )

    def to_kwargs(self) -> Dict[str, Any]:
        return dict(
            type_=self.type,
            default_value=self.default_value,
            description=self.description,
            out_name=self.out_name,
            ast_node=self.ast_node,
        )


def is_required_argument(arg: GraphQLArgument) -> bool:
    return is_non_null_type(arg.type) and arg.default_value is INVALID


T = TypeVar("T")
Thunk = Union[Callable[[], T], T]

GraphQLFieldMap = Dict[str, GraphQLField]


class GraphQLObjectType(GraphQLNamedType):
    """Object Type Definition

    Almost all of the GraphQL types you define will be object types. Object types have
    a name, but most importantly describe their fields.

    Example::

        AddressType = GraphQLObjectType('Address', {
            'street': GraphQLField(GraphQLString),
            'number': GraphQLField(GraphQLInt),
            'formatted': GraphQLField(GraphQLString,
                lambda obj, info, **args: f'{obj.number} {obj.street}')
        })

    When two types need to refer to each other, or a type needs to refer to itself in
    a field, you can use a lambda function with no arguments (a so-called "thunk")
    to supply the fields lazily.

    Example::

        PersonType = GraphQLObjectType('Person', lambda: {
            'name': GraphQLField(GraphQLString),
            'bestFriend': GraphQLField(PersonType)
        })

    """

    is_type_of: Optional[GraphQLIsTypeOfFn]
    ast_node: Optional[ObjectTypeDefinitionNode]
    extension_ast_nodes: Optional[FrozenList[ObjectTypeExtensionNode]]

    def __init__(
        self,
        name: str,
        fields: Thunk[GraphQLFieldMap],
        interfaces: Thunk[Sequence["GraphQLInterfaceType"]] = None,
        is_type_of: GraphQLIsTypeOfFn = None,
        description: str = None,
        ast_node: ObjectTypeDefinitionNode = None,
        extension_ast_nodes: Sequence[ObjectTypeExtensionNode] = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        if is_type_of is not None and not callable(is_type_of):
            raise TypeError(
                f"{name} must provide 'is_type_of' as a function,"
                f" but got: {inspect(is_type_of)}."
            )
        if ast_node and not isinstance(ast_node, ObjectTypeDefinitionNode):
            raise TypeError(f"{name} AST node must be an ObjectTypeDefinitionNode.")
        if extension_ast_nodes and not all(
            isinstance(node, ObjectTypeExtensionNode) for node in extension_ast_nodes
        ):
            raise TypeError(
                f"{name} extension AST nodes must be specified"
                " as a sequence of ObjectTypeExtensionNode instances."
            )
        self._fields = fields
        self._interfaces = interfaces
        self.is_type_of = is_type_of

    def to_kwargs(self) -> Dict[str, Any]:
        return dict(
            **super().to_kwargs(),
            fields=self.fields.copy(),
            interfaces=self.interfaces,
            is_type_of=self.is_type_of,
        )

    @cached_property
    def fields(self) -> GraphQLFieldMap:
        """Get provided fields, wrapping them as GraphQLFields if needed."""
        try:
            fields = resolve_thunk(self._fields)
        except Exception as error:
            raise TypeError(f"{self.name} fields cannot be resolved: {error}")
        if not isinstance(fields, dict) or not all(
            isinstance(key, str) for key in fields
        ):
            raise TypeError(
                f"{self.name} fields must be specified"
                " as a dict with field names as keys."
            )
        if not all(
            isinstance(value, GraphQLField) or is_output_type(value)
            for value in fields.values()
        ):
            raise TypeError(
                f"{self.name} fields must be GraphQLField or output type objects."
            )
        return {
            name: value if isinstance(value, GraphQLField) else GraphQLField(value)
            for name, value in fields.items()
        }

    @cached_property
    def interfaces(self) -> List["GraphQLInterfaceType"]:
        """Get provided interfaces."""
        try:
            interfaces: Sequence["GraphQLInterfaceType"] = resolve_thunk(
                self._interfaces
            )
        except Exception as error:
            raise TypeError(f"{self.name} interfaces cannot be resolved: {error}")
        if interfaces is None:
            interfaces = []
        elif not isinstance(interfaces, AbstractSequence) or not all(
            isinstance(value, GraphQLInterfaceType) for value in interfaces
        ):
            raise TypeError(
                f"{self.name} interfaces must be specified"
                " as a sequence of GraphQLInterfaceType instances."
            )
        return list(interfaces)


def is_object_type(type_: Any) -> bool:
    return isinstance(type_, GraphQLObjectType)


def assert_object_type(type_: Any) -> GraphQLObjectType:
    if not is_object_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Object type.")
    return cast(GraphQLObjectType, type_)


class GraphQLInterfaceType(GraphQLNamedType):
    """Interface Type Definition

    When a field can return one of a heterogeneous set of types, an Interface type
    is used to describe what types are possible, what fields are in common across
    all types, as well as a function to determine which type is actually used when
    the field is resolved.

    Example::

        EntityType = GraphQLInterfaceType('Entity', {
                'name': GraphQLField(GraphQLString),
            })
    """

    resolve_type: Optional[GraphQLTypeResolver]
    ast_node: Optional[InterfaceTypeDefinitionNode]
    extension_ast_nodes: Optional[FrozenList[InterfaceTypeExtensionNode]]

    def __init__(
        self,
        name: str,
        fields: Thunk[GraphQLFieldMap] = None,
        resolve_type: GraphQLTypeResolver = None,
        description: str = None,
        ast_node: InterfaceTypeDefinitionNode = None,
        extension_ast_nodes: Sequence[InterfaceTypeExtensionNode] = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        if resolve_type is not None and not callable(resolve_type):
            raise TypeError(
                f"{name} must provide 'resolve_type' as a function,"
                f" but got: {inspect(resolve_type)}."
            )
        if ast_node and not isinstance(ast_node, InterfaceTypeDefinitionNode):
            raise TypeError(f"{name} AST node must be an InterfaceTypeDefinitionNode.")
        if extension_ast_nodes and not all(
            isinstance(node, InterfaceTypeExtensionNode) for node in extension_ast_nodes
        ):
            raise TypeError(
                f"{name} extension AST nodes must be specified"
                " as a sequence of InterfaceTypeExtensionNode instances."
            )
        self._fields = fields
        self.resolve_type = resolve_type
        self.description = description

    def to_kwargs(self) -> Dict[str, Any]:
        return dict(
            **super().to_kwargs(),
            fields=self.fields.copy(),
            resolve_type=self.resolve_type,
        )

    @cached_property
    def fields(self) -> GraphQLFieldMap:
        """Get provided fields, wrapping them as GraphQLFields if needed."""
        try:
            fields = resolve_thunk(self._fields)
        except Exception as error:
            raise TypeError(f"{self.name} fields cannot be resolved: {error}")
        if not isinstance(fields, dict) or not all(
            isinstance(key, str) for key in fields
        ):
            raise TypeError(
                f"{self.name} fields must be specified"
                " as a dict with field names as keys."
            )
        if not all(
            isinstance(value, GraphQLField) or is_output_type(value)
            for value in fields.values()
        ):
            raise TypeError(
                f"{self.name} fields must be GraphQLField or output type objects."
            )
        return {
            name: value if isinstance(value, GraphQLField) else GraphQLField(value)
            for name, value in fields.items()
        }


def is_interface_type(type_: Any) -> bool:
    return isinstance(type_, GraphQLInterfaceType)


def assert_interface_type(type_: Any) -> GraphQLInterfaceType:
    if not is_interface_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Interface type.")
    return cast(GraphQLInterfaceType, type_)


class GraphQLUnionType(GraphQLNamedType):
    """Union Type Definition

    When a field can return one of a heterogeneous set of types, a Union type is used
    to describe what types are possible as well as providing a function to determine
    which type is actually used when the field is resolved.

    Example:

        class PetType(GraphQLUnionType):
            name = 'Pet'
            types = [DogType, CatType]

            def resolve_type(self, value, _type):
                if isinstance(value, Dog):
                    return DogType()
                if isinstance(value, Cat):
                    return CatType()
    """

    resolve_type: Optional[GraphQLTypeResolver]
    ast_node: Optional[UnionTypeDefinitionNode]
    extension_ast_nodes: Optional[FrozenList[UnionTypeExtensionNode]]

    def __init__(
        self,
        name,
        types: Thunk[Sequence[GraphQLObjectType]],
        resolve_type: GraphQLTypeResolver = None,
        description: str = None,
        ast_node: UnionTypeDefinitionNode = None,
        extension_ast_nodes: Sequence[UnionTypeExtensionNode] = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        if resolve_type is not None and not callable(resolve_type):
            raise TypeError(
                f"{name} must provide 'resolve_type' as a function,"
                f" but got: {inspect(resolve_type)}."
            )
        if ast_node and not isinstance(ast_node, UnionTypeDefinitionNode):
            raise TypeError(f"{name} AST node must be a UnionTypeDefinitionNode.")
        if extension_ast_nodes and not all(
            isinstance(node, UnionTypeExtensionNode) for node in extension_ast_nodes
        ):
            raise TypeError(
                f"{name} extension AST nodes must be specified"
                " as a sequence of UnionTypeExtensionNode instances."
            )
        self._types = types
        self.resolve_type = resolve_type

    def to_kwargs(self) -> Dict[str, Any]:
        return dict(
            **super().to_kwargs(), types=self.types, resolve_type=self.resolve_type
        )

    @cached_property
    def types(self) -> List[GraphQLObjectType]:
        """Get provided types."""
        try:
            types: Sequence[GraphQLObjectType] = resolve_thunk(self._types)
        except Exception as error:
            raise TypeError(f"{self.name} types cannot be resolved: {error}")
        if types is None:
            types = []
        elif not isinstance(types, AbstractSequence) or not all(
            isinstance(value, GraphQLObjectType) for value in types
        ):
            raise TypeError(
                f"{self.name} types must be specified"
                " as a sequence of GraphQLObjectType instances."
            )
        return list(types)


def is_union_type(type_: Any) -> bool:
    return isinstance(type_, GraphQLUnionType)


def assert_union_type(type_: Any) -> GraphQLUnionType:
    if not is_union_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Union type.")
    return cast(GraphQLUnionType, type_)


GraphQLEnumValueMap = Dict[str, "GraphQLEnumValue"]


class GraphQLEnumType(GraphQLNamedType):
    """Enum Type Definition

    Some leaf values of requests and input values are Enums. GraphQL serializes Enum
    values as strings, however internally Enums can be represented by any kind of type,
    often integers. They can also be provided as a Python Enum.

    Example::

        RGBType = GraphQLEnumType('RGB', {
            'RED': 0,
            'GREEN': 1,
            'BLUE': 2
        })

    Example using a Python Enum::

        class RGBEnum(enum.Enum):
            RED = 0
            GREEN = 1
            BLUE = 2

        RGBType = GraphQLEnumType('RGB', enum.Enum)

    Instead of raw values, you can also specify GraphQLEnumValue objects with more
    detail like description or deprecation information.

    Note: If a value is not provided in a definition, the name of the enum value will
    be used as its internal value when the value is serialized.
    """

    values: GraphQLEnumValueMap
    ast_node: Optional[EnumTypeDefinitionNode]
    extension_ast_nodes: Optional[FrozenList[EnumTypeExtensionNode]]

    def __init__(
        self,
        name: str,
        values: Union[GraphQLEnumValueMap, Dict[str, Any], Type[Enum]],
        description: str = None,
        ast_node: EnumTypeDefinitionNode = None,
        extension_ast_nodes: Sequence[EnumTypeExtensionNode] = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        try:  # check for enum
            values = cast(Enum, values).__members__  # type: ignore
        except AttributeError:
            if not isinstance(values, dict) or not all(
                isinstance(name, str) for name in values
            ):
                try:
                    # noinspection PyTypeChecker
                    values = dict(values)  # type: ignore
                except (TypeError, ValueError):
                    raise TypeError(
                        f"{name} values must be an Enum or a dict"
                        " with value names as keys."
                    )
            values = cast(Dict, values)
        else:
            values = cast(Dict, values)
            values = {key: value.value for key, value in values.items()}
        values = {
            key: value
            if isinstance(value, GraphQLEnumValue)
            else GraphQLEnumValue(value)
            for key, value in values.items()
        }
        if ast_node and not isinstance(ast_node, EnumTypeDefinitionNode):
            raise TypeError(f"{name} AST node must be an EnumTypeDefinitionNode.")
        if extension_ast_nodes and not all(
            isinstance(node, EnumTypeExtensionNode) for node in extension_ast_nodes
        ):
            raise TypeError(
                f"{name} extension AST nodes must be specified"
                " as a sequence of EnumTypeExtensionNode instances."
            )
        self.values = values

    def to_kwargs(self) -> Dict[str, Any]:
        return dict(**super().to_kwargs(), values=self.values.copy())

    @cached_property
    def _value_lookup(self) -> Dict[Any, str]:
        # use first value or name as lookup
        lookup: Dict[Any, str] = {}
        for name, enum_value in self.values.items():
            value = enum_value.value
            if value is None:
                value = name
            try:
                if value not in lookup:
                    lookup[value] = name
            except TypeError:
                pass  # ignore unhashable values
        return lookup

    def serialize(self, value: Any) -> Union[str, None, InvalidType]:
        try:
            return self._value_lookup.get(value, INVALID)
        except TypeError:  # unhashable value
            for enum_name, enum_value in self.values.items():
                if enum_value.value == value:
                    return enum_name
        return INVALID

    def parse_value(self, value: str) -> Any:
        if isinstance(value, str):
            try:
                enum_value = self.values[value]
            except KeyError:
                return INVALID
            if enum_value.value is None:
                return value
            return enum_value.value
        return INVALID

    def parse_literal(
        self, value_node: ValueNode, _variables: Dict[str, Any] = None
    ) -> Any:
        # Note: variables will be resolved before calling this method.
        if isinstance(value_node, EnumValueNode):
            value = value_node.value
            try:
                enum_value = self.values[value]
            except KeyError:
                return INVALID
            if enum_value.value is None:
                return value
            return enum_value.value
        return INVALID


def is_enum_type(type_: Any) -> bool:
    return isinstance(type_, GraphQLEnumType)


def assert_enum_type(type_: Any) -> GraphQLEnumType:
    if not is_enum_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Enum type.")
    return cast(GraphQLEnumType, type_)


class GraphQLEnumValue:

    value: Any
    description: Optional[str]
    deprecation_reason: Optional[str]
    ast_node: Optional[EnumValueDefinitionNode]

    def __init__(
        self,
        value: Any = None,
        description: str = None,
        deprecation_reason: str = None,
        ast_node: EnumValueDefinitionNode = None,
    ) -> None:
        if description is not None and not isinstance(description, str):
            raise TypeError("The description of the enum value must be a string.")
        if deprecation_reason is not None and not isinstance(deprecation_reason, str):
            raise TypeError(
                "The deprecation reason for the enum value must be a string."
            )
        if ast_node and not isinstance(ast_node, EnumValueDefinitionNode):
            raise TypeError("AST node must be an EnumValueDefinitionNode.")
        self.value = value
        self.description = description
        self.deprecation_reason = deprecation_reason
        self.ast_node = ast_node

    def __eq__(self, other):
        return self is other or (
            isinstance(other, GraphQLEnumValue)
            and self.value == other.value
            and self.description == other.description
            and self.deprecation_reason == other.deprecation_reason
        )

    def to_kwargs(self) -> Dict[str, Any]:
        return dict(
            value=self.value,
            description=self.description,
            deprecation_reason=self.deprecation_reason,
            ast_node=self.ast_node,
        )

    @property
    def is_deprecated(self) -> bool:
        return bool(self.deprecation_reason)


GraphQLInputFieldMap = Dict[str, "GraphQLInputField"]
GraphQLInputFieldOutType = Callable[[Dict[str, Any]], Any]


class GraphQLInputObjectType(GraphQLNamedType):
    """Input Object Type Definition

    An input object defines a structured collection of fields which may be supplied
    to a field argument.

    Using `NonNull` will ensure that a value must be provided by the query.

    Example::

        NonNullFloat = GraphQLNonNull(GraphQLFloat())

        class GeoPoint(GraphQLInputObjectType):
            name = 'GeoPoint'
            fields = {
                'lat': GraphQLInputField(NonNullFloat),
                'lon': GraphQLInputField(NonNullFloat),
                'alt': GraphQLInputField(
                          GraphQLFloat(), default_value=0)
            }

    The outbound values will be Python dictionaries by default, but you can have them
    converted to other types by specifying an `out_type` function or class.
    """

    ast_node: Optional[InputObjectTypeDefinitionNode]
    extension_ast_nodes: Optional[FrozenList[InputObjectTypeExtensionNode]]

    def __init__(
        self,
        name: str,
        fields: Thunk[GraphQLInputFieldMap],
        description: str = None,
        out_type: GraphQLInputFieldOutType = None,
        ast_node: InputObjectTypeDefinitionNode = None,
        extension_ast_nodes: Sequence[InputObjectTypeExtensionNode] = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        if out_type is not None and not callable(out_type):
            raise TypeError(f"The out type for {name} must be a function or a class.")
        if ast_node and not isinstance(ast_node, InputObjectTypeDefinitionNode):
            raise TypeError(
                f"{name} AST node must be an InputObjectTypeDefinitionNode."
            )
        if extension_ast_nodes and not all(
            isinstance(node, InputObjectTypeExtensionNode)
            for node in extension_ast_nodes
        ):
            raise TypeError(
                f"{name} extension AST nodes must be specified"
                " as a sequence of InputObjectTypeExtensionNode instances."
            )
        self._fields = fields
        if out_type is not None:
            self.out_type = out_type

    @staticmethod
    def out_type(value: Dict[str, Any]) -> Any:
        """Transform outbound values (this is an extension of GraphQL.js).

        This default implementation passes values unaltered as dictionaries.
        """
        return value

    def to_kwargs(self) -> Dict[str, Any]:
        return dict(
            **super().to_kwargs(),
            fields=self.fields.copy(),
            out_type=None
            if self.out_type is GraphQLInputObjectType.out_type
            else self.out_type,
        )

    @cached_property
    def fields(self) -> GraphQLInputFieldMap:
        """Get provided fields, wrap them as GraphQLInputField if needed."""
        try:
            fields = resolve_thunk(self._fields)
        except Exception as error:
            raise TypeError(f"{self.name} fields cannot be resolved: {error}")
        if not isinstance(fields, dict) or not all(
            isinstance(key, str) for key in fields
        ):
            raise TypeError(
                f"{self.name} fields must be specified"
                " as a dict with field names as keys."
            )
        if not all(
            isinstance(value, GraphQLInputField) or is_input_type(value)
            for value in fields.values()
        ):
            raise TypeError(
                f"{self.name} fields must be"
                " GraphQLInputField or input type objects."
            )
        return {
            name: value
            if isinstance(value, GraphQLInputField)
            else GraphQLInputField(value)
            for name, value in fields.items()
        }


def is_input_object_type(type_: Any) -> bool:
    return isinstance(type_, GraphQLInputObjectType)


def assert_input_object_type(type_: Any) -> GraphQLInputObjectType:
    if not is_input_object_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Input Object type.")
    return cast(GraphQLInputObjectType, type_)


class GraphQLInputField:
    """Definition of a GraphQL input field"""

    type: "GraphQLInputType"
    default_value: Any
    description: Optional[str]
    out_name: Optional[str]  # for transforming names (extension of GraphQL.js)
    ast_node: Optional[InputValueDefinitionNode]

    def __init__(
        self,
        type_: "GraphQLInputType",
        default_value: Any = INVALID,
        description: str = None,
        out_name: str = None,
        ast_node: InputValueDefinitionNode = None,
    ) -> None:
        if not is_input_type(type_):
            raise TypeError(f"Input field type must be a GraphQL input type.")
        if description is not None and not isinstance(description, str):
            raise TypeError("Input field description must be a string.")
        if out_name is not None and not isinstance(out_name, str):
            raise TypeError("Input field out name must be a string.")
        if ast_node and not isinstance(ast_node, InputValueDefinitionNode):
            raise TypeError("Input field AST node must be an InputValueDefinitionNode.")
        self.type = type_
        self.default_value = default_value
        self.description = description
        self.out_name = out_name
        self.ast_node = ast_node

    def __eq__(self, other):
        return self is other or (
            isinstance(other, GraphQLInputField)
            and self.type == other.type
            and self.default_value == other.default_value
            and self.description == other.description
            and self.out_name == other.out_name
        )

    def to_kwargs(self) -> Dict[str, Any]:
        return dict(
            type_=self.type,
            description=self.description,
            default_value=self.default_value,
            out_name=self.out_name,
            ast_node=self.ast_node,
        )


def is_required_input_field(field: GraphQLInputField) -> bool:
    return is_non_null_type(field.type) and field.default_value is INVALID


# Wrapper types


class GraphQLList(Generic[GT], GraphQLWrappingType[GT]):
    """List Type Wrapper

    A list is a wrapping type which points to another type. Lists are often created
    within the context of defining the fields of an object type.

    Example::

        class PersonType(GraphQLObjectType):
            name = 'Person'

            @property
            def fields(self):
                return {
                    'parents': GraphQLField(GraphQLList(PersonType())),
                    'children': GraphQLField(GraphQLList(PersonType())),
                }
    """

    def __init__(self, type_: GT) -> None:
        super().__init__(type_=type_)

    def __str__(self):
        return f"[{self.of_type}]"


def is_list_type(type_: Any) -> bool:
    return isinstance(type_, GraphQLList)


def assert_list_type(type_: Any) -> GraphQLList:
    if not is_list_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL List type.")
    return cast(GraphQLList, type_)


GNT = TypeVar("GNT", bound="GraphQLNullableType")


class GraphQLNonNull(GraphQLWrappingType[GNT], Generic[GNT]):
    """Non-Null Type Wrapper

    A non-null is a wrapping type which points to another type. Non-null types enforce
    that their values are never null and can ensure an error is raised if this ever
    occurs during a request. It is useful for fields which you can make a strong
    guarantee on non-nullability, for example usually the id field of a database row
    will never be null.

    Example::

        class RowType(GraphQLObjectType):
            name = 'Row'
            fields = {
                'id': GraphQLField(GraphQLNonNull(GraphQLString()))
            }

    Note: the enforcement of non-nullability occurs within the executor.
    """

    def __init__(self, type_: GNT) -> None:
        super().__init__(type_=type_)
        if isinstance(type_, GraphQLNonNull):
            raise TypeError(
                "Can only create NonNull of a Nullable GraphQLType but got:"
                f" {type_}."
            )

    def __str__(self):
        return f"{self.of_type}!"


def is_non_null_type(type_: Any) -> bool:
    return isinstance(type_, GraphQLNonNull)


def assert_non_null_type(type_: Any) -> GraphQLNonNull:
    if not is_non_null_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Non-Null type.")
    return cast(GraphQLNonNull, type_)


# These types can all accept null as a value.

graphql_nullable_types = (
    GraphQLScalarType,
    GraphQLObjectType,
    GraphQLInterfaceType,
    GraphQLUnionType,
    GraphQLEnumType,
    GraphQLInputObjectType,
    GraphQLList,
)

GraphQLNullableType = Union[
    GraphQLScalarType,
    GraphQLObjectType,
    GraphQLInterfaceType,
    GraphQLUnionType,
    GraphQLEnumType,
    GraphQLInputObjectType,
    GraphQLList,
]


def is_nullable_type(type_: Any) -> bool:
    return isinstance(type_, graphql_nullable_types)


def assert_nullable_type(type_: Any) -> GraphQLNullableType:
    if not is_nullable_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL nullable type.")
    return cast(GraphQLNullableType, type_)


@overload
def get_nullable_type(type_: None) -> None:
    ...  # pragma: no cover


@overload  # noqa: F811 (pycqa/flake8#423)
def get_nullable_type(type_: GraphQLNullableType) -> GraphQLNullableType:
    ...  # pragma: no cover


@overload  # noqa: F811
def get_nullable_type(type_: GraphQLNonNull) -> GraphQLNullableType:
    ...  # pragma: no cover


def get_nullable_type(type_):  # noqa: F811
    """Unwrap possible non-null type"""
    if is_non_null_type(type_):
        type_ = cast(GraphQLNonNull, type_)
        type_ = type_.of_type
    return cast(Optional[GraphQLNullableType], type_)


# These types may be used as input types for arguments and directives.

graphql_input_types = (GraphQLScalarType, GraphQLEnumType, GraphQLInputObjectType)

GraphQLInputType = Union[
    GraphQLScalarType, GraphQLEnumType, GraphQLInputObjectType, GraphQLWrappingType
]


def is_input_type(type_: Any) -> bool:
    return isinstance(type_, graphql_input_types) or (
        isinstance(type_, GraphQLWrappingType) and is_input_type(type_.of_type)
    )


def assert_input_type(type_: Any) -> GraphQLInputType:
    if not is_input_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL input type.")
    return cast(GraphQLInputType, type_)


# These types may be used as output types as the result of fields.

graphql_output_types = (
    GraphQLScalarType,
    GraphQLObjectType,
    GraphQLInterfaceType,
    GraphQLUnionType,
    GraphQLEnumType,
)

GraphQLOutputType = Union[
    GraphQLScalarType,
    GraphQLObjectType,
    GraphQLInterfaceType,
    GraphQLUnionType,
    GraphQLEnumType,
    GraphQLWrappingType,
]


def is_output_type(type_: Any) -> bool:
    return isinstance(type_, graphql_output_types) or (
        isinstance(type_, GraphQLWrappingType) and is_output_type(type_.of_type)
    )


def assert_output_type(type_: Any) -> GraphQLOutputType:
    if not is_output_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL output type.")
    return cast(GraphQLOutputType, type_)


# These types may describe types which may be leaf values.

graphql_leaf_types = (GraphQLScalarType, GraphQLEnumType)

GraphQLLeafType = Union[GraphQLScalarType, GraphQLEnumType]


def is_leaf_type(type_: Any) -> bool:
    return isinstance(type_, graphql_leaf_types)


def assert_leaf_type(type_: Any) -> GraphQLLeafType:
    if not is_leaf_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL leaf type.")
    return cast(GraphQLLeafType, type_)


# These types may describe the parent context of a selection set.

graphql_composite_types = (GraphQLObjectType, GraphQLInterfaceType, GraphQLUnionType)

GraphQLCompositeType = Union[GraphQLObjectType, GraphQLInterfaceType, GraphQLUnionType]


def is_composite_type(type_: Any) -> bool:
    return isinstance(type_, graphql_composite_types)


def assert_composite_type(type_: Any) -> GraphQLType:
    if not is_composite_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL composite type.")
    return cast(GraphQLType, type_)


# These types may describe abstract types.

graphql_abstract_types = (GraphQLInterfaceType, GraphQLUnionType)

GraphQLAbstractType = Union[GraphQLInterfaceType, GraphQLUnionType]


def is_abstract_type(type_: Any) -> bool:
    return isinstance(type_, graphql_abstract_types)


def assert_abstract_type(type_: Any) -> GraphQLAbstractType:
    if not is_abstract_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL composite type.")
    return cast(GraphQLAbstractType, type_)
