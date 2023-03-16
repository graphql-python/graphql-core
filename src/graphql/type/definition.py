from __future__ import annotations  # Python < 3.10

from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Collection,
    Dict,
    Generic,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from ..error import GraphQLError
from ..language import (
    EnumTypeDefinitionNode,
    EnumTypeExtensionNode,
    EnumValueDefinitionNode,
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
    print_ast,
)
from ..pyutils import (
    AwaitableOrValue,
    Path,
    Undefined,
    cached_property,
    did_you_mean,
    inspect,
    suggestion_list,
)
from ..utilities.value_from_ast_untyped import value_from_ast_untyped
from .assert_name import assert_enum_value_name, assert_name


try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict
try:
    from typing import TypeAlias, TypeGuard
except ImportError:  # Python < 3.10
    from typing_extensions import TypeAlias, TypeGuard

if TYPE_CHECKING:
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
    "resolve_thunk",
    "GraphQLAbstractType",
    "GraphQLArgument",
    "GraphQLArgumentKwargs",
    "GraphQLArgumentMap",
    "GraphQLCompositeType",
    "GraphQLEnumType",
    "GraphQLEnumTypeKwargs",
    "GraphQLEnumValue",
    "GraphQLEnumValueKwargs",
    "GraphQLEnumValueMap",
    "GraphQLField",
    "GraphQLFieldKwargs",
    "GraphQLFieldMap",
    "GraphQLFieldResolver",
    "GraphQLInputField",
    "GraphQLInputFieldKwargs",
    "GraphQLInputFieldMap",
    "GraphQLInputFieldOutType",
    "GraphQLInputObjectType",
    "GraphQLInputObjectTypeKwargs",
    "GraphQLInputType",
    "GraphQLInterfaceType",
    "GraphQLInterfaceTypeKwargs",
    "GraphQLIsTypeOfFn",
    "GraphQLLeafType",
    "GraphQLList",
    "GraphQLNamedType",
    "GraphQLNamedTypeKwargs",
    "GraphQLNamedInputType",
    "GraphQLNamedOutputType",
    "GraphQLNullableType",
    "GraphQLNullableInputType",
    "GraphQLNullableOutputType",
    "GraphQLNonNull",
    "GraphQLResolveInfo",
    "GraphQLScalarType",
    "GraphQLScalarTypeKwargs",
    "GraphQLScalarSerializer",
    "GraphQLScalarValueParser",
    "GraphQLScalarLiteralParser",
    "GraphQLObjectType",
    "GraphQLObjectTypeKwargs",
    "GraphQLOutputType",
    "GraphQLType",
    "GraphQLTypeResolver",
    "GraphQLUnionType",
    "GraphQLUnionTypeKwargs",
    "GraphQLWrappingType",
    "Thunk",
    "ThunkCollection",
    "ThunkMapping",
]


class GraphQLType:
    """Base class for all GraphQL types"""

    # Note: We don't use slots for GraphQLType objects because memory considerations
    # are not really important for the schema definition, and it would make caching
    # properties slower or more complicated.


# There are predicates for each kind of GraphQL type.


def is_type(type_: Any) -> TypeGuard[GraphQLType]:
    return isinstance(type_, GraphQLType)


def assert_type(type_: Any) -> GraphQLType:
    if not is_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL type.")
    return type_


# These types wrap and modify other types

GT = TypeVar("GT", bound=GraphQLType, covariant=True)


class GraphQLWrappingType(GraphQLType, Generic[GT]):
    """Base class for all GraphQL wrapping types"""

    of_type: GT

    def __init__(self, type_: GT) -> None:
        self.of_type = type_

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.of_type!r}>"


def is_wrapping_type(type_: Any) -> TypeGuard[GraphQLWrappingType]:
    return isinstance(type_, GraphQLWrappingType)


def assert_wrapping_type(type_: Any) -> GraphQLWrappingType:
    if not is_wrapping_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL wrapping type.")
    return type_


class GraphQLNamedTypeKwargs(TypedDict, total=False):
    name: str
    description: Optional[str]
    extensions: Dict[str, Any]
    # unfortunately, we cannot make the following more specific, because they are
    # used by subclasses with different node types and typed dicts cannot be refined
    ast_node: Optional[Any]
    extension_ast_nodes: Tuple[Any, ...]


class GraphQLNamedType(GraphQLType):
    """Base class for all GraphQL named types"""

    name: str
    description: Optional[str]
    extensions: Dict[str, Any]
    ast_node: Optional[TypeDefinitionNode]
    extension_ast_nodes: Tuple[TypeExtensionNode, ...]

    reserved_types: Dict[str, GraphQLNamedType] = {}

    def __new__(cls, name: str, *_args: Any, **_kwargs: Any) -> GraphQLNamedType:
        if name in cls.reserved_types:
            raise TypeError(f"Redefinition of reserved type {name!r}")
        return super().__new__(cls)

    def __reduce__(self) -> Tuple[Callable, Tuple]:
        return self._get_instance, (self.name, tuple(self.to_kwargs().items()))

    @classmethod
    def _get_instance(cls, name: str, args: Tuple) -> GraphQLNamedType:
        try:
            return cls.reserved_types[name]
        except KeyError:
            return cls(**dict(args))

    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[TypeDefinitionNode] = None,
        extension_ast_nodes: Optional[Collection[TypeExtensionNode]] = None,
    ) -> None:
        assert_name(name)
        self.name = name
        self.description = description
        self.extensions = extensions or {}
        self.ast_node = ast_node
        self.extension_ast_nodes = (
            tuple(extension_ast_nodes) if extension_ast_nodes else ()
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name!r}>"

    def __str__(self) -> str:
        return self.name

    def to_kwargs(self) -> GraphQLNamedTypeKwargs:
        return GraphQLNamedTypeKwargs(
            name=self.name,
            description=self.description,
            extensions=self.extensions,
            ast_node=self.ast_node,
            extension_ast_nodes=self.extension_ast_nodes,
        )

    def __copy__(self) -> GraphQLNamedType:  # pragma: no cover
        return self.__class__(**self.to_kwargs())


T = TypeVar("T")

ThunkCollection: TypeAlias = Union[Callable[[], Collection[T]], Collection[T]]
ThunkMapping: TypeAlias = Union[Callable[[], Mapping[str, T]], Mapping[str, T]]
Thunk: TypeAlias = Union[Callable[[], T], T]


def resolve_thunk(thunk: Thunk[T]) -> T:
    """Resolve the given thunk.

    Used while defining GraphQL types to allow for circular references in otherwise
    immutable type definitions.
    """
    return thunk() if callable(thunk) else thunk


GraphQLScalarSerializer: TypeAlias = Callable[[Any], Any]
GraphQLScalarValueParser: TypeAlias = Callable[[Any], Any]
GraphQLScalarLiteralParser: TypeAlias = Callable[
    [ValueNode, Optional[Dict[str, Any]]], Any
]


class GraphQLScalarTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    serialize: Optional[GraphQLScalarSerializer]
    parse_value: Optional[GraphQLScalarValueParser]
    parse_literal: Optional[GraphQLScalarLiteralParser]
    specified_by_url: Optional[str]


class GraphQLScalarType(GraphQLNamedType):
    """Scalar Type Definition

    The leaf values of any request and input values to arguments are Scalars (or Enums)
    and are defined with a name and a series of functions used to parse input from ast
    or variables and to ensure validity.

    If a type's serialize function returns ``None``, then an error will be raised and a
    ``None`` value will be returned in the response. It is always better to validate.

    Example::

        def serialize_odd(value: Any) -> int:
            try:
                value = int(value)
            except ValueError:
                raise GraphQLError(
                    f"Scalar 'Odd' cannot represent '{value}'"
                    " since it is not an integer.")
            if not value % 2:
                raise GraphQLError(
                    f"Scalar 'Odd' cannot represent '{value}' since it is even.")
            return value

        odd_type = GraphQLScalarType('Odd', serialize=serialize_odd)

    """

    specified_by_url: Optional[str]
    ast_node: Optional[ScalarTypeDefinitionNode]
    extension_ast_nodes: Tuple[ScalarTypeExtensionNode, ...]

    def __init__(
        self,
        name: str,
        serialize: Optional[GraphQLScalarSerializer] = None,
        parse_value: Optional[GraphQLScalarValueParser] = None,
        parse_literal: Optional[GraphQLScalarLiteralParser] = None,
        description: Optional[str] = None,
        specified_by_url: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[ScalarTypeDefinitionNode] = None,
        extension_ast_nodes: Optional[Collection[ScalarTypeExtensionNode]] = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            extensions=extensions,
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )

        if serialize is not None:
            self.serialize = serialize  # type: ignore
        if parse_value is not None:
            self.parse_value = parse_value  # type: ignore
        if parse_literal is not None:
            self.parse_literal = parse_literal  # type: ignore
        if parse_literal is not None:
            if parse_value is None:
                raise TypeError(
                    f"{name} must provide"
                    " both 'parse_value' and 'parse_literal' functions."
                )
        self.specified_by_url = specified_by_url

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name!r}>"

    def __str__(self) -> str:
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

    def parse_literal(
        self, node: ValueNode, variables: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Parses an externally provided literal value to use as an input.

        This default method uses the parse_value method and should be replaced
        with a more specific version when creating a scalar type.
        """
        return self.parse_value(value_from_ast_untyped(node, variables))

    def to_kwargs(self) -> GraphQLScalarTypeKwargs:
        # noinspection PyArgumentList
        return GraphQLScalarTypeKwargs(  # type: ignore
            super().to_kwargs(),
            serialize=None
            if self.serialize is GraphQLScalarType.serialize
            else self.serialize,
            parse_value=None
            if self.parse_value is GraphQLScalarType.parse_value
            else self.parse_value,
            parse_literal=None
            if getattr(self.parse_literal, "__func__", None)
            is GraphQLScalarType.parse_literal
            else self.parse_literal,
            specified_by_url=self.specified_by_url,
        )

    def __copy__(self) -> GraphQLScalarType:  # pragma: no cover
        return self.__class__(**self.to_kwargs())


def is_scalar_type(type_: Any) -> TypeGuard[GraphQLScalarType]:
    return isinstance(type_, GraphQLScalarType)


def assert_scalar_type(type_: Any) -> GraphQLScalarType:
    if not is_scalar_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Scalar type.")
    return type_


GraphQLArgumentMap: TypeAlias = Dict[str, "GraphQLArgument"]


class GraphQLFieldKwargs(TypedDict, total=False):
    type_: GraphQLOutputType
    args: Optional[GraphQLArgumentMap]
    resolve: Optional[GraphQLFieldResolver]
    subscribe: Optional[GraphQLFieldResolver]
    description: Optional[str]
    deprecation_reason: Optional[str]
    extensions: Dict[str, Any]
    ast_node: Optional[FieldDefinitionNode]


class GraphQLField:
    """Definition of a GraphQL field"""

    type: GraphQLOutputType
    args: GraphQLArgumentMap
    resolve: Optional[GraphQLFieldResolver]
    subscribe: Optional[GraphQLFieldResolver]
    description: Optional[str]
    deprecation_reason: Optional[str]
    extensions: Dict[str, Any]
    ast_node: Optional[FieldDefinitionNode]

    def __init__(
        self,
        type_: GraphQLOutputType,
        args: Optional[GraphQLArgumentMap] = None,
        resolve: Optional[GraphQLFieldResolver] = None,
        subscribe: Optional[GraphQLFieldResolver] = None,
        description: Optional[str] = None,
        deprecation_reason: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[FieldDefinitionNode] = None,
    ) -> None:
        if args:
            args = {
                assert_name(name): value
                if isinstance(value, GraphQLArgument)
                else GraphQLArgument(cast(GraphQLInputType, value))
                for name, value in args.items()
            }
        else:
            args = {}
        self.type = type_
        self.args = args or {}
        self.resolve = resolve
        self.subscribe = subscribe
        self.description = description
        self.deprecation_reason = deprecation_reason
        self.extensions = extensions or {}
        self.ast_node = ast_node

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.type!r}>"

    def __str__(self) -> str:
        return f"Field: {self.type}"

    def __eq__(self, other: Any) -> bool:
        return self is other or (
            isinstance(other, GraphQLField)
            and self.type == other.type
            and self.args == other.args
            and self.resolve == other.resolve
            and self.description == other.description
            and self.deprecation_reason == other.deprecation_reason
            and self.extensions == other.extensions
        )

    def to_kwargs(self) -> GraphQLFieldKwargs:
        return GraphQLFieldKwargs(
            type_=self.type,
            args=self.args.copy() if self.args else None,
            resolve=self.resolve,
            subscribe=self.subscribe,
            deprecation_reason=self.deprecation_reason,
            description=self.description,
            extensions=self.extensions,
            ast_node=self.ast_node,
        )

    def __copy__(self) -> GraphQLField:  # pragma: no cover
        return self.__class__(**self.to_kwargs())


class GraphQLResolveInfo(NamedTuple):
    """Collection of information passed to the resolvers.

    This is always passed as the first argument to the resolvers.

    Note that contrary to the JavaScript implementation, the context (commonly used to
    represent an authenticated user, or request-specific caches) is included here and
    not passed as an additional argument.
    """

    field_name: str
    field_nodes: List[FieldNode]
    return_type: GraphQLOutputType
    parent_type: GraphQLObjectType
    path: Path
    schema: "GraphQLSchema"
    fragments: Dict[str, FragmentDefinitionNode]
    root_value: Any
    operation: OperationDefinitionNode
    variable_values: Dict[str, Any]
    context: Any
    is_awaitable: Callable[[Any], bool]


# Note: Contrary to the Javascript implementation of GraphQLFieldResolver,
# the context is passed as part of the GraphQLResolveInfo and any arguments
# are passed individually as keyword arguments.
GraphQLFieldResolverWithoutArgs: TypeAlias = Callable[[Any, GraphQLResolveInfo], Any]
# Unfortunately there is currently no syntax to indicate optional or keyword
# arguments in Python, so we also allow any other Callable as a workaround:
GraphQLFieldResolver: TypeAlias = Callable[..., Any]

# Note: Contrary to the Javascript implementation of GraphQLTypeResolver,
# the context is passed as part of the GraphQLResolveInfo:
GraphQLTypeResolver: TypeAlias = Callable[
    [Any, GraphQLResolveInfo, "GraphQLAbstractType"],
    AwaitableOrValue[Optional[str]],
]

# Note: Contrary to the Javascript implementation of GraphQLIsTypeOfFn,
# the context is passed as part of the GraphQLResolveInfo:
GraphQLIsTypeOfFn: TypeAlias = Callable[
    [Any, GraphQLResolveInfo], AwaitableOrValue[bool]
]

GraphQLFieldMap: TypeAlias = Dict[str, GraphQLField]


class GraphQLArgumentKwargs(TypedDict, total=False):
    type_: GraphQLInputType
    default_value: Any
    description: Optional[str]
    deprecation_reason: Optional[str]
    out_name: Optional[str]
    extensions: Dict[str, Any]
    ast_node: Optional[InputValueDefinitionNode]


class GraphQLArgument:
    """Definition of a GraphQL argument"""

    type: GraphQLInputType
    default_value: Any
    description: Optional[str]
    deprecation_reason: Optional[str]
    out_name: Optional[str]  # for transforming names (extension of GraphQL.js)
    extensions: Dict[str, Any]
    ast_node: Optional[InputValueDefinitionNode]

    def __init__(
        self,
        type_: GraphQLInputType,
        default_value: Any = Undefined,
        description: Optional[str] = None,
        deprecation_reason: Optional[str] = None,
        out_name: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[InputValueDefinitionNode] = None,
    ) -> None:
        self.type = type_
        self.default_value = default_value
        self.description = description
        self.deprecation_reason = deprecation_reason
        self.out_name = out_name
        self.extensions = extensions or {}
        self.ast_node = ast_node

    def __eq__(self, other: Any) -> bool:
        return self is other or (
            isinstance(other, GraphQLArgument)
            and self.type == other.type
            and self.default_value == other.default_value
            and self.description == other.description
            and self.deprecation_reason == other.deprecation_reason
            and self.out_name == other.out_name
            and self.extensions == other.extensions
        )

    def to_kwargs(self) -> GraphQLArgumentKwargs:
        return GraphQLArgumentKwargs(
            type_=self.type,
            default_value=self.default_value,
            description=self.description,
            deprecation_reason=self.deprecation_reason,
            out_name=self.out_name,
            extensions=self.extensions,
            ast_node=self.ast_node,
        )

    def __copy__(self) -> GraphQLArgument:  # pragma: no cover
        return self.__class__(**self.to_kwargs())


def is_required_argument(arg: GraphQLArgument) -> bool:
    return is_non_null_type(arg.type) and arg.default_value is Undefined


class GraphQLObjectTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    fields: GraphQLFieldMap
    interfaces: Tuple[GraphQLInterfaceType, ...]
    is_type_of: Optional[GraphQLIsTypeOfFn]


class GraphQLObjectType(GraphQLNamedType):
    """Object Type Definition

    Almost all the GraphQL types you define will be object types. Object types have
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
    extension_ast_nodes: Tuple[ObjectTypeExtensionNode, ...]

    def __init__(
        self,
        name: str,
        fields: ThunkMapping[GraphQLField],
        interfaces: Optional[ThunkCollection[GraphQLInterfaceType]] = None,
        is_type_of: Optional[GraphQLIsTypeOfFn] = None,
        extensions: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        ast_node: Optional[ObjectTypeDefinitionNode] = None,
        extension_ast_nodes: Optional[Collection[ObjectTypeExtensionNode]] = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            extensions=extensions,
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        self._fields = fields
        self._interfaces = interfaces
        self.is_type_of = is_type_of

    def to_kwargs(self) -> GraphQLObjectTypeKwargs:
        # noinspection PyArgumentList
        return GraphQLObjectTypeKwargs(  # type: ignore
            super().to_kwargs(),
            fields=self.fields.copy(),
            interfaces=self.interfaces,
            is_type_of=self.is_type_of,
        )

    def __copy__(self) -> GraphQLObjectType:  # pragma: no cover
        return self.__class__(**self.to_kwargs())

    @cached_property
    def fields(self) -> GraphQLFieldMap:
        """Get provided fields, wrapping them as GraphQLFields if needed."""
        try:
            fields = resolve_thunk(self._fields)
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            raise cls(f"{self.name} fields cannot be resolved. {error}") from error
        return {
            assert_name(name): value
            if isinstance(value, GraphQLField)
            else GraphQLField(value)  # type: ignore
            for name, value in fields.items()
        }

    @cached_property
    def interfaces(self) -> Tuple[GraphQLInterfaceType, ...]:
        """Get provided interfaces."""
        try:
            interfaces: Collection[GraphQLInterfaceType] = resolve_thunk(
                self._interfaces  # type: ignore
            )
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            raise cls(f"{self.name} interfaces cannot be resolved. {error}") from error
        return tuple(interfaces) if interfaces else ()


def is_object_type(type_: Any) -> TypeGuard[GraphQLObjectType]:
    return isinstance(type_, GraphQLObjectType)


def assert_object_type(type_: Any) -> GraphQLObjectType:
    if not is_object_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Object type.")
    return type_


class GraphQLInterfaceTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    fields: GraphQLFieldMap
    interfaces: Tuple[GraphQLInterfaceType, ...]
    resolve_type: Optional[GraphQLTypeResolver]


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
    extension_ast_nodes: Tuple[InterfaceTypeExtensionNode, ...]

    def __init__(
        self,
        name: str,
        fields: ThunkMapping[GraphQLField],
        interfaces: Optional[ThunkCollection[GraphQLInterfaceType]] = None,
        resolve_type: Optional[GraphQLTypeResolver] = None,
        description: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[InterfaceTypeDefinitionNode] = None,
        extension_ast_nodes: Optional[Collection[InterfaceTypeExtensionNode]] = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            extensions=extensions,
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        self._fields = fields
        self._interfaces = interfaces
        self.resolve_type = resolve_type

    def to_kwargs(self) -> GraphQLInterfaceTypeKwargs:
        # noinspection PyArgumentList
        return GraphQLInterfaceTypeKwargs(  # type: ignore
            super().to_kwargs(),
            fields=self.fields.copy(),
            interfaces=self.interfaces,
            resolve_type=self.resolve_type,
        )

    def __copy__(self) -> GraphQLInterfaceType:  # pragma: no cover
        return self.__class__(**self.to_kwargs())

    @cached_property
    def fields(self) -> GraphQLFieldMap:
        """Get provided fields, wrapping them as GraphQLFields if needed."""
        try:
            fields = resolve_thunk(self._fields)
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            raise cls(f"{self.name} fields cannot be resolved. {error}") from error
        return {
            assert_name(name): value
            if isinstance(value, GraphQLField)
            else GraphQLField(value)  # type: ignore
            for name, value in fields.items()
        }

    @cached_property
    def interfaces(self) -> Tuple[GraphQLInterfaceType, ...]:
        """Get provided interfaces."""
        try:
            interfaces: Collection[GraphQLInterfaceType] = resolve_thunk(
                self._interfaces  # type: ignore
            )
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            raise cls(f"{self.name} interfaces cannot be resolved. {error}") from error
        return tuple(interfaces) if interfaces else ()


def is_interface_type(type_: Any) -> TypeGuard[GraphQLInterfaceType]:
    return isinstance(type_, GraphQLInterfaceType)


def assert_interface_type(type_: Any) -> GraphQLInterfaceType:
    if not is_interface_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Interface type.")
    return type_


class GraphQLUnionTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    types: Tuple[GraphQLObjectType, ...]
    resolve_type: Optional[GraphQLTypeResolver]


class GraphQLUnionType(GraphQLNamedType):
    """Union Type Definition

    When a field can return one of a heterogeneous set of types, a Union type is used
    to describe what types are possible as well as providing a function to determine
    which type is actually used when the field is resolved.

    Example::

        def resolve_type(obj, _info, _type):
            if isinstance(obj, Dog):
                return DogType()
            if isinstance(obj, Cat):
                return CatType()

        PetType = GraphQLUnionType('Pet', [DogType, CatType], resolve_type)
    """

    resolve_type: Optional[GraphQLTypeResolver]
    ast_node: Optional[UnionTypeDefinitionNode]
    extension_ast_nodes: Tuple[UnionTypeExtensionNode, ...]

    def __init__(
        self,
        name: str,
        types: ThunkCollection[GraphQLObjectType],
        resolve_type: Optional[GraphQLTypeResolver] = None,
        description: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[UnionTypeDefinitionNode] = None,
        extension_ast_nodes: Optional[Collection[UnionTypeExtensionNode]] = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            extensions=extensions,
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        self._types = types
        self.resolve_type = resolve_type

    def to_kwargs(self) -> GraphQLUnionTypeKwargs:
        # noinspection PyArgumentList
        return GraphQLUnionTypeKwargs(  # type: ignore
            super().to_kwargs(), types=self.types, resolve_type=self.resolve_type
        )

    def __copy__(self) -> GraphQLUnionType:  # pragma: no cover
        return self.__class__(**self.to_kwargs())

    @cached_property
    def types(self) -> Tuple[GraphQLObjectType, ...]:
        """Get provided types."""
        try:
            types: Collection[GraphQLObjectType] = resolve_thunk(self._types)
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            raise cls(f"{self.name} types cannot be resolved. {error}") from error
        return tuple(types) if types else ()


def is_union_type(type_: Any) -> TypeGuard[GraphQLUnionType]:
    return isinstance(type_, GraphQLUnionType)


def assert_union_type(type_: Any) -> GraphQLUnionType:
    if not is_union_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Union type.")
    return type_


GraphQLEnumValueMap: TypeAlias = Dict[str, "GraphQLEnumValue"]


class GraphQLEnumTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    values: GraphQLEnumValueMap
    names_as_values: Optional[bool]


class GraphQLEnumType(GraphQLNamedType):
    """Enum Type Definition

    Some leaf values of requests and input values are Enums. GraphQL serializes Enum
    values as strings, however internally Enums can be represented by any kind of type,
    often integers. They can also be provided as a Python Enum. In this case, the flag
    `names_as_values` determines what will be used as internal representation. The
    default value of `False` will use the enum values, the value `True` will use the
    enum names, and the value `None` will use the members themselves.

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
    extension_ast_nodes: Tuple[EnumTypeExtensionNode, ...]

    def __init__(
        self,
        name: str,
        values: Union[GraphQLEnumValueMap, Mapping[str, Any], Type[Enum]],
        names_as_values: Optional[bool] = False,
        description: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[EnumTypeDefinitionNode] = None,
        extension_ast_nodes: Optional[Collection[EnumTypeExtensionNode]] = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            extensions=extensions,
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        try:  # check for enum
            values = cast(Enum, values).__members__  # type: ignore
        except AttributeError:
            if not isinstance(values, Mapping) or not all(
                isinstance(name, str) for name in values
            ):
                try:
                    # noinspection PyTypeChecker
                    values = dict(values)  # type: ignore
                except (TypeError, ValueError):
                    raise TypeError(
                        f"{name} values must be an Enum or a mapping"
                        " with value names as keys."
                    )
            values = cast(Dict[str, Any], values)
        else:
            values = cast(Dict[str, Enum], values)
            if names_as_values is False:
                values = {key: value.value for key, value in values.items()}
            elif names_as_values is True:
                values = {key: key for key in values}
        values = {
            assert_enum_value_name(key): value
            if isinstance(value, GraphQLEnumValue)
            else GraphQLEnumValue(value)
            for key, value in values.items()
        }
        self.values = values

    def to_kwargs(self) -> GraphQLEnumTypeKwargs:
        # noinspection PyArgumentList
        return GraphQLEnumTypeKwargs(  # type: ignore
            super().to_kwargs(), values=self.values.copy()
        )

    def __copy__(self) -> GraphQLEnumType:  # pragma: no cover
        return self.__class__(**self.to_kwargs())

    @cached_property
    def _value_lookup(self) -> Dict[Any, str]:
        # use first value or name as lookup
        lookup: Dict[Any, str] = {}
        for name, enum_value in self.values.items():
            value = enum_value.value
            if value is None or value is Undefined:
                value = name
            try:
                if value not in lookup:
                    lookup[value] = name
            except TypeError:
                pass  # ignore unhashable values
        return lookup

    def serialize(self, output_value: Any) -> str:
        try:
            return self._value_lookup[output_value]
        except KeyError:  # hashable value not found
            pass
        except TypeError:  # unhashable value, we need to scan all values
            for enum_name, enum_value in self.values.items():
                if enum_value.value == output_value:
                    return enum_name
        raise GraphQLError(
            f"Enum '{self.name}' cannot represent value: {inspect(output_value)}"
        )

    def parse_value(self, input_value: str) -> Any:
        if isinstance(input_value, str):
            try:
                enum_value = self.values[input_value]
            except KeyError:
                raise GraphQLError(
                    f"Value '{input_value}' does not exist in '{self.name}' enum."
                    + did_you_mean_enum_value(self, input_value)
                )
            return enum_value.value
        value_str = inspect(input_value)
        raise GraphQLError(
            f"Enum '{self.name}' cannot represent non-string value: {value_str}."
            + did_you_mean_enum_value(self, value_str)
        )

    def parse_literal(
        self, value_node: ValueNode, _variables: Optional[Dict[str, Any]] = None
    ) -> Any:
        # Note: variables will be resolved before calling this method.
        if isinstance(value_node, EnumValueNode):
            try:
                enum_value = self.values[value_node.value]
            except KeyError:
                value_str = print_ast(value_node)
                raise GraphQLError(
                    f"Value '{value_str}' does not exist in '{self.name}' enum."
                    + did_you_mean_enum_value(self, value_str),
                    value_node,
                )
            return enum_value.value
        value_str = print_ast(value_node)
        raise GraphQLError(
            f"Enum '{self.name}' cannot represent non-enum value: {value_str}."
            + did_you_mean_enum_value(self, value_str),
            value_node,
        )


def is_enum_type(type_: Any) -> TypeGuard[GraphQLEnumType]:
    return isinstance(type_, GraphQLEnumType)


def assert_enum_type(type_: Any) -> GraphQLEnumType:
    if not is_enum_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Enum type.")
    return type_


def did_you_mean_enum_value(enum_type: GraphQLEnumType, unknown_value_str: str) -> str:
    suggested_values = suggestion_list(unknown_value_str, enum_type.values)
    return did_you_mean(suggested_values, "the enum value")


class GraphQLEnumValueKwargs(TypedDict, total=False):
    value: Any
    description: Optional[str]
    deprecation_reason: Optional[str]
    extensions: Dict[str, Any]
    ast_node: Optional[EnumValueDefinitionNode]


class GraphQLEnumValue:
    value: Any
    description: Optional[str]
    deprecation_reason: Optional[str]
    extensions: Dict[str, Any]
    ast_node: Optional[EnumValueDefinitionNode]

    def __init__(
        self,
        value: Any = None,
        description: Optional[str] = None,
        deprecation_reason: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[EnumValueDefinitionNode] = None,
    ) -> None:
        self.value = value
        self.description = description
        self.deprecation_reason = deprecation_reason
        self.extensions = extensions or {}
        self.ast_node = ast_node

    def __eq__(self, other: Any) -> bool:
        return self is other or (
            isinstance(other, GraphQLEnumValue)
            and self.value == other.value
            and self.description == other.description
            and self.deprecation_reason == other.deprecation_reason
            and self.extensions == other.extensions
        )

    def to_kwargs(self) -> GraphQLEnumValueKwargs:
        return GraphQLEnumValueKwargs(
            value=self.value,
            description=self.description,
            deprecation_reason=self.deprecation_reason,
            extensions=self.extensions,
            ast_node=self.ast_node,
        )

    def __copy__(self) -> GraphQLEnumValue:  # pragma: no cover
        return self.__class__(**self.to_kwargs())


GraphQLInputFieldMap: TypeAlias = Dict[str, "GraphQLInputField"]
GraphQLInputFieldOutType = Callable[[Dict[str, Any]], Any]


class GraphQLInputObjectTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    fields: GraphQLInputFieldMap
    out_type: Optional[GraphQLInputFieldOutType]


class GraphQLInputObjectType(GraphQLNamedType):
    """Input Object Type Definition

    An input object defines a structured collection of fields which may be supplied
    to a field argument.

    Using ``NonNull`` will ensure that a value must be provided by the query.

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
    converted to other types by specifying an ``out_type`` function or class.
    """

    ast_node: Optional[InputObjectTypeDefinitionNode]
    extension_ast_nodes: Tuple[InputObjectTypeExtensionNode, ...]

    def __init__(
        self,
        name: str,
        fields: ThunkMapping[GraphQLInputField],
        description: Optional[str] = None,
        out_type: Optional[GraphQLInputFieldOutType] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[InputObjectTypeDefinitionNode] = None,
        extension_ast_nodes: Optional[Collection[InputObjectTypeExtensionNode]] = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            extensions=extensions,
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        self._fields = fields
        if out_type is not None:
            self.out_type = out_type  # type: ignore

    @staticmethod
    def out_type(value: Dict[str, Any]) -> Any:
        """Transform outbound values (this is an extension of GraphQL.js).

        This default implementation passes values unaltered as dictionaries.
        """
        return value

    def to_kwargs(self) -> GraphQLInputObjectTypeKwargs:
        # noinspection PyArgumentList
        return GraphQLInputObjectTypeKwargs(  # type: ignore
            super().to_kwargs(),
            fields=self.fields.copy(),
            out_type=None
            if self.out_type is GraphQLInputObjectType.out_type
            else self.out_type,
        )

    def __copy__(self) -> GraphQLInputObjectType:  # pragma: no cover
        return self.__class__(**self.to_kwargs())

    @cached_property
    def fields(self) -> GraphQLInputFieldMap:
        """Get provided fields, wrap them as GraphQLInputField if needed."""
        try:
            fields = resolve_thunk(self._fields)
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            raise cls(f"{self.name} fields cannot be resolved. {error}") from error
        return {
            assert_name(name): value
            if isinstance(value, GraphQLInputField)
            else GraphQLInputField(value)  # type: ignore
            for name, value in fields.items()
        }


def is_input_object_type(type_: Any) -> TypeGuard[GraphQLInputObjectType]:
    return isinstance(type_, GraphQLInputObjectType)


def assert_input_object_type(type_: Any) -> GraphQLInputObjectType:
    if not is_input_object_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Input Object type.")
    return type_


class GraphQLInputFieldKwargs(TypedDict, total=False):
    type_: GraphQLInputType
    default_value: Any
    description: Optional[str]
    deprecation_reason: Optional[str]
    out_name: Optional[str]
    extensions: Dict[str, Any]
    ast_node: Optional[InputValueDefinitionNode]


class GraphQLInputField:
    """Definition of a GraphQL input field"""

    type: GraphQLInputType
    default_value: Any
    description: Optional[str]
    deprecation_reason: Optional[str]
    out_name: Optional[str]  # for transforming names (extension of GraphQL.js)
    extensions: Dict[str, Any]
    ast_node: Optional[InputValueDefinitionNode]

    def __init__(
        self,
        type_: GraphQLInputType,
        default_value: Any = Undefined,
        description: Optional[str] = None,
        deprecation_reason: Optional[str] = None,
        out_name: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[InputValueDefinitionNode] = None,
    ) -> None:
        self.type = type_
        self.default_value = default_value
        self.description = description
        self.deprecation_reason = deprecation_reason
        self.out_name = out_name
        self.extensions = extensions or {}
        self.ast_node = ast_node

    def __eq__(self, other: Any) -> bool:
        return self is other or (
            isinstance(other, GraphQLInputField)
            and self.type == other.type
            and self.default_value == other.default_value
            and self.description == other.description
            and self.deprecation_reason == other.deprecation_reason
            and self.extensions == other.extensions
            and self.out_name == other.out_name
        )

    def to_kwargs(self) -> GraphQLInputFieldKwargs:
        return GraphQLInputFieldKwargs(
            type_=self.type,
            default_value=self.default_value,
            description=self.description,
            deprecation_reason=self.deprecation_reason,
            out_name=self.out_name,
            extensions=self.extensions,
            ast_node=self.ast_node,
        )

    def __copy__(self) -> GraphQLInputField:  # pragma: no cover
        return self.__class__(**self.to_kwargs())


def is_required_input_field(field: GraphQLInputField) -> bool:
    return is_non_null_type(field.type) and field.default_value is Undefined


# Wrapper types


class GraphQLList(GraphQLWrappingType[GT]):
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

    def __str__(self) -> str:
        return f"[{self.of_type}]"


def is_list_type(type_: Any) -> TypeGuard[GraphQLList]:
    return isinstance(type_, GraphQLList)


def assert_list_type(type_: Any) -> GraphQLList:
    if not is_list_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL List type.")
    return type_


GNT = TypeVar("GNT", bound="GraphQLNullableType", covariant=True)


class GraphQLNonNull(GraphQLWrappingType[GNT]):
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

    def __init__(self, type_: GNT):
        super().__init__(type_=type_)

    def __str__(self) -> str:
        return f"{self.of_type}!"


# These types can all accept null as a value.

GraphQLNullableType: TypeAlias = Union[
    GraphQLScalarType,
    GraphQLObjectType,
    GraphQLInterfaceType,
    GraphQLUnionType,
    GraphQLEnumType,
    GraphQLInputObjectType,
    GraphQLList,
]


# These types may be used as input types for arguments and directives.

GraphQLNullableInputType: TypeAlias = Union[
    GraphQLScalarType,
    GraphQLEnumType,
    GraphQLInputObjectType,
    # actually GraphQLList[GraphQLInputType], but we can't recurse
    GraphQLList,
]

GraphQLInputType: TypeAlias = Union[
    GraphQLNullableInputType, GraphQLNonNull[GraphQLNullableInputType]
]


# These types may be used as output types as the result of fields.

GraphQLNullableOutputType: TypeAlias = Union[
    GraphQLScalarType,
    GraphQLObjectType,
    GraphQLInterfaceType,
    GraphQLUnionType,
    GraphQLEnumType,
    # actually GraphQLList[GraphQLOutputType], but we can't recurse
    GraphQLList,
]

GraphQLOutputType: TypeAlias = Union[
    GraphQLNullableOutputType, GraphQLNonNull[GraphQLNullableOutputType]
]


# Predicates and Assertions


def is_input_type(type_: Any) -> TypeGuard[GraphQLInputType]:
    return isinstance(
        type_, (GraphQLScalarType, GraphQLEnumType, GraphQLInputObjectType)
    ) or (isinstance(type_, GraphQLWrappingType) and is_input_type(type_.of_type))


def assert_input_type(type_: Any) -> GraphQLInputType:
    if not is_input_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL input type.")
    return type_


def is_output_type(type_: Any) -> TypeGuard[GraphQLOutputType]:
    return isinstance(
        type_,
        (
            GraphQLScalarType,
            GraphQLObjectType,
            GraphQLInterfaceType,
            GraphQLUnionType,
            GraphQLEnumType,
        ),
    ) or (isinstance(type_, GraphQLWrappingType) and is_output_type(type_.of_type))


def assert_output_type(type_: Any) -> GraphQLOutputType:
    if not is_output_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL output type.")
    return type_


def is_non_null_type(type_: Any) -> TypeGuard[GraphQLNonNull]:
    return isinstance(type_, GraphQLNonNull)


def assert_non_null_type(type_: Any) -> GraphQLNonNull:
    if not is_non_null_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Non-Null type.")
    return type_


def is_nullable_type(type_: Any) -> TypeGuard[GraphQLNullableType]:
    return isinstance(
        type_,
        (
            GraphQLScalarType,
            GraphQLObjectType,
            GraphQLInterfaceType,
            GraphQLUnionType,
            GraphQLEnumType,
            GraphQLInputObjectType,
            GraphQLList,
        ),
    )


def assert_nullable_type(type_: Any) -> GraphQLNullableType:
    if not is_nullable_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL nullable type.")
    return type_


@overload
def get_nullable_type(type_: None) -> None:
    ...


@overload
def get_nullable_type(type_: GraphQLNullableType) -> GraphQLNullableType:
    ...


@overload
def get_nullable_type(type_: GraphQLNonNull) -> GraphQLNullableType:
    ...


def get_nullable_type(
    type_: Optional[Union[GraphQLNullableType, GraphQLNonNull]]
) -> Optional[GraphQLNullableType]:
    """Unwrap possible non-null type"""
    if is_non_null_type(type_):
        type_ = type_.of_type
    return cast(Optional[GraphQLNullableType], type_)


# These named types do not include modifiers like List or NonNull.

GraphQLNamedInputType: TypeAlias = Union[
    GraphQLScalarType, GraphQLEnumType, GraphQLInputObjectType
]

GraphQLNamedOutputType: TypeAlias = Union[
    GraphQLScalarType,
    GraphQLObjectType,
    GraphQLInterfaceType,
    GraphQLUnionType,
    GraphQLEnumType,
]


def is_named_type(type_: Any) -> TypeGuard[GraphQLNamedType]:
    return isinstance(type_, GraphQLNamedType)


def assert_named_type(type_: Any) -> GraphQLNamedType:
    if not is_named_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL named type.")
    return type_


@overload
def get_named_type(type_: None) -> None:
    ...


@overload
def get_named_type(type_: GraphQLType) -> GraphQLNamedType:
    ...


def get_named_type(type_: Optional[GraphQLType]) -> Optional[GraphQLNamedType]:
    """Unwrap possible wrapping type"""
    if type_:
        unwrapped_type = type_
        while is_wrapping_type(unwrapped_type):
            unwrapped_type = unwrapped_type.of_type
        return cast(GraphQLNamedType, unwrapped_type)
    return None


# These types may describe types which may be leaf values.

GraphQLLeafType: TypeAlias = Union[GraphQLScalarType, GraphQLEnumType]


def is_leaf_type(type_: Any) -> TypeGuard[GraphQLLeafType]:
    return isinstance(type_, (GraphQLScalarType, GraphQLEnumType))


def assert_leaf_type(type_: Any) -> GraphQLLeafType:
    if not is_leaf_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL leaf type.")
    return type_


# These types may describe the parent context of a selection set.

GraphQLCompositeType: TypeAlias = Union[
    GraphQLObjectType, GraphQLInterfaceType, GraphQLUnionType
]


def is_composite_type(type_: Any) -> TypeGuard[GraphQLCompositeType]:
    return isinstance(
        type_, (GraphQLObjectType, GraphQLInterfaceType, GraphQLUnionType)
    )


def assert_composite_type(type_: Any) -> GraphQLType:
    if not is_composite_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL composite type.")
    return type_


# These types may describe abstract types.

GraphQLAbstractType: TypeAlias = Union[GraphQLInterfaceType, GraphQLUnionType]


def is_abstract_type(type_: Any) -> TypeGuard[GraphQLAbstractType]:
    return isinstance(type_, (GraphQLInterfaceType, GraphQLUnionType))


def assert_abstract_type(type_: Any) -> GraphQLAbstractType:
    if not is_abstract_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL composite type.")
    return type_
