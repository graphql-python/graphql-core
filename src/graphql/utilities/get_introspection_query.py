"""Get introspection query"""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..language import DirectiveLocation

from typing import Literal, TypeAlias, TypedDict

__all__ = [
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
    "get_introspection_query",
]


def get_introspection_query(
    descriptions: bool = True,
    specified_by_url: bool = False,
    directive_is_repeatable: bool = False,
    schema_description: bool = False,
    input_value_deprecation: bool = False,
    experimental_directive_deprecation: bool = False,
    one_of: bool = False,
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
    """
    maybe_description = "description" if descriptions else ""
    maybe_specified_by_url = "specifiedByURL" if specified_by_url else ""
    maybe_directive_is_repeatable = "isRepeatable" if directive_is_repeatable else ""
    maybe_schema_description = maybe_description if schema_description else ""
    maybe_one_of = "isOneOf" if one_of else ""

    def input_deprecation(string: str) -> str | None:
        return string if input_value_deprecation else ""

    def directive_deprecation(string: str) -> str | None:
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

    return dedent(
        f"""
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
          {maybe_one_of}
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
        """
    )


# Unfortunately, the following type definitions are a bit simplistic
# because of current restrictions in the typing system (mypy):
# - no recursion, see https://github.com/python/mypy/issues/731
# - no generic typed dicts, see https://github.com/python/mypy/issues/3863

# simplified IntrospectionNamedType to avoids cycles
SimpleIntrospectionType: TypeAlias = dict[str, Any]


class MaybeWithDescription(TypedDict, total=False):
    description: str | None


class WithName(MaybeWithDescription):
    name: str


class MaybeWithSpecifiedByUrl(TypedDict, total=False):
    specifiedByURL: str | None


class WithDeprecated(TypedDict):
    isDeprecated: bool
    deprecationReason: str | None


class MaybeWithDeprecated(TypedDict, total=False):
    isDeprecated: bool
    deprecationReason: str | None


class IntrospectionInputValue(WithName, MaybeWithDeprecated):
    type: SimpleIntrospectionType  # should be IntrospectionInputType
    defaultValue: str | None


class IntrospectionField(WithName, WithDeprecated):
    args: list[IntrospectionInputValue]
    type: SimpleIntrospectionType  # should be IntrospectionOutputType


class IntrospectionEnumValue(WithName, WithDeprecated):
    pass


class MaybeWithIsRepeatable(TypedDict, total=False):
    isRepeatable: bool


class IntrospectionDirective(WithName, MaybeWithIsRepeatable, MaybeWithDeprecated):
    locations: list[DirectiveLocation]
    args: list[IntrospectionInputValue]


class IntrospectionScalarType(WithName, MaybeWithSpecifiedByUrl):
    kind: Literal["scalar"]


class IntrospectionInterfaceType(WithName):
    kind: Literal["interface"]
    fields: list[IntrospectionField]
    interfaces: list[SimpleIntrospectionType]  # should be InterfaceType
    possibleTypes: list[SimpleIntrospectionType]  # should be NamedType


class IntrospectionObjectType(WithName):
    kind: Literal["object"]
    fields: list[IntrospectionField]
    interfaces: list[SimpleIntrospectionType]  # should be InterfaceType


class IntrospectionUnionType(WithName):
    kind: Literal["union"]
    possibleTypes: list[SimpleIntrospectionType]  # should be NamedType


class IntrospectionEnumType(WithName):
    kind: Literal["enum"]
    enumValues: list[IntrospectionEnumValue]


class IntrospectionInputObjectType(WithName):
    kind: Literal["input_object"]
    inputFields: list[IntrospectionInputValue]
    isOneOf: bool


IntrospectionType: TypeAlias = (
    IntrospectionScalarType
    | IntrospectionObjectType
    | IntrospectionInterfaceType
    | IntrospectionUnionType
    | IntrospectionEnumType
    | IntrospectionInputObjectType
)

IntrospectionOutputType: TypeAlias = (
    IntrospectionScalarType
    | IntrospectionObjectType
    | IntrospectionInterfaceType
    | IntrospectionUnionType
    | IntrospectionEnumType
)

IntrospectionInputType: TypeAlias = (
    IntrospectionScalarType | IntrospectionEnumType | IntrospectionInputObjectType
)


class IntrospectionListType(TypedDict):
    kind: Literal["list"]
    ofType: SimpleIntrospectionType  # should be IntrospectionType


class IntrospectionNonNullType(TypedDict):
    kind: Literal["non_null"]
    ofType: SimpleIntrospectionType  # should be IntrospectionType


IntrospectionTypeRef: TypeAlias = (
    IntrospectionType | IntrospectionListType | IntrospectionNonNullType
)


class IntrospectionSchema(MaybeWithDescription):
    queryType: IntrospectionObjectType
    mutationType: IntrospectionObjectType | None
    subscriptionType: IntrospectionObjectType | None
    types: list[IntrospectionType]
    directives: list[IntrospectionDirective]


# The root typed dictionary for schema introspections.
# Note: We don't use class syntax here since the key looks like a private attribute.
IntrospectionQuery = TypedDict(
    "IntrospectionQuery",
    {"__schema": IntrospectionSchema},
)
