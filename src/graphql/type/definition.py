"""GraphQL type definitions."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Collection,
    Dict,
    Generic,
    Mapping,
    NamedTuple,
    Optional,
    TypeVar,
    Union,
    cast,
    overload,
)

try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict
try:
    from typing import TypeAlias, TypeGuard
except ImportError:  # Python < 3.10
    from typing_extensions import TypeAlias, TypeGuard

if TYPE_CHECKING:
    from enum import Enum

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

if TYPE_CHECKING:
    from .schema import GraphQLSchema


__all__ = [
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
    "GraphQLNamedInputType",
    "GraphQLNamedOutputType",
    "GraphQLNamedType",
    "GraphQLNamedTypeKwargs",
    "GraphQLNonNull",
    "GraphQLNullableInputType",
    "GraphQLNullableOutputType",
    "GraphQLNullableType",
    "GraphQLObjectType",
    "GraphQLObjectTypeKwargs",
    "GraphQLOutputType",
    "GraphQLResolveInfo",
    "GraphQLScalarLiteralParser",
    "GraphQLScalarSerializer",
    "GraphQLScalarType",
    "GraphQLScalarTypeKwargs",
    "GraphQLScalarValueParser",
    "GraphQLType",
    "GraphQLTypeResolver",
    "GraphQLUnionType",
    "GraphQLUnionTypeKwargs",
    "GraphQLWrappingType",
    "Thunk",
    "ThunkCollection",
    "ThunkMapping",
    "assert_abstract_type",
    "assert_composite_type",
    "assert_enum_type",
    "assert_input_object_type",
    "assert_input_type",
    "assert_interface_type",
    "assert_leaf_type",
    "assert_list_type",
    "assert_named_type",
    "assert_non_null_type",
    "assert_nullable_type",
    "assert_object_type",
    "assert_output_type",
    "assert_scalar_type",
    "assert_type",
    "assert_union_type",
    "assert_wrapping_type",
    "get_named_type",
    "get_nullable_type",
    "is_abstract_type",
    "is_composite_type",
    "is_enum_type",
    "is_input_object_type",
    "is_input_type",
    "is_interface_type",
    "is_leaf_type",
    "is_list_type",
    "is_named_type",
    "is_non_null_type",
    "is_nullable_type",
    "is_object_type",
    "is_output_type",
    "is_required_argument",
    "is_required_input_field",
    "is_scalar_type",
    "is_type",
    "is_union_type",
    "is_wrapping_type",
    "resolve_thunk",
]


class GraphQLType:
    """Base class for all GraphQL types"""

    # Note: We don't use slots for GraphQLType objects because memory considerations
    # are not really important for the schema definition, and it would make caching
    # properties slower or more complicated.


# There are predicates for each kind of GraphQL type.


def is_type(type_: Any) -> TypeGuard[GraphQLType]:
    """Check whether this is a GraphQL type."""
    return isinstance(type_, GraphQLType)


def assert_type(type_: Any) -> GraphQLType:
    """Assert that this is a GraphQL type."""
    if not is_type(type_):
        msg = f"Expected {type_} to be a GraphQL type."
        raise TypeError(msg)
    return type_


# These types wrap and modify other types

GT_co = TypeVar("GT_co", bound=GraphQLType, covariant=True)


class GraphQLWrappingType(GraphQLType, Generic[GT_co]):
    """Base class for all GraphQL wrapping types"""

    of_type: GT_co

    def __init__(self, type_: GT_co) -> None:
        self.of_type = type_

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.of_type!r}>"


def is_wrapping_type(type_: Any) -> TypeGuard[GraphQLWrappingType]:
    """Check whether this is a GraphQL wrapping type."""
    return isinstance(type_, GraphQLWrappingType)


def assert_wrapping_type(type_: Any) -> GraphQLWrappingType:
    """Assert that this is a GraphQL wrapping type."""
    if not is_wrapping_type(type_):
        msg = f"Expected {type_} to be a GraphQL wrapping type."
        raise TypeError(msg)
    return type_


class GraphQLNamedTypeKwargs(TypedDict, total=False):
    """Arguments for GraphQL named types"""

    name: str
    description: str | None
    extensions: dict[str, Any]
    # unfortunately, we cannot make the following more specific, because they are
    # used by subclasses with different node types and typed dicts cannot be refined
    ast_node: Any | None
    extension_ast_nodes: tuple[Any, ...]


class GraphQLNamedType(GraphQLType):
    """Base class for all GraphQL named types"""

    name: str
    description: str | None
    extensions: dict[str, Any]
    ast_node: TypeDefinitionNode | None
    extension_ast_nodes: tuple[TypeExtensionNode, ...]

    reserved_types: Mapping[str, GraphQLNamedType] = {}

    def __new__(cls, name: str, *_args: Any, **_kwargs: Any) -> GraphQLNamedType:
        """Create a GraphQL named type."""
        if name in cls.reserved_types:
            msg = f"Redefinition of reserved type {name!r}"
            raise TypeError(msg)
        return super().__new__(cls)

    def __reduce__(self) -> tuple[Callable, tuple]:
        return self._get_instance, (self.name, tuple(self.to_kwargs().items()))

    @classmethod
    def _get_instance(cls, name: str, args: tuple) -> GraphQLNamedType:
        try:
            return cls.reserved_types[name]
        except KeyError:
            return cls(**dict(args))  # pyright: ignore

    def __init__(
        self,
        name: str,
        description: str | None = None,
        extensions: dict[str, Any] | None = None,
        ast_node: TypeDefinitionNode | None = None,
        extension_ast_nodes: Collection[TypeExtensionNode] | None = None,
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
        """Get corresponding arguments."""
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
    """Arguments for GraphQL scalar types"""

    serialize: GraphQLScalarSerializer | None
    parse_value: GraphQLScalarValueParser | None
    parse_literal: GraphQLScalarLiteralParser | None
    specified_by_url: str | None


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

    specified_by_url: str | None
    ast_node: ScalarTypeDefinitionNode | None
    extension_ast_nodes: tuple[ScalarTypeExtensionNode, ...]

    def __init__(
        self,
        name: str,
        serialize: GraphQLScalarSerializer | None = None,
        parse_value: GraphQLScalarValueParser | None = None,
        parse_literal: GraphQLScalarLiteralParser | None = None,
        description: str | None = None,
        specified_by_url: str | None = None,
        extensions: dict[str, Any] | None = None,
        ast_node: ScalarTypeDefinitionNode | None = None,
        extension_ast_nodes: Collection[ScalarTypeExtensionNode] | None = None,
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
        if parse_literal is not None and parse_value is None:
            msg = (
                f"{name} must provide both 'parse_value' and 'parse_literal' functions."
            )
            raise TypeError(msg)
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
        self, node: ValueNode, variables: dict[str, Any] | None = None
    ) -> Any:
        """Parses an externally provided literal value to use as an input.

        This default method uses the parse_value method and should be replaced
        with a more specific version when creating a scalar type.
        """
        return self.parse_value(value_from_ast_untyped(node, variables))

    def to_kwargs(self) -> GraphQLScalarTypeKwargs:
        """Get corresponding arguments."""
        # noinspection PyArgumentList
        return GraphQLScalarTypeKwargs(
            super().to_kwargs(),  # type: ignore
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
    """Check whether this is a GraphQL scalar type."""
    return isinstance(type_, GraphQLScalarType)


def assert_scalar_type(type_: Any) -> GraphQLScalarType:
    """Assert that this is a GraphQL scalar type."""
    if not is_scalar_type(type_):
        msg = f"Expected {type_} to be a GraphQL Scalar type."
        raise TypeError(msg)
    return type_


GraphQLArgumentMap: TypeAlias = Dict[str, "GraphQLArgument"]


class GraphQLFieldKwargs(TypedDict, total=False):
    """Arguments for GraphQL fields"""

    type_: GraphQLOutputType
    args: GraphQLArgumentMap | None
    resolve: GraphQLFieldResolver | None
    subscribe: GraphQLFieldResolver | None
    description: str | None
    deprecation_reason: str | None
    extensions: dict[str, Any]
    ast_node: FieldDefinitionNode | None


class GraphQLField:  # noqa: PLW1641
    """Definition of a GraphQL field"""

    type: GraphQLOutputType
    args: GraphQLArgumentMap
    resolve: GraphQLFieldResolver | None
    subscribe: GraphQLFieldResolver | None
    description: str | None
    deprecation_reason: str | None
    extensions: dict[str, Any]
    ast_node: FieldDefinitionNode | None

    def __init__(
        self,
        type_: GraphQLOutputType,
        args: GraphQLArgumentMap | None = None,
        resolve: GraphQLFieldResolver | None = None,
        subscribe: GraphQLFieldResolver | None = None,
        description: str | None = None,
        deprecation_reason: str | None = None,
        extensions: dict[str, Any] | None = None,
        ast_node: FieldDefinitionNode | None = None,
    ) -> None:
        if args:
            args = {
                assert_name(name): value
                if isinstance(value, GraphQLArgument)
                else GraphQLArgument(cast("GraphQLInputType", value))
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

    def __eq__(self, other: object) -> bool:
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
        """Get corresponding arguments."""
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


TContext = TypeVar("TContext")  # pylint: disable=invalid-name

try:

    class GraphQLResolveInfo(NamedTuple, Generic[TContext]):  # pyright: ignore
        """Collection of information passed to the resolvers.

        This is always passed as the first argument to the resolvers.

        Note that contrary to the JavaScript implementation, the context (commonly used
        to represent an authenticated user, or request-specific caches) is included here
        and not passed as an additional argument.
        """

        field_name: str
        field_nodes: list[FieldNode]
        return_type: GraphQLOutputType
        parent_type: GraphQLObjectType
        path: Path
        schema: GraphQLSchema
        fragments: dict[str, FragmentDefinitionNode]
        root_value: Any
        operation: OperationDefinitionNode
        variable_values: dict[str, Any]
        context: TContext
        is_awaitable: Callable[[Any], bool]
except TypeError as error:  # pragma: no cover
    if "Multiple inheritance with NamedTuple is not supported" not in str(error):
        raise  # only catch expected error for Python 3.9 and 3.10

    class GraphQLResolveInfo(NamedTuple):  # type: ignore[no-redef]
        """Collection of information passed to the resolvers.

        This is always passed as the first argument to the resolvers.

        Note that contrary to the JavaScript implementation, the context (commonly used
        to represent an authenticated user, or request-specific caches) is included here
        and not passed as an additional argument.
        """

        field_name: str
        field_nodes: list[FieldNode]
        return_type: GraphQLOutputType
        parent_type: GraphQLObjectType
        path: Path
        schema: GraphQLSchema
        fragments: dict[str, FragmentDefinitionNode]
        root_value: Any
        operation: OperationDefinitionNode
        variable_values: dict[str, Any]
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
    """Python arguments for GraphQL arguments"""

    type_: GraphQLInputType
    default_value: Any
    description: str | None
    deprecation_reason: str | None
    out_name: str | None
    extensions: dict[str, Any]
    ast_node: InputValueDefinitionNode | None


class GraphQLArgument:  # noqa: PLW1641
    """Definition of a GraphQL argument"""

    type: GraphQLInputType
    default_value: Any
    description: str | None
    deprecation_reason: str | None
    out_name: str | None  # for transforming names (extension of GraphQL.js)
    extensions: dict[str, Any]
    ast_node: InputValueDefinitionNode | None

    def __init__(
        self,
        type_: GraphQLInputType,
        default_value: Any = Undefined,
        description: str | None = None,
        deprecation_reason: str | None = None,
        out_name: str | None = None,
        extensions: dict[str, Any] | None = None,
        ast_node: InputValueDefinitionNode | None = None,
    ) -> None:
        self.type = type_
        self.default_value = default_value
        self.description = description
        self.deprecation_reason = deprecation_reason
        self.out_name = out_name
        self.extensions = extensions or {}
        self.ast_node = ast_node

    def __eq__(self, other: object) -> bool:
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
        """Get corresponding arguments."""
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
    """Check whether the argument is required."""
    return is_non_null_type(arg.type) and arg.default_value is Undefined


class GraphQLObjectTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    """Arguments for GraphQL object types"""

    fields: GraphQLFieldMap
    interfaces: tuple[GraphQLInterfaceType, ...]
    is_type_of: GraphQLIsTypeOfFn | None


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

    is_type_of: GraphQLIsTypeOfFn | None
    ast_node: ObjectTypeDefinitionNode | None
    extension_ast_nodes: tuple[ObjectTypeExtensionNode, ...]

    def __init__(
        self,
        name: str,
        fields: ThunkMapping[GraphQLField],
        interfaces: ThunkCollection[GraphQLInterfaceType] | None = None,
        is_type_of: GraphQLIsTypeOfFn | None = None,
        extensions: dict[str, Any] | None = None,
        description: str | None = None,
        ast_node: ObjectTypeDefinitionNode | None = None,
        extension_ast_nodes: Collection[ObjectTypeExtensionNode] | None = None,
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
        """Get corresponding arguments."""
        # noinspection PyArgumentList
        return GraphQLObjectTypeKwargs(
            super().to_kwargs(),  # type: ignore
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
            msg = f"{self.name} fields cannot be resolved. {error}"
            raise cls(msg) from error
        return {
            assert_name(name): value
            if isinstance(value, GraphQLField)
            else GraphQLField(value)
            for name, value in fields.items()
        }

    @cached_property
    def interfaces(self) -> tuple[GraphQLInterfaceType, ...]:
        """Get provided interfaces."""
        try:
            interfaces: Collection[GraphQLInterfaceType] = resolve_thunk(
                self._interfaces  # type: ignore
            )
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            msg = f"{self.name} interfaces cannot be resolved. {error}"
            raise cls(msg) from error
        return tuple(interfaces) if interfaces else ()


def is_object_type(type_: Any) -> TypeGuard[GraphQLObjectType]:
    """Check whether this is a graphql object type"""
    return isinstance(type_, GraphQLObjectType)


def assert_object_type(type_: Any) -> GraphQLObjectType:
    """Assume that this is a graphql object type"""
    if not is_object_type(type_):
        msg = f"Expected {type_} to be a GraphQL Object type."
        raise TypeError(msg)
    return type_


class GraphQLInterfaceTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    """Arguments for GraphQL interface types"""

    fields: GraphQLFieldMap
    interfaces: tuple[GraphQLInterfaceType, ...]
    resolve_type: GraphQLTypeResolver | None


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

    resolve_type: GraphQLTypeResolver | None
    ast_node: InterfaceTypeDefinitionNode | None
    extension_ast_nodes: tuple[InterfaceTypeExtensionNode, ...]

    def __init__(
        self,
        name: str,
        fields: ThunkMapping[GraphQLField],
        interfaces: ThunkCollection[GraphQLInterfaceType] | None = None,
        resolve_type: GraphQLTypeResolver | None = None,
        description: str | None = None,
        extensions: dict[str, Any] | None = None,
        ast_node: InterfaceTypeDefinitionNode | None = None,
        extension_ast_nodes: Collection[InterfaceTypeExtensionNode] | None = None,
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
        """Get corresponding arguments."""
        # noinspection PyArgumentList
        return GraphQLInterfaceTypeKwargs(
            super().to_kwargs(),  # type: ignore
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
            msg = f"{self.name} fields cannot be resolved. {error}"
            raise cls(msg) from error
        return {
            assert_name(name): value
            if isinstance(value, GraphQLField)
            else GraphQLField(value)
            for name, value in fields.items()
        }

    @cached_property
    def interfaces(self) -> tuple[GraphQLInterfaceType, ...]:
        """Get provided interfaces."""
        try:
            interfaces: Collection[GraphQLInterfaceType] = resolve_thunk(
                self._interfaces  # type: ignore
            )
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            msg = f"{self.name} interfaces cannot be resolved. {error}"
            raise cls(msg) from error
        return tuple(interfaces) if interfaces else ()


def is_interface_type(type_: Any) -> TypeGuard[GraphQLInterfaceType]:
    """Check whether this is a GraphQL interface type."""
    return isinstance(type_, GraphQLInterfaceType)


def assert_interface_type(type_: Any) -> GraphQLInterfaceType:
    """Assert that this is a GraphQL interface type."""
    if not is_interface_type(type_):
        msg = f"Expected {type_} to be a GraphQL Interface type."
        raise TypeError(msg)
    return type_


class GraphQLUnionTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    """Arguments for GraphQL union types"""

    types: tuple[GraphQLObjectType, ...]
    resolve_type: GraphQLTypeResolver | None


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

    resolve_type: GraphQLTypeResolver | None
    ast_node: UnionTypeDefinitionNode | None
    extension_ast_nodes: tuple[UnionTypeExtensionNode, ...]

    def __init__(
        self,
        name: str,
        types: ThunkCollection[GraphQLObjectType],
        resolve_type: GraphQLTypeResolver | None = None,
        description: str | None = None,
        extensions: dict[str, Any] | None = None,
        ast_node: UnionTypeDefinitionNode | None = None,
        extension_ast_nodes: Collection[UnionTypeExtensionNode] | None = None,
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
        """Get corresponding arguments."""
        # noinspection PyArgumentList
        return GraphQLUnionTypeKwargs(
            super().to_kwargs(),  # type: ignore
            types=self.types,
            resolve_type=self.resolve_type,
        )

    def __copy__(self) -> GraphQLUnionType:  # pragma: no cover
        return self.__class__(**self.to_kwargs())

    @cached_property
    def types(self) -> tuple[GraphQLObjectType, ...]:
        """Get provided types."""
        try:
            types: Collection[GraphQLObjectType] = resolve_thunk(self._types)
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            msg = f"{self.name} types cannot be resolved. {error}"
            raise cls(msg) from error
        return tuple(types) if types else ()


def is_union_type(type_: Any) -> TypeGuard[GraphQLUnionType]:
    """Check whether this is a GraphQL union type."""
    return isinstance(type_, GraphQLUnionType)


def assert_union_type(type_: Any) -> GraphQLUnionType:
    """Assert that this is a GraphQL union type."""
    if not is_union_type(type_):
        msg = f"Expected {type_} to be a GraphQL Union type."
        raise TypeError(msg)
    return type_


GraphQLEnumValueMap: TypeAlias = Dict[str, "GraphQLEnumValue"]


class GraphQLEnumTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    """Arguments for GraphQL enum types"""

    values: GraphQLEnumValueMap
    names_as_values: bool | None


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
    ast_node: EnumTypeDefinitionNode | None
    extension_ast_nodes: tuple[EnumTypeExtensionNode, ...]

    def __init__(
        self,
        name: str,
        values: GraphQLEnumValueMap | Mapping[str, Any] | type[Enum],
        names_as_values: bool | None = False,
        description: str | None = None,
        extensions: dict[str, Any] | None = None,
        ast_node: EnumTypeDefinitionNode | None = None,
        extension_ast_nodes: Collection[EnumTypeExtensionNode] | None = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            extensions=extensions,
            ast_node=ast_node,
            extension_ast_nodes=extension_ast_nodes,
        )
        try:  # check for enum
            values = cast("Enum", values).__members__  # type: ignore
        except AttributeError:
            if not isinstance(values, Mapping) or not all(
                isinstance(name, str) for name in values
            ):
                try:
                    values = dict(values)  # pyright: ignore
                except (TypeError, ValueError) as error:
                    msg = (
                        f"{name} values must be an Enum or a mapping"
                        " with value names as keys."
                    )
                    raise TypeError(msg) from error
            values = cast("Dict[str, Any]", values)
        else:
            values = cast("Dict[str, Enum]", values)
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
        """Get corresponding arguments."""
        # noinspection PyArgumentList
        return GraphQLEnumTypeKwargs(
            super().to_kwargs(),  # type: ignore
            values=self.values.copy(),
        )

    def __copy__(self) -> GraphQLEnumType:  # pragma: no cover
        return self.__class__(**self.to_kwargs())

    @cached_property
    def _value_lookup(self) -> dict[Any, str]:
        # use first value or name as lookup
        lookup: dict[Any, str] = {}
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
        """Serialize an output value."""
        try:
            return self._value_lookup[output_value]
        except KeyError:  # hashable value not found
            pass
        except TypeError:  # unhashable value, we need to scan all values
            for enum_name, enum_value in self.values.items():
                if enum_value.value == output_value:
                    return enum_name
        msg = f"Enum '{self.name}' cannot represent value: {inspect(output_value)}"
        raise GraphQLError(msg)

    def parse_value(self, input_value: str) -> Any:
        """Parse an enum value."""
        if isinstance(input_value, str):
            try:
                enum_value = self.values[input_value]
            except KeyError as error:
                msg = (
                    f"Value '{input_value}' does not exist in '{self.name}' enum."
                    + did_you_mean_enum_value(self, input_value)
                )
                raise GraphQLError(msg) from error
            return enum_value.value
        value_str = inspect(input_value)
        msg = (
            f"Enum '{self.name}' cannot represent non-string value: {value_str}."
            + did_you_mean_enum_value(self, value_str)
        )
        raise GraphQLError(msg)

    def parse_literal(
        self, value_node: ValueNode, _variables: dict[str, Any] | None = None
    ) -> Any:
        """Parse literal value."""
        # Note: variables will be resolved before calling this method.
        if isinstance(value_node, EnumValueNode):
            try:
                enum_value = self.values[value_node.value]
            except KeyError as error:
                value_str = print_ast(value_node)
                msg = (
                    f"Value '{value_str}' does not exist in '{self.name}' enum."
                    + did_you_mean_enum_value(self, value_str)
                )
                raise GraphQLError(msg, value_node) from error
            return enum_value.value
        value_str = print_ast(value_node)
        msg = (
            f"Enum '{self.name}' cannot represent non-enum value: {value_str}."
            + did_you_mean_enum_value(self, value_str)
        )
        raise GraphQLError(msg, value_node)


def is_enum_type(type_: Any) -> TypeGuard[GraphQLEnumType]:
    """Check whether this is a GraphQL enum type."""
    return isinstance(type_, GraphQLEnumType)


def assert_enum_type(type_: Any) -> GraphQLEnumType:
    """Assert that this is a GraphQL enum type."""
    if not is_enum_type(type_):
        msg = f"Expected {type_} to be a GraphQL Enum type."
        raise TypeError(msg)
    return type_


def did_you_mean_enum_value(enum_type: GraphQLEnumType, unknown_value_str: str) -> str:
    """Return suggestions for enum value."""
    suggested_values = suggestion_list(unknown_value_str, enum_type.values)
    return did_you_mean(suggested_values, "the enum value")


class GraphQLEnumValueKwargs(TypedDict, total=False):
    """Arguments for GraphQL enum values"""

    value: Any
    description: str | None
    deprecation_reason: str | None
    extensions: dict[str, Any]
    ast_node: EnumValueDefinitionNode | None


class GraphQLEnumValue:  # noqa: PLW1641
    """A GraphQL enum value."""

    value: Any
    description: str | None
    deprecation_reason: str | None
    extensions: dict[str, Any]
    ast_node: EnumValueDefinitionNode | None

    def __init__(
        self,
        value: Any = None,
        description: str | None = None,
        deprecation_reason: str | None = None,
        extensions: dict[str, Any] | None = None,
        ast_node: EnumValueDefinitionNode | None = None,
    ) -> None:
        self.value = value
        self.description = description
        self.deprecation_reason = deprecation_reason
        self.extensions = extensions or {}
        self.ast_node = ast_node

    def __eq__(self, other: object) -> bool:
        return self is other or (
            isinstance(other, GraphQLEnumValue)
            and self.value == other.value
            and self.description == other.description
            and self.deprecation_reason == other.deprecation_reason
            and self.extensions == other.extensions
        )

    def to_kwargs(self) -> GraphQLEnumValueKwargs:
        """Get corresponding arguments."""
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
    """Arguments for GraphQL input object types"""

    fields: GraphQLInputFieldMap
    out_type: GraphQLInputFieldOutType | None
    is_one_of: bool


class GraphQLInputObjectType(GraphQLNamedType):
    """Input Object Type Definition

    An input object defines a structured collection of fields which may be supplied
    to a field argument.

    Using ``NonNull`` will ensure that a value must be provided by the query.

    Example::

        NonNullFloat = GraphQLNonNull(GraphQLFloat)

        class GeoPoint(GraphQLInputObjectType):
            name = 'GeoPoint'
            fields = {
                'lat': GraphQLInputField(NonNullFloat),
                'lon': GraphQLInputField(NonNullFloat),
                'alt': GraphQLInputField(
                          GraphQLFloat, default_value=0)
            }

    The outbound values will be Python dictionaries by default, but you can have them
    converted to other types by specifying an ``out_type`` function or class.
    """

    ast_node: InputObjectTypeDefinitionNode | None
    extension_ast_nodes: tuple[InputObjectTypeExtensionNode, ...]
    is_one_of: bool

    def __init__(
        self,
        name: str,
        fields: ThunkMapping[GraphQLInputField],
        description: str | None = None,
        out_type: GraphQLInputFieldOutType | None = None,
        extensions: dict[str, Any] | None = None,
        ast_node: InputObjectTypeDefinitionNode | None = None,
        extension_ast_nodes: Collection[InputObjectTypeExtensionNode] | None = None,
        is_one_of: bool = False,
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
        self.is_one_of = is_one_of

    @staticmethod
    def out_type(value: dict[str, Any]) -> Any:
        """Transform outbound values (this is an extension of GraphQL.js).

        This default implementation passes values unaltered as dictionaries.
        """
        return value

    def to_kwargs(self) -> GraphQLInputObjectTypeKwargs:
        """Get corresponding arguments."""
        # noinspection PyArgumentList
        return GraphQLInputObjectTypeKwargs(
            super().to_kwargs(),  # type: ignore
            fields=self.fields.copy(),
            out_type=None
            if self.out_type is GraphQLInputObjectType.out_type
            else self.out_type,
            is_one_of=self.is_one_of,
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
            msg = f"{self.name} fields cannot be resolved. {error}"
            raise cls(msg) from error
        return {
            assert_name(name): value
            if isinstance(value, GraphQLInputField)
            else GraphQLInputField(value)
            for name, value in fields.items()
        }


def is_input_object_type(type_: Any) -> TypeGuard[GraphQLInputObjectType]:
    """Check whether this is a GraphQL input type."""
    return isinstance(type_, GraphQLInputObjectType)


def assert_input_object_type(type_: Any) -> GraphQLInputObjectType:
    """Assert that this is a GraphQL input type."""
    if not is_input_object_type(type_):
        msg = f"Expected {type_} to be a GraphQL Input Object type."
        raise TypeError(msg)
    return type_


class GraphQLInputFieldKwargs(TypedDict, total=False):
    """Arguments for GraphQL input fields"""

    type_: GraphQLInputType
    default_value: Any
    description: str | None
    deprecation_reason: str | None
    out_name: str | None
    extensions: dict[str, Any]
    ast_node: InputValueDefinitionNode | None


class GraphQLInputField:  # noqa: PLW1641
    """Definition of a GraphQL input field"""

    type: GraphQLInputType
    default_value: Any
    description: str | None
    deprecation_reason: str | None
    out_name: str | None  # for transforming names (extension of GraphQL.js)
    extensions: dict[str, Any]
    ast_node: InputValueDefinitionNode | None

    def __init__(
        self,
        type_: GraphQLInputType,
        default_value: Any = Undefined,
        description: str | None = None,
        deprecation_reason: str | None = None,
        out_name: str | None = None,
        extensions: dict[str, Any] | None = None,
        ast_node: InputValueDefinitionNode | None = None,
    ) -> None:
        self.type = type_
        self.default_value = default_value
        self.description = description
        self.deprecation_reason = deprecation_reason
        self.out_name = out_name
        self.extensions = extensions or {}
        self.ast_node = ast_node

    def __eq__(self, other: object) -> bool:
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
        """Get corresponding arguments."""
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
    """Check whether this is input field is required."""
    return is_non_null_type(field.type) and field.default_value is Undefined


# Wrapper types


class GraphQLList(GraphQLWrappingType[GT_co]):
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

    def __init__(self, type_: GT_co) -> None:
        super().__init__(type_=type_)

    def __str__(self) -> str:
        return f"[{self.of_type}]"


def is_list_type(type_: Any) -> TypeGuard[GraphQLList]:
    """Check whether this is a GraphQL list type."""
    return isinstance(type_, GraphQLList)


def assert_list_type(type_: Any) -> GraphQLList:
    """Assert that this is a GraphQL list type."""
    if not is_list_type(type_):
        msg = f"Expected {type_} to be a GraphQL List type."
        raise TypeError(msg)
    return type_


GNT_co = TypeVar("GNT_co", bound="GraphQLNullableType", covariant=True)


class GraphQLNonNull(GraphQLWrappingType[GNT_co]):
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
                'id': GraphQLField(GraphQLNonNull(GraphQLString))
            }

    Note: the enforcement of non-nullability occurs within the executor.
    """

    def __init__(self, type_: GNT_co) -> None:
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
    """Check whether this is a GraphQL input type."""
    return isinstance(
        type_, (GraphQLScalarType, GraphQLEnumType, GraphQLInputObjectType)
    ) or (isinstance(type_, GraphQLWrappingType) and is_input_type(type_.of_type))


def assert_input_type(type_: Any) -> GraphQLInputType:
    """Assert that this is a GraphQL input type."""
    if not is_input_type(type_):
        msg = f"Expected {type_} to be a GraphQL input type."
        raise TypeError(msg)
    return type_


def is_output_type(type_: Any) -> TypeGuard[GraphQLOutputType]:
    """Check whether this is a GraphQL output type."""
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
    """Assert that this is a GraphQL output type."""
    if not is_output_type(type_):
        msg = f"Expected {type_} to be a GraphQL output type."
        raise TypeError(msg)
    return type_


def is_non_null_type(type_: Any) -> TypeGuard[GraphQLNonNull]:
    """Check whether this is a non-null GraphQL type."""
    return isinstance(type_, GraphQLNonNull)


def assert_non_null_type(type_: Any) -> GraphQLNonNull:
    """Assert that this is a non-null GraphQL type."""
    if not is_non_null_type(type_):
        msg = f"Expected {type_} to be a GraphQL Non-Null type."
        raise TypeError(msg)
    return type_


def is_nullable_type(type_: Any) -> TypeGuard[GraphQLNullableType]:
    """Check whether this is a nullable GraphQL type."""
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
    """Assert that this is a nullable GraphQL type."""
    if not is_nullable_type(type_):
        msg = f"Expected {type_} to be a GraphQL nullable type."
        raise TypeError(msg)
    return type_


@overload
def get_nullable_type(type_: None) -> None: ...


@overload
def get_nullable_type(type_: GraphQLNullableType) -> GraphQLNullableType: ...


@overload
def get_nullable_type(type_: GraphQLNonNull) -> GraphQLNullableType: ...


def get_nullable_type(
    type_: GraphQLNullableType | GraphQLNonNull | None,
) -> GraphQLNullableType | None:
    """Unwrap possible non-null type"""
    if is_non_null_type(type_):
        type_ = type_.of_type
    return cast("Optional[GraphQLNullableType]", type_)


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
    """Check whether this is a named GraphQL type."""
    return isinstance(type_, GraphQLNamedType)


def assert_named_type(type_: Any) -> GraphQLNamedType:
    """Assert that this is a named GraphQL type."""
    if not is_named_type(type_):
        msg = f"Expected {type_} to be a GraphQL named type."
        raise TypeError(msg)
    return type_


@overload
def get_named_type(type_: None) -> None: ...


@overload
def get_named_type(type_: GraphQLType) -> GraphQLNamedType: ...


def get_named_type(type_: GraphQLType | None) -> GraphQLNamedType | None:
    """Unwrap possible wrapping type"""
    if type_:
        unwrapped_type = type_
        while is_wrapping_type(unwrapped_type):
            unwrapped_type = unwrapped_type.of_type
        return cast("GraphQLNamedType", unwrapped_type)
    return None


# These types may describe types which may be leaf values.

GraphQLLeafType: TypeAlias = Union[GraphQLScalarType, GraphQLEnumType]


def is_leaf_type(type_: Any) -> TypeGuard[GraphQLLeafType]:
    """Check whether this is a GraphQL leaf type."""
    return isinstance(type_, (GraphQLScalarType, GraphQLEnumType))


def assert_leaf_type(type_: Any) -> GraphQLLeafType:
    """Assert that this is a GraphQL leaf type."""
    if not is_leaf_type(type_):
        msg = f"Expected {type_} to be a GraphQL leaf type."
        raise TypeError(msg)
    return type_


# These types may describe the parent context of a selection set.

GraphQLCompositeType: TypeAlias = Union[
    GraphQLObjectType, GraphQLInterfaceType, GraphQLUnionType
]


def is_composite_type(type_: Any) -> TypeGuard[GraphQLCompositeType]:
    """Check whether this is a GraphQL composite type."""
    return isinstance(
        type_, (GraphQLObjectType, GraphQLInterfaceType, GraphQLUnionType)
    )


def assert_composite_type(type_: Any) -> GraphQLCompositeType:
    """Assert that this is a GraphQL composite type."""
    if not is_composite_type(type_):
        msg = f"Expected {type_} to be a GraphQL composite type."
        raise TypeError(msg)
    return type_


# These types may describe abstract types.

GraphQLAbstractType: TypeAlias = Union[GraphQLInterfaceType, GraphQLUnionType]


def is_abstract_type(type_: Any) -> TypeGuard[GraphQLAbstractType]:
    """Check whether this is a GraphQL abstract type."""
    return isinstance(type_, (GraphQLInterfaceType, GraphQLUnionType))


def assert_abstract_type(type_: Any) -> GraphQLAbstractType:
    """Assert that this is a GraphQL abstract type."""
    if not is_abstract_type(type_):
        msg = f"Expected {type_} to be a GraphQL composite type."
        raise TypeError(msg)
    return type_
