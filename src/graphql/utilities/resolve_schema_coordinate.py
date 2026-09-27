"""Resolve schema coordinates"""

from typing import NamedTuple, Optional, Union

from ..language import (
    ArgumentCoordinateNode,
    DirectiveArgumentCoordinateNode,
    DirectiveCoordinateNode,
    MemberCoordinateNode,
    SchemaCoordinateNode,
    Source,
    TypeCoordinateNode,
    parse_schema_coordinate,
)
from ..pyutils import inspect
from ..type import (
    GraphQLArgument,
    GraphQLDirective,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLNamedType,
    GraphQLObjectType,
    GraphQLSchema,
)

__all__ = [
    "resolve_schema_coordinate",
    "resolve_ast_schema_coordinate",
    "ResolvedNamedType",
    "ResolvedField",
    "ResolvedInputField",
    "ResolvedEnumValue",
    "ResolvedFieldArgument",
    "ResolvedDirective",
    "ResolvedDirectiveArgument",
    "ResolvedSchemaElement",
]


class ResolvedNamedType(NamedTuple):
    """A named type resolved from a schema coordinate."""

    type: GraphQLNamedType
    """The resolved named type."""
    kind: str = "NamedType"
    """The kind of the resolved schema element."""


class ResolvedField(NamedTuple):
    """A field resolved from a schema coordinate."""

    type: Union[GraphQLObjectType, GraphQLInterfaceType]
    """The object or interface type that declares the field."""
    field: GraphQLField
    """The resolved field."""
    kind: str = "Field"
    """The kind of the resolved schema element."""


class ResolvedInputField(NamedTuple):
    """An input field resolved from a schema coordinate."""

    type: GraphQLInputObjectType
    """The input object type that declares the input field."""
    input_field: GraphQLInputField
    """The resolved input field."""
    kind: str = "InputField"
    """The kind of the resolved schema element."""


class ResolvedEnumValue(NamedTuple):
    """An enum value resolved from a schema coordinate."""

    type: GraphQLEnumType
    """The enum type that declares the enum value."""
    enum_value: GraphQLEnumValue
    """The resolved enum value."""
    kind: str = "EnumValue"
    """The kind of the resolved schema element."""


class ResolvedFieldArgument(NamedTuple):
    """A field argument resolved from a schema coordinate."""

    type: Union[GraphQLObjectType, GraphQLInterfaceType]
    """The object or interface type that declares the field."""
    field: GraphQLField
    """The field that declares the argument."""
    field_argument: GraphQLArgument
    """The resolved field argument."""
    kind: str = "FieldArgument"
    """The kind of the resolved schema element."""


class ResolvedDirective(NamedTuple):
    """A directive resolved from a schema coordinate."""

    directive: GraphQLDirective
    """The resolved directive."""
    kind: str = "Directive"
    """The kind of the resolved schema element."""


class ResolvedDirectiveArgument(NamedTuple):
    """A directive argument resolved from a schema coordinate."""

    directive: GraphQLDirective
    """The directive that declares the argument."""
    directive_argument: GraphQLArgument
    """The resolved directive argument."""
    kind: str = "DirectiveArgument"
    """The kind of the resolved schema element."""


ResolvedSchemaElement = Union[
    ResolvedNamedType,
    ResolvedField,
    ResolvedInputField,
    ResolvedEnumValue,
    ResolvedFieldArgument,
    ResolvedDirective,
    ResolvedDirectiveArgument,
]


def resolve_schema_coordinate(
    schema: GraphQLSchema, schema_coordinate: Union[str, Source]
) -> Optional[ResolvedSchemaElement]:
    """Resolve a string schema coordinate in the context of a GraphQL schema.

    A schema coordinate is resolved in the context of a GraphQL schema to uniquely
    identify a schema element. It returns None if the schema coordinate does not
    resolve to a schema element, meta-field, or introspection schema element. It will
    raise an error if the containing schema element (if applicable) does not exist.

    `<https://spec.graphql.org/draft/#sec-Schema-Coordinates.Semantics>`_

    :param schema: The GraphQL schema to use.
    :param schema_coordinate: The schema coordinate to resolve.
    :returns: The schema element identified by the coordinate, or ``None`` if none
        exists.

    >>> from graphql import build_schema, resolve_schema_coordinate
    >>> schema = build_schema('''
    ...     directive @tag(name: String!) on FIELD_DEFINITION
    ...
    ...     input ReviewInput {
    ...       stars: Int!
    ...     }
    ...
    ...     enum Episode {
    ...       NEW_HOPE
    ...     }
    ...
    ...     type Query {
    ...       reviews(input: ReviewInput): [String] @tag(name: "reviews")
    ...     }
    ... ''')
    >>> resolve_schema_coordinate(schema, 'Query').kind
    'NamedType'
    >>> resolve_schema_coordinate(schema, 'Query.reviews').kind
    'Field'
    >>> resolve_schema_coordinate(schema, 'Query.reviews(input:)').kind
    'FieldArgument'
    >>> resolve_schema_coordinate(schema, 'ReviewInput.stars').kind
    'InputField'
    >>> resolve_schema_coordinate(schema, 'Episode.NEW_HOPE').kind
    'EnumValue'
    >>> resolve_schema_coordinate(schema, '@tag').kind
    'Directive'
    >>> resolve_schema_coordinate(schema, '@tag(name:)').kind
    'DirectiveArgument'
    >>> print(resolve_schema_coordinate(schema, 'Query.missing'))
    None
    """
    return resolve_ast_schema_coordinate(
        schema, parse_schema_coordinate(schema_coordinate)
    )


def resolve_type_coordinate(
    schema: GraphQLSchema, schema_coordinate: TypeCoordinateNode
) -> Optional[ResolvedNamedType]:
    """TypeCoordinate : Name"""
    # 1. Let {typeName} be the value of {Name}.
    type_name = schema_coordinate.name.value
    type_ = schema.get_type(type_name)

    # 2. Return the type in the {schema} named {typeName} if it exists.
    if type_ is None:
        return None

    return ResolvedNamedType(type_)


def resolve_member_coordinate(
    schema: GraphQLSchema, schema_coordinate: MemberCoordinateNode
) -> Optional[Union[ResolvedField, ResolvedInputField, ResolvedEnumValue]]:
    """MemberCoordinate : Name . Name"""
    # 1. Let {typeName} be the value of the first {Name}.
    # 2. Let {type} be the type in the {schema} named {typeName}.
    type_name = schema_coordinate.name.value
    type_ = schema.get_type(type_name)

    # 3. Assert: {type} must exist, and must be an Enum, Input Object, Object or
    #    Interface type.
    if type_ is None:
        raise TypeError(
            f"Expected {inspect(type_name)} to be defined as a type in the schema."
        )
    if not isinstance(
        type_,
        (
            GraphQLEnumType,
            GraphQLInputObjectType,
            GraphQLObjectType,
            GraphQLInterfaceType,
        ),
    ):
        raise TypeError(
            f"Expected {inspect(type_name)}"
            " to be an Enum, Input Object, Object or Interface type."
        )

    member_name = schema_coordinate.member_name.value

    # 4. If {type} is an Enum type:
    if isinstance(type_, GraphQLEnumType):
        # 1. Let {enumValueName} be the value of the second {Name}.
        # 2. Return the enum value of {type} named {enumValueName} if it exists.
        enum_value = type_.values.get(member_name)
        if enum_value is None:
            return None
        return ResolvedEnumValue(type_, enum_value)

    # 5. Otherwise, if {type} is an Input Object type:
    if isinstance(type_, GraphQLInputObjectType):
        # 1. Let {inputFieldName} be the value of the second {Name}.
        # 2. Return the input field of {type} named {inputFieldName} if it exists.
        input_field = type_.fields.get(member_name)
        if input_field is None:
            return None
        return ResolvedInputField(type_, input_field)

    # 6. Otherwise:
    # 1. Let {fieldName} be the value of the second {Name}.
    # 2. Return the field of {type} named {fieldName} if it exists.
    field = type_.fields.get(member_name)
    if field is None:
        return None
    return ResolvedField(type_, field)


def resolve_argument_coordinate(
    schema: GraphQLSchema, schema_coordinate: ArgumentCoordinateNode
) -> Optional[ResolvedFieldArgument]:
    """ArgumentCoordinate : Name . Name ( Name : )"""
    # 1. Let {typeName} be the value of the first {Name}.
    # 2. Let {type} be the type in the {schema} named {typeName}.
    type_name = schema_coordinate.name.value
    type_ = schema.get_type(type_name)

    # 3. Assert: {type} must exist, and be an Object or Interface type.
    if type_ is None:
        raise TypeError(
            f"Expected {inspect(type_name)} to be defined as a type in the schema."
        )
    if not isinstance(type_, (GraphQLObjectType, GraphQLInterfaceType)):
        raise TypeError(
            f"Expected {inspect(type_name)} to be an object type or interface type."
        )

    # 4. Let {fieldName} be the value of the second {Name}.
    # 5. Let {field} be the field of {type} named {fieldName}.
    field_name = schema_coordinate.field_name.value
    field = type_.fields.get(field_name)

    # 6. Assert: {field} must exist.
    if field is None:
        raise TypeError(
            f"Expected {inspect(field_name)} to exist as a field"
            f" of type {inspect(type_name)} in the schema."
        )

    # 7. Let {fieldArgumentName} be the value of the third {Name}.
    field_argument_name = schema_coordinate.argument_name.value
    field_argument = field.args.get(field_argument_name)

    # 8. Return the argument of {field} named {fieldArgumentName} if it exists.
    if field_argument is None:
        return None

    return ResolvedFieldArgument(type_, field, field_argument)


def resolve_directive_coordinate(
    schema: GraphQLSchema, schema_coordinate: DirectiveCoordinateNode
) -> Optional[ResolvedDirective]:
    """DirectiveCoordinate : @ Name"""
    # 1. Let {directiveName} be the value of {Name}.
    directive_name = schema_coordinate.name.value
    directive = schema.get_directive(directive_name)

    # 2. Return the directive in the {schema} named {directiveName} if it exists.
    if directive is None:
        return None

    return ResolvedDirective(directive)


def resolve_directive_argument_coordinate(
    schema: GraphQLSchema, schema_coordinate: DirectiveArgumentCoordinateNode
) -> Optional[ResolvedDirectiveArgument]:
    """DirectiveArgumentCoordinate : @ Name ( Name : )"""
    # 1. Let {directiveName} be the value of the first {Name}.
    # 2. Let {directive} be the directive in the {schema} named {directiveName}.
    directive_name = schema_coordinate.name.value
    directive = schema.get_directive(directive_name)

    # 3. Assert {directive} must exist.
    if directive is None:
        raise TypeError(
            f"Expected {inspect(directive_name)}"
            " to be defined as a directive in the schema."
        )

    # 4. Let {directiveArgumentName} be the value of the second {Name}.
    directive_argument_name = schema_coordinate.argument_name.value
    directive_argument = directive.args.get(directive_argument_name)

    # 5. Return the argument of {directive} named {directiveArgumentName} if it exists.
    if directive_argument is None:
        return None

    return ResolvedDirectiveArgument(directive, directive_argument)


def resolve_ast_schema_coordinate(
    schema: GraphQLSchema, schema_coordinate: SchemaCoordinateNode
) -> Optional[ResolvedSchemaElement]:
    """Resolve schema coordinate from a parsed SchemaCoordinate node.

    :param schema: The GraphQL schema to use.
    :param schema_coordinate: The parsed schema coordinate to resolve.
    :returns: The schema element identified by the parsed coordinate, or ``None`` if
        none exists.

    >>> from graphql import (
    ...     build_schema, parse_schema_coordinate, resolve_ast_schema_coordinate)
    >>> schema = build_schema('''
    ...     type Query {
    ...       greeting(name: String): String
    ...     }
    ... ''')
    >>> coordinate = parse_schema_coordinate('Query.greeting(name:)')
    >>> resolved = resolve_ast_schema_coordinate(schema, coordinate)
    >>> resolved.kind
    'FieldArgument'
    >>> resolved.type.name
    'Query'
    >>> resolved.field_argument.type
    <GraphQLScalarType 'String'>
    """
    if isinstance(schema_coordinate, TypeCoordinateNode):
        return resolve_type_coordinate(schema, schema_coordinate)
    if isinstance(schema_coordinate, MemberCoordinateNode):
        return resolve_member_coordinate(schema, schema_coordinate)
    if isinstance(schema_coordinate, ArgumentCoordinateNode):
        return resolve_argument_coordinate(schema, schema_coordinate)
    if isinstance(schema_coordinate, DirectiveCoordinateNode):
        return resolve_directive_coordinate(schema, schema_coordinate)
    # DirectiveArgumentCoordinateNode is the only remaining kind.
    return resolve_directive_argument_coordinate(schema, schema_coordinate)
