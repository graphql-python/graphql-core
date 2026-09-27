"""GraphQL type definitions."""

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
    is_collection,
    is_description,
    suggestion_list,
)
from ..utilities.value_from_ast_untyped import value_from_ast_untyped
from .assert_name import assert_enum_value_name, assert_name

try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict

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
    "GraphQLEnumValuesDefinition",
    "GraphQLField",
    "GraphQLFieldKwargs",
    "GraphQLFieldMap",
    "GraphQLFieldResolver",
    "GraphQLInputField",
    "GraphQLInputFieldKwargs",
    "GraphQLInputFieldMap",
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
    # are not really important for the schema definition and it would make caching
    # properties slower or more complicated.


# There are predicates for each kind of GraphQL type.


def is_type(type_: Any) -> bool:
    """Check whether the given value is any GraphQL type.

    :param type_: the value to inspect
    :returns: whether the value is any GraphQL type

    >>> from graphql import build_schema, GraphQLList, GraphQLString, is_type
    >>> schema = build_schema('''
    ...     type Query {
    ...       name: String
    ...     }
    ... ''')
    >>> is_type(GraphQLString)
    True
    >>> is_type(GraphQLList(GraphQLString))
    True
    >>> is_type(schema.get_type('Query'))
    True
    >>> is_type('String')
    False
    """
    return isinstance(type_, GraphQLType)


def assert_type(type_: Any) -> GraphQLType:
    """Return the value as a GraphQL type, or raise a TypeError if it is not one.

    :param type_: the value to inspect
    :returns: the value typed as a GraphQL type

    >>> from graphql import build_schema, assert_type
    >>> schema = build_schema('''
    ...     type Query {
    ...       name: String
    ...     }
    ... ''')
    >>> query_type = assert_type(schema.get_type('Query'))
    >>> str(query_type)
    'Query'
    >>> assert_type('Query')
    Traceback (most recent call last):
    ...
    TypeError: Expected Query to be a GraphQL type.
    """
    if not is_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL type.")
    return cast(GraphQLType, type_)


# These types wrap and modify other types

GT = TypeVar("GT", bound=GraphQLType)


class GraphQLWrappingType(GraphQLType, Generic[GT]):
    """Base class for all GraphQL wrapping types

    These types wrap and modify other types. The concrete wrapping types are
    :class:`GraphQLList` and :class:`GraphQLNonNull`.

    :param type_: the type to wrap

    >>> from graphql import GraphQLList, GraphQLString, GraphQLWrappingType
    >>> string_list = GraphQLList(GraphQLString)
    >>> isinstance(string_list, GraphQLWrappingType)
    True
    >>> string_list.of_type
    <GraphQLScalarType 'String'>
    """

    of_type: GT
    """The type wrapped by this list or non-null type."""

    def __init__(self, type_: GT) -> None:
        if not is_type(type_):
            raise TypeError(
                f"Can only create a wrapper for a GraphQLType, but got: {type_}."
            )
        self.of_type = type_

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.of_type!r}>"


def is_wrapping_type(type_: Any) -> bool:
    """Check whether the given value is a GraphQL list or non-null wrapper type.

    :param type_: the value to inspect
    :returns: whether the value is a GraphQL list or non-null wrapper type

    >>> from graphql import (
    ...     GraphQLList, GraphQLNonNull, GraphQLString, is_wrapping_type)
    >>> is_wrapping_type(GraphQLList(GraphQLString))
    True
    >>> is_wrapping_type(GraphQLNonNull(GraphQLString))
    True
    >>> is_wrapping_type(GraphQLString)
    False
    """
    return isinstance(type_, GraphQLWrappingType)


def assert_wrapping_type(type_: Any) -> GraphQLWrappingType:
    """Return the value as a GraphQL wrapping type, or raise a TypeError otherwise.

    :param type_: the value to inspect
    :returns: the value typed as a GraphQL wrapping type

    >>> from graphql import GraphQLList, GraphQLString, assert_wrapping_type
    >>> wrapping_type = assert_wrapping_type(GraphQLList(GraphQLString))
    >>> str(wrapping_type)
    '[String]'
    >>> assert_wrapping_type(GraphQLString)
    Traceback (most recent call last):
    ...
    TypeError: Expected String to be a GraphQL wrapping type.
    """
    if not is_wrapping_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL wrapping type.")
    return cast(GraphQLWrappingType, type_)


class GraphQLNamedTypeKwargs(TypedDict, total=False):
    """Arguments used to construct a GraphQL named type.

    This is the type of the dictionary returned by
    :meth:`GraphQLNamedType.to_kwargs`.
    """

    name: str
    """The GraphQL name for this schema element."""
    description: Optional[str]
    """Human-readable description for this schema element, if provided."""
    extensions: Dict[str, Any]
    """Custom extension fields reserved for users."""
    # unfortunately, we cannot make the following more specific, because they are
    # used by subclasses with different node types and typed dicts cannot be refined
    ast_node: Optional[Any]
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: Tuple[Any, ...]
    """AST extension nodes applied to this schema element."""


class GraphQLNamedType(GraphQLType):
    """Base class for all GraphQL named types

    Named types do not include modifiers like List or NonNull.

    :param name: the GraphQL name for this type
    :param description: human-readable description for this type, if provided
    :param extensions: custom extensions; use a unique identifier name for your
        extension, for example the name of your library or project. Do not use a
        shortened identifier as this increases the risk of conflicts. We recommend
        you add at most one extension field, a dictionary which can contain all the
        values you need.
    :param ast_node: AST node from which this type was built, if available
    :param extension_ast_nodes: AST extension nodes applied to this type

    >>> from graphql import GraphQLNamedType, GraphQLList, GraphQLString
    >>> isinstance(GraphQLString, GraphQLNamedType)
    True
    >>> isinstance(GraphQLList(GraphQLString), GraphQLNamedType)
    False
    >>> named_type = GraphQLNamedType(
    ...     'Named', description='A named type.', extensions={'custom': True})
    >>> named_type.name, named_type.description, named_type.extensions
    ('Named', 'A named type.', {'custom': True})
    """

    name: str
    """The GraphQL name for this schema element."""
    description: Optional[str]
    """Human-readable description for this schema element, if provided."""
    extensions: Dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: Optional[TypeDefinitionNode]
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: Tuple[TypeExtensionNode, ...]
    """AST extension nodes applied to this schema element."""

    reserved_types: Dict[str, "GraphQLNamedType"] = {}
    """Registry of reserved types (standard scalars and introspection types).

    Named types with these names cannot be redefined.
    """

    def __new__(cls, name: str, *_args: Any, **_kwargs: Any) -> "GraphQLNamedType":
        """Create a named type, but do not allow to redefine a reserved type."""
        if name in cls.reserved_types:
            raise TypeError(f"Redefinition of reserved type {name!r}")
        return super().__new__(cls)

    def __reduce__(self) -> Tuple[Callable, Tuple]:
        return self._get_instance, (self.name, tuple(self.to_kwargs().items()))

    @classmethod
    def _get_instance(cls, name: str, args: Tuple) -> "GraphQLNamedType":
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
        if description is not None and not is_description(description):
            raise TypeError("The description must be a string.")
        if extensions is None:
            extensions = {}
        elif not isinstance(extensions, dict) or not all(
            isinstance(key, str) for key in extensions
        ):
            raise TypeError(f"{name} extensions must be a dictionary with string keys.")
        if ast_node and not isinstance(ast_node, TypeDefinitionNode):
            raise TypeError(f"{name} AST node must be a TypeDefinitionNode.")
        if extension_ast_nodes:
            if not is_collection(extension_ast_nodes) or not all(
                isinstance(node, TypeExtensionNode) for node in extension_ast_nodes
            ):
                raise TypeError(
                    f"{name} extension AST nodes must be specified"
                    " as a collection of TypeExtensionNode instances."
                )
            if not isinstance(extension_ast_nodes, tuple):
                extension_ast_nodes = tuple(extension_ast_nodes)
        else:
            extension_ast_nodes = ()
        self.name = name
        self.description = description
        self.extensions = extensions
        self.ast_node = ast_node
        self.extension_ast_nodes = extension_ast_nodes

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name!r}>"

    def __str__(self) -> str:
        return self.name

    def to_kwargs(self) -> GraphQLNamedTypeKwargs:
        """Get the keyword arguments that can be used to recreate this type.

        :returns: a dictionary with the constructor arguments for this type

        >>> from graphql import GraphQLNamedType
        >>> named_type = GraphQLNamedType('Named', description='A named type.')
        >>> kwargs = named_type.to_kwargs()
        >>> kwargs['name'], kwargs['description']
        ('Named', 'A named type.')
        >>> GraphQLNamedType(**kwargs).name
        'Named'
        """
        return GraphQLNamedTypeKwargs(
            name=self.name,
            description=self.description,
            extensions=self.extensions,
            ast_node=self.ast_node,
            extension_ast_nodes=self.extension_ast_nodes,
        )

    def __copy__(self) -> "GraphQLNamedType":  # pragma: no cover
        return self.__class__(**self.to_kwargs())


T = TypeVar("T")

ThunkCollection = Union[Callable[[], Collection[T]], Collection[T]]
ThunkMapping = Union[Callable[[], Mapping[str, T]], Mapping[str, T]]
Thunk = Union[Callable[[], T], T]


def resolve_thunk(thunk: Thunk[T]) -> T:
    """Resolve the given thunk.

    Used while defining GraphQL types to allow for circular references in otherwise
    immutable type definitions.

    :param thunk: the thunk (a function without arguments) or value to resolve
    :returns: the result of calling the thunk, or the value itself

    >>> from graphql import GraphQLString, resolve_thunk
    >>> lazy_fields = resolve_thunk(lambda: {'name': GraphQLString})
    >>> fields = resolve_thunk({'name': GraphQLString})
    >>> lazy_fields['name']
    <GraphQLScalarType 'String'>
    >>> fields['name']
    <GraphQLScalarType 'String'>
    """
    return thunk() if callable(thunk) else thunk


GraphQLScalarSerializer = Callable[[Any], Any]
GraphQLScalarValueParser = Callable[[Any], Any]
GraphQLScalarLiteralParser = Callable[[ValueNode, Optional[Dict[str, Any]]], Any]


class GraphQLScalarTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    """Arguments used to construct a GraphQLScalarType.

    This is the type of the dictionary returned by
    :meth:`GraphQLScalarType.to_kwargs`.
    """

    serialize: Optional[GraphQLScalarSerializer]
    """Serializes an internal value to include in a response."""
    parse_value: Optional[GraphQLScalarValueParser]
    """Parses an externally provided value to use as an input."""
    parse_literal: Optional[GraphQLScalarLiteralParser]
    """Parses an externally provided literal value to use as an input."""
    specified_by_url: Optional[str]
    """URL identifying the behavior specified for this custom scalar."""


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

    :param name: the GraphQL name for this scalar type
    :param serialize: function that converts internal values to externally visible
        scalar values
    :param parse_value: function that converts variable input into this scalar's
        internal value
    :param parse_literal: function that converts AST input literals into this
        scalar's internal value
    :param description: human-readable description for this type, if provided
    :param specified_by_url: URL identifying the behavior specified for this
        custom scalar
    :param extensions: custom extensions for this type
    :param ast_node: AST node from which this type was built, if available
    :param extension_ast_nodes: AST extension nodes applied to this type

    >>> from graphql import GraphQLScalarType, IntValueNode, parse, parse_value
    >>> document = parse('''
    ...     "Odd integer values."
    ...     scalar Odd @specifiedBy(url: "https://example.com/odd")
    ...
    ...     extend scalar Odd @specifiedBy(url: "https://example.com/odd-v2")
    ... ''')
    >>> def serialize_odd(value):
    ...     if not isinstance(value, int) or value % 2 == 0:
    ...         raise TypeError('Odd can only serialize odd numbers.')
    ...     return value
    >>> def parse_odd_value(value):
    ...     if not isinstance(value, int) or value % 2 == 0:
    ...         raise TypeError('Odd can only parse odd numbers.')
    ...     return value
    >>> def parse_odd_literal(value_node, _variables=None):
    ...     if not isinstance(value_node, IntValueNode):
    ...         raise TypeError('Odd can only parse integer literals.')
    ...     value = int(value_node.value)
    ...     if value % 2 == 0:
    ...         raise TypeError('Odd can only parse odd integer literals.')
    ...     return value
    >>> odd_type = GraphQLScalarType(
    ...     'Odd',
    ...     description='Odd integer values.',
    ...     specified_by_url='https://example.com/odd',
    ...     serialize=serialize_odd,
    ...     parse_value=parse_odd_value,
    ...     parse_literal=parse_odd_literal,
    ...     extensions={'numeric': True},
    ...     ast_node=document.definitions[0],
    ...     extension_ast_nodes=[document.definitions[1]],
    ... )
    >>> odd_type.description
    'Odd integer values.'
    >>> odd_type.specified_by_url
    'https://example.com/odd'
    >>> odd_type.serialize(3)
    3
    >>> odd_type.parse_value(5)
    5
    >>> odd_type.parse_literal(parse_value('7'))
    7
    >>> odd_type.extensions
    {'numeric': True}
    >>> str(odd_type)
    'Odd'
    """

    specified_by_url: Optional[str]
    """URL identifying the behavior specified for this custom scalar."""
    ast_node: Optional[ScalarTypeDefinitionNode]
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: Tuple[ScalarTypeExtensionNode, ...]
    """AST extension nodes applied to this schema element."""

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
        if specified_by_url is not None and not isinstance(specified_by_url, str):
            raise TypeError(
                f"{name} must provide 'specified_by_url' as a string,"
                f" but got: {inspect(specified_by_url)}."
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
                " as a collection of ScalarTypeExtensionNode instances."
            )
        if serialize is not None:
            self.serialize = serialize  # type: ignore
        if parse_value is not None:
            self.parse_value = parse_value  # type: ignore
        if parse_literal is not None:
            self.parse_literal = parse_literal  # type: ignore
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

        :param value: the internal value to serialize
        :returns: the serialized value
        """
        return value

    @staticmethod
    def parse_value(value: Any) -> Any:
        """Parses an externally provided value to use as an input.

        This default method just passes the value through and should be replaced
        with a more specific version when creating a scalar type.

        :param value: the externally provided value
        :returns: the internal value
        """
        return value

    def parse_literal(
        self, node: ValueNode, variables: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Parses an externally provided literal value to use as an input.

        This default method uses the parse_value method and should be replaced
        with a more specific version when creating a scalar type.

        :param node: the AST value literal to parse
        :param variables: runtime variable values keyed by variable name, used to
            resolve variables contained in the literal
        :returns: the internal value

        >>> from graphql import GraphQLScalarType, parse_value
        >>> json_type = GraphQLScalarType('JSON')
        >>> json_type.parse_literal(parse_value('{a: [1, 2], b: $var}'), {'var': 3})
        {'a': [1, 2], 'b': 3}
        """
        return self.parse_value(value_from_ast_untyped(node, variables))

    def to_kwargs(self) -> GraphQLScalarTypeKwargs:
        """Get the keyword arguments that can be used to recreate this type.

        :returns: a dictionary with the constructor arguments for this type

        >>> from graphql import GraphQLScalarType
        >>> url_type = GraphQLScalarType(
        ...     'Url',
        ...     description='An absolute URL string.',
        ...     specified_by_url='https://url.spec.whatwg.org/',
        ... )
        >>> kwargs = url_type.to_kwargs()
        >>> url_type_copy = GraphQLScalarType(**kwargs)
        >>> kwargs['name']
        'Url'
        >>> kwargs['specified_by_url']
        'https://url.spec.whatwg.org/'
        >>> url_type_copy.name == url_type.name
        True
        """
        # noinspection PyArgumentList
        return GraphQLScalarTypeKwargs(  # type: ignore
            super().to_kwargs(),
            serialize=(
                None
                if self.serialize is GraphQLScalarType.serialize
                else self.serialize
            ),
            parse_value=(
                None
                if self.parse_value is GraphQLScalarType.parse_value
                else self.parse_value
            ),
            parse_literal=(
                None
                if getattr(self.parse_literal, "__func__", None)
                is GraphQLScalarType.parse_literal
                else self.parse_literal
            ),
            specified_by_url=self.specified_by_url,
        )

    def __copy__(self) -> "GraphQLScalarType":  # pragma: no cover
        return self.__class__(**self.to_kwargs())


def is_scalar_type(type_: Any) -> bool:
    """Check whether the given value is a GraphQLScalarType.

    :param type_: the value to inspect
    :returns: whether the value is a GraphQLScalarType

    >>> from graphql import build_schema, is_scalar_type
    >>> schema = build_schema('''
    ...     scalar DateTime
    ...
    ...     type Query {
    ...       createdAt: DateTime
    ...     }
    ... ''')
    >>> is_scalar_type(schema.get_type('DateTime'))
    True
    >>> is_scalar_type(schema.get_type('Query'))
    False
    """
    return isinstance(type_, GraphQLScalarType)


def assert_scalar_type(type_: Any) -> GraphQLScalarType:
    """Return the value as a GraphQLScalarType, or raise a TypeError otherwise.

    :param type_: the value to inspect
    :returns: the value typed as a GraphQLScalarType

    >>> from graphql import build_schema, assert_scalar_type
    >>> schema = build_schema('''
    ...     scalar DateTime
    ...
    ...     type Query {
    ...       createdAt: DateTime
    ...     }
    ... ''')
    >>> date_time_type = assert_scalar_type(schema.get_type('DateTime'))
    >>> date_time_type.name
    'DateTime'
    >>> assert_scalar_type(schema.get_type('Query'))
    Traceback (most recent call last):
    ...
    TypeError: Expected Query to be a GraphQL Scalar type.
    """
    if not is_scalar_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Scalar type.")
    return cast(GraphQLScalarType, type_)


GraphQLArgumentMap = Dict[str, "GraphQLArgument"]


class GraphQLFieldKwargs(TypedDict, total=False):
    """Arguments used to define a GraphQL field.

    This is the type of the dictionary returned by :meth:`GraphQLField.to_kwargs`.
    """

    type_: "GraphQLOutputType"
    """The GraphQL type reference or runtime type for this element."""
    args: Optional[GraphQLArgumentMap]
    """Arguments accepted by this field or directive."""
    resolve: Optional["GraphQLFieldResolver"]
    """Resolver function used to produce this field value."""
    subscribe: Optional["GraphQLFieldResolver"]
    """Resolver function used to create a subscription event stream for this field."""
    description: Optional[str]
    """Human-readable description for this schema element, if provided."""
    deprecation_reason: Optional[str]
    """Reason this element is deprecated, if one was provided."""
    extensions: Dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: Optional[FieldDefinitionNode]
    """AST node from which this schema element was built, if available."""


class GraphQLField:
    """Definition of a GraphQL field

    :param type_: the GraphQL output type of this field
    :param args: arguments accepted by this field, as a dictionary with argument
        names as keys and :class:`GraphQLArgument` instances (or input types) as
        values
    :param resolve: resolver function used to produce this field value
    :param subscribe: resolver function used to create a subscription event stream
        for this field
    :param description: human-readable description for this field, if provided
    :param deprecation_reason: reason this field is deprecated, if one was provided
    :param extensions: custom extensions for this field
    :param ast_node: AST node from which this field was built, if available

    >>> from graphql import GraphQLArgument, GraphQLField, GraphQLString, parse
    >>> document = parse('''
    ...     type User {
    ...       name(format: String = "short"): String
    ...     }
    ... ''')
    >>> name_field = document.definitions[0].fields[0]
    >>> field = GraphQLField(
    ...     GraphQLString,
    ...     description='The formatted user name.',
    ...     args={'format': GraphQLArgument(GraphQLString, default_value='short')},
    ...     resolve=lambda user, _info, format: (
    ...         user['full_name'] if format == 'long' else user['name']),
    ...     deprecation_reason='Use displayName.',
    ...     extensions={'cacheSeconds': 60},
    ...     ast_node=name_field,
    ... )
    >>> field.type
    <GraphQLScalarType 'String'>
    >>> field.args['format'].default_value
    'short'
    >>> field.resolve({'name': 'Luke', 'full_name': 'Luke Skywalker'}, None, 'long')
    'Luke Skywalker'
    >>> field.deprecation_reason
    'Use displayName.'
    >>> field.extensions
    {'cacheSeconds': 60}
    """

    type: "GraphQLOutputType"
    """The GraphQL type reference or runtime type for this element."""
    args: GraphQLArgumentMap
    """Arguments accepted by this field or directive."""
    resolve: Optional["GraphQLFieldResolver"]
    """Resolver function used to produce this field value."""
    subscribe: Optional["GraphQLFieldResolver"]
    """Resolver function used to create a subscription event stream for this field."""
    description: Optional[str]
    """Human-readable description for this schema element, if provided."""
    deprecation_reason: Optional[str]
    """Reason this element is deprecated, if one was provided."""
    extensions: Dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: Optional[FieldDefinitionNode]
    """AST node from which this schema element was built, if available."""

    def __init__(
        self,
        type_: "GraphQLOutputType",
        args: Optional[GraphQLArgumentMap] = None,
        resolve: Optional["GraphQLFieldResolver"] = None,
        subscribe: Optional["GraphQLFieldResolver"] = None,
        description: Optional[str] = None,
        deprecation_reason: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[FieldDefinitionNode] = None,
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
                assert_name(name): (
                    value
                    if isinstance(value, GraphQLArgument)
                    else GraphQLArgument(cast(GraphQLInputType, value))
                )
                for name, value in args.items()
            }
        if resolve is not None and not callable(resolve):
            raise TypeError(
                "Field resolver must be a function if provided, "
                f" but got: {inspect(resolve)}."
            )
        if description is not None and not is_description(description):
            raise TypeError("The description must be a string.")
        if deprecation_reason is not None and not is_description(deprecation_reason):
            raise TypeError("The deprecation reason must be a string.")
        if extensions is None:
            extensions = {}
        elif not isinstance(extensions, dict) or not all(
            isinstance(key, str) for key in extensions
        ):
            raise TypeError("Field extensions must be a dictionary with string keys.")
        if ast_node and not isinstance(ast_node, FieldDefinitionNode):
            raise TypeError("Field AST node must be a FieldDefinitionNode.")
        self.type = type_
        self.args = args or {}
        self.resolve = resolve
        self.subscribe = subscribe
        self.description = description
        self.deprecation_reason = deprecation_reason
        self.extensions = extensions
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
        """Get the keyword arguments that can be used to recreate this field.

        :returns: a dictionary with the constructor arguments for this field

        >>> from graphql import GraphQLField, GraphQLString
        >>> field = GraphQLField(GraphQLString, description='The user name.')
        >>> kwargs = field.to_kwargs()
        >>> kwargs['type_'], kwargs['description']
        (<GraphQLScalarType 'String'>, 'The user name.')
        >>> GraphQLField(**kwargs) == field
        True
        """
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

    def __copy__(self) -> "GraphQLField":  # pragma: no cover
        return self.__class__(**self.to_kwargs())


class GraphQLResolveInfo(NamedTuple):
    """Collection of information passed to the resolvers.

    This is always passed as the first argument to the resolvers.

    Note that contrary to the JavaScript implementation, the context (commonly used to
    represent an authenticated user, or request-specific caches) is included here and
    not passed as an additional argument.
    """

    field_name: str
    """The name of the field that is currently being resolved."""
    field_nodes: List[FieldNode]
    """AST field nodes that contributed to the current field execution."""
    return_type: "GraphQLOutputType"
    """GraphQL output type declared for the current field."""
    parent_type: "GraphQLObjectType"
    """Object type that owns the current field."""
    path: Path
    """Response path to the field that is currently being resolved."""
    schema: "GraphQLSchema"
    """The schema used for execution."""
    fragments: Dict[str, FragmentDefinitionNode]
    """Fragment definitions in the operation document keyed by fragment name."""
    root_value: Any
    """Initial root value passed to the operation."""
    operation: OperationDefinitionNode
    """The operation selected for execution."""
    variable_values: Dict[str, Any]
    """Runtime variable values keyed by variable name."""
    context: Any
    """The context value passed to the operation.

    This is commonly used to represent an authenticated user, or request-specific
    caches.
    """
    is_awaitable: Callable[[Any], bool]
    """Function used to check whether a value is awaitable."""


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
    AwaitableOrValue[Optional[str]],
]

# Note: Contrary to the Javascript implementation of GraphQLIsTypeOfFn,
# the context is passed as part of the GraphQLResolveInfo:
GraphQLIsTypeOfFn = Callable[[Any, GraphQLResolveInfo], AwaitableOrValue[bool]]

GraphQLFieldMap = Dict[str, GraphQLField]


class GraphQLArgumentKwargs(TypedDict, total=False):
    """Arguments used to define a GraphQL argument.

    This is the type of the dictionary returned by
    :meth:`GraphQLArgument.to_kwargs`.
    """

    type_: "GraphQLInputType"
    """The GraphQL type reference or runtime type for this element."""
    default_value: Any
    """Default value used when no explicit value is supplied."""
    description: Optional[str]
    """Human-readable description for this schema element, if provided."""
    deprecation_reason: Optional[str]
    """Reason this element is deprecated, if one was provided."""
    out_name: Optional[str]
    """Name of the Python keyword argument (extension of GraphQL.js)."""
    extensions: Dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: Optional[InputValueDefinitionNode]
    """AST node from which this schema element was built, if available."""


class GraphQLArgument:
    """Definition of a GraphQL argument

    :param type_: the GraphQL input type of this argument
    :param default_value: default value used when no explicit value is supplied
    :param description: human-readable description for this argument, if provided
    :param deprecation_reason: reason this argument is deprecated, if one was
        provided
    :param out_name: name of the keyword argument passed to the resolver, if it
        should differ from the argument name (extension of GraphQL.js)
    :param extensions: custom extensions for this argument
    :param ast_node: AST node from which this argument was built, if available

    >>> from graphql import GraphQLArgument, GraphQLString, parse
    >>> document = parse('''
    ...     type User {
    ...       name(format: String = "short"): String
    ...     }
    ... ''')
    >>> format_arg = document.definitions[0].fields[0].arguments[0]
    >>> arg = GraphQLArgument(
    ...     GraphQLString,
    ...     description='Controls the name format.',
    ...     default_value='short',
    ...     deprecation_reason='Use locale instead.',
    ...     out_name='name_format',
    ...     extensions={'public': True},
    ...     ast_node=format_arg,
    ... )
    >>> arg.type
    <GraphQLScalarType 'String'>
    >>> arg.default_value
    'short'
    >>> arg.out_name
    'name_format'
    >>> arg.extensions
    {'public': True}
    """

    type: "GraphQLInputType"
    """The GraphQL type reference or runtime type for this element."""
    default_value: Any
    """Default value used when no explicit value is supplied."""
    description: Optional[str]
    """Human-readable description for this schema element, if provided."""
    deprecation_reason: Optional[str]
    """Reason this element is deprecated, if one was provided."""
    out_name: Optional[str]
    """Name of the Python keyword argument (extension of GraphQL.js).

    Used for transforming names; if not set, the argument name is used.
    """
    extensions: Dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: Optional[InputValueDefinitionNode]
    """AST node from which this schema element was built, if available."""

    def __init__(
        self,
        type_: "GraphQLInputType",
        default_value: Any = Undefined,
        description: Optional[str] = None,
        deprecation_reason: Optional[str] = None,
        out_name: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[InputValueDefinitionNode] = None,
    ) -> None:
        if not is_input_type(type_):
            raise TypeError("Argument type must be a GraphQL input type.")
        if description is not None and not is_description(description):
            raise TypeError("Argument description must be a string.")
        if deprecation_reason is not None and not is_description(deprecation_reason):
            raise TypeError("Argument deprecation reason must be a string.")
        if out_name is not None and not isinstance(out_name, str):
            raise TypeError("Argument out name must be a string.")
        if extensions is None:
            extensions = {}
        elif not isinstance(extensions, dict) or not all(
            isinstance(key, str) for key in extensions
        ):
            raise TypeError(
                "Argument extensions must be a dictionary with string keys."
            )
        if ast_node and not isinstance(ast_node, InputValueDefinitionNode):
            raise TypeError("Argument AST node must be an InputValueDefinitionNode.")
        self.type = type_
        self.default_value = default_value
        self.description = description
        self.deprecation_reason = deprecation_reason
        self.out_name = out_name
        self.extensions = extensions
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
        """Get the keyword arguments that can be used to recreate this argument.

        :returns: a dictionary with the constructor arguments for this argument

        >>> from graphql import GraphQLArgument, GraphQLInt
        >>> arg = GraphQLArgument(GraphQLInt, default_value=10)
        >>> kwargs = arg.to_kwargs()
        >>> kwargs['type_'], kwargs['default_value']
        (<GraphQLScalarType 'Int'>, 10)
        >>> GraphQLArgument(**kwargs) == arg
        True
        """
        return GraphQLArgumentKwargs(
            type_=self.type,
            default_value=self.default_value,
            description=self.description,
            deprecation_reason=self.deprecation_reason,
            out_name=self.out_name,
            extensions=self.extensions,
            ast_node=self.ast_node,
        )

    def __copy__(self) -> "GraphQLArgument":  # pragma: no cover
        return self.__class__(**self.to_kwargs())


def is_required_argument(arg: GraphQLArgument) -> bool:
    """Check whether the argument is non-null and has no default value.

    :param arg: the argument definition to inspect
    :returns: whether the argument is non-null and has no default value

    >>> from graphql import (
    ...     GraphQLArgument, GraphQLInt, GraphQLNonNull, GraphQLString,
    ...     is_required_argument)
    >>> required_argument = GraphQLArgument(GraphQLNonNull(GraphQLInt))
    >>> optional_argument = GraphQLArgument(GraphQLString)
    >>> argument_with_default = GraphQLArgument(
    ...     GraphQLNonNull(GraphQLInt), default_value=10)
    >>> is_required_argument(required_argument)
    True
    >>> is_required_argument(optional_argument)
    False
    >>> is_required_argument(argument_with_default)
    False
    """
    return is_non_null_type(arg.type) and arg.default_value is Undefined


class GraphQLObjectTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    """Arguments used to construct a GraphQLObjectType.

    This is the type of the dictionary returned by
    :meth:`GraphQLObjectType.to_kwargs`.
    """

    fields: GraphQLFieldMap
    """Fields declared by this object, interface, input object, or literal."""
    interfaces: Tuple["GraphQLInterfaceType", ...]
    """Interfaces implemented by this object or interface type."""
    is_type_of: Optional[GraphQLIsTypeOfFn]
    """Predicate used to determine whether a runtime value belongs to this type."""


class GraphQLObjectType(GraphQLNamedType):
    """Object Type Definition

    Almost all the GraphQL types you define will be object types. Object types have
    a name, but most importantly describe their fields.

    Example::

        AddressType = GraphQLObjectType('Address', {
            'street': GraphQLField(GraphQLString),
            'number': GraphQLField(GraphQLInt),
            'formatted': GraphQLField(GraphQLString,
                resolve=lambda obj, info: f'{obj.number} {obj.street}')
        })

    When two types need to refer to each other, or a type needs to refer to itself in
    a field, you can use a lambda function with no arguments (a so-called "thunk")
    to supply the fields lazily.

    Example::

        PersonType = GraphQLObjectType('Person', lambda: {
            'name': GraphQLField(GraphQLString),
            'bestFriend': GraphQLField(PersonType)
        })

    :param name: the GraphQL name for this object type
    :param fields: fields declared by this object type, as a dictionary with field
        names as keys and :class:`GraphQLField` instances (or output types) as
        values, or a thunk returning such a dictionary
    :param interfaces: interfaces implemented by this object type, or a thunk
        returning these
    :param is_type_of: predicate used to determine whether a runtime value belongs
        to this object type
    :param extensions: custom extensions for this type
    :param description: human-readable description for this type, if provided
    :param ast_node: AST node from which this type was built, if available
    :param extension_ast_nodes: AST extension nodes applied to this type

    Configure an object type with interfaces, fields, arguments, and metadata:

    >>> from graphql import (
    ...     GraphQLArgument, GraphQLField, GraphQLID, GraphQLInterfaceType,
    ...     GraphQLNonNull, GraphQLObjectType, GraphQLString, parse)
    >>> document = parse('''
    ...     type User implements Node {
    ...       id: ID!
    ...       name(format: String = "short"): String
    ...     }
    ...
    ...     extend type User {
    ...       displayName: String
    ...     }
    ... ''')
    >>> definition = document.definitions[0]
    >>> name_field = definition.fields[1]
    >>> format_arg = name_field.arguments[0]
    >>> node_type = GraphQLInterfaceType(
    ...     'Node', {'id': GraphQLField(GraphQLNonNull(GraphQLID))})
    >>> user_type = GraphQLObjectType(
    ...     'User',
    ...     description='A registered user.',
    ...     interfaces=[node_type],
    ...     fields={
    ...         'id': GraphQLField(GraphQLNonNull(GraphQLID)),
    ...         'name': GraphQLField(
    ...             GraphQLString,
    ...             description='The formatted user name.',
    ...             args={
    ...                 'format': GraphQLArgument(
    ...                     GraphQLString,
    ...                     description='Controls the name format.',
    ...                     default_value='short',
    ...                     deprecation_reason='Use locale instead.',
    ...                     extensions={'public': True},
    ...                     ast_node=format_arg,
    ...                 ),
    ...             },
    ...             resolve=lambda user, _info, format: (
    ...                 user['full_name'] if format == 'long' else user['name']),
    ...             deprecation_reason='Use displayName.',
    ...             extensions={'cacheSeconds': 60},
    ...             ast_node=name_field,
    ...         ),
    ...     },
    ...     is_type_of=lambda value, _info: isinstance(value, dict) and 'id' in value,
    ...     extensions={'entity': 'User'},
    ...     ast_node=definition,
    ...     extension_ast_nodes=[document.definitions[1]],
    ... )
    >>> user_type.name
    'User'
    >>> user_type.interfaces
    (<GraphQLInterfaceType 'Node'>,)
    >>> list(user_type.fields)
    ['id', 'name']
    >>> user_type.fields['name'].args['format'].default_value
    'short'
    >>> user_type.extensions
    {'entity': 'User'}

    This variant configures a subscription field with subscribe and resolve
    functions:

    >>> async def subscribe_greeting(_obj, _info):
    ...     yield {'greeting': 'Hello!'}
    >>> subscription_type = GraphQLObjectType(
    ...     'Subscription',
    ...     fields={
    ...         'greeting': GraphQLField(
    ...             GraphQLString,
    ...             subscribe=subscribe_greeting,
    ...             resolve=lambda event, _info: event['greeting'],
    ...         ),
    ...     },
    ... )
    >>> callable(subscription_type.fields['greeting'].subscribe)
    True
    """

    is_type_of: Optional[GraphQLIsTypeOfFn]
    """Predicate used to determine whether a runtime value belongs to this type."""
    ast_node: Optional[ObjectTypeDefinitionNode]
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: Tuple[ObjectTypeExtensionNode, ...]
    """AST extension nodes applied to this schema element."""

    def __init__(
        self,
        name: str,
        fields: ThunkMapping[GraphQLField],
        interfaces: Optional[ThunkCollection["GraphQLInterfaceType"]] = None,
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
                " as a collection of ObjectTypeExtensionNode instances."
            )
        self._fields = fields
        self._interfaces = interfaces
        self.is_type_of = is_type_of

    def to_kwargs(self) -> GraphQLObjectTypeKwargs:
        """Get the keyword arguments that can be used to recreate this type.

        :returns: a dictionary with the constructor arguments for this type

        >>> from graphql import GraphQLField, GraphQLObjectType, GraphQLString
        >>> user_type = GraphQLObjectType(
        ...     'User', {'name': GraphQLField(GraphQLString)})
        >>> kwargs = user_type.to_kwargs()
        >>> user_type_copy = GraphQLObjectType(**kwargs)
        >>> kwargs['fields']['name'].type
        <GraphQLScalarType 'String'>
        >>> user_type_copy.fields['name'].type
        <GraphQLScalarType 'String'>
        """
        # noinspection PyArgumentList
        return GraphQLObjectTypeKwargs(  # type: ignore
            super().to_kwargs(),
            fields=self.fields.copy(),
            interfaces=self.interfaces,
            is_type_of=self.is_type_of,
        )

    def __copy__(self) -> "GraphQLObjectType":  # pragma: no cover
        return self.__class__(**self.to_kwargs())

    @cached_property
    def fields(self) -> GraphQLFieldMap:
        """Get provided fields, wrapping them as GraphQLFields if needed.

        :returns: the fields keyed by field name

        >>> from graphql import assert_object_type, build_schema
        >>> schema = build_schema('''
        ...     type User {
        ...       id: ID!
        ...       name: String
        ...     }
        ...
        ...     type Query {
        ...       viewer: User
        ...     }
        ... ''')
        >>> user_type = assert_object_type(schema.get_type('User'))
        >>> fields = user_type.fields
        >>> list(fields)
        ['id', 'name']
        >>> str(fields['id'].type)
        'ID!'
        """
        try:
            fields = resolve_thunk(self._fields)
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            raise cls(f"{self.name} fields cannot be resolved. {error}") from error
        if not isinstance(fields, Mapping) or not all(
            isinstance(key, str) for key in fields
        ):
            raise TypeError(
                f"{self.name} fields must be specified"
                " as a mapping with field names as keys."
            )
        if not all(
            isinstance(value, GraphQLField) or is_output_type(value)
            for value in fields.values()
        ):
            raise TypeError(
                f"{self.name} fields must be GraphQLField or output type objects."
            )
        return {
            assert_name(name): (
                value if isinstance(value, GraphQLField) else GraphQLField(value)
            )
            for name, value in fields.items()
        }

    @cached_property
    def interfaces(self) -> Tuple["GraphQLInterfaceType", ...]:
        """Get provided interfaces.

        :returns: the implemented interfaces

        >>> from graphql import assert_object_type, build_schema
        >>> schema = build_schema('''
        ...     interface Node {
        ...       id: ID!
        ...     }
        ...
        ...     type User implements Node {
        ...       id: ID!
        ...     }
        ...
        ...     type Query {
        ...       viewer: User
        ...     }
        ... ''')
        >>> user_type = assert_object_type(schema.get_type('User'))
        >>> [type_.name for type_ in user_type.interfaces]
        ['Node']
        """
        try:
            interfaces: Collection["GraphQLInterfaceType"] = resolve_thunk(
                self._interfaces  # type: ignore
            )
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            raise cls(f"{self.name} interfaces cannot be resolved. {error}") from error
        if interfaces is None:
            interfaces = ()
        elif not is_collection(interfaces) or not all(
            isinstance(value, GraphQLInterfaceType) for value in interfaces
        ):
            raise TypeError(
                f"{self.name} interfaces must be specified"
                " as a collection of GraphQLInterfaceType instances."
            )
        return tuple(interfaces)


def is_object_type(type_: Any) -> bool:
    """Check whether the given value is a GraphQLObjectType.

    :param type_: the value to inspect
    :returns: whether the value is a GraphQLObjectType

    >>> from graphql import build_schema, is_object_type
    >>> schema = build_schema('''
    ...     input ReviewInput {
    ...       stars: Int!
    ...     }
    ...
    ...     type User {
    ...       name: String
    ...     }
    ...
    ...     type Query {
    ...       user: User
    ...     }
    ... ''')
    >>> is_object_type(schema.get_type('User'))
    True
    >>> is_object_type(schema.get_type('ReviewInput'))
    False
    """
    return isinstance(type_, GraphQLObjectType)


def assert_object_type(type_: Any) -> GraphQLObjectType:
    """Return the value as a GraphQLObjectType, or raise a TypeError otherwise.

    :param type_: the value to inspect
    :returns: the value typed as a GraphQLObjectType

    >>> from graphql import build_schema, assert_object_type
    >>> schema = build_schema('''
    ...     input ReviewInput {
    ...       stars: Int!
    ...     }
    ...
    ...     type User {
    ...       name: String
    ...     }
    ...
    ...     type Query {
    ...       user: User
    ...     }
    ... ''')
    >>> user_type = assert_object_type(schema.get_type('User'))
    >>> list(user_type.fields)
    ['name']
    >>> assert_object_type(schema.get_type('ReviewInput'))
    Traceback (most recent call last):
    ...
    TypeError: Expected ReviewInput to be a GraphQL Object type.
    """
    if not is_object_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Object type.")
    return cast(GraphQLObjectType, type_)


class GraphQLInterfaceTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    """Arguments used to construct a GraphQLInterfaceType.

    This is the type of the dictionary returned by
    :meth:`GraphQLInterfaceType.to_kwargs`.
    """

    fields: GraphQLFieldMap
    """Fields declared by this object, interface, input object, or literal."""
    interfaces: Tuple["GraphQLInterfaceType", ...]
    """Interfaces implemented by this object or interface type."""
    resolve_type: Optional[GraphQLTypeResolver]
    """Optionally provide a custom type resolver function.

    If one is not provided, the default implementation will call ``is_type_of`` on
    each implementing Object type.
    """


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

    :param name: the GraphQL name for this interface type
    :param fields: fields declared by this interface type, as a dictionary with
        field names as keys and :class:`GraphQLField` instances (or output types) as
        values, or a thunk returning such a dictionary
    :param interfaces: interfaces implemented by this interface type, or a thunk
        returning these
    :param resolve_type: optionally provide a custom type resolver function. If one
        is not provided, the default implementation will call ``is_type_of`` on each
        implementing Object type.
    :param description: human-readable description for this type, if provided
    :param extensions: custom extensions for this type
    :param ast_node: AST node from which this type was built, if available
    :param extension_ast_nodes: AST extension nodes applied to this type

    >>> from graphql import (
    ...     GraphQLField, GraphQLID, GraphQLInterfaceType, GraphQLNonNull, parse)
    >>> document = parse('''
    ...     interface Node {
    ...       id: ID!
    ...     }
    ...
    ...     interface Resource implements Node {
    ...       id: ID!
    ...     }
    ...
    ...     extend interface Resource {
    ...       url: String
    ...     }
    ... ''')
    >>> node_type = GraphQLInterfaceType(
    ...     'Node', {'id': GraphQLField(GraphQLNonNull(GraphQLID))})
    >>> resource_type = GraphQLInterfaceType(
    ...     'Resource',
    ...     description='An addressable resource.',
    ...     interfaces=[node_type],
    ...     fields={'id': GraphQLField(GraphQLNonNull(GraphQLID))},
    ...     resolve_type=lambda value, _info, _type: (
    ...         'WebPage' if isinstance(value, dict) and 'url' in value else None),
    ...     extensions={'abstract': True},
    ...     ast_node=document.definitions[1],
    ...     extension_ast_nodes=[document.definitions[2]],
    ... )
    >>> resource_type.name
    'Resource'
    >>> resource_type.interfaces
    (<GraphQLInterfaceType 'Node'>,)
    >>> list(resource_type.fields)
    ['id']
    >>> resource_type.extensions
    {'abstract': True}
    """

    resolve_type: Optional[GraphQLTypeResolver]
    """Function that resolves the concrete object type for this abstract type."""
    ast_node: Optional[InterfaceTypeDefinitionNode]
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: Tuple[InterfaceTypeExtensionNode, ...]
    """AST extension nodes applied to this schema element."""

    def __init__(
        self,
        name: str,
        fields: ThunkMapping[GraphQLField],
        interfaces: Optional[ThunkCollection["GraphQLInterfaceType"]] = None,
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
                " as a collection of InterfaceTypeExtensionNode instances."
            )
        self._fields = fields
        self._interfaces = interfaces
        self.resolve_type = resolve_type

    def to_kwargs(self) -> GraphQLInterfaceTypeKwargs:
        """Get the keyword arguments that can be used to recreate this type.

        :returns: a dictionary with the constructor arguments for this type

        >>> from graphql import (
        ...     GraphQLField, GraphQLID, GraphQLInterfaceType, GraphQLNonNull)
        >>> node_type = GraphQLInterfaceType(
        ...     'Node', {'id': GraphQLField(GraphQLNonNull(GraphQLID))})
        >>> kwargs = node_type.to_kwargs()
        >>> node_type_copy = GraphQLInterfaceType(**kwargs)
        >>> str(kwargs['fields']['id'].type)
        'ID!'
        >>> str(node_type_copy.fields['id'].type)
        'ID!'
        """
        # noinspection PyArgumentList
        return GraphQLInterfaceTypeKwargs(  # type: ignore
            super().to_kwargs(),
            fields=self.fields.copy(),
            interfaces=self.interfaces,
            resolve_type=self.resolve_type,
        )

    def __copy__(self) -> "GraphQLInterfaceType":  # pragma: no cover
        return self.__class__(**self.to_kwargs())

    @cached_property
    def fields(self) -> GraphQLFieldMap:
        """Get provided fields, wrapping them as GraphQLFields if needed.

        :returns: the fields keyed by field name

        >>> from graphql import assert_interface_type, build_schema
        >>> schema = build_schema('''
        ...     interface Node {
        ...       id: ID!
        ...     }
        ...
        ...     type User implements Node {
        ...       id: ID!
        ...     }
        ...
        ...     type Query {
        ...       node: Node
        ...     }
        ... ''')
        >>> node_type = assert_interface_type(schema.get_type('Node'))
        >>> fields = node_type.fields
        >>> list(fields)
        ['id']
        >>> str(fields['id'].type)
        'ID!'
        """
        try:
            fields = resolve_thunk(self._fields)
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            raise cls(f"{self.name} fields cannot be resolved. {error}") from error
        if not isinstance(fields, Mapping) or not all(
            isinstance(key, str) for key in fields
        ):
            raise TypeError(
                f"{self.name} fields must be specified"
                " as a mapping with field names as keys."
            )
        if not all(
            isinstance(value, GraphQLField) or is_output_type(value)
            for value in fields.values()
        ):
            raise TypeError(
                f"{self.name} fields must be GraphQLField or output type objects."
            )
        return {
            assert_name(name): (
                value if isinstance(value, GraphQLField) else GraphQLField(value)
            )
            for name, value in fields.items()
        }

    @cached_property
    def interfaces(self) -> Tuple["GraphQLInterfaceType", ...]:
        """Get provided interfaces.

        :returns: the implemented interfaces

        >>> from graphql import assert_interface_type, build_schema
        >>> schema = build_schema('''
        ...     interface Resource {
        ...       url: String!
        ...     }
        ...
        ...     interface Image implements Resource {
        ...       url: String!
        ...       width: Int
        ...     }
        ...
        ...     type Photo implements Resource & Image {
        ...       url: String!
        ...       width: Int
        ...     }
        ...
        ...     type Query {
        ...       image: Image
        ...     }
        ... ''')
        >>> image_type = assert_interface_type(schema.get_type('Image'))
        >>> [type_.name for type_ in image_type.interfaces]
        ['Resource']
        """
        try:
            interfaces: Collection["GraphQLInterfaceType"] = resolve_thunk(
                self._interfaces  # type: ignore
            )
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            raise cls(f"{self.name} interfaces cannot be resolved. {error}") from error
        if interfaces is None:
            interfaces = ()
        elif not is_collection(interfaces) or not all(
            isinstance(value, GraphQLInterfaceType) for value in interfaces
        ):
            raise TypeError(
                f"{self.name} interfaces must be specified"
                " as a collection of GraphQLInterfaceType instances."
            )
        return tuple(interfaces)


def is_interface_type(type_: Any) -> bool:
    """Check whether the given value is a GraphQLInterfaceType.

    :param type_: the value to inspect
    :returns: whether the value is a GraphQLInterfaceType

    >>> from graphql import build_schema, is_interface_type
    >>> schema = build_schema('''
    ...     interface Node {
    ...       id: ID!
    ...     }
    ...
    ...     type User implements Node {
    ...       id: ID!
    ...     }
    ...
    ...     type Query {
    ...       node: Node
    ...     }
    ... ''')
    >>> is_interface_type(schema.get_type('Node'))
    True
    >>> is_interface_type(schema.get_type('User'))
    False
    """
    return isinstance(type_, GraphQLInterfaceType)


def assert_interface_type(type_: Any) -> GraphQLInterfaceType:
    """Return the value as a GraphQLInterfaceType, or raise a TypeError otherwise.

    :param type_: the value to inspect
    :returns: the value typed as a GraphQLInterfaceType

    >>> from graphql import build_schema, assert_interface_type
    >>> schema = build_schema('''
    ...     interface Node {
    ...       id: ID!
    ...     }
    ...
    ...     type User implements Node {
    ...       id: ID!
    ...     }
    ...
    ...     type Query {
    ...       node: Node
    ...     }
    ... ''')
    >>> node_type = assert_interface_type(schema.get_type('Node'))
    >>> node_type.name
    'Node'
    >>> assert_interface_type(schema.get_type('User'))
    Traceback (most recent call last):
    ...
    TypeError: Expected User to be a GraphQL Interface type.
    """
    if not is_interface_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Interface type.")
    return cast(GraphQLInterfaceType, type_)


class GraphQLUnionTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    """Arguments used to construct a GraphQLUnionType.

    This is the type of the dictionary returned by
    :meth:`GraphQLUnionType.to_kwargs`.
    """

    types: Tuple[GraphQLObjectType, ...]
    """Object types that belong to this union type."""
    resolve_type: Optional[GraphQLTypeResolver]
    """Optionally provide a custom type resolver function.

    If one is not provided, the default implementation will call ``is_type_of`` on
    each implementing Object type.
    """


class GraphQLUnionType(GraphQLNamedType):
    """Union Type Definition

    When a field can return one of a heterogeneous set of types, a Union type is used
    to describe what types are possible as well as providing a function to determine
    which type is actually used when the field is resolved.

    Example::

        def resolve_type(obj, _info, _type):
            if isinstance(obj, Dog):
                return 'Dog'
            if isinstance(obj, Cat):
                return 'Cat'

        PetType = GraphQLUnionType('Pet', [DogType, CatType], resolve_type)

    :param name: the GraphQL name for this union type
    :param types: object types that belong to this union type, or a thunk
        returning these
    :param resolve_type: optionally provide a custom type resolver function. If one
        is not provided, the default implementation will call ``is_type_of`` on each
        implementing Object type.
    :param description: human-readable description for this type, if provided
    :param extensions: custom extensions for this type
    :param ast_node: AST node from which this type was built, if available
    :param extension_ast_nodes: AST extension nodes applied to this type

    >>> from graphql import (
    ...     GraphQLField, GraphQLObjectType, GraphQLString, GraphQLUnionType, parse)
    >>> document = parse('''
    ...     union Media = Photo | Video
    ...
    ...     extend union Media = Audio
    ... ''')
    >>> photo_type = GraphQLObjectType(
    ...     'Photo', {'url': GraphQLField(GraphQLString)})
    >>> video_type = GraphQLObjectType(
    ...     'Video', {'url': GraphQLField(GraphQLString)})
    >>> media_type = GraphQLUnionType(
    ...     'Media',
    ...     description='Media that can appear in a search result.',
    ...     types=[photo_type, video_type],
    ...     resolve_type=lambda value, _info, _type: (
    ...         'Video' if isinstance(value, dict) and 'duration' in value
    ...         else 'Photo'),
    ...     extensions={'searchable': True},
    ...     ast_node=document.definitions[0],
    ...     extension_ast_nodes=[document.definitions[1]],
    ... )
    >>> media_type.description
    'Media that can appear in a search result.'
    >>> [type_.name for type_ in media_type.types]
    ['Photo', 'Video']
    >>> media_type.extensions
    {'searchable': True}
    """

    resolve_type: Optional[GraphQLTypeResolver]
    """Function that resolves the concrete object type for this abstract type."""
    ast_node: Optional[UnionTypeDefinitionNode]
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: Tuple[UnionTypeExtensionNode, ...]
    """AST extension nodes applied to this schema element."""

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
                " as a collection of UnionTypeExtensionNode instances."
            )
        self._types = types
        self.resolve_type = resolve_type

    def to_kwargs(self) -> GraphQLUnionTypeKwargs:
        """Get the keyword arguments that can be used to recreate this type.

        :returns: a dictionary with the constructor arguments for this type

        >>> from graphql import (
        ...     GraphQLField, GraphQLObjectType, GraphQLString, GraphQLUnionType)
        >>> photo_type = GraphQLObjectType(
        ...     'Photo', {'url': GraphQLField(GraphQLString)})
        >>> video_type = GraphQLObjectType(
        ...     'Video', {'url': GraphQLField(GraphQLString)})
        >>> media_type = GraphQLUnionType('Media', [photo_type, video_type])
        >>> kwargs = media_type.to_kwargs()
        >>> media_type_copy = GraphQLUnionType(**kwargs)
        >>> [type_.name for type_ in media_type_copy.types]
        ['Photo', 'Video']
        """
        # noinspection PyArgumentList
        return GraphQLUnionTypeKwargs(  # type: ignore
            super().to_kwargs(), types=self.types, resolve_type=self.resolve_type
        )

    def __copy__(self) -> "GraphQLUnionType":  # pragma: no cover
        return self.__class__(**self.to_kwargs())

    @cached_property
    def types(self) -> Tuple[GraphQLObjectType, ...]:
        """Get provided types.

        :returns: the union member object types

        >>> from graphql import assert_union_type, build_schema
        >>> schema = build_schema('''
        ...     type Photo {
        ...       url: String!
        ...     }
        ...
        ...     type Video {
        ...       url: String!
        ...     }
        ...
        ...     union Media = Photo | Video
        ...
        ...     type Query {
        ...       media: [Media]
        ...     }
        ... ''')
        >>> media_type = assert_union_type(schema.get_type('Media'))
        >>> [type_.name for type_ in media_type.types]
        ['Photo', 'Video']
        """
        try:
            types: Collection[GraphQLObjectType] = resolve_thunk(self._types)
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            raise cls(f"{self.name} types cannot be resolved. {error}") from error
        if types is None:
            types = ()
        elif not is_collection(types) or not all(
            isinstance(value, GraphQLObjectType) for value in types
        ):
            raise TypeError(
                f"{self.name} types must be specified"
                " as a collection of GraphQLObjectType instances."
            )
        return tuple(types)


def is_union_type(type_: Any) -> bool:
    """Check whether the given value is a GraphQLUnionType.

    :param type_: the value to inspect
    :returns: whether the value is a GraphQLUnionType

    >>> from graphql import build_schema, is_union_type
    >>> schema = build_schema('''
    ...     type Photo {
    ...       url: String!
    ...     }
    ...
    ...     type Video {
    ...       url: String!
    ...     }
    ...
    ...     union Media = Photo | Video
    ...
    ...     type Query {
    ...       media: [Media]
    ...     }
    ... ''')
    >>> is_union_type(schema.get_type('Media'))
    True
    >>> is_union_type(schema.get_type('Photo'))
    False
    """
    return isinstance(type_, GraphQLUnionType)


def assert_union_type(type_: Any) -> GraphQLUnionType:
    """Return the value as a GraphQLUnionType, or raise a TypeError otherwise.

    :param type_: the value to inspect
    :returns: the value typed as a GraphQLUnionType

    >>> from graphql import build_schema, assert_union_type
    >>> schema = build_schema('''
    ...     type Photo {
    ...       url: String!
    ...     }
    ...
    ...     type Video {
    ...       url: String!
    ...     }
    ...
    ...     union Media = Photo | Video
    ...
    ...     type Query {
    ...       media: [Media]
    ...     }
    ... ''')
    >>> media_type = assert_union_type(schema.get_type('Media'))
    >>> [type_.name for type_ in media_type.types]
    ['Photo', 'Video']
    >>> assert_union_type(schema.get_type('Photo'))
    Traceback (most recent call last):
    ...
    TypeError: Expected Photo to be a GraphQL Union type.
    """
    if not is_union_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Union type.")
    return cast(GraphQLUnionType, type_)


GraphQLEnumValueMap = Dict[str, "GraphQLEnumValue"]

GraphQLEnumValuesDefinition = Union[GraphQLEnumValueMap, Mapping[str, Any], Type[Enum]]


class GraphQLEnumTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    """Arguments used to construct a GraphQLEnumType.

    This is the type of the dictionary returned by
    :meth:`GraphQLEnumType.to_kwargs`.
    """

    values: GraphQLEnumValueMap
    """Values contained in this enum, list, or input-object definition."""
    names_as_values: Optional[bool]
    """What to use as internal values when the values are given as a Python Enum.

    ``False`` uses the enum values, ``True`` the enum names, and ``None`` the enum
    members themselves (extension of GraphQL.js).
    """


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

        RGBType = GraphQLEnumType('RGB', RGBEnum)

    Instead of raw values, you can also specify GraphQLEnumValue objects with more
    detail like description or deprecation information.

    Note: If a value is not provided in a definition, the name of the enum value will
    be used as its internal value when the value is serialized.

    :param name: the GraphQL name for this enum type
    :param values: values contained in this enum, as a dictionary with value names
        as keys and :class:`GraphQLEnumValue` instances or internal values as
        values, or as a Python Enum, or a thunk returning one of these
    :param names_as_values: what to use as internal values when the values are
        given as a Python Enum: ``False`` uses the enum values, ``True`` the enum
        names, and ``None`` the enum members themselves (extension of GraphQL.js)
    :param description: human-readable description for this type, if provided
    :param extensions: custom extensions for this type
    :param ast_node: AST node from which this type was built, if available
    :param extension_ast_nodes: AST extension nodes applied to this type

    >>> from graphql import GraphQLEnumType, GraphQLEnumValue, parse
    >>> document = parse('''
    ...     enum Episode {
    ...       NEW_HOPE
    ...       EMPIRE
    ...       JEDI
    ...     }
    ...
    ...     extend enum Episode {
    ...       FORCE_AWAKENS
    ...     }
    ... ''')
    >>> definition = document.definitions[0]
    >>> episode_type = GraphQLEnumType(
    ...     'Episode',
    ...     description='A Star Wars film episode.',
    ...     values={
    ...         'NEW_HOPE': GraphQLEnumValue(
    ...             4,
    ...             description='Released in 1977.',
    ...             extensions={'trilogy': 'original'},
    ...             ast_node=definition.values[0],
    ...         ),
    ...         'EMPIRE': GraphQLEnumValue(5, ast_node=definition.values[1]),
    ...         'JEDI': GraphQLEnumValue(
    ...             6,
    ...             deprecation_reason='Use RETURN_OF_THE_JEDI.',
    ...             ast_node=definition.values[2],
    ...         ),
    ...     },
    ...     extensions={'catalog': 'films'},
    ...     ast_node=definition,
    ...     extension_ast_nodes=[document.definitions[1]],
    ... )
    >>> episode_type.description
    'A Star Wars film episode.'
    >>> episode_type.serialize(5)
    'EMPIRE'
    >>> episode_type.parse_value('JEDI')
    6
    >>> episode_type.values['JEDI'].deprecation_reason
    'Use RETURN_OF_THE_JEDI.'
    >>> episode_type.extensions
    {'catalog': 'films'}

    This variant uses a Python Enum and shows the effect of ``names_as_values``:

    >>> from enum import Enum
    >>> class RGBEnum(Enum):
    ...     RED = 0
    ...     GREEN = 1
    ...     BLUE = 2
    >>> GraphQLEnumType('RGB', RGBEnum).parse_value('GREEN')
    1
    >>> GraphQLEnumType('RGB', RGBEnum, names_as_values=True).parse_value('GREEN')
    'GREEN'
    >>> GraphQLEnumType('RGB', RGBEnum, names_as_values=None).parse_value('GREEN')
    <RGBEnum.GREEN: 1>
    """

    values: GraphQLEnumValueMap
    """The values of this enum type, keyed by value name."""
    ast_node: Optional[EnumTypeDefinitionNode]
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: Tuple[EnumTypeExtensionNode, ...]
    """AST extension nodes applied to this schema element."""

    def __init__(
        self,
        name: str,
        values: Thunk[GraphQLEnumValuesDefinition],
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
        if not isinstance(values, type):
            values = resolve_thunk(values)  # type: ignore
        try:  # check for enum
            values = cast(Enum, values).__members__  # type: ignore
        except AttributeError:
            if not isinstance(values, Mapping) or not all(
                isinstance(name, str) for name in values
            ):
                try:
                    # noinspection PyTypeChecker
                    values = dict(values)  # type: ignore
                except (TypeError, ValueError) as error:
                    raise TypeError(
                        f"{name} values must be an Enum or a mapping"
                        " with value names as keys."
                    ) from error
            values = cast(Dict[str, Any], values)
        else:
            values = cast(Dict[str, Enum], values)
            if names_as_values is False:
                values = {key: value.value for key, value in values.items()}
            elif names_as_values is True:
                values = {key: key for key in values}
        values = {
            assert_enum_value_name(key): (
                value
                if isinstance(value, GraphQLEnumValue)
                else GraphQLEnumValue(value)
            )
            for key, value in values.items()
        }
        if ast_node and not isinstance(ast_node, EnumTypeDefinitionNode):
            raise TypeError(f"{name} AST node must be an EnumTypeDefinitionNode.")
        if extension_ast_nodes and not all(
            isinstance(node, EnumTypeExtensionNode) for node in extension_ast_nodes
        ):
            raise TypeError(
                f"{name} extension AST nodes must be specified"
                " as a collection of EnumTypeExtensionNode instances."
            )
        self.values = values

    def to_kwargs(self) -> GraphQLEnumTypeKwargs:
        """Get the keyword arguments that can be used to recreate this type.

        :returns: a dictionary with the constructor arguments for this type

        >>> from graphql import GraphQLEnumType
        >>> rgb_type = GraphQLEnumType('RGB', {'RED': 0, 'GREEN': 1, 'BLUE': 2})
        >>> kwargs = rgb_type.to_kwargs()
        >>> rgb_type_copy = GraphQLEnumType(**kwargs)
        >>> kwargs['values']['GREEN'].value
        1
        >>> rgb_type_copy.serialize(2)
        'BLUE'
        """
        # noinspection PyArgumentList
        return GraphQLEnumTypeKwargs(  # type: ignore
            super().to_kwargs(), values=self.values.copy()
        )

    def __copy__(self) -> "GraphQLEnumType":  # pragma: no cover
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
        """Serialize a runtime enum value as a GraphQL enum name.

        :param output_value: runtime enum value to serialize
        :returns: the GraphQL enum name for the runtime value

        >>> from graphql import GraphQLEnumType
        >>> rgb_type = GraphQLEnumType('RGB', {'RED': 0, 'GREEN': 1, 'BLUE': 2})
        >>> rgb_type.serialize(1)
        'GREEN'
        >>> rgb_type.serialize(3)
        Traceback (most recent call last):
        ...
        graphql.error.graphql_error.GraphQLError: Enum 'RGB' cannot represent value: 3
        """
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
        """Parse a GraphQL enum name from variable input.

        :param input_value: runtime input value to parse
        :returns: the internal enum value represented by the input name

        >>> from graphql import GraphQLEnumType
        >>> rgb_type = GraphQLEnumType('RGB', {'RED': 0, 'GREEN': 1, 'BLUE': 2})
        >>> rgb_type.parse_value('BLUE')
        2
        >>> rgb_type.parse_value('PURPLE')
        Traceback (most recent call last):
        ...
        graphql.error.graphql_error.GraphQLError: Value 'PURPLE' does not exist
        in 'RGB' enum...
        >>> rgb_type.parse_value(2)
        Traceback (most recent call last):
        ...
        graphql.error.graphql_error.GraphQLError: Enum 'RGB' cannot represent
        non-string value: 2...
        """
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
        """Parse a GraphQL enum name from an AST value literal.

        :param value_node: AST value literal to parse
        :param _variables: runtime variable values; ignored because variables will
            be resolved before calling this method
        :returns: the internal enum value represented by the literal

        >>> from graphql import GraphQLEnumType, parse_value
        >>> rgb_type = GraphQLEnumType('RGB', {'RED': 0, 'GREEN': 1, 'BLUE': 2})
        >>> rgb_type.parse_literal(parse_value('RED'))
        0
        >>> rgb_type.parse_literal(parse_value('"RED"'))
        Traceback (most recent call last):
        ...
        graphql.error.graphql_error.GraphQLError: Enum 'RGB' cannot represent
        non-enum value: "RED"...
        """
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


def is_enum_type(type_: Any) -> bool:
    """Check whether the given value is a GraphQLEnumType.

    :param type_: the value to inspect
    :returns: whether the value is a GraphQLEnumType

    >>> from graphql import build_schema, is_enum_type
    >>> schema = build_schema('''
    ...     enum Episode {
    ...       NEW_HOPE
    ...       EMPIRE
    ...     }
    ...
    ...     type Query {
    ...       favoriteEpisode: Episode
    ...     }
    ... ''')
    >>> is_enum_type(schema.get_type('Episode'))
    True
    >>> is_enum_type(schema.get_type('Query'))
    False
    """
    return isinstance(type_, GraphQLEnumType)


def assert_enum_type(type_: Any) -> GraphQLEnumType:
    """Return the value as a GraphQLEnumType, or raise a TypeError otherwise.

    :param type_: the value to inspect
    :returns: the value typed as a GraphQLEnumType

    >>> from graphql import build_schema, assert_enum_type
    >>> schema = build_schema('''
    ...     enum Episode {
    ...       NEW_HOPE
    ...       EMPIRE
    ...     }
    ...
    ...     type Query {
    ...       favoriteEpisode: Episode
    ...     }
    ... ''')
    >>> episode_type = assert_enum_type(schema.get_type('Episode'))
    >>> list(episode_type.values)
    ['NEW_HOPE', 'EMPIRE']
    >>> assert_enum_type(schema.get_type('Query'))
    Traceback (most recent call last):
    ...
    TypeError: Expected Query to be a GraphQL Enum type.
    """
    if not is_enum_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Enum type.")
    return cast(GraphQLEnumType, type_)


def did_you_mean_enum_value(enum_type: GraphQLEnumType, unknown_value_str: str) -> str:
    suggested_values = suggestion_list(unknown_value_str, enum_type.values)
    return did_you_mean(suggested_values, "the enum value")


class GraphQLEnumValueKwargs(TypedDict, total=False):
    """Arguments used to define a GraphQL enum value.

    This is the type of the dictionary returned by
    :meth:`GraphQLEnumValue.to_kwargs`.
    """

    value: Any
    """Internal value represented by this enum value."""
    description: Optional[str]
    """Human-readable description for this schema element, if provided."""
    deprecation_reason: Optional[str]
    """Reason this element is deprecated, if one was provided."""
    extensions: Dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: Optional[EnumValueDefinitionNode]
    """AST node from which this schema element was built, if available."""


class GraphQLEnumValue:
    """Definition of a GraphQL enum value

    :param value: internal value represented by this enum value; if it is not
        provided, the name of the enum value will be used as its internal value
        when the value is serialized
    :param description: human-readable description for this enum value, if
        provided
    :param deprecation_reason: reason this enum value is deprecated, if one was
        provided
    :param extensions: custom extensions for this enum value
    :param ast_node: AST node from which this enum value was built, if available

    >>> from graphql import GraphQLEnumType, GraphQLEnumValue, parse
    >>> document = parse('''
    ...     enum Episode {
    ...       NEW_HOPE
    ...     }
    ... ''')
    >>> new_hope = GraphQLEnumValue(
    ...     4,
    ...     description='Released in 1977.',
    ...     deprecation_reason='Use A_NEW_HOPE.',
    ...     extensions={'trilogy': 'original'},
    ...     ast_node=document.definitions[0].values[0],
    ... )
    >>> new_hope.value, new_hope.description
    (4, 'Released in 1977.')
    >>> episode_type = GraphQLEnumType('Episode', {'NEW_HOPE': new_hope})
    >>> episode_type.serialize(4)
    'NEW_HOPE'
    """

    value: Any
    """Internal value represented by this enum value."""
    description: Optional[str]
    """Human-readable description for this schema element, if provided."""
    deprecation_reason: Optional[str]
    """Reason this element is deprecated, if one was provided."""
    extensions: Dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: Optional[EnumValueDefinitionNode]
    """AST node from which this schema element was built, if available."""

    def __init__(
        self,
        value: Any = None,
        description: Optional[str] = None,
        deprecation_reason: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[EnumValueDefinitionNode] = None,
    ) -> None:
        if description is not None and not is_description(description):
            raise TypeError("The description of the enum value must be a string.")
        if deprecation_reason is not None and not is_description(deprecation_reason):
            raise TypeError(
                "The deprecation reason for the enum value must be a string."
            )
        if extensions is None:
            extensions = {}
        elif not isinstance(extensions, dict) or not all(
            isinstance(key, str) for key in extensions
        ):
            raise TypeError(
                "Enum value extensions must be a dictionary with string keys."
            )
        if ast_node and not isinstance(ast_node, EnumValueDefinitionNode):
            raise TypeError("AST node must be an EnumValueDefinitionNode.")
        self.value = value
        self.description = description
        self.deprecation_reason = deprecation_reason
        self.extensions = extensions
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
        """Get the keyword arguments that can be used to recreate this enum value.

        :returns: a dictionary with the constructor arguments for this enum value

        >>> from graphql import GraphQLEnumValue
        >>> enum_value = GraphQLEnumValue(4, description='Released in 1977.')
        >>> kwargs = enum_value.to_kwargs()
        >>> kwargs['value'], kwargs['description']
        (4, 'Released in 1977.')
        >>> GraphQLEnumValue(**kwargs) == enum_value
        True
        """
        return GraphQLEnumValueKwargs(
            value=self.value,
            description=self.description,
            deprecation_reason=self.deprecation_reason,
            extensions=self.extensions,
            ast_node=self.ast_node,
        )

    def __copy__(self) -> "GraphQLEnumValue":  # pragma: no cover
        return self.__class__(**self.to_kwargs())


GraphQLInputFieldMap = Dict[str, "GraphQLInputField"]
GraphQLInputFieldOutType = Callable[[Dict[str, Any]], Any]


class GraphQLInputObjectTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    """Arguments used to construct a GraphQLInputObjectType.

    This is the type of the dictionary returned by
    :meth:`GraphQLInputObjectType.to_kwargs`.
    """

    fields: GraphQLInputFieldMap
    """Fields declared by this object, interface, input object, or literal."""
    out_type: Optional[GraphQLInputFieldOutType]
    """Function or class used to transform outbound values (extension of GraphQL.js).

    If not set, the outbound values will be Python dictionaries.
    """
    is_one_of: bool
    """Whether this input object uses the experimental OneOf input object semantics."""


class GraphQLInputObjectType(GraphQLNamedType):
    """Input Object Type Definition

    An input object defines a structured collection of fields which may be supplied
    to a field argument.

    Using ``NonNull`` will ensure that a value must be provided by the query.

    Example::

        NonNullFloat = GraphQLNonNull(GraphQLFloat)

        GeoPoint = GraphQLInputObjectType('GeoPoint', {
            'lat': GraphQLInputField(NonNullFloat),
            'lon': GraphQLInputField(NonNullFloat),
            'alt': GraphQLInputField(GraphQLFloat, default_value=0),
        })

    The outbound values will be Python dictionaries by default, but you can have them
    converted to other types by specifying an ``out_type`` function or class.

    :param name: the GraphQL name for this input object type
    :param fields: fields declared by this input object type, as a dictionary with
        field names as keys and :class:`GraphQLInputField` instances (or input types)
        as values, or a thunk returning such a dictionary
    :param description: human-readable description for this type, if provided
    :param out_type: function or class used to transform outbound values
        (extension of GraphQL.js)
    :param extensions: custom extensions for this type
    :param ast_node: AST node from which this type was built, if available
    :param extension_ast_nodes: AST extension nodes applied to this type
    :param is_one_of: whether this input object uses the experimental OneOf input
        object semantics

    >>> from graphql import (
    ...     GraphQLID, GraphQLInputField, GraphQLInputObjectType, GraphQLInt,
    ...     GraphQLNonNull, GraphQLString, parse)
    >>> document = parse('''
    ...     input ReviewInput {
    ...       stars: Int!
    ...       commentary: String
    ...     }
    ...
    ...     extend input ReviewInput {
    ...       body: String
    ...     }
    ... ''')
    >>> definition = document.definitions[0]
    >>> review_input_type = GraphQLInputObjectType(
    ...     'ReviewInput',
    ...     description='Input collected when reviewing a product.',
    ...     fields={
    ...         'stars': GraphQLInputField(
    ...             GraphQLNonNull(GraphQLInt),
    ...             description='Star rating from one to five.',
    ...             extensions={'min': 1, 'max': 5},
    ...             ast_node=definition.fields[0],
    ...         ),
    ...         'commentary': GraphQLInputField(
    ...             GraphQLString,
    ...             default_value='',
    ...             deprecation_reason='Use body.',
    ...             ast_node=definition.fields[1],
    ...         ),
    ...     },
    ...     extensions={'form': 'review'},
    ...     ast_node=definition,
    ...     extension_ast_nodes=[document.definitions[1]],
    ...     is_one_of=False,
    ... )
    >>> search_by_type = GraphQLInputObjectType(
    ...     'SearchBy',
    ...     fields={
    ...         'id': GraphQLInputField(GraphQLID),
    ...         'slug': GraphQLInputField(GraphQLString),
    ...     },
    ...     is_one_of=True,
    ... )
    >>> fields = review_input_type.fields
    >>> review_input_type.description
    'Input collected when reviewing a product.'
    >>> str(fields['stars'].type)
    'Int!'
    >>> fields['stars'].extensions
    {'min': 1, 'max': 5}
    >>> fields['commentary'].default_value
    ''
    >>> fields['commentary'].deprecation_reason
    'Use body.'
    >>> review_input_type.is_one_of
    False
    >>> search_by_type.is_one_of
    True

    This variant converts the outbound values using an ``out_type``:

    >>> geo_point_type = GraphQLInputObjectType(
    ...     'GeoPoint',
    ...     {
    ...         'lat': GraphQLInputField(GraphQLInt),
    ...         'lon': GraphQLInputField(GraphQLInt),
    ...     },
    ...     out_type=lambda value: (value['lat'], value['lon']),
    ... )
    >>> geo_point_type.out_type({'lat': 52, 'lon': 13})
    (52, 13)
    """

    ast_node: Optional[InputObjectTypeDefinitionNode]
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: Tuple[InputObjectTypeExtensionNode, ...]
    """AST extension nodes applied to this schema element."""
    is_one_of: bool
    """Whether this input object uses the experimental OneOf input object semantics."""

    def __init__(
        self,
        name: str,
        fields: ThunkMapping["GraphQLInputField"],
        description: Optional[str] = None,
        out_type: Optional[GraphQLInputFieldOutType] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[InputObjectTypeDefinitionNode] = None,
        extension_ast_nodes: Optional[Collection[InputObjectTypeExtensionNode]] = None,
        is_one_of: bool = False,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            extensions=extensions,
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
                " as a collection of InputObjectTypeExtensionNode instances."
            )
        self._fields = fields
        if out_type is not None:
            self.out_type = out_type  # type: ignore
        self.is_one_of = is_one_of

    @staticmethod
    def out_type(value: Dict[str, Any]) -> Any:
        """Transform outbound values (this is an extension of GraphQL.js).

        This default implementation passes values unaltered as dictionaries.

        :param value: the coerced input object value as a dictionary
        :returns: the transformed value
        """
        return value

    def to_kwargs(self) -> GraphQLInputObjectTypeKwargs:
        """Get the keyword arguments that can be used to recreate this type.

        :returns: a dictionary with the constructor arguments for this type

        >>> from graphql import (
        ...     GraphQLInputField, GraphQLInputObjectType, GraphQLInt, GraphQLNonNull)
        >>> review_input_type = GraphQLInputObjectType(
        ...     'ReviewInput', {'stars': GraphQLInputField(GraphQLNonNull(GraphQLInt))})
        >>> kwargs = review_input_type.to_kwargs()
        >>> review_input_type_copy = GraphQLInputObjectType(**kwargs)
        >>> str(kwargs['fields']['stars'].type)
        'Int!'
        >>> str(review_input_type_copy.fields['stars'].type)
        'Int!'
        """
        # noinspection PyArgumentList
        return GraphQLInputObjectTypeKwargs(  # type: ignore
            super().to_kwargs(),
            fields=self.fields.copy(),
            out_type=(
                None
                if self.out_type is GraphQLInputObjectType.out_type
                else self.out_type
            ),
            is_one_of=self.is_one_of,
        )

    def __copy__(self) -> "GraphQLInputObjectType":  # pragma: no cover
        return self.__class__(**self.to_kwargs())

    @cached_property
    def fields(self) -> GraphQLInputFieldMap:
        """Get provided fields, wrap them as GraphQLInputField if needed.

        :returns: the fields keyed by field name

        >>> from graphql import assert_input_object_type, build_schema
        >>> schema = build_schema('''
        ...     input ReviewInput {
        ...       stars: Int!
        ...       commentary: String = ""
        ...     }
        ...
        ...     type Query {
        ...       reviews(filter: ReviewInput): [String]
        ...     }
        ... ''')
        >>> review_input_type = assert_input_object_type(
        ...     schema.get_type('ReviewInput'))
        >>> fields = review_input_type.fields
        >>> list(fields)
        ['stars', 'commentary']
        >>> fields['commentary'].default_value
        ''
        """
        try:
            fields = resolve_thunk(self._fields)
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            raise cls(f"{self.name} fields cannot be resolved. {error}") from error
        if not isinstance(fields, Mapping) or not all(
            isinstance(key, str) for key in fields
        ):
            raise TypeError(
                f"{self.name} fields must be specified"
                " as a mapping with field names as keys."
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
            assert_name(name): (
                value
                if isinstance(value, GraphQLInputField)
                else GraphQLInputField(value)
            )
            for name, value in fields.items()
        }


def is_input_object_type(type_: Any) -> bool:
    """Check whether the given value is a GraphQLInputObjectType.

    :param type_: the value to inspect
    :returns: whether the value is a GraphQLInputObjectType

    >>> from graphql import build_schema, is_input_object_type
    >>> schema = build_schema('''
    ...     input ReviewInput {
    ...       stars: Int!
    ...     }
    ...
    ...     type Review {
    ...       stars: Int!
    ...     }
    ...
    ...     type Query {
    ...       review(input: ReviewInput): Review
    ...     }
    ... ''')
    >>> is_input_object_type(schema.get_type('ReviewInput'))
    True
    >>> is_input_object_type(schema.get_type('Review'))
    False
    """
    return isinstance(type_, GraphQLInputObjectType)


def assert_input_object_type(type_: Any) -> GraphQLInputObjectType:
    """Return the value as a GraphQLInputObjectType, or raise a TypeError otherwise.

    :param type_: the value to inspect
    :returns: the value typed as a GraphQLInputObjectType

    >>> from graphql import build_schema, assert_input_object_type
    >>> schema = build_schema('''
    ...     input ReviewInput {
    ...       stars: Int!
    ...     }
    ...
    ...     type Review {
    ...       stars: Int!
    ...     }
    ...
    ...     type Query {
    ...       review(input: ReviewInput): Review
    ...     }
    ... ''')
    >>> input_type = assert_input_object_type(schema.get_type('ReviewInput'))
    >>> list(input_type.fields)
    ['stars']
    >>> assert_input_object_type(schema.get_type('Review'))
    Traceback (most recent call last):
    ...
    TypeError: Expected Review to be a GraphQL Input Object type.
    """
    if not is_input_object_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL Input Object type.")
    return cast(GraphQLInputObjectType, type_)


class GraphQLInputFieldKwargs(TypedDict, total=False):
    """Arguments used to define a GraphQL input field.

    This is the type of the dictionary returned by
    :meth:`GraphQLInputField.to_kwargs`.
    """

    type_: "GraphQLInputType"
    """The GraphQL type reference or runtime type for this element."""
    default_value: Any
    """Default value used when no explicit value is supplied."""
    description: Optional[str]
    """Human-readable description for this schema element, if provided."""
    deprecation_reason: Optional[str]
    """Reason this element is deprecated, if one was provided."""
    out_name: Optional[str]
    """Name of the key in the outbound value (extension of GraphQL.js)."""
    extensions: Dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: Optional[InputValueDefinitionNode]
    """AST node from which this schema element was built, if available."""


class GraphQLInputField:
    """Definition of a GraphQL input field

    :param type_: the GraphQL input type of this input field
    :param default_value: default value used when no explicit value is supplied
    :param description: human-readable description for this input field, if
        provided
    :param deprecation_reason: reason this input field is deprecated, if one was
        provided
    :param out_name: name of the key in the outbound value, if it should differ
        from the field name (extension of GraphQL.js)
    :param extensions: custom extensions for this input field
    :param ast_node: AST node from which this input field was built, if available

    >>> from graphql import GraphQLInputField, GraphQLInt, GraphQLNonNull, parse
    >>> document = parse('''
    ...     input ReviewInput {
    ...       stars: Int!
    ...     }
    ... ''')
    >>> stars_field = GraphQLInputField(
    ...     GraphQLNonNull(GraphQLInt),
    ...     description='Star rating from one to five.',
    ...     out_name='star_rating',
    ...     extensions={'min': 1, 'max': 5},
    ...     ast_node=document.definitions[0].fields[0],
    ... )
    >>> str(stars_field.type)
    'Int!'
    >>> stars_field.out_name
    'star_rating'
    >>> stars_field.extensions
    {'min': 1, 'max': 5}
    """

    type: "GraphQLInputType"
    """The GraphQL type reference or runtime type for this element."""
    default_value: Any
    """Default value used when no explicit value is supplied."""
    description: Optional[str]
    """Human-readable description for this schema element, if provided."""
    deprecation_reason: Optional[str]
    """Reason this element is deprecated, if one was provided."""
    out_name: Optional[str]
    """Name of the key in the outbound value (extension of GraphQL.js).

    Used for transforming names; if not set, the field name is used.
    """
    extensions: Dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: Optional[InputValueDefinitionNode]
    """AST node from which this schema element was built, if available."""

    def __init__(
        self,
        type_: "GraphQLInputType",
        default_value: Any = Undefined,
        description: Optional[str] = None,
        deprecation_reason: Optional[str] = None,
        out_name: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[InputValueDefinitionNode] = None,
    ) -> None:
        if not is_input_type(type_):
            raise TypeError("Input field type must be a GraphQL input type.")
        if description is not None and not is_description(description):
            raise TypeError("Input field description must be a string.")
        if deprecation_reason is not None and not is_description(deprecation_reason):
            raise TypeError("Input field deprecation reason must be a string.")
        if out_name is not None and not isinstance(out_name, str):
            raise TypeError("Input field out name must be a string.")
        if extensions is None:
            extensions = {}
        elif not isinstance(extensions, dict) or not all(
            isinstance(key, str) for key in extensions
        ):
            raise TypeError(
                "Input field extensions must be a dictionary with string keys."
            )
        if ast_node and not isinstance(ast_node, InputValueDefinitionNode):
            raise TypeError("Input field AST node must be an InputValueDefinitionNode.")
        self.type = type_
        self.default_value = default_value
        self.description = description
        self.deprecation_reason = deprecation_reason
        self.out_name = out_name
        self.extensions = extensions
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
        """Get the keyword arguments that can be used to recreate this input field.

        :returns: a dictionary with the constructor arguments for this input field

        >>> from graphql import GraphQLInputField, GraphQLString
        >>> field = GraphQLInputField(GraphQLString, default_value='')
        >>> kwargs = field.to_kwargs()
        >>> kwargs['type_'], kwargs['default_value']
        (<GraphQLScalarType 'String'>, '')
        >>> GraphQLInputField(**kwargs) == field
        True
        """
        return GraphQLInputFieldKwargs(
            type_=self.type,
            default_value=self.default_value,
            description=self.description,
            deprecation_reason=self.deprecation_reason,
            out_name=self.out_name,
            extensions=self.extensions,
            ast_node=self.ast_node,
        )

    def __copy__(self) -> "GraphQLInputField":  # pragma: no cover
        return self.__class__(**self.to_kwargs())


def is_required_input_field(field: GraphQLInputField) -> bool:
    """Check whether the input field is non-null and has no default value.

    :param field: the input field definition to inspect
    :returns: whether the input field is non-null and has no default value

    >>> from graphql import (
    ...     GraphQLInputField, GraphQLInt, GraphQLNonNull, GraphQLString,
    ...     is_required_input_field)
    >>> required_field = GraphQLInputField(GraphQLNonNull(GraphQLInt))
    >>> optional_field = GraphQLInputField(GraphQLString)
    >>> field_with_default = GraphQLInputField(
    ...     GraphQLNonNull(GraphQLInt), default_value=10)
    >>> is_required_input_field(required_field)
    True
    >>> is_required_input_field(optional_field)
    False
    >>> is_required_input_field(field_with_default)
    False
    """
    return is_non_null_type(field.type) and field.default_value is Undefined


# Wrapper types


class GraphQLList(Generic[GT], GraphQLWrappingType[GT]):
    """List Type Wrapper

    A list is a wrapping type which points to another type. Lists are often created
    within the context of defining the fields of an object type.

    Example::

        PersonType = GraphQLObjectType('Person', lambda: {
            'parents': GraphQLField(GraphQLList(PersonType)),
            'children': GraphQLField(GraphQLList(PersonType)),
        })

    :param type_: the type to wrap

    >>> from graphql import GraphQLList, GraphQLNonNull, GraphQLString
    >>> string_list = GraphQLList(GraphQLString)
    >>> string_list.of_type
    <GraphQLScalarType 'String'>
    >>> str(string_list)
    '[String]'
    >>> str(GraphQLList(GraphQLNonNull(GraphQLString)))
    '[String!]'
    """

    def __init__(self, type_: GT) -> None:
        super().__init__(type_=type_)

    def __str__(self) -> str:
        return f"[{self.of_type}]"


def is_list_type(type_: Any) -> bool:
    """Check whether the given value is a GraphQLList.

    :param type_: the value to inspect
    :returns: whether the value is a GraphQLList

    >>> from graphql import (
    ...     build_schema, get_nullable_type, GraphQLList, GraphQLString, is_list_type)
    >>> schema = build_schema('''
    ...     type Query {
    ...       tags: [String!]!
    ...     }
    ... ''')
    >>> tags_field = schema.query_type.fields['tags']
    >>> is_list_type(GraphQLList(GraphQLString))
    True
    >>> is_list_type(GraphQLString)
    False
    >>> is_list_type(tags_field.type)
    False
    >>> is_list_type(get_nullable_type(tags_field.type))
    True
    >>> is_list_type('[String]')
    False
    >>> is_list_type(None)
    False
    """
    return isinstance(type_, GraphQLList)


def assert_list_type(type_: Any) -> GraphQLList:
    """Return the value as a GraphQLList, or raise a TypeError otherwise.

    :param type_: the value to inspect
    :returns: the value typed as a GraphQLList

    >>> from graphql import GraphQLList, GraphQLString, assert_list_type
    >>> list_type = assert_list_type(GraphQLList(GraphQLString))
    >>> list_type.of_type
    <GraphQLScalarType 'String'>
    >>> assert_list_type(GraphQLString)
    Traceback (most recent call last):
    ...
    TypeError: Expected String to be a GraphQL List type.
    """
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

        RowType = GraphQLObjectType('Row', lambda: {
            'id': GraphQLField(GraphQLNonNull(GraphQLString)),
        })

    Note: the enforcement of non-nullability occurs within the executor.

    :param type_: the nullable type to wrap

    >>> from graphql import GraphQLList, GraphQLNonNull, GraphQLString
    >>> required_string = GraphQLNonNull(GraphQLString)
    >>> required_string.of_type
    <GraphQLScalarType 'String'>
    >>> str(required_string)
    'String!'
    >>> str(GraphQLNonNull(GraphQLList(GraphQLString)))
    '[String]!'
    """

    def __init__(self, type_: GNT):
        super().__init__(type_=type_)
        if isinstance(type_, GraphQLNonNull):
            raise TypeError(
                "Can only create NonNull of a Nullable GraphQLType but got:"
                f" {type_}."
            )

    def __str__(self) -> str:
        return f"{self.of_type}!"


def is_non_null_type(type_: Any) -> bool:
    """Check whether the given value is a GraphQLNonNull.

    :param type_: the value to inspect
    :returns: whether the value is a GraphQLNonNull

    >>> from graphql import (
    ...     build_schema, GraphQLNonNull, GraphQLString, is_non_null_type)
    >>> schema = build_schema('''
    ...     type Query {
    ...       name: String!
    ...       nickname: String
    ...     }
    ... ''')
    >>> fields = schema.query_type.fields
    >>> is_non_null_type(GraphQLNonNull(GraphQLString))
    True
    >>> is_non_null_type(fields['name'].type)
    True
    >>> is_non_null_type(fields['nickname'].type)
    False
    >>> is_non_null_type('String!')
    False
    >>> is_non_null_type(None)
    False
    """
    return isinstance(type_, GraphQLNonNull)


def assert_non_null_type(type_: Any) -> GraphQLNonNull:
    """Return the value as a GraphQLNonNull, or raise a TypeError otherwise.

    :param type_: the value to inspect
    :returns: the value typed as a GraphQLNonNull

    >>> from graphql import GraphQLNonNull, GraphQLString, assert_non_null_type
    >>> non_null_type = assert_non_null_type(GraphQLNonNull(GraphQLString))
    >>> non_null_type.of_type
    <GraphQLScalarType 'String'>
    >>> assert_non_null_type(GraphQLString)
    Traceback (most recent call last):
    ...
    TypeError: Expected String to be a GraphQL Non-Null type.
    """
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
    """Check whether the given value is a GraphQL type that can accept null.

    :param type_: the value to inspect
    :returns: whether the value is a GraphQL type that can accept null

    >>> from graphql import GraphQLNonNull, GraphQLString, is_nullable_type
    >>> is_nullable_type(GraphQLString)
    True
    >>> is_nullable_type(GraphQLNonNull(GraphQLString))
    False
    >>> is_nullable_type(None)
    False
    """
    return isinstance(type_, graphql_nullable_types)


def assert_nullable_type(type_: Any) -> GraphQLNullableType:
    """Return the value as a nullable GraphQL type, or raise a TypeError otherwise.

    :param type_: the value to inspect
    :returns: the value typed as a nullable GraphQL type

    >>> from graphql import GraphQLNonNull, GraphQLString, assert_nullable_type
    >>> assert_nullable_type(GraphQLString)
    <GraphQLScalarType 'String'>
    >>> assert_nullable_type(GraphQLNonNull(GraphQLString))
    Traceback (most recent call last):
    ...
    TypeError: Expected String! to be a GraphQL nullable type.
    """
    if not is_nullable_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL nullable type.")
    return cast(GraphQLNullableType, type_)


@overload
def get_nullable_type(type_: None) -> None: ...


@overload
def get_nullable_type(type_: GraphQLNullableType) -> GraphQLNullableType: ...


@overload
def get_nullable_type(type_: GraphQLNonNull) -> GraphQLNullableType: ...


def get_nullable_type(
    type_: Optional[Union[GraphQLNullableType, GraphQLNonNull]],
) -> Optional[GraphQLNullableType]:
    """Unwrap possible non-null type

    :param type_: the GraphQL type to inspect
    :returns: the nullable type after removing one non-null wrapper, if present

    >>> from graphql import (
    ...     GraphQLList, GraphQLNonNull, GraphQLString, get_nullable_type)
    >>> get_nullable_type(GraphQLNonNull(GraphQLString))
    <GraphQLScalarType 'String'>
    >>> string_list = GraphQLList(GraphQLString)
    >>> get_nullable_type(string_list) is string_list
    True
    >>> str(get_nullable_type(GraphQLNonNull(GraphQLList(GraphQLString))))
    '[String]'
    >>> get_nullable_type(None) is None
    True
    """
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
    """Check whether the given value can be used as a GraphQL input type.

    :param type_: the value to inspect
    :returns: whether the value can be used as a GraphQL input type

    >>> from graphql import build_schema, is_input_type
    >>> schema = build_schema('''
    ...     input ReviewInput {
    ...       stars: Int!
    ...     }
    ...
    ...     type Review {
    ...       stars: Int!
    ...     }
    ...
    ...     type Query {
    ...       review(input: ReviewInput): Review
    ...     }
    ... ''')
    >>> is_input_type(schema.get_type('ReviewInput'))
    True
    >>> is_input_type(schema.get_type('Review'))
    False
    """
    return isinstance(type_, graphql_input_types) or (
        isinstance(type_, GraphQLWrappingType) and is_input_type(type_.of_type)
    )


def assert_input_type(type_: Any) -> GraphQLInputType:
    """Return the value as a GraphQL input type, or raise a TypeError otherwise.

    :param type_: the value to inspect
    :returns: the value typed as a GraphQL input type

    >>> from graphql import build_schema, assert_input_type
    >>> schema = build_schema('''
    ...     input ReviewInput {
    ...       stars: Int!
    ...     }
    ...
    ...     type Review {
    ...       stars: Int!
    ...     }
    ...
    ...     type Query {
    ...       review(input: ReviewInput): Review
    ...     }
    ... ''')
    >>> input_type = assert_input_type(schema.get_type('ReviewInput'))
    >>> str(input_type)
    'ReviewInput'
    >>> assert_input_type(schema.get_type('Review'))
    Traceback (most recent call last):
    ...
    TypeError: Expected Review to be a GraphQL input type.
    """
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
    """Check whether the given value can be used as a GraphQL output type.

    :param type_: the value to inspect
    :returns: whether the value can be used as a GraphQL output type

    >>> from graphql import build_schema, is_output_type
    >>> schema = build_schema('''
    ...     input ReviewInput {
    ...       stars: Int!
    ...     }
    ...
    ...     type Review {
    ...       stars: Int!
    ...     }
    ...
    ...     type Query {
    ...       review(input: ReviewInput): Review
    ...     }
    ... ''')
    >>> is_output_type(schema.get_type('Review'))
    True
    >>> is_output_type(schema.get_type('ReviewInput'))
    False
    """
    return isinstance(type_, graphql_output_types) or (
        isinstance(type_, GraphQLWrappingType) and is_output_type(type_.of_type)
    )


def assert_output_type(type_: Any) -> GraphQLOutputType:
    """Return the value as a GraphQL output type, or raise a TypeError otherwise.

    :param type_: the value to inspect
    :returns: the value typed as a GraphQL output type

    >>> from graphql import build_schema, assert_output_type
    >>> schema = build_schema('''
    ...     input ReviewInput {
    ...       stars: Int!
    ...     }
    ...
    ...     type Review {
    ...       stars: Int!
    ...     }
    ...
    ...     type Query {
    ...       review(input: ReviewInput): Review
    ...     }
    ... ''')
    >>> output_type = assert_output_type(schema.get_type('Review'))
    >>> str(output_type)
    'Review'
    >>> assert_output_type(schema.get_type('ReviewInput'))
    Traceback (most recent call last):
    ...
    TypeError: Expected ReviewInput to be a GraphQL output type.
    """
    if not is_output_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL output type.")
    return cast(GraphQLOutputType, type_)


# These named types do not include modifiers like List or NonNull.

GraphQLNamedInputType = Union[
    GraphQLScalarType, GraphQLEnumType, GraphQLInputObjectType
]

GraphQLNamedOutputType = Union[
    GraphQLScalarType,
    GraphQLObjectType,
    GraphQLInterfaceType,
    GraphQLUnionType,
    GraphQLEnumType,
]


def is_named_type(type_: Any) -> bool:
    """Check whether the given value is a GraphQL named type.

    :param type_: the value to inspect
    :returns: whether the value is a GraphQL named type

    >>> from graphql import GraphQLList, GraphQLString, is_named_type
    >>> is_named_type(GraphQLString)
    True
    >>> is_named_type(GraphQLList(GraphQLString))
    False
    >>> is_named_type(None)
    False
    """
    return isinstance(type_, GraphQLNamedType)


def assert_named_type(type_: Any) -> GraphQLNamedType:
    """Return the value as a GraphQL named type, or raise a TypeError otherwise.

    :param type_: the value to inspect
    :returns: the value typed as a GraphQL named type

    >>> from graphql import GraphQLList, GraphQLString, assert_named_type
    >>> named_type = assert_named_type(GraphQLString)
    >>> named_type.name
    'String'
    >>> assert_named_type(GraphQLList(GraphQLString))
    Traceback (most recent call last):
    ...
    TypeError: Expected [String] to be a GraphQL named type.
    """
    if not is_named_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL named type.")
    return cast(GraphQLNamedType, type_)


@overload
def get_named_type(type_: None) -> None: ...


@overload
def get_named_type(type_: GraphQLType) -> GraphQLNamedType: ...


def get_named_type(type_: Optional[GraphQLType]) -> Optional[GraphQLNamedType]:
    """Unwrap possible wrapping type

    :param type_: the GraphQL type to inspect
    :returns: the named type after unwrapping all list and non-null wrappers,
        or ``None`` if ``None`` was passed

    >>> from graphql import (
    ...     build_schema, get_named_type, GraphQLList, GraphQLNonNull, GraphQLString)
    >>> schema = build_schema('''
    ...     input ReviewInput {
    ...       stars: Int!
    ...     }
    ...
    ...     type User {
    ...       name: String
    ...     }
    ...
    ...     type Query {
    ...       review(input: [ReviewInput!]!): Boolean
    ...       users: [User!]!
    ...     }
    ... ''')
    >>> fields = schema.query_type.fields
    >>> str(get_named_type(fields['review'].args['input'].type))
    'ReviewInput'
    >>> str(get_named_type(fields['users'].type))
    'User'
    >>> get_named_type(GraphQLNonNull(GraphQLList(GraphQLNonNull(GraphQLString))))
    <GraphQLScalarType 'String'>
    >>> get_named_type(None) is None
    True
    """
    if type_:
        unwrapped_type = type_
        while is_wrapping_type(unwrapped_type):
            unwrapped_type = cast(GraphQLWrappingType, unwrapped_type)
            unwrapped_type = unwrapped_type.of_type
        return cast(GraphQLNamedType, unwrapped_type)
    return None


# These types may describe types which may be leaf values.

graphql_leaf_types = (GraphQLScalarType, GraphQLEnumType)

GraphQLLeafType = Union[GraphQLScalarType, GraphQLEnumType]


def is_leaf_type(type_: Any) -> bool:
    """Check whether the given value is a GraphQL scalar or enum type.

    :param type_: the value to inspect
    :returns: whether the value is a GraphQL scalar or enum type

    >>> from graphql import build_schema, is_leaf_type
    >>> schema = build_schema('''
    ...     enum Episode {
    ...       NEW_HOPE
    ...     }
    ...
    ...     type Review {
    ...       stars: Int!
    ...     }
    ...
    ...     type Query {
    ...       episode: Episode
    ...       review: Review
    ...     }
    ... ''')
    >>> is_leaf_type(schema.get_type('Episode'))
    True
    >>> is_leaf_type(schema.get_type('String'))
    True
    >>> is_leaf_type(schema.get_type('Review'))
    False
    """
    return isinstance(type_, graphql_leaf_types)


def assert_leaf_type(type_: Any) -> GraphQLLeafType:
    """Return the value as a GraphQL leaf type, or raise a TypeError otherwise.

    :param type_: the value to inspect
    :returns: the value typed as a GraphQL leaf type

    >>> from graphql import build_schema, assert_leaf_type
    >>> schema = build_schema('''
    ...     enum Episode {
    ...       NEW_HOPE
    ...     }
    ...
    ...     type Review {
    ...       stars: Int!
    ...     }
    ...
    ...     type Query {
    ...       episode: Episode
    ...       review: Review
    ...     }
    ... ''')
    >>> episode_type = assert_leaf_type(schema.get_type('Episode'))
    >>> str(episode_type)
    'Episode'
    >>> assert_leaf_type(schema.get_type('Review'))
    Traceback (most recent call last):
    ...
    TypeError: Expected Review to be a GraphQL leaf type.
    """
    if not is_leaf_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL leaf type.")
    return cast(GraphQLLeafType, type_)


# These types may describe the parent context of a selection set.

graphql_composite_types = (GraphQLObjectType, GraphQLInterfaceType, GraphQLUnionType)

GraphQLCompositeType = Union[GraphQLObjectType, GraphQLInterfaceType, GraphQLUnionType]


def is_composite_type(type_: Any) -> bool:
    """Check whether the given value is a GraphQL object, interface, or union type.

    :param type_: the value to inspect
    :returns: whether the value is a GraphQL object, interface, or union type

    >>> from graphql import build_schema, is_composite_type
    >>> schema = build_schema('''
    ...     interface Node {
    ...       id: ID!
    ...     }
    ...
    ...     type User implements Node {
    ...       id: ID!
    ...     }
    ...
    ...     union SearchResult = User
    ...
    ...     type Query {
    ...       node: Node
    ...       search: [SearchResult]
    ...     }
    ... ''')
    >>> is_composite_type(schema.get_type('User'))
    True
    >>> is_composite_type(schema.get_type('Node'))
    True
    >>> is_composite_type(schema.get_type('SearchResult'))
    True
    >>> is_composite_type(schema.get_type('String'))
    False
    """
    return isinstance(type_, graphql_composite_types)


def assert_composite_type(type_: Any) -> GraphQLType:
    """Return the value as a GraphQL composite type, or raise a TypeError otherwise.

    :param type_: the value to inspect
    :returns: the value typed as a GraphQL composite type

    >>> from graphql import build_schema, assert_composite_type
    >>> schema = build_schema('''
    ...     interface Node {
    ...       id: ID!
    ...     }
    ...
    ...     type User implements Node {
    ...       id: ID!
    ...     }
    ...
    ...     type Query {
    ...       node: Node
    ...     }
    ... ''')
    >>> user_type = assert_composite_type(schema.get_type('User'))
    >>> str(user_type)
    'User'
    >>> assert_composite_type(schema.get_type('String'))
    Traceback (most recent call last):
    ...
    TypeError: Expected String to be a GraphQL composite type.
    """
    if not is_composite_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL composite type.")
    return cast(GraphQLType, type_)


# These types may describe abstract types.

graphql_abstract_types = (GraphQLInterfaceType, GraphQLUnionType)

GraphQLAbstractType = Union[GraphQLInterfaceType, GraphQLUnionType]


def is_abstract_type(type_: Any) -> bool:
    """Check whether the given value is a GraphQL interface or union type.

    :param type_: the value to inspect
    :returns: whether the value is a GraphQL interface or union type

    >>> from graphql import build_schema, is_abstract_type
    >>> schema = build_schema('''
    ...     interface Node {
    ...       id: ID!
    ...     }
    ...
    ...     type User implements Node {
    ...       id: ID!
    ...     }
    ...
    ...     union SearchResult = User
    ...
    ...     type Query {
    ...       node: Node
    ...       search: [SearchResult]
    ...     }
    ... ''')
    >>> is_abstract_type(schema.get_type('Node'))
    True
    >>> is_abstract_type(schema.get_type('SearchResult'))
    True
    >>> is_abstract_type(schema.get_type('User'))
    False
    """
    return isinstance(type_, graphql_abstract_types)


def assert_abstract_type(type_: Any) -> GraphQLAbstractType:
    """Return the value as a GraphQL abstract type, or raise a TypeError otherwise.

    :param type_: the value to inspect
    :returns: the value typed as a GraphQL abstract type

    >>> from graphql import build_schema, assert_abstract_type
    >>> schema = build_schema('''
    ...     interface Node {
    ...       id: ID!
    ...     }
    ...
    ...     type User implements Node {
    ...       id: ID!
    ...     }
    ...
    ...     type Query {
    ...       node: Node
    ...     }
    ... ''')
    >>> node_type = assert_abstract_type(schema.get_type('Node'))
    >>> str(node_type)
    'Node'
    >>> assert_abstract_type(schema.get_type('User'))
    Traceback (most recent call last):
    ...
    TypeError: Expected User to be a GraphQL abstract type.
    """
    if not is_abstract_type(type_):
        raise TypeError(f"Expected {type_} to be a GraphQL abstract type.")
    return cast(GraphQLAbstractType, type_)
