"""Get introspection query"""

from textwrap import dedent
from typing import Any, Dict, List, Optional, Union

from ..language import DirectiveLocation

try:
    from typing import Literal, TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import Literal, TypedDict

__all__ = [
    "get_introspection_query",
    "IntrospectionDirective",
    "IntrospectionEnumType",
    "IntrospectionField",
    "IntrospectionInputObjectType",
    "IntrospectionInputValue",
    "IntrospectionInterfaceType",
    "IntrospectionListType",
    "IntrospectionNonNullType",
    "IntrospectionObjectType",
    "IntrospectionQuery",
    "IntrospectionScalarType",
    "IntrospectionSchema",
    "IntrospectionType",
    "IntrospectionTypeRef",
    "IntrospectionUnionType",
]


def get_introspection_query(
    descriptions: bool = True,
    specified_by_url: bool = False,
    directive_is_repeatable: bool = False,
    schema_description: bool = False,
    input_value_deprecation: bool = False,
    experimental_directive_deprecation: bool = False,
    input_object_one_of: bool = False,
    type_depth: int = 9,
) -> str:
    """Get a query for introspection.

    Optionally, you can exclude descriptions, include specification URLs,
    include repeatability of directives, and specify whether to include
    the schema description as well.

    The ``type_depth`` argument controls how deep to recurse into nested types.
    Larger values will result in more accurate results, but have a higher load
    on the server. Some servers might restrict the maximum query depth or
    complexity. If that's the case, try decreasing this value. The default is 9.

    :param descriptions: Whether to include descriptions in the introspection result.
    :param specified_by_url: Whether to include ``specifiedByURL`` in the
        introspection result.
    :param directive_is_repeatable: Whether to include the ``isRepeatable`` flag on
        directives.
    :param schema_description: Whether to include the ``description`` field on the
        schema.
    :param input_value_deprecation: Whether the target GraphQL server supports
        deprecation of input values.
    :param experimental_directive_deprecation: Whether the target GraphQL server
        supports deprecation of directives.
    :param input_object_one_of: Whether the target GraphQL server supports ``@oneOf``
        input objects.
    :param type_depth: How deep to recurse into nested types.
    :returns: The resolved introspection query.

    Generate the default introspection query:

    >>> from graphql import get_introspection_query
    >>> query = get_introspection_query()
    >>> '__schema' in query
    True
    >>> 'description' in query
    True
    >>> 'specifiedByURL' in query
    False

    This variant customizes optional introspection fields and nesting depth:

    >>> query = get_introspection_query(
    ...     descriptions=False,
    ...     specified_by_url=True,
    ...     directive_is_repeatable=True,
    ...     schema_description=True,
    ...     input_value_deprecation=True,
    ...     experimental_directive_deprecation=True,
    ...     input_object_one_of=True,
    ...     type_depth=3,
    ... )
    >>> 'description' in query
    False
    >>> 'specifiedByURL' in query
    True
    >>> 'isRepeatable' in query
    True
    >>> 'includeDeprecated: true' in query
    True
    >>> 'isOneOf' in query
    True
    >>> query.count('ofType') > 0
    True
    """
    maybe_description = "description" if descriptions else ""
    maybe_specified_by_url = "specifiedByURL" if specified_by_url else ""
    maybe_directive_is_repeatable = "isRepeatable" if directive_is_repeatable else ""
    maybe_schema_description = maybe_description if schema_description else ""
    maybe_input_object_one_of = "isOneOf" if input_object_one_of else ""

    def input_deprecation(string: str) -> Optional[str]:
        return string if input_value_deprecation else ""

    def directive_deprecation(string: str) -> Optional[str]:
        return string if experimental_directive_deprecation else ""

    def of_type(level: int, indent: str) -> str:
        if level <= 0:
            return ""
        if level > 100:
            msg = (
                "Please set type_depth to a reasonable value"
                " between 0 and 100; the default is 9."
            )
            raise ValueError(msg)
        return (
            f"\n{indent}ofType {{"
            f"\n{indent}  name"
            f"\n{indent}  kind{of_type(level - 1, indent + '  ')}"
            f"\n{indent}}}"
        )

    return dedent(f"""
        query IntrospectionQuery {{
          __schema {{
            {maybe_schema_description}
            queryType {{ name kind }}
            mutationType {{ name kind }}
            subscriptionType {{ name kind }}
            types {{
              ...FullType
            }}
            directives{directive_deprecation("(includeDeprecated: true)")} {{
              name
              {maybe_description}
              {maybe_directive_is_repeatable}
              {directive_deprecation("isDeprecated")}
              {directive_deprecation("deprecationReason")}
              locations
              args{input_deprecation("(includeDeprecated: true)")} {{
                ...InputValue
              }}
            }}
          }}
        }}

        fragment FullType on __Type {{
          kind
          name
          {maybe_description}
          {maybe_specified_by_url}
          {maybe_input_object_one_of}
          fields(includeDeprecated: true) {{
            name
            {maybe_description}
            args{input_deprecation("(includeDeprecated: true)")} {{
              ...InputValue
            }}
            type {{
              ...TypeRef
            }}
            isDeprecated
            deprecationReason
          }}
          inputFields{input_deprecation("(includeDeprecated: true)")} {{
            ...InputValue
          }}
          interfaces {{
            ...TypeRef
          }}
          enumValues(includeDeprecated: true) {{
            name
            {maybe_description}
            isDeprecated
            deprecationReason
          }}
          possibleTypes {{
            ...TypeRef
          }}
        }}

        fragment InputValue on __InputValue {{
          name
          {maybe_description}
          type {{ ...TypeRef }}
          defaultValue
          {input_deprecation("isDeprecated")}
          {input_deprecation("deprecationReason")}
        }}

        fragment TypeRef on __Type {{
          kind
          name{of_type(type_depth, "          ")}
        }}
        """)


# Unfortunately, the following type definitions are a bit simplistic
# because of current restrictions in the typing system (mypy):
# - no recursion, see https://github.com/python/mypy/issues/731
# - no generic typed dicts, see https://github.com/python/mypy/issues/3863

# simplified IntrospectionNamedType to avoids cycles
SimpleIntrospectionType = Dict[str, Any]


class MaybeWithDescription(TypedDict, total=False):
    """Introspection data with an optional description."""

    description: Optional[str]
    """Human-readable description for this schema element, if provided."""


class WithName(MaybeWithDescription):
    """Introspection data with a name and an optional description."""

    name: str
    """The GraphQL name for this schema element."""


class MaybeWithSpecifiedByUrl(TypedDict, total=False):
    """Introspection data with an optional ``specifiedByURL``."""

    specifiedByURL: Optional[str]
    """URL identifying the behavior specified for this custom scalar."""


class WithDeprecated(TypedDict):
    """Introspection data with deprecation information."""

    isDeprecated: bool
    """Whether this field, argument, enum value, or input value is deprecated."""
    deprecationReason: Optional[str]
    """Reason this element is deprecated, if one was provided."""


class MaybeWithDeprecated(TypedDict, total=False):
    """Introspection data with optional deprecation information."""

    isDeprecated: bool
    """Whether this field, argument, enum value, or input value is deprecated."""
    deprecationReason: Optional[str]
    """Reason this element is deprecated, if one was provided."""


class IntrospectionInputValue(WithName, MaybeWithDeprecated):
    """The introspection representation of an argument or input field."""

    type: SimpleIntrospectionType  # should be IntrospectionInputType
    """The GraphQL type reference or runtime type for this element."""
    defaultValue: Optional[str]
    """Default value used when no explicit value is supplied."""


class IntrospectionField(WithName, WithDeprecated):
    """The introspection representation of a field."""

    args: List[IntrospectionInputValue]
    """Arguments accepted by this field or directive."""
    type: SimpleIntrospectionType  # should be IntrospectionOutputType
    """The GraphQL type reference or runtime type for this element."""


class IntrospectionEnumValue(WithName, WithDeprecated):
    """The introspection representation of an enum value."""


class MaybeWithIsRepeatable(TypedDict, total=False):
    """Introspection data with an optional ``isRepeatable`` flag."""

    isRepeatable: bool
    """Whether this directive may appear more than once at the same location."""


class IntrospectionDirective(WithName, MaybeWithIsRepeatable, MaybeWithDeprecated):
    """The introspection representation of a directive."""

    locations: List[DirectiveLocation]
    """Locations where this directive may be applied."""
    args: List[IntrospectionInputValue]
    """Arguments accepted by this field or directive."""


class IntrospectionScalarType(WithName, MaybeWithSpecifiedByUrl):
    """The introspection representation of a scalar type."""

    kind: Literal["SCALAR"]
    """The introspection kind discriminator for this type reference or type."""


class IntrospectionInterfaceType(WithName):
    """The introspection representation of an interface type."""

    kind: Literal["INTERFACE"]
    """The introspection kind discriminator for this type reference or type."""
    fields: List[IntrospectionField]
    """Fields declared by this object, interface, input object, or literal."""
    interfaces: List[SimpleIntrospectionType]  # should be InterfaceType
    """Interfaces implemented by this object or interface type."""
    possibleTypes: List[SimpleIntrospectionType]  # should be NamedType
    """Object types that may be returned for this abstract type."""


class IntrospectionObjectType(WithName):
    """The introspection representation of an object type."""

    kind: Literal["OBJECT"]
    """The introspection kind discriminator for this type reference or type."""
    fields: List[IntrospectionField]
    """Fields declared by this object, interface, input object, or literal."""
    interfaces: List[SimpleIntrospectionType]  # should be InterfaceType
    """Interfaces implemented by this object or interface type."""


class IntrospectionUnionType(WithName):
    """The introspection representation of a union type."""

    kind: Literal["UNION"]
    """The introspection kind discriminator for this type reference or type."""
    possibleTypes: List[SimpleIntrospectionType]  # should be NamedType
    """Object types that may be returned for this abstract type."""


class IntrospectionEnumType(WithName):
    """The introspection representation of an enum type."""

    kind: Literal["ENUM"]
    """The introspection kind discriminator for this type reference or type."""
    enumValues: List[IntrospectionEnumValue]
    """Values declared by this enum type."""


class IntrospectionInputObjectType(WithName):
    """The introspection representation of an input object type."""

    kind: Literal["INPUT_OBJECT"]
    """The introspection kind discriminator for this type reference or type."""
    inputFields: List[IntrospectionInputValue]
    """Input fields declared by this input object type."""
    isOneOf: bool
    """Whether this input object uses the OneOf input object semantics."""


IntrospectionType = Union[
    IntrospectionScalarType,
    IntrospectionObjectType,
    IntrospectionInterfaceType,
    IntrospectionUnionType,
    IntrospectionEnumType,
    IntrospectionInputObjectType,
]

IntrospectionOutputType = Union[
    IntrospectionScalarType,
    IntrospectionObjectType,
    IntrospectionInterfaceType,
    IntrospectionUnionType,
    IntrospectionEnumType,
]

IntrospectionInputType = Union[
    IntrospectionScalarType, IntrospectionEnumType, IntrospectionInputObjectType
]


class IntrospectionListType(TypedDict):
    """The introspection representation of a list type reference."""

    kind: Literal["LIST"]
    """The introspection kind discriminator for this type reference or type."""
    ofType: SimpleIntrospectionType  # should be IntrospectionType
    """The type wrapped by this list or non-null type."""


class IntrospectionNonNullType(TypedDict):
    """The introspection representation of a non-null type reference."""

    kind: Literal["NON_NULL"]
    """The introspection kind discriminator for this type reference or type."""
    ofType: SimpleIntrospectionType  # should be IntrospectionType
    """The type wrapped by this list or non-null type."""


IntrospectionTypeRef = Union[
    IntrospectionType, IntrospectionListType, IntrospectionNonNullType
]


class IntrospectionSchema(MaybeWithDescription):
    """The introspection representation of a GraphQL schema."""

    queryType: IntrospectionObjectType
    """The root object type used for query operations."""
    mutationType: Optional[IntrospectionObjectType]
    """The root object type used for mutation operations, if supported."""
    subscriptionType: Optional[IntrospectionObjectType]
    """The root object type used for subscription operations, if supported."""
    types: List[IntrospectionType]
    """All named types that belong to this schema."""
    directives: List[IntrospectionDirective]
    """Directives available in this schema."""


# The root typed dictionary for schema introspections.
# Note: We don't use class syntax here since the key looks like a private attribute.
IntrospectionQuery = TypedDict(
    "IntrospectionQuery",
    {"__schema": IntrospectionSchema},
)
IntrospectionQuery.__doc__ = """The result shape returned by a full introspection query.

The ``__schema`` key holds the introspection representation of the schema.
"""
