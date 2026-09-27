"""GraphQL type definitions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Collection, Mapping, Sequence
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    NamedTuple,
    TypedDict,
    TypeVar,
    cast,
    overload,
)

if TYPE_CHECKING:
    from typing import TypeAlias, TypeGuard

from ..error import GraphQLError
from ..language import (
    ConstValueNode,
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
    AbortSignal,
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
    from ..execution.get_variable_signature import GraphQLVariableSignature
    from ..execution.values import VariableValues
    from .schema import GraphQLSchema

    try:
        from typing import Self
    except ImportError:  # Python < 3.11
        from typing_extensions import Self


__all__ = [
    "GraphQLAbstractType",
    "GraphQLArgument",
    "GraphQLArgumentKwargs",
    "GraphQLArgumentMap",
    "GraphQLCompositeType",
    "GraphQLDefaultInput",
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
    "GraphQLResolveInfoHelpers",
    "GraphQLScalarInputLiteralCoercer",
    "GraphQLScalarInputValueCoercer",
    "GraphQLScalarLiteralParser",
    "GraphQLScalarOutputValueCoercer",
    "GraphQLScalarSerializer",
    "GraphQLScalarType",
    "GraphQLScalarTypeKwargs",
    "GraphQLScalarValueParser",
    "GraphQLScalarValueToLiteral",
    "GraphQLType",
    "GraphQLTypeResolver",
    "GraphQLUnionType",
    "GraphQLUnionTypeKwargs",
    "GraphQLWrappingType",
    "Thunk",
    "ThunkCollection",
    "ThunkMapping",
    "assert_abstract_type",
    "assert_argument",
    "assert_composite_type",
    "assert_enum_type",
    "assert_enum_value",
    "assert_field",
    "assert_input_field",
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
    "is_argument",
    "is_composite_type",
    "is_enum_type",
    "is_enum_value",
    "is_field",
    "is_input_field",
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
        msg = f"Expected {type_} to be a GraphQL type."
        raise TypeError(msg)
    return type_


# These types wrap and modify other types

GT_co = TypeVar("GT_co", bound=GraphQLType, covariant=True)


class GraphQLWrappingType(GraphQLType, Generic[GT_co]):
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

    of_type: GT_co
    """The type wrapped by this list or non-null type."""

    def __init__(self, type_: GT_co) -> None:
        self.of_type = type_

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.of_type!r}>"


def is_wrapping_type(type_: Any) -> TypeGuard[GraphQLWrappingType]:
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
        msg = f"Expected {type_} to be a GraphQL wrapping type."
        raise TypeError(msg)
    return type_


class GraphQLNamedTypeKwargs(TypedDict, total=False):
    """Arguments for GraphQL named types"""

    name: str
    """The GraphQL name for this schema element."""
    description: str | None
    """Human-readable description for this schema element, if provided."""
    extensions: dict[str, Any]
    """Custom extension fields reserved for users."""
    # unfortunately, we cannot make the following more specific, because they are
    # used by subclasses with different node types and typed dicts cannot be refined
    ast_node: Any | None
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: tuple[Any, ...]
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
    description: str | None
    """Human-readable description for this schema element, if provided."""
    extensions: dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: TypeDefinitionNode | None
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: tuple[TypeExtensionNode, ...]
    """AST extension nodes applied to this schema element."""

    reserved_types: Mapping[str, GraphQLNamedType] = {}
    """Registry of reserved types (standard scalars and introspection types).

    Named types with these names cannot be redefined.
    """

    def __new__(cls, name: str, *_args: Any, **_kwargs: Any) -> Self:
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

    def __copy__(self) -> GraphQLNamedType:  # pragma: no cover
        return self.__class__(**self.to_kwargs())


T = TypeVar("T")

ThunkCollection: TypeAlias = Callable[[], Collection[T]] | Collection[T]
ThunkMapping: TypeAlias = Callable[[], Mapping[str, T]] | Mapping[str, T]
Thunk: TypeAlias = Callable[[], T] | T


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


# Deprecated in favor of GraphQLScalarOutputValueCoercer, will be removed in v3.4
GraphQLScalarSerializer: TypeAlias = Callable[[Any], Any]
GraphQLScalarOutputValueCoercer: TypeAlias = Callable[[Any], Any]
# Deprecated in favor of GraphQLScalarInputValueCoercer, will be removed in v3.4
GraphQLScalarValueParser: TypeAlias = Callable[[Any], Any]
GraphQLScalarInputValueCoercer: TypeAlias = Callable[[Any], Any]
# Deprecated in favor of GraphQLScalarInputLiteralCoercer, will be removed in v3.4
GraphQLScalarLiteralParser: TypeAlias = Callable[
    [ValueNode, dict[str, Any] | None], Any
]
GraphQLScalarInputLiteralCoercer: TypeAlias = Callable[[ConstValueNode], Any]
GraphQLScalarValueToLiteral: TypeAlias = Callable[[Any], "ConstValueNode | None"]


class GraphQLScalarTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    """Arguments for GraphQL scalar types"""

    serialize: GraphQLScalarSerializer | None
    """Legacy serializer used to convert internal values for response output.

    .. deprecated:: 3.3
        Use ``coerce_output_value`` instead. ``serialize`` will be removed in a
        future version.
    """
    parse_value: GraphQLScalarValueParser | None
    """Legacy parser used to convert externally provided input values.

    .. deprecated:: 3.3
        Use ``coerce_input_value`` instead. ``parse_value`` will be removed in a
        future version.
    """
    parse_literal: GraphQLScalarLiteralParser | None
    """Legacy parser used to convert externally provided input literals.

    .. deprecated:: 3.3
        Use ``replace_variables()`` and ``coerce_input_literal`` instead.
        ``parse_literal`` will be removed in a future version.
    """
    coerce_output_value: GraphQLScalarOutputValueCoercer | None
    """Coerces an internal value to include in a response."""
    coerce_input_value: GraphQLScalarInputValueCoercer | None
    """Coerces an externally provided value to use as an input."""
    coerce_input_literal: GraphQLScalarInputLiteralCoercer | None
    """Coerces an externally provided const literal value to use as an input."""
    value_to_literal: GraphQLScalarValueToLiteral | None
    """Translates an externally provided value to a literal (AST)."""
    specified_by_url: str | None
    """URL identifying the behavior specified for this custom scalar."""


class GraphQLScalarType(GraphQLNamedType):
    """Scalar Type Definition

    Scalar types define the leaf values of a GraphQL response and the input values
    accepted by arguments and input object fields. A scalar type has a name and
    coercion functions that validate and convert runtime values and GraphQL literals.

    If a type's ``coerce_output_value`` function returns ``None`` or ``Undefined``,
    then an error will be raised and a ``None`` value will be returned in the
    response. Prefer validating inputs before execution so clients receive input
    diagnostics before result coercion fails.

    Custom scalar behavior is defined via the following functions:

    - ``coerce_output_value(value)``: Implements "Result Coercion". Given an internal
      value, produces an external value valid for this type. Returns ``Undefined``
      or raises an error to indicate invalid values.
    - ``coerce_input_value(value)``: Implements "Input Coercion" for values. Given
      an external value (for example, variable values), produces an internal value
      valid for this type. Returns ``Undefined`` or raises an error to indicate
      invalid values.
    - ``coerce_input_literal(ast)``: Implements "Input Coercion" for constant
      literals. Given a GraphQL literal (AST) (for example, an argument value),
      produces an internal value valid for this type. Returns ``Undefined`` or
      raises an error to indicate invalid values.
    - ``value_to_literal(value)``: Converts an external value to a GraphQL literal
      (AST). Returns ``Undefined`` or raises an error to indicate invalid values.

    Deprecated, to be removed in a future version:

    - ``serialize(value)``: Implements "Result Coercion". Renamed to
      ``coerce_output_value()``.
    - ``parse_value(value)``: Implements "Input Coercion" for values. Renamed to
      ``coerce_input_value()``.
    - ``parse_literal(ast)``: Implements "Input Coercion" for literals including
      non-specified replacement of variables embedded within complex scalars.
      Replaced by the combination of the ``replace_variables()`` utility and the
      ``coerce_input_literal()`` method.

    :param name: the GraphQL name for this scalar type
    :param serialize: legacy serializer used to convert internal values for
        response output; deprecated, use ``coerce_output_value`` instead
    :param parse_value: legacy parser used to convert externally provided input
        values; deprecated, use ``coerce_input_value`` instead
    :param parse_literal: legacy parser used to convert externally provided input
        literals; deprecated, use ``coerce_input_literal`` instead
    :param coerce_output_value: coerces an internal value to include in a response
    :param coerce_input_value: coerces an externally provided value to use as an
        input
    :param coerce_input_literal: coerces an externally provided const literal value
        to use as an input
    :param value_to_literal: translates an externally provided value to a literal
        (AST)
    :param description: human-readable description for this type, if provided
    :param specified_by_url: URL identifying the behavior specified for this custom
        scalar
    :param extensions: custom extensions for this type
    :param ast_node: AST node from which this type was built, if available
    :param extension_ast_nodes: AST extension nodes applied to this type

    >>> from graphql import GraphQLError, GraphQLScalarType, IntValueNode
    >>> def ensure_odd(value):
    ...     if not isinstance(value, int):
    ...         raise GraphQLError(
    ...             f"Scalar 'Odd' cannot represent '{value}'"
    ...             " since it is not an integer.")
    ...     if not value % 2:
    ...         raise GraphQLError(
    ...             f"Scalar 'Odd' cannot represent '{value}' since it is even.")
    ...     return value
    >>> odd_type = GraphQLScalarType(
    ...     'Odd',
    ...     coerce_output_value=ensure_odd,
    ...     coerce_input_value=ensure_odd,
    ...     value_to_literal=lambda value: IntValueNode(value=str(ensure_odd(value))),
    ... )
    >>> odd_type.coerce_output_value(3)
    3
    >>> odd_type.coerce_input_value(4)
    Traceback (most recent call last):
    ...
    graphql.error.graphql_error.GraphQLError: Scalar 'Odd' cannot represent '4' ...
    >>> odd_type.value_to_literal(5).value
    '5'

    Configure a scalar type with all coercion functions and metadata:

    >>> from graphql import IntValueNode, parse
    >>> document = parse('''
    ...     "Odd integer values."
    ...     scalar Odd @specifiedBy(url: "https://example.com/odd")
    ...
    ...     extend scalar Odd @specifiedBy(url: "https://example.com/odd-v2")
    ... ''')
    >>> def coerce_input_literal(ast):
    ...     if not isinstance(ast, IntValueNode):
    ...         raise TypeError('Odd can only accept integer literals.')
    ...     value = int(ast.value)
    ...     if not value % 2:
    ...         raise TypeError('Odd can only accept odd integer literals.')
    ...     return value
    >>> odd_type = GraphQLScalarType(
    ...     'Odd',
    ...     description='Odd integer values.',
    ...     specified_by_url='https://example.com/odd',
    ...     coerce_output_value=ensure_odd,
    ...     coerce_input_value=ensure_odd,
    ...     coerce_input_literal=coerce_input_literal,
    ...     value_to_literal=lambda value: IntValueNode(value=str(ensure_odd(value))),
    ...     extensions={'numeric': True},
    ...     ast_node=document.definitions[0],
    ...     extension_ast_nodes=[document.definitions[1]],
    ... )
    >>> odd_type.description
    'Odd integer values.'
    >>> odd_type.specified_by_url
    'https://example.com/odd'
    >>> odd_type.coerce_output_value(3)
    3
    >>> odd_type.coerce_input_value(5)
    5
    >>> odd_type.extensions
    {'numeric': True}
    """

    specified_by_url: str | None
    """URL identifying the behavior specified for this custom scalar."""
    ast_node: ScalarTypeDefinitionNode | None
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: tuple[ScalarTypeExtensionNode, ...]
    """AST extension nodes applied to this schema element."""

    coerce_output_value: GraphQLScalarOutputValueCoercer
    """Coercer used to convert internal scalar values for response output."""
    coerce_input_value: GraphQLScalarInputValueCoercer
    """Coercer used to convert externally provided scalar input values."""
    coerce_input_literal: GraphQLScalarInputLiteralCoercer | None
    """Coercer used to convert GraphQL scalar input literals."""
    value_to_literal: GraphQLScalarValueToLiteral | None
    """Converter used to produce GraphQL literals from runtime input values."""

    def __init__(
        self,
        name: str,
        serialize: GraphQLScalarSerializer | None = None,
        parse_value: GraphQLScalarValueParser | None = None,
        parse_literal: GraphQLScalarLiteralParser | None = None,
        coerce_output_value: GraphQLScalarOutputValueCoercer | None = None,
        coerce_input_value: GraphQLScalarInputValueCoercer | None = None,
        coerce_input_literal: GraphQLScalarInputLiteralCoercer | None = None,
        value_to_literal: GraphQLScalarValueToLiteral | None = None,
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
        elif coerce_output_value is not None:
            self.serialize = coerce_output_value  # type: ignore
        if parse_value is not None:
            self.parse_value = parse_value  # type: ignore
        elif coerce_input_value is not None:
            self.parse_value = coerce_input_value  # type: ignore
        if parse_literal is not None:
            self.parse_literal = parse_literal  # type: ignore
        self.coerce_output_value = (
            self.serialize if coerce_output_value is None else coerce_output_value
        )
        self.coerce_input_value = (
            self.parse_value if coerce_input_value is None else coerce_input_value
        )
        self.coerce_input_literal = coerce_input_literal
        self.value_to_literal = value_to_literal
        if parse_literal is not None and parse_value is None:
            msg = (
                f"{name} must provide both 'parse_value' and 'parse_literal' functions."
            )
            raise TypeError(msg)
        if coerce_input_literal is not None and coerce_input_value is None:
            msg = (
                f"{name} must provide both 'coerce_input_value'"
                " and 'coerce_input_literal' functions."
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

        .. deprecated:: 3.3
            Use ``coerce_output_value()`` instead. ``serialize()`` will be removed
            in a future version.

        :param value: the internal value to serialize
        :returns: the serialized value
        """
        return value

    @staticmethod
    def parse_value(value: Any) -> Any:
        """Parses an externally provided value to use as an input.

        This default method just passes the value through and should be replaced
        with a more specific version when creating a scalar type.

        .. deprecated:: 3.3
            Use ``coerce_input_value()`` instead. ``parse_value()`` will be removed
            in a future version.

        :param value: the externally provided value
        :returns: the internal value
        """
        return value

    def parse_literal(
        self, node: ValueNode, variables: dict[str, Any] | None = None
    ) -> Any:
        """Parses an externally provided literal value to use as an input.

        This default method uses the coerce_input_value method and should be
        replaced with a more specific version when creating a scalar type.

        .. deprecated:: 3.3
            Use ``replace_variables()`` and ``coerce_input_literal()`` instead.
            ``parse_literal()`` will be removed in a future version.

        :param node: the AST value literal to parse
        :param variables: runtime variable values keyed by variable name, used to
            resolve variables contained in the literal
        :returns: the internal value

        >>> from graphql import GraphQLScalarType, parse_value
        >>> json_type = GraphQLScalarType('JSON')
        >>> json_type.parse_literal(parse_value('{a: [1, 2], b: $var}'), {'var': 3})
        {'a': [1, 2], 'b': 3}
        """
        return self.coerce_input_value(value_from_ast_untyped(node, variables))

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
            coerce_output_value=None
            if self.coerce_output_value is GraphQLScalarType.serialize
            else self.coerce_output_value,
            coerce_input_value=None
            if self.coerce_input_value is GraphQLScalarType.parse_value
            else self.coerce_input_value,
            coerce_input_literal=self.coerce_input_literal,
            value_to_literal=self.value_to_literal,
            specified_by_url=self.specified_by_url,
        )

    def __copy__(self) -> GraphQLScalarType:  # pragma: no cover
        return self.__class__(**self.to_kwargs())


def is_scalar_type(type_: Any) -> TypeGuard[GraphQLScalarType]:
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
        msg = f"Expected {type_} to be a GraphQL Scalar type."
        raise TypeError(msg)
    return type_


GraphQLArgumentMap: TypeAlias = dict[str, "GraphQLArgument"]


class GraphQLFieldKwargs(TypedDict, total=False):
    """Arguments for GraphQL fields"""

    type_: GraphQLOutputType
    """The GraphQL type reference or runtime type for this element."""
    args: GraphQLArgumentMap | None
    """Arguments accepted by this field or directive."""
    resolve: GraphQLFieldResolver | None
    """Resolver function used to produce this field value."""
    subscribe: GraphQLFieldResolver | None
    """Resolver function used to create a subscription event stream for this field."""
    description: str | None
    """Human-readable description for this schema element, if provided."""
    deprecation_reason: str | None
    """Reason this element is deprecated, if one was provided."""
    extensions: dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: FieldDefinitionNode | None
    """AST node from which this schema element was built, if available."""


class GraphQLField:  # noqa: PLW1641
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

    >>> from graphql import (
    ...     GraphQLArgument, GraphQLDefaultInput, GraphQLField, GraphQLString, parse)
    >>> document = parse('''
    ...     type User {
    ...       name(format: String = "short"): String
    ...     }
    ... ''')
    >>> name_field = document.definitions[0].fields[0]
    >>> field = GraphQLField(
    ...     GraphQLString,
    ...     description='The formatted user name.',
    ...     args={
    ...         'format': GraphQLArgument(
    ...             GraphQLString, default=GraphQLDefaultInput('short'))
    ...     },
    ...     resolve=lambda user, _info, format: (
    ...         user['full_name'] if format == 'long' else user['name']),
    ...     deprecation_reason='Use displayName.',
    ...     extensions={'cacheSeconds': 60},
    ...     ast_node=name_field,
    ... )
    >>> field.type
    <GraphQLScalarType 'String'>
    >>> field.args['format'].default.value
    'short'
    >>> field.resolve({'name': 'Luke', 'full_name': 'Luke Skywalker'}, None, 'long')
    'Luke Skywalker'
    >>> field.deprecation_reason
    'Use displayName.'
    >>> field.extensions
    {'cacheSeconds': 60}
    """

    type: GraphQLOutputType
    """The GraphQL type reference or runtime type for this element."""
    args: GraphQLArgumentMap
    """Arguments accepted by this field or directive."""
    resolve: GraphQLFieldResolver | None
    """Resolver function used to produce this field value."""
    subscribe: GraphQLFieldResolver | None
    """Resolver function used to create a subscription event stream for this field."""
    description: str | None
    """Human-readable description for this schema element, if provided."""
    deprecation_reason: str | None
    """Reason this element is deprecated, if one was provided."""
    extensions: dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: FieldDefinitionNode | None
    """AST node from which this schema element was built, if available."""

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

    def __copy__(self) -> GraphQLField:  # pragma: no cover
        return self.__class__(**self.to_kwargs())


def is_field(field: Any) -> TypeGuard[GraphQLField]:
    """Check whether this is a GraphQL field.

    :param field: the value to inspect
    :returns: whether the value is a GraphQLField

    >>> from graphql import build_schema, is_field
    >>> schema = build_schema('type Query { greeting: String }')
    >>> field = schema.query_type.fields['greeting']
    >>> is_field(field)
    True
    >>> is_field(schema.query_type)
    False
    """
    return isinstance(field, GraphQLField)


def assert_field(field: Any) -> GraphQLField:
    """Return the value as a GraphQLField, or raise a TypeError otherwise.

    :param field: the value to inspect
    :returns: the value typed as a GraphQLField

    >>> from graphql import assert_field, build_schema
    >>> schema = build_schema('type Query { greeting: String }')
    >>> field = assert_field(schema.query_type.fields['greeting'])
    >>> field.type
    <GraphQLScalarType 'String'>
    >>> assert_field(schema.query_type)
    Traceback (most recent call last):
    ...
    TypeError: Expected Query to be a GraphQL field.
    """
    if not is_field(field):
        msg = f"Expected {inspect(field)} to be a GraphQL field."
        raise TypeError(msg)
    return field


TContext = TypeVar("TContext")  # pylint: disable=invalid-name


class GraphQLResolveInfoHelpers(NamedTuple):
    """Helpers for resolvers to interact with the execution engine.

    Utilities available from resolver info for tracking asynchronous work.
    """

    gather: Callable[[Sequence[Awaitable[Any]]], Awaitable[list[Any]]]
    """Concurrently await the given values as one unit of asynchronous work.

    When one of the values fails, the others are cancelled and settled before the
    error is propagated, so that no asynchronous work is orphaned.
    This is the counterpart of ``promiseAll`` in GraphQL.js.

    Intended use: return or await the result from resolver work. Un-awaited async
    side effects are an anti-pattern; use :attr:`track` for them instead.
    """
    track: Callable[[Sequence[Any]], None]
    """Track asynchronous work that should delay execution completion.

    Registers possibly awaitable values as pending asynchronous work of the
    execution, so that they are still settled and their errors observed when they
    would otherwise be abandoned.
    """


try:

    class GraphQLResolveInfo(NamedTuple, Generic[TContext]):  # pyright: ignore
        """Collection of information passed to the resolvers.

        Information about the currently executing GraphQL field.
        This is always passed as the second argument to the resolvers.

        Note that contrary to the JavaScript implementation, the context (commonly used
        to represent an authenticated user, or request-specific caches) is included here
        and not passed as an additional argument. The same applies to the abort signal
        which in JavaScript is passed as an additional argument to the resolvers.
        """

        field_name: str
        """The name of the field that is currently being resolved."""
        field_nodes: list[FieldNode]
        """AST field nodes that contributed to the current field execution."""
        return_type: GraphQLOutputType
        """GraphQL output type declared for the current field."""
        parent_type: GraphQLObjectType
        """Object type that owns the current field."""
        path: Path
        """Response path to the field that is currently being resolved."""
        schema: GraphQLSchema
        """The schema used for execution."""
        fragments: dict[str, FragmentDefinitionNode]
        """Fragment definitions in the operation document keyed by fragment name."""
        root_value: Any
        """Initial root value passed to the operation."""
        operation: OperationDefinitionNode
        """The operation selected for execution."""
        variable_values: VariableValues
        """Coerced variable values and source metadata for this operation.

        Resolver code that needs runtime variable values should read
        ``variable_values.coerced``.
        """
        context: TContext
        """The context value passed to the operation.

        This is commonly used to represent an authenticated user, or request-specific
        caches.
        """
        is_awaitable: Callable[[Any], TypeGuard[Awaitable]]
        """Function used to check whether a value is awaitable."""
        abort_signal: AbortSignal | None
        """The abort signal supplied for this execution, if any."""
        async_helpers: GraphQLResolveInfoHelpers
        """Helper functions for tracking asynchronous resolver work."""
except TypeError as error:  # pragma: no cover
    if "Multiple inheritance with NamedTuple is not supported" not in str(error):
        raise  # only catch expected error for Python 3.10

    class GraphQLResolveInfo(NamedTuple):  # type: ignore[no-redef]
        """Collection of information passed to the resolvers.

        Information about the currently executing GraphQL field.
        This is always passed as the second argument to the resolvers.

        Note that contrary to the JavaScript implementation, the context (commonly used
        to represent an authenticated user, or request-specific caches) is included here
        and not passed as an additional argument. The same applies to the abort signal
        which in JavaScript is passed as an additional argument to the resolvers.
        """

        field_name: str
        """The name of the field that is currently being resolved."""
        field_nodes: list[FieldNode]
        """AST field nodes that contributed to the current field execution."""
        return_type: GraphQLOutputType
        """GraphQL output type declared for the current field."""
        parent_type: GraphQLObjectType
        """Object type that owns the current field."""
        path: Path
        """Response path to the field that is currently being resolved."""
        schema: GraphQLSchema
        """The schema used for execution."""
        fragments: dict[str, FragmentDefinitionNode]
        """Fragment definitions in the operation document keyed by fragment name."""
        root_value: Any
        """Initial root value passed to the operation."""
        operation: OperationDefinitionNode
        """The operation selected for execution."""
        variable_values: VariableValues
        """Coerced variable values and source metadata for this operation.

        Resolver code that needs runtime variable values should read
        ``variable_values.coerced``.
        """
        context: Any
        """The context value passed to the operation.

        This is commonly used to represent an authenticated user, or request-specific
        caches.
        """
        is_awaitable: Callable[[Any], TypeGuard[Awaitable]]
        """Function used to check whether a value is awaitable."""
        abort_signal: AbortSignal | None
        """The abort signal supplied for this execution, if any."""
        async_helpers: GraphQLResolveInfoHelpers
        """Helper functions for tracking asynchronous resolver work."""


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
    AwaitableOrValue[str | None],
]

# Note: Contrary to the Javascript implementation of GraphQLIsTypeOfFn,
# the context is passed as part of the GraphQLResolveInfo:
GraphQLIsTypeOfFn: TypeAlias = Callable[
    [Any, GraphQLResolveInfo], AwaitableOrValue[bool]
]

GraphQLFieldMap: TypeAlias = dict[str, GraphQLField]


class GraphQLDefaultInput:  # noqa: PLW1641
    """A default value, preserved either as a coerced value or as a literal.

    Default values can be provided either as already coerced Python values or as
    GraphQL literals (AST nodes). Preserving the original literal allows it to be
    printed back without a lossy round-trip through coercion (see `GraphQL.js issue
    #3051 <https://github.com/graphql/graphql-js/issues/3051>`_).
    Exactly one of ``value`` or ``literal`` is set; the other is left undefined.

    Here ``value`` is the *external* default value (it will be coerced), while the
    deprecated ``default_value`` config option of arguments and input fields holds
    the *internal* (already coerced) value.

    :param value: the runtime default value, if provided
    :param literal: the GraphQL literal default value, if provided

    >>> from graphql import GraphQLDefaultInput, parse_const_value, print_ast
    >>> default = GraphQLDefaultInput(['en', 'de'])
    >>> default.value
    ['en', 'de']
    >>> default = GraphQLDefaultInput(literal=parse_const_value('{ lang: "en" }'))
    >>> print_ast(default.literal)
    '{ lang: "en" }'
    """

    value: Any
    """Runtime default value, or Undefined if a literal is provided instead."""
    literal: ConstValueNode | None
    """GraphQL literal default value, or None if a runtime value is provided instead."""

    __slots__ = "_memoized_coerced_value", "literal", "value"

    def __init__(
        self, value: Any = Undefined, literal: ConstValueNode | None = None
    ) -> None:
        self.value = value
        self.literal = literal
        # Used to memoize the result of coercing the default value (see
        # coerce_default_value() in the utilities).
        self._memoized_coerced_value: Any = Undefined

    def __eq__(self, other: object) -> bool:
        return self is other or (
            isinstance(other, GraphQLDefaultInput)
            and self.value == other.value
            and self.literal == other.literal
        )


class GraphQLArgumentKwargs(TypedDict, total=False):
    """Python arguments for GraphQL arguments"""

    type_: GraphQLInputType
    """The GraphQL type reference or runtime type for this element."""
    default_value: Any
    """Legacy default value for this argument.

    .. deprecated:: 3.3
        Use ``default`` instead. ``default_value`` will be removed in a future
        version.
    """
    default: GraphQLDefaultInput | None
    """Default value represented as either a runtime value or a GraphQL literal."""
    description: str | None
    """Human-readable description for this schema element, if provided."""
    deprecation_reason: str | None
    """Reason this element is deprecated, if one was provided."""
    out_name: str | None
    """Name of the Python keyword argument (extension of GraphQL.js)."""
    extensions: dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: InputValueDefinitionNode | None
    """AST node from which this schema element was built, if available."""


class GraphQLArgument:  # noqa: PLW1641
    """Definition of a GraphQL argument

    :param type_: the GraphQL input type of this argument
    :param default_value: legacy internal (already coerced) default value used when
        no explicit value is supplied; deprecated, use ``default`` instead
    :param description: human-readable description for this argument, if provided
    :param deprecation_reason: reason this argument is deprecated, if one was
        provided
    :param out_name: name of the Python keyword argument passed to the resolver,
        if different from the argument name (extension of GraphQL.js)
    :param extensions: custom extensions for this argument
    :param ast_node: AST node from which this argument was built, if available
    :param default: default value represented as either a runtime value or a
        GraphQL literal

    >>> from graphql import (
    ...     GraphQLArgument, GraphQLDefaultInput, GraphQLField, GraphQLString)
    >>> arg = GraphQLArgument(GraphQLString, default=GraphQLDefaultInput('world'))
    >>> field = GraphQLField(GraphQLString, args={'name': arg})
    >>> field.args['name'] is arg
    True
    >>> arg.default.value
    'world'
    """

    type: GraphQLInputType
    """The GraphQL type reference or runtime type for this element."""
    default_value: Any
    """Legacy default value used when no explicit value is supplied.

    This is the internal (already coerced) default value, or Undefined.

    .. deprecated:: 3.3
        Use ``default`` instead. ``default_value`` will be removed in a future
        version.
    """
    default: GraphQLDefaultInput | None
    """Default value represented as either a runtime value or a GraphQL literal."""
    description: str | None
    """Human-readable description for this schema element, if provided."""
    deprecation_reason: str | None
    """Reason this element is deprecated, if one was provided."""
    out_name: str | None
    """Name of the Python keyword argument (extension of GraphQL.js).

    Used for transforming names; if not set, the argument name is used.
    """
    extensions: dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: InputValueDefinitionNode | None
    """AST node from which this schema element was built, if available."""

    def __init__(
        self,
        type_: GraphQLInputType,
        default_value: Any = Undefined,
        description: str | None = None,
        deprecation_reason: str | None = None,
        out_name: str | None = None,
        extensions: dict[str, Any] | None = None,
        ast_node: InputValueDefinitionNode | None = None,
        default: GraphQLDefaultInput | None = None,
    ) -> None:
        # Note: ``default_value`` is deprecated in favor of ``default`` and will be
        # removed in the next major version. It holds the internal default value,
        # while ``default`` holds the external one (see GraphQLDefaultInput).
        self.type = type_
        self.default_value = default_value
        self.default = default
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
            and self.default == other.default
            and self.description == other.description
            and self.deprecation_reason == other.deprecation_reason
            and self.out_name == other.out_name
            and self.extensions == other.extensions
        )

    def to_kwargs(self) -> GraphQLArgumentKwargs:
        """Get the keyword arguments that can be used to recreate this argument.

        :returns: a dictionary with the constructor arguments for this argument

        >>> from graphql import GraphQLArgument, GraphQLDefaultInput, GraphQLInt
        >>> arg = GraphQLArgument(GraphQLInt, default=GraphQLDefaultInput(10))
        >>> kwargs = arg.to_kwargs()
        >>> kwargs['type_'], kwargs['default'].value
        (<GraphQLScalarType 'Int'>, 10)
        >>> GraphQLArgument(**kwargs) == arg
        True
        """
        return GraphQLArgumentKwargs(
            type_=self.type,
            default_value=self.default_value,
            default=self.default,
            description=self.description,
            deprecation_reason=self.deprecation_reason,
            out_name=self.out_name,
            extensions=self.extensions,
            ast_node=self.ast_node,
        )

    def __copy__(self) -> GraphQLArgument:  # pragma: no cover
        return self.__class__(**self.to_kwargs())


def is_argument(arg: Any) -> TypeGuard[GraphQLArgument]:
    """Check whether this is a GraphQL argument.

    :param arg: the value to inspect
    :returns: whether the value is a GraphQLArgument

    >>> from graphql import build_schema, is_argument
    >>> schema = build_schema('type Query { greeting(name: String): String }')
    >>> arg = schema.query_type.fields['greeting'].args['name']
    >>> is_argument(arg)
    True
    >>> is_argument(schema.query_type)
    False
    """
    return isinstance(arg, GraphQLArgument)


def assert_argument(arg: Any) -> GraphQLArgument:
    """Return the value as a GraphQLArgument, or raise a TypeError otherwise.

    :param arg: the value to inspect
    :returns: the value typed as a GraphQLArgument

    >>> from graphql import assert_argument, build_schema
    >>> schema = build_schema('type Query { greeting(name: String): String }')
    >>> arg = assert_argument(schema.query_type.fields['greeting'].args['name'])
    >>> arg.type
    <GraphQLScalarType 'String'>
    >>> assert_argument(schema.query_type)
    Traceback (most recent call last):
    ...
    TypeError: Expected Query to be a GraphQL argument.
    """
    if not is_argument(arg):
        msg = f"Expected {inspect(arg)} to be a GraphQL argument."
        raise TypeError(msg)
    return arg


def is_required_argument(
    arg: GraphQLArgument | GraphQLVariableSignature,
) -> bool:
    """Check whether the argument is non-null and has no default value.

    :param arg: the argument definition to inspect
    :returns: whether the argument is non-null and has no default value

    >>> from graphql import (
    ...     GraphQLArgument, GraphQLDefaultInput, GraphQLInt, GraphQLNonNull,
    ...     GraphQLString, is_required_argument)
    >>> required_argument = GraphQLArgument(GraphQLNonNull(GraphQLInt))
    >>> optional_argument = GraphQLArgument(GraphQLString)
    >>> argument_with_default = GraphQLArgument(
    ...     GraphQLNonNull(GraphQLInt), default=GraphQLDefaultInput(10))
    >>> is_required_argument(required_argument)
    True
    >>> is_required_argument(optional_argument)
    False
    >>> is_required_argument(argument_with_default)
    False
    """
    return (
        is_non_null_type(arg.type)
        and arg.default is None
        and arg.default_value is Undefined
    )


class GraphQLObjectTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    """Arguments for GraphQL object types"""

    fields: GraphQLFieldMap
    """Fields declared by this object, interface, input object, or literal."""
    interfaces: tuple[GraphQLInterfaceType, ...]
    """Interfaces implemented by this object or interface type."""
    is_type_of: GraphQLIsTypeOfFn | None
    """Predicate used to determine whether a runtime value belongs to this type."""


class GraphQLObjectType(GraphQLNamedType):
    """Object Type Definition

    Almost all of the GraphQL types you define will be object types. Object types have
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
    ...     GraphQLArgument, GraphQLDefaultInput, GraphQLField, GraphQLID,
    ...     GraphQLInterfaceType, GraphQLNonNull, GraphQLObjectType, GraphQLString,
    ...     parse)
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
    ...                     default=GraphQLDefaultInput('short'),
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
    >>> user_type.fields['name'].args['format'].default.value
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

    is_type_of: GraphQLIsTypeOfFn | None
    """Predicate used to determine whether a runtime value belongs to this type."""
    ast_node: ObjectTypeDefinitionNode | None
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: tuple[ObjectTypeExtensionNode, ...]
    """AST extension nodes applied to this schema element."""

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
            interfaces: Collection[GraphQLInterfaceType] = resolve_thunk(
                self._interfaces  # type: ignore
            )
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            msg = f"{self.name} interfaces cannot be resolved. {error}"
            raise cls(msg) from error
        return tuple(interfaces) if interfaces else ()


def is_object_type(type_: Any) -> TypeGuard[GraphQLObjectType]:
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
        msg = f"Expected {type_} to be a GraphQL Object type."
        raise TypeError(msg)
    return type_


class GraphQLInterfaceTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    """Arguments for GraphQL interface types"""

    fields: GraphQLFieldMap
    """Fields declared by this object, interface, input object, or literal."""
    interfaces: tuple[GraphQLInterfaceType, ...]
    """Interfaces implemented by this object or interface type."""
    resolve_type: GraphQLTypeResolver | None
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

    resolve_type: GraphQLTypeResolver | None
    """Function that resolves the concrete object type for this abstract type."""
    ast_node: InterfaceTypeDefinitionNode | None
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: tuple[InterfaceTypeExtensionNode, ...]
    """AST extension nodes applied to this schema element."""

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
            interfaces: Collection[GraphQLInterfaceType] = resolve_thunk(
                self._interfaces  # type: ignore
            )
        except Exception as error:
            cls = GraphQLError if isinstance(error, GraphQLError) else TypeError
            msg = f"{self.name} interfaces cannot be resolved. {error}"
            raise cls(msg) from error
        return tuple(interfaces) if interfaces else ()


def is_interface_type(type_: Any) -> TypeGuard[GraphQLInterfaceType]:
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
        msg = f"Expected {type_} to be a GraphQL Interface type."
        raise TypeError(msg)
    return type_


class GraphQLUnionTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    """Arguments for GraphQL union types"""

    types: tuple[GraphQLObjectType, ...]
    """Object types that belong to this union type."""
    resolve_type: GraphQLTypeResolver | None
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

    resolve_type: GraphQLTypeResolver | None
    """Function that resolves the concrete object type for this abstract type."""
    ast_node: UnionTypeDefinitionNode | None
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: tuple[UnionTypeExtensionNode, ...]
    """AST extension nodes applied to this schema element."""

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
        return GraphQLUnionTypeKwargs(
            super().to_kwargs(),  # type: ignore
            types=self.types,
            resolve_type=self.resolve_type,
        )

    def __copy__(self) -> GraphQLUnionType:  # pragma: no cover
        return self.__class__(**self.to_kwargs())

    @cached_property
    def types(self) -> tuple[GraphQLObjectType, ...]:
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
            msg = f"{self.name} types cannot be resolved. {error}"
            raise cls(msg) from error
        return tuple(types) if types else ()


def is_union_type(type_: Any) -> TypeGuard[GraphQLUnionType]:
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
        msg = f"Expected {type_} to be a GraphQL Union type."
        raise TypeError(msg)
    return type_


GraphQLEnumValueMap: TypeAlias = dict[str, "GraphQLEnumValue"]

GraphQLEnumValuesDefinition: TypeAlias = (
    GraphQLEnumValueMap | Mapping[str, Any] | type[Enum]
)


class GraphQLEnumTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    """Arguments for GraphQL enum types"""

    values: GraphQLEnumValueMap
    """Values contained in this enum, list, or input-object definition."""
    names_as_values: bool | None
    """What to use as internal values when the values are given as a Python Enum.

    ``False`` uses the enum values, ``True`` the enum names, and ``None`` the enum
    members themselves (extension of GraphQL.js).
    """


class GraphQLEnumType(GraphQLNamedType):
    """Enum Type Definition

    Enum types define leaf values whose serialized form is one of a fixed set of
    GraphQL enum names. Internally, enum values can map to any runtime value, often
    integers. They can also be provided as a Python Enum. In this case, the flag
    ``names_as_values`` determines what will be used as internal representation. The
    default value of ``False`` will use the enum values, the value ``True`` will use
    the enum names, and the value ``None`` will use the members themselves.

    >>> from graphql import GraphQLEnumType
    >>> rgb_type = GraphQLEnumType('RGB', {'RED': 0, 'GREEN': 1, 'BLUE': 2})
    >>> rgb_type.values['GREEN'].value
    1

    Instead of raw values, you can also specify GraphQLEnumValue objects with more
    detail like description or deprecation information.

    Note: If a value is not provided in a definition, the name of the enum value will
    be used as its internal value.

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
    >>> episode_type.coerce_output_value(5)
    'EMPIRE'
    >>> episode_type.coerce_input_value('JEDI')
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
    >>> GraphQLEnumType('RGB', RGBEnum).coerce_input_value('GREEN')
    1
    >>> GraphQLEnumType(
    ...     'RGB', RGBEnum, names_as_values=True).coerce_input_value('GREEN')
    'GREEN'
    >>> GraphQLEnumType(
    ...     'RGB', RGBEnum, names_as_values=None).coerce_input_value('GREEN')
    <RGBEnum.GREEN: 1>
    """

    ast_node: EnumTypeDefinitionNode | None
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: tuple[EnumTypeExtensionNode, ...]
    """AST extension nodes applied to this schema element."""

    def __init__(
        self,
        name: str,
        values: Thunk[GraphQLEnumValuesDefinition],
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
        self._values = values
        self._names_as_values = names_as_values

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
        return GraphQLEnumTypeKwargs(
            super().to_kwargs(),  # type: ignore
            values=self.values.copy(),
        )

    def __copy__(self) -> GraphQLEnumType:  # pragma: no cover
        return self.__class__(**self.to_kwargs())

    @cached_property
    def values(self) -> GraphQLEnumValueMap:
        """Get provided values, wrapping them as GraphQLEnumValues if needed.

        :returns: the enum value definitions keyed by value name, in schema order

        >>> from graphql import assert_enum_type, build_schema
        >>> schema = build_schema('''
        ...     enum Episode {
        ...       NEW_HOPE
        ...       EMPIRE
        ...       JEDI
        ...     }
        ...
        ...     type Query {
        ...       episode: Episode
        ...     }
        ... ''')
        >>> episode_type = assert_enum_type(schema.get_type('Episode'))
        >>> list(episode_type.values)
        ['NEW_HOPE', 'EMPIRE', 'JEDI']
        >>> episode_type.values.get('JEDI') is not None
        True
        >>> episode_type.values.get('FORCE_AWAKENS') is None
        True
        """
        values = self._values
        names_as_values = self._names_as_values
        if not isinstance(values, type):
            values = resolve_thunk(values)  # type: ignore
        try:  # check for enum
            values = cast("Enum", values).__members__  # type: ignore
        except AttributeError:
            if not isinstance(values, Mapping) or not all(
                isinstance(name, str) for name in values
            ):
                try:
                    values = dict(values)  # type: ignore
                except (TypeError, ValueError) as error:
                    msg = (
                        f"{self.name} values must be an Enum or a mapping"
                        " with value names as keys."
                    )
                    raise TypeError(msg) from error
            values = cast("dict[str, Any]", values)
        else:
            values = cast("dict[str, Enum]", values)
            if names_as_values is False:
                values = {key: value.value for key, value in values.items()}
            elif names_as_values is True:
                values = {key: key for key in values}
        return {
            assert_enum_value_name(key): value
            if isinstance(value, GraphQLEnumValue)
            else GraphQLEnumValue(value)
            for key, value in values.items()
        }

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
        """Serialize a runtime enum value as a GraphQL enum name.

        .. deprecated:: 3.3
            Use ``coerce_output_value()`` instead. ``serialize()`` will be removed
            in a future version.

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
        return self.coerce_output_value(output_value)

    def coerce_output_value(self, output_value: Any) -> str:
        """Coerce a runtime enum value to a GraphQL enum name.

        :param output_value: runtime enum value to coerce
        :returns: the GraphQL enum name for the runtime value

        >>> from graphql import GraphQLEnumType
        >>> rgb_type = GraphQLEnumType('RGB', {'RED': 0, 'GREEN': 1, 'BLUE': 2})
        >>> rgb_type.coerce_output_value(1)
        'GREEN'
        >>> rgb_type.coerce_output_value(3)
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
        msg = f"Enum '{self.name}' cannot represent value: {inspect(output_value)}"
        raise GraphQLError(msg)

    def parse_value(self, input_value: str, hide_suggestions: bool = False) -> Any:
        """Parse an enum value.

        Legacy enum parser for externally provided input values.

        .. deprecated:: 3.3
            Use ``coerce_input_value()`` instead. ``parse_value()`` will be removed
            in a future version.

        :param input_value: external enum name to parse
        :param hide_suggestions: whether suggestion text should be omitted from errors
        :returns: the internal runtime value for the enum name

        >>> from graphql import GraphQLEnumType
        >>> rgb_type = GraphQLEnumType('RGB', {'RED': 0, 'GREEN': 1, 'BLUE': 2})
        >>> rgb_type.parse_value('BLUE')
        2
        >>> rgb_type.parse_value('PURPLE', True)
        Traceback (most recent call last):
        ...
        graphql.error.graphql_error.GraphQLError: Value 'PURPLE' does not exist ...
        """
        return self.coerce_input_value(input_value, hide_suggestions)

    def coerce_input_value(
        self, input_value: str, hide_suggestions: bool = False
    ) -> Any:
        """Coerce an external enum name to its internal runtime value.

        :param input_value: external enum name to coerce
        :param hide_suggestions: whether suggestion text should be omitted from errors
        :returns: the internal runtime value for the enum name

        >>> from graphql import GraphQLEnumType
        >>> rgb_type = GraphQLEnumType('RGB', {'RED': 0, 'GREEN': 1, 'BLUE': 2})
        >>> rgb_type.coerce_input_value('BLUE')
        2
        >>> rgb_type.coerce_input_value('PURPLE')
        Traceback (most recent call last):
        ...
        graphql.error.graphql_error.GraphQLError: Value 'PURPLE' does not exist ...
        >>> rgb_type.coerce_input_value(2)
        Traceback (most recent call last):
        ...
        graphql.error.graphql_error.GraphQLError: Enum 'RGB' cannot represent ...
        """
        if isinstance(input_value, str):
            try:
                enum_value = self.values[input_value]
            except KeyError as error:
                msg = f"Value '{input_value}' does not exist in '{self.name}' enum." + (
                    ""
                    if hide_suggestions
                    else did_you_mean_enum_value(self, input_value)
                )
                raise GraphQLError(msg) from error
            return enum_value.value
        value_str = inspect(input_value)
        msg = f"Enum '{self.name}' cannot represent non-string value: {value_str}." + (
            "" if hide_suggestions else did_you_mean_enum_value(self, value_str)
        )
        raise GraphQLError(msg)

    def parse_literal(
        self,
        value_node: ValueNode,
        _variables: dict[str, Any] | None = None,
        hide_suggestions: bool = False,
    ) -> Any:
        """Parse literal value.

        Legacy enum parser for externally provided input literals.

        .. deprecated:: 3.3
            Use ``coerce_input_literal()`` instead. ``parse_literal()`` will be
            removed in a future version.

        :param value_node: enum value AST node to parse
        :param _variables: deprecated variable values parameter that is no longer used
        :param hide_suggestions: whether suggestion text should be omitted from errors
        :returns: the internal runtime value for the enum literal

        >>> from graphql import GraphQLEnumType, parse_value
        >>> rgb_type = GraphQLEnumType('RGB', {'RED': 0, 'GREEN': 1, 'BLUE': 2})
        >>> rgb_type.parse_literal(parse_value('RED'))
        0
        >>> rgb_type.parse_literal(parse_value('"RED"'))
        Traceback (most recent call last):
        ...
        graphql.error.graphql_error.GraphQLError: Enum 'RGB' cannot represent ...
        """
        # Note: variables will be resolved before calling this method.
        return self.coerce_input_literal(
            cast("ConstValueNode", value_node), hide_suggestions
        )

    def coerce_input_literal(
        self, value_node: ConstValueNode, hide_suggestions: bool = False
    ) -> Any:
        """Coerce an enum value AST node to its internal runtime value.

        :param value_node: enum value AST node to coerce
        :param hide_suggestions: whether suggestion text should be omitted from errors
        :returns: the internal runtime value for the enum literal

        >>> from graphql import GraphQLEnumType, parse_const_value
        >>> rgb_type = GraphQLEnumType('RGB', {'RED': 0, 'GREEN': 1, 'BLUE': 2})
        >>> rgb_type.coerce_input_literal(parse_const_value('RED'))
        0
        >>> rgb_type.coerce_input_literal(parse_const_value('"RED"'), True)
        Traceback (most recent call last):
        ...
        graphql.error.graphql_error.GraphQLError: Enum 'RGB' cannot represent ...
        """
        if isinstance(value_node, EnumValueNode):
            try:
                enum_value = self.values[value_node.value]
            except KeyError as error:
                value_str = print_ast(value_node)
                msg = f"Value '{value_str}' does not exist in '{self.name}' enum." + (
                    "" if hide_suggestions else did_you_mean_enum_value(self, value_str)
                )
                raise GraphQLError(msg, value_node) from error
            return enum_value.value
        value_str = print_ast(value_node)
        msg = f"Enum '{self.name}' cannot represent non-enum value: {value_str}." + (
            "" if hide_suggestions else did_you_mean_enum_value(self, value_str)
        )
        raise GraphQLError(msg, value_node)

    def value_to_literal(self, value: Any) -> ConstValueNode | None:
        """Convert an external enum value to a GraphQL enum value AST node.

        :param value: external enum value (the enum name) to convert
        :returns: enum value AST node, or None if the value is invalid

        >>> from graphql import GraphQLEnumType, print_ast
        >>> rgb_type = GraphQLEnumType('RGB', {'RED': 0, 'GREEN': 1, 'BLUE': 2})
        >>> print_ast(rgb_type.value_to_literal('BLUE'))
        'BLUE'
        >>> rgb_type.value_to_literal(3) is None
        True
        """
        if isinstance(value, str) and self.values.get(value):
            return EnumValueNode(value=value)
        return None


def is_enum_type(type_: Any) -> TypeGuard[GraphQLEnumType]:
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
    """Internal value represented by this enum value."""
    description: str | None
    """Human-readable description for this schema element, if provided."""
    deprecation_reason: str | None
    """Reason this element is deprecated, if one was provided."""
    extensions: dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: EnumValueDefinitionNode | None
    """AST node from which this schema element was built, if available."""


class GraphQLEnumValue:  # noqa: PLW1641
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
    description: str | None
    """Human-readable description for this schema element, if provided."""
    deprecation_reason: str | None
    """Reason this element is deprecated, if one was provided."""
    extensions: dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: EnumValueDefinitionNode | None
    """AST node from which this schema element was built, if available."""

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

    def __copy__(self) -> GraphQLEnumValue:  # pragma: no cover
        return self.__class__(**self.to_kwargs())


def is_enum_value(value: Any) -> TypeGuard[GraphQLEnumValue]:
    """Check whether this is a GraphQL enum value.

    :param value: the value to inspect
    :returns: whether the value is a GraphQLEnumValue

    >>> from graphql import assert_enum_type, build_schema, is_enum_value
    >>> schema = build_schema(
    ...     'enum Episode { NEW_HOPE } type Query { episode: Episode }')
    >>> enum_value = assert_enum_type(schema.get_type('Episode')).values['NEW_HOPE']
    >>> is_enum_value(enum_value)
    True
    >>> is_enum_value(schema.get_type('Episode'))
    False
    """
    return isinstance(value, GraphQLEnumValue)


def assert_enum_value(value: Any) -> GraphQLEnumValue:
    """Return the value as a GraphQLEnumValue, or raise a TypeError otherwise.

    :param value: the value to inspect
    :returns: the value typed as a GraphQLEnumValue

    >>> from graphql import assert_enum_type, assert_enum_value, build_schema
    >>> schema = build_schema(
    ...     'enum Episode { NEW_HOPE } type Query { episode: Episode }')
    >>> enum_value = assert_enum_value(
    ...     assert_enum_type(schema.get_type('Episode')).values['NEW_HOPE'])
    >>> enum_value.value
    'NEW_HOPE'
    >>> assert_enum_value(schema.get_type('Episode'))
    Traceback (most recent call last):
    ...
    TypeError: Expected Episode to be a GraphQL Enum value.
    """
    if not is_enum_value(value):
        msg = f"Expected {inspect(value)} to be a GraphQL Enum value."
        raise TypeError(msg)
    return value


GraphQLInputFieldMap: TypeAlias = dict[str, "GraphQLInputField"]
GraphQLInputFieldOutType = Callable[[dict[str, Any]], Any]


class GraphQLInputObjectTypeKwargs(GraphQLNamedTypeKwargs, total=False):
    """Arguments for GraphQL input object types"""

    fields: GraphQLInputFieldMap
    """Fields declared by this object, interface, input object, or literal."""
    out_type: GraphQLInputFieldOutType | None
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
            'alt': GraphQLInputField(GraphQLFloat, default=GraphQLDefaultInput(0)),
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
    ...     GraphQLDefaultInput, GraphQLID, GraphQLInputField, GraphQLInputObjectType,
    ...     GraphQLInt, GraphQLNonNull, GraphQLString, parse)
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
    ...             default=GraphQLDefaultInput(''),
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
    >>> fields['commentary'].default.value
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

    ast_node: InputObjectTypeDefinitionNode | None
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: tuple[InputObjectTypeExtensionNode, ...]
    """AST extension nodes applied to this schema element."""
    is_one_of: bool
    """Whether this input object uses the experimental OneOf input object semantics."""

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
        """Get provided fields, wrap them as GraphQLInputField if needed.

        :returns: the fields keyed by field name

        >>> from graphql import assert_input_object_type, build_schema, print_ast
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
        >>> print_ast(fields['commentary'].default.literal)
        '""'
        """
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
        msg = f"Expected {type_} to be a GraphQL Input Object type."
        raise TypeError(msg)
    return type_


class GraphQLInputFieldKwargs(TypedDict, total=False):
    """Arguments for GraphQL input fields"""

    type_: GraphQLInputType
    """The GraphQL type reference or runtime type for this element."""
    default_value: Any
    """Legacy default value for this input field.

    .. deprecated:: 3.3
        Use ``default`` instead. ``default_value`` will be removed in a future
        version.
    """
    default: GraphQLDefaultInput | None
    """Default value represented as either a runtime value or a GraphQL literal."""
    description: str | None
    """Human-readable description for this schema element, if provided."""
    deprecation_reason: str | None
    """Reason this element is deprecated, if one was provided."""
    out_name: str | None
    """Name of the key in the outbound value (extension of GraphQL.js)."""
    extensions: dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: InputValueDefinitionNode | None
    """AST node from which this schema element was built, if available."""


class GraphQLInputField:  # noqa: PLW1641
    """Definition of a GraphQL input field

    :param type_: the GraphQL input type of this input field
    :param default_value: legacy internal (already coerced) default value used when
        no explicit value is supplied; deprecated, use ``default`` instead
    :param description: human-readable description for this input field, if
        provided
    :param deprecation_reason: reason this input field is deprecated, if one was
        provided
    :param out_name: name of the key in the outbound value, if different from the
        field name (extension of GraphQL.js)
    :param extensions: custom extensions for this input field
    :param ast_node: AST node from which this input field was built, if available
    :param default: default value represented as either a runtime value or a
        GraphQL literal

    >>> from graphql import (
    ...     GraphQLDefaultInput, GraphQLInputField, GraphQLInputObjectType,
    ...     GraphQLString)
    >>> field = GraphQLInputField(GraphQLString, default=GraphQLDefaultInput(''))
    >>> review_input_type = GraphQLInputObjectType(
    ...     'ReviewInput', {'commentary': field})
    >>> review_input_type.fields['commentary'] is field
    True
    >>> field.default.value
    ''
    """

    type: GraphQLInputType
    """The GraphQL type reference or runtime type for this element."""
    default_value: Any
    """Legacy default value used when no explicit value is supplied.

    This is the internal (already coerced) default value, or Undefined.

    .. deprecated:: 3.3
        Use ``default`` instead. ``default_value`` will be removed in a future
        version.
    """
    default: GraphQLDefaultInput | None
    """Default value represented as either a runtime value or a GraphQL literal."""
    description: str | None
    """Human-readable description for this schema element, if provided."""
    deprecation_reason: str | None
    """Reason this element is deprecated, if one was provided."""
    out_name: str | None
    """Name of the key in the outbound value (extension of GraphQL.js).

    Used for transforming names; if not set, the field name is used.
    """
    extensions: dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: InputValueDefinitionNode | None
    """AST node from which this schema element was built, if available."""

    def __init__(
        self,
        type_: GraphQLInputType,
        default_value: Any = Undefined,
        description: str | None = None,
        deprecation_reason: str | None = None,
        out_name: str | None = None,
        extensions: dict[str, Any] | None = None,
        ast_node: InputValueDefinitionNode | None = None,
        default: GraphQLDefaultInput | None = None,
    ) -> None:
        # Note: ``default_value`` is deprecated in favor of ``default`` and will be
        # removed in the next major version. It holds the internal default value,
        # while ``default`` holds the external one (see GraphQLDefaultInput).
        self.type = type_
        self.default_value = default_value
        self.default = default
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
            and self.default == other.default
            and self.description == other.description
            and self.deprecation_reason == other.deprecation_reason
            and self.extensions == other.extensions
            and self.out_name == other.out_name
        )

    def to_kwargs(self) -> GraphQLInputFieldKwargs:
        """Get the keyword arguments that can be used to recreate this input field.

        :returns: a dictionary with the constructor arguments for this input field

        >>> from graphql import GraphQLDefaultInput, GraphQLInputField, GraphQLString
        >>> field = GraphQLInputField(GraphQLString, default=GraphQLDefaultInput(''))
        >>> kwargs = field.to_kwargs()
        >>> kwargs['type_'], kwargs['default'].value
        (<GraphQLScalarType 'String'>, '')
        >>> GraphQLInputField(**kwargs) == field
        True
        """
        return GraphQLInputFieldKwargs(
            type_=self.type,
            default_value=self.default_value,
            default=self.default,
            description=self.description,
            deprecation_reason=self.deprecation_reason,
            out_name=self.out_name,
            extensions=self.extensions,
            ast_node=self.ast_node,
        )

    def __copy__(self) -> GraphQLInputField:  # pragma: no cover
        return self.__class__(**self.to_kwargs())


def is_input_field(field: Any) -> TypeGuard[GraphQLInputField]:
    """Check whether this is a GraphQL input field.

    :param field: the value to inspect
    :returns: whether the value is a GraphQLInputField

    >>> from graphql import assert_input_object_type, build_schema, is_input_field
    >>> schema = build_schema(
    ...     'input ReviewInput { stars: Int } type Query { ok: Boolean }')
    >>> input_field = assert_input_object_type(
    ...     schema.get_type('ReviewInput')).fields['stars']
    >>> is_input_field(input_field)
    True
    >>> is_input_field(schema.query_type)
    False
    """
    return isinstance(field, GraphQLInputField)


def assert_input_field(field: Any) -> GraphQLInputField:
    """Return the value as a GraphQLInputField, or raise a TypeError otherwise.

    :param field: the value to inspect
    :returns: the value typed as a GraphQLInputField

    >>> from graphql import (
    ...     assert_input_field, assert_input_object_type, build_schema)
    >>> schema = build_schema(
    ...     'input ReviewInput { stars: Int } type Query { ok: Boolean }')
    >>> input_field = assert_input_field(
    ...     assert_input_object_type(schema.get_type('ReviewInput')).fields['stars'])
    >>> input_field.type
    <GraphQLScalarType 'Int'>
    >>> assert_input_field(schema.query_type)
    Traceback (most recent call last):
    ...
    TypeError: Expected Query to be a GraphQL input field.
    """
    if not is_input_field(field):
        msg = f"Expected {inspect(field)} to be a GraphQL input field."
        raise TypeError(msg)
    return field


def is_required_input_field(field: GraphQLInputField) -> bool:
    """Check whether the input field is non-null and has no default value.

    :param field: the input field definition to inspect
    :returns: whether the input field is non-null and has no default value

    >>> from graphql import (
    ...     GraphQLDefaultInput, GraphQLInputField, GraphQLInt, GraphQLNonNull,
    ...     GraphQLString, is_required_input_field)
    >>> required_field = GraphQLInputField(GraphQLNonNull(GraphQLInt))
    >>> optional_field = GraphQLInputField(GraphQLString)
    >>> field_with_default = GraphQLInputField(
    ...     GraphQLNonNull(GraphQLInt), default=GraphQLDefaultInput(10))
    >>> is_required_input_field(required_field)
    True
    >>> is_required_input_field(optional_field)
    False
    >>> is_required_input_field(field_with_default)
    False
    """
    return (
        is_non_null_type(field.type)
        and field.default is None
        and field.default_value is Undefined
    )


# Wrapper types


class GraphQLList(GraphQLWrappingType[GT_co]):
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

    def __init__(self, type_: GT_co) -> None:
        super().__init__(type_=type_)

    def __str__(self) -> str:
        return f"[{self.of_type}]"


def is_list_type(type_: Any) -> TypeGuard[GraphQLList]:
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

    def __init__(self, type_: GNT_co) -> None:
        super().__init__(type_=type_)

    def __str__(self) -> str:
        return f"{self.of_type}!"


# These types can all accept null as a value.

GraphQLNullableType: TypeAlias = (
    GraphQLScalarType
    | GraphQLObjectType
    | GraphQLInterfaceType
    | GraphQLUnionType
    | GraphQLEnumType
    | GraphQLInputObjectType
    | GraphQLList
)

# These types may be used as input types for arguments and directives.

GraphQLNullableInputType: TypeAlias = (
    GraphQLScalarType | GraphQLEnumType | GraphQLInputObjectType | GraphQLList
)

GraphQLInputType: TypeAlias = (
    GraphQLNullableInputType | GraphQLNonNull[GraphQLNullableInputType]
)

# These types may be used as output types as the result of fields.

GraphQLNullableOutputType: TypeAlias = (
    GraphQLScalarType
    | GraphQLObjectType
    | GraphQLInterfaceType
    | GraphQLUnionType
    | GraphQLEnumType
    | GraphQLList
)

GraphQLOutputType: TypeAlias = (
    GraphQLNullableOutputType | GraphQLNonNull[GraphQLNullableOutputType]
)


# Predicates and Assertions


def is_input_type(type_: Any) -> TypeGuard[GraphQLInputType]:
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
    return isinstance(
        type_, (GraphQLScalarType, GraphQLEnumType, GraphQLInputObjectType)
    ) or (isinstance(type_, GraphQLWrappingType) and is_input_type(type_.of_type))


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
        msg = f"Expected {type_} to be a GraphQL input type."
        raise TypeError(msg)
    return type_


def is_output_type(type_: Any) -> TypeGuard[GraphQLOutputType]:
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
        msg = f"Expected {type_} to be a GraphQL output type."
        raise TypeError(msg)
    return type_


def is_non_null_type(type_: Any) -> TypeGuard[GraphQLNonNull]:
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
        msg = f"Expected {type_} to be a GraphQL Non-Null type."
        raise TypeError(msg)
    return type_


def is_nullable_type(type_: Any) -> TypeGuard[GraphQLNullableType]:
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
        type_ = type_.of_type
    return cast("GraphQLNullableType | None", type_)


# These named types do not include modifiers like List or NonNull.

GraphQLNamedInputType: TypeAlias = (
    GraphQLScalarType | GraphQLEnumType | GraphQLInputObjectType
)

GraphQLNamedOutputType: TypeAlias = (
    GraphQLScalarType
    | GraphQLObjectType
    | GraphQLInterfaceType
    | GraphQLUnionType
    | GraphQLEnumType
)


def is_named_type(type_: Any) -> TypeGuard[GraphQLNamedType]:
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
        msg = f"Expected {type_} to be a GraphQL named type."
        raise TypeError(msg)
    return type_


@overload
def get_named_type(type_: None) -> None: ...


@overload
def get_named_type(type_: GraphQLType) -> GraphQLNamedType: ...


def get_named_type(type_: GraphQLType | None) -> GraphQLNamedType | None:
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
            unwrapped_type = unwrapped_type.of_type
        return cast("GraphQLNamedType", unwrapped_type)
    return None


# These types may describe types which may be leaf values.

GraphQLLeafType: TypeAlias = GraphQLScalarType | GraphQLEnumType


def is_leaf_type(type_: Any) -> TypeGuard[GraphQLLeafType]:
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
    return isinstance(type_, (GraphQLScalarType, GraphQLEnumType))


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
        msg = f"Expected {type_} to be a GraphQL leaf type."
        raise TypeError(msg)
    return type_


# These types may describe the parent context of a selection set.

GraphQLCompositeType: TypeAlias = (
    GraphQLObjectType | GraphQLInterfaceType | GraphQLUnionType
)


def is_composite_type(type_: Any) -> TypeGuard[GraphQLCompositeType]:
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
    return isinstance(
        type_, (GraphQLObjectType, GraphQLInterfaceType, GraphQLUnionType)
    )


def assert_composite_type(type_: Any) -> GraphQLCompositeType:
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
        msg = f"Expected {type_} to be a GraphQL composite type."
        raise TypeError(msg)
    return type_


# These types may describe abstract types.

GraphQLAbstractType: TypeAlias = GraphQLInterfaceType | GraphQLUnionType


def is_abstract_type(type_: Any) -> TypeGuard[GraphQLAbstractType]:
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
    return isinstance(type_, (GraphQLInterfaceType, GraphQLUnionType))


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
        msg = f"Expected {type_} to be a GraphQL abstract type."
        raise TypeError(msg)
    return type_
