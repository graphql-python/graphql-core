from enum import Enum
from typing import Mapping

from .definition import (
    GraphQLArgument,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLFieldMap,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
    is_abstract_type,
    is_enum_type,
    is_input_object_type,
    is_interface_type,
    is_list_type,
    is_non_null_type,
    is_object_type,
    is_scalar_type,
    is_union_type,
)
from ..language import DirectiveLocation, print_ast
from ..pyutils import inspect
from .scalars import GraphQLBoolean, GraphQLString

__all__ = [
    "SchemaMetaFieldDef",
    "TypeKind",
    "TypeMetaFieldDef",
    "TypeNameMetaFieldDef",
    "introspection_types",
    "is_introspection_type",
]


class SchemaFields(GraphQLFieldMap):
    def __new__(cls):
        return {
            "description": GraphQLField(GraphQLString, resolve=cls.description),
            "types": GraphQLField(
                GraphQLNonNull(GraphQLList(GraphQLNonNull(_Type))),
                resolve=cls.types,
                description="A list of all types supported by this server.",
            ),
            "queryType": GraphQLField(
                GraphQLNonNull(_Type),
                resolve=cls.query_type,
                description="The type that query operations will be rooted at.",
            ),
            "mutationType": GraphQLField(
                _Type,
                resolve=cls.mutation_type,
                description="If this server supports mutation, the type that"
                " mutation operations will be rooted at.",
            ),
            "subscriptionType": GraphQLField(
                _Type,
                resolve=cls.subscription_type,
                description="If this server supports subscription, the type that"
                " subscription operations will be rooted at.",
            ),
            "directives": GraphQLField(
                GraphQLNonNull(GraphQLList(GraphQLNonNull(_Directive))),
                resolve=cls.directives,
                description="A list of all directives supported by this server.",
            ),
        }

    @staticmethod
    def description(schema, _info):
        return schema.description

    @staticmethod
    def types(schema, _info):
        return schema.type_map.values()

    @staticmethod
    def query_type(schema, _info):
        return schema.query_type

    @staticmethod
    def mutation_type(schema, _info):
        return schema.mutation_type

    @staticmethod
    def subscription_type(schema, _info):
        return schema.subscription_type

    @staticmethod
    def directives(schema, _info):
        return schema.directives


_Schema: GraphQLObjectType = GraphQLObjectType(
    name="__Schema",
    description="A GraphQL Schema defines the capabilities of a GraphQL"
    " server. It exposes all available types and directives"
    " on the server, as well as the entry points for query,"
    " mutation, and subscription operations.",
    fields=SchemaFields,
)


class DirectiveFields(GraphQLFieldMap):
    def __new__(cls):
        return {
            # Note: The fields onOperation, onFragment and onField are deprecated
            "name": GraphQLField(
                GraphQLNonNull(GraphQLString),
                resolve=cls.name,
            ),
            "description": GraphQLField(
                GraphQLString,
                resolve=cls.description,
            ),
            "isRepeatable": GraphQLField(
                GraphQLNonNull(GraphQLBoolean),
                resolve=cls.is_repeatable,
            ),
            "locations": GraphQLField(
                GraphQLNonNull(GraphQLList(GraphQLNonNull(_DirectiveLocation))),
                resolve=cls.locations,
            ),
            "args": GraphQLField(
                GraphQLNonNull(GraphQLList(GraphQLNonNull(_InputValue))),
                args={
                    "includeDeprecated": GraphQLArgument(
                        GraphQLBoolean, default_value=False
                    )
                },
                resolve=cls.args,
            ),
        }

    @staticmethod
    def name(directive, _info):
        return directive.name

    @staticmethod
    def description(directive, _info):
        return directive.description

    @staticmethod
    def is_repeatable(directive, _info):
        return directive.is_repeatable

    @staticmethod
    def locations(directive, _info):
        return directive.locations

    # noinspection PyPep8Naming
    @staticmethod
    def args(directive, _info, includeDeprecated=False):
        items = directive.args.items()
        return (
            list(items)
            if includeDeprecated
            else [item for item in items if item[1].deprecation_reason is None]
        )


_Directive: GraphQLObjectType = GraphQLObjectType(
    name="__Directive",
    description="A Directive provides a way to describe alternate runtime"
    " execution and type validation behavior in a GraphQL"
    " document.\n\nIn some cases, you need to provide options"
    " to alter GraphQL's execution behavior in ways field"
    " arguments will not suffice, such as conditionally including"
    " or skipping a field. Directives provide this by describing"
    " additional information to the executor.",
    fields=DirectiveFields,
)


_DirectiveLocation: GraphQLEnumType = GraphQLEnumType(
    name="__DirectiveLocation",
    description="A Directive can be adjacent to many parts of the GraphQL"
    " language, a __DirectiveLocation describes one such possible"
    " adjacencies.",
    values={
        "QUERY": GraphQLEnumValue(
            DirectiveLocation.QUERY,
            description="Location adjacent to a query operation.",
        ),
        "MUTATION": GraphQLEnumValue(
            DirectiveLocation.MUTATION,
            description="Location adjacent to a mutation operation.",
        ),
        "SUBSCRIPTION": GraphQLEnumValue(
            DirectiveLocation.SUBSCRIPTION,
            description="Location adjacent to a subscription operation.",
        ),
        "FIELD": GraphQLEnumValue(
            DirectiveLocation.FIELD, description="Location adjacent to a field."
        ),
        "FRAGMENT_DEFINITION": GraphQLEnumValue(
            DirectiveLocation.FRAGMENT_DEFINITION,
            description="Location adjacent to a fragment definition.",
        ),
        "FRAGMENT_SPREAD": GraphQLEnumValue(
            DirectiveLocation.FRAGMENT_SPREAD,
            description="Location adjacent to a fragment spread.",
        ),
        "INLINE_FRAGMENT": GraphQLEnumValue(
            DirectiveLocation.INLINE_FRAGMENT,
            description="Location adjacent to an inline fragment.",
        ),
        "VARIABLE_DEFINITION": GraphQLEnumValue(
            DirectiveLocation.VARIABLE_DEFINITION,
            description="Location adjacent to a variable definition.",
        ),
        "SCHEMA": GraphQLEnumValue(
            DirectiveLocation.SCHEMA,
            description="Location adjacent to a schema definition.",
        ),
        "SCALAR": GraphQLEnumValue(
            DirectiveLocation.SCALAR,
            description="Location adjacent to a scalar definition.",
        ),
        "OBJECT": GraphQLEnumValue(
            DirectiveLocation.OBJECT,
            description="Location adjacent to an object type definition.",
        ),
        "FIELD_DEFINITION": GraphQLEnumValue(
            DirectiveLocation.FIELD_DEFINITION,
            description="Location adjacent to a field definition.",
        ),
        "ARGUMENT_DEFINITION": GraphQLEnumValue(
            DirectiveLocation.ARGUMENT_DEFINITION,
            description="Location adjacent to an argument definition.",
        ),
        "INTERFACE": GraphQLEnumValue(
            DirectiveLocation.INTERFACE,
            description="Location adjacent to an interface definition.",
        ),
        "UNION": GraphQLEnumValue(
            DirectiveLocation.UNION,
            description="Location adjacent to a union definition.",
        ),
        "ENUM": GraphQLEnumValue(
            DirectiveLocation.ENUM,
            description="Location adjacent to an enum definition.",
        ),
        "ENUM_VALUE": GraphQLEnumValue(
            DirectiveLocation.ENUM_VALUE,
            description="Location adjacent to an enum value definition.",
        ),
        "INPUT_OBJECT": GraphQLEnumValue(
            DirectiveLocation.INPUT_OBJECT,
            description="Location adjacent to an input object type definition.",
        ),
        "INPUT_FIELD_DEFINITION": GraphQLEnumValue(
            DirectiveLocation.INPUT_FIELD_DEFINITION,
            description="Location adjacent to an input object field definition.",
        ),
    },
)


class TypeFields(GraphQLFieldMap):
    def __new__(cls):
        return {
            "kind": GraphQLField(GraphQLNonNull(_TypeKind), resolve=cls.kind),
            "name": GraphQLField(GraphQLString, resolve=cls.name),
            "description": GraphQLField(GraphQLString, resolve=cls.description),
            "specifiedByURL": GraphQLField(GraphQLString, resolve=cls.specified_by_url),
            "fields": GraphQLField(
                GraphQLList(GraphQLNonNull(_Field)),
                args={
                    "includeDeprecated": GraphQLArgument(
                        GraphQLBoolean, default_value=False
                    )
                },
                resolve=cls.fields,
            ),
            "interfaces": GraphQLField(
                GraphQLList(GraphQLNonNull(_Type)), resolve=cls.interfaces
            ),
            "possibleTypes": GraphQLField(
                GraphQLList(GraphQLNonNull(_Type)),
                resolve=cls.possible_types,
            ),
            "enumValues": GraphQLField(
                GraphQLList(GraphQLNonNull(_EnumValue)),
                args={
                    "includeDeprecated": GraphQLArgument(
                        GraphQLBoolean, default_value=False
                    )
                },
                resolve=cls.enum_values,
            ),
            "inputFields": GraphQLField(
                GraphQLList(GraphQLNonNull(_InputValue)),
                args={
                    "includeDeprecated": GraphQLArgument(
                        GraphQLBoolean, default_value=False
                    )
                },
                resolve=cls.input_fields,
            ),
            "ofType": GraphQLField(_Type, resolve=cls.of_type),
            "isOneOf": GraphQLField(GraphQLBoolean, resolve=cls.is_one_of),
        }

    @staticmethod
    def kind(type_, _info):
        if is_scalar_type(type_):
            return TypeKind.SCALAR
        if is_object_type(type_):
            return TypeKind.OBJECT
        if is_interface_type(type_):
            return TypeKind.INTERFACE
        if is_union_type(type_):
            return TypeKind.UNION
        if is_enum_type(type_):
            return TypeKind.ENUM
        if is_input_object_type(type_):
            return TypeKind.INPUT_OBJECT
        if is_list_type(type_):
            return TypeKind.LIST
        if is_non_null_type(type_):
            return TypeKind.NON_NULL

        # Not reachable. All possible types have been considered.
        raise TypeError(f"Unexpected type: {inspect(type_)}.")  # pragma: no cover

    @staticmethod
    def name(type_, _info):
        return getattr(type_, "name", None)

    @staticmethod
    def description(type_, _info):
        return getattr(type_, "description", None)

    @staticmethod
    def specified_by_url(type_, _info):
        return getattr(type_, "specified_by_url", None)

    # noinspection PyPep8Naming
    @staticmethod
    def fields(type_, _info, includeDeprecated=False):
        if is_object_type(type_) or is_interface_type(type_):
            items = type_.fields.items()
            return (
                list(items)
                if includeDeprecated
                else [item for item in items if item[1].deprecation_reason is None]
            )

    @staticmethod
    def interfaces(type_, _info):
        if is_object_type(type_) or is_interface_type(type_):
            return type_.interfaces

    @staticmethod
    def possible_types(type_, info):
        if is_abstract_type(type_):
            return info.schema.get_possible_types(type_)

    # noinspection PyPep8Naming
    @staticmethod
    def enum_values(type_, _info, includeDeprecated=False):
        if is_enum_type(type_):
            items = type_.values.items()
            return (
                items
                if includeDeprecated
                else [item for item in items if item[1].deprecation_reason is None]
            )

    # noinspection PyPep8Naming
    @staticmethod
    def input_fields(type_, _info, includeDeprecated=False):
        if is_input_object_type(type_):
            items = type_.fields.items()
            return (
                items
                if includeDeprecated
                else [item for item in items if item[1].deprecation_reason is None]
            )

    @staticmethod
    def of_type(type_, _info):
        return getattr(type_, "of_type", None)

    @staticmethod
    def is_one_of(type_, _info):
        return type_.is_one_of if is_input_object_type(type_) else None


_Type: GraphQLObjectType = GraphQLObjectType(
    name="__Type",
    description="The fundamental unit of any GraphQL Schema is the type."
    " There are many kinds of types in GraphQL as represented"
    " by the `__TypeKind` enum.\n\nDepending on the kind of a"
    " type, certain fields describe information about that type."
    " Scalar types provide no information beyond a name, description"
    " and optional `specifiedByURL`, while Enum types provide their values."
    " Object and Interface types provide the fields they describe."
    " Abstract types, Union and Interface, provide the Object"
    " types possible at runtime. List and NonNull types compose"
    " other types.",
    fields=TypeFields,
)


class FieldFields(GraphQLFieldMap):
    def __new__(cls):
        return {
            "name": GraphQLField(GraphQLNonNull(GraphQLString), resolve=cls.name),
            "description": GraphQLField(GraphQLString, resolve=cls.description),
            "args": GraphQLField(
                GraphQLNonNull(GraphQLList(GraphQLNonNull(_InputValue))),
                args={
                    "includeDeprecated": GraphQLArgument(
                        GraphQLBoolean, default_value=False
                    )
                },
                resolve=cls.args,
            ),
            "type": GraphQLField(GraphQLNonNull(_Type), resolve=cls.type),
            "isDeprecated": GraphQLField(
                GraphQLNonNull(GraphQLBoolean),
                resolve=cls.is_deprecated,
            ),
            "deprecationReason": GraphQLField(
                GraphQLString, resolve=cls.deprecation_reason
            ),
        }

    @staticmethod
    def name(item, _info):
        return item[0]

    @staticmethod
    def description(item, _info):
        return item[1].description

    # noinspection PyPep8Naming
    @staticmethod
    def args(item, _info, includeDeprecated=False):
        items = item[1].args.items()
        return (
            items
            if includeDeprecated
            else [item for item in items if item[1].deprecation_reason is None]
        )

    @staticmethod
    def type(item, _info):
        return item[1].type

    @staticmethod
    def is_deprecated(item, _info):
        return item[1].deprecation_reason is not None

    @staticmethod
    def deprecation_reason(item, _info):
        return item[1].deprecation_reason


_Field: GraphQLObjectType = GraphQLObjectType(
    name="__Field",
    description="Object and Interface types are described by a list of Fields,"
    " each of which has a name, potentially a list of arguments,"
    " and a return type.",
    fields=FieldFields,
)


class InputValueFields(GraphQLFieldMap):
    def __new__(cls):
        return {
            "name": GraphQLField(GraphQLNonNull(GraphQLString), resolve=cls.name),
            "description": GraphQLField(
                GraphQLString, resolve=InputValueFields.description
            ),
            "type": GraphQLField(GraphQLNonNull(_Type), resolve=cls.type),
            "defaultValue": GraphQLField(
                GraphQLString,
                description="A GraphQL-formatted string representing"
                " the default value for this input value.",
                resolve=cls.default_value,
            ),
            "isDeprecated": GraphQLField(
                GraphQLNonNull(GraphQLBoolean),
                resolve=cls.is_deprecated,
            ),
            "deprecationReason": GraphQLField(
                GraphQLString, resolve=cls.deprecation_reason
            ),
        }

    @staticmethod
    def name(item, _info):
        return item[0]

    @staticmethod
    def description(item, _info):
        return item[1].description

    @staticmethod
    def type(item, _info):
        return item[1].type

    @staticmethod
    def default_value(item, _info):
        # Since ast_from_value needs graphql.type, it can only be imported later
        from ..utilities import ast_from_value

        value_ast = ast_from_value(item[1].default_value, item[1].type)
        return print_ast(value_ast) if value_ast else None

    @staticmethod
    def is_deprecated(item, _info):
        return item[1].deprecation_reason is not None

    @staticmethod
    def deprecation_reason(item, _info):
        return item[1].deprecation_reason


_InputValue: GraphQLObjectType = GraphQLObjectType(
    name="__InputValue",
    description="Arguments provided to Fields or Directives and the input"
    " fields of an InputObject are represented as Input Values"
    " which describe their type and optionally a default value.",
    fields=InputValueFields,
)


class EnumValueFields(GraphQLFieldMap):
    def __new__(cls):
        return {
            "name": GraphQLField(
                GraphQLNonNull(GraphQLString), resolve=EnumValueFields.name
            ),
            "description": GraphQLField(
                GraphQLString, resolve=EnumValueFields.description
            ),
            "isDeprecated": GraphQLField(
                GraphQLNonNull(GraphQLBoolean),
                resolve=EnumValueFields.is_deprecated,
            ),
            "deprecationReason": GraphQLField(
                GraphQLString, resolve=EnumValueFields.deprecation_reason
            ),
        }

    @staticmethod
    def name(item, _info):
        return item[0]

    @staticmethod
    def description(item, _info):
        return item[1].description

    @staticmethod
    def is_deprecated(item, _info):
        return item[1].deprecation_reason is not None

    @staticmethod
    def deprecation_reason(item, _info):
        return item[1].deprecation_reason


_EnumValue: GraphQLObjectType = GraphQLObjectType(
    name="__EnumValue",
    description="One possible value for a given Enum. Enum values are unique"
    " values, not a placeholder for a string or numeric value."
    " However an Enum value is returned in a JSON response as a"
    " string.",
    fields=EnumValueFields,
)


class TypeKind(Enum):
    SCALAR = "scalar"
    OBJECT = "object"
    INTERFACE = "interface"
    UNION = "union"
    ENUM = "enum"
    INPUT_OBJECT = "input object"
    LIST = "list"
    NON_NULL = "non-null"


_TypeKind: GraphQLEnumType = GraphQLEnumType(
    name="__TypeKind",
    description="An enum describing what kind of type a given `__Type` is.",
    values={
        "SCALAR": GraphQLEnumValue(
            TypeKind.SCALAR, description="Indicates this type is a scalar."
        ),
        "OBJECT": GraphQLEnumValue(
            TypeKind.OBJECT,
            description="Indicates this type is an object."
            " `fields` and `interfaces` are valid fields.",
        ),
        "INTERFACE": GraphQLEnumValue(
            TypeKind.INTERFACE,
            description="Indicates this type is an interface."
            " `fields`, `interfaces`, and `possibleTypes` are valid fields.",
        ),
        "UNION": GraphQLEnumValue(
            TypeKind.UNION,
            description="Indicates this type is a union."
            " `possibleTypes` is a valid field.",
        ),
        "ENUM": GraphQLEnumValue(
            TypeKind.ENUM,
            description="Indicates this type is an enum."
            " `enumValues` is a valid field.",
        ),
        "INPUT_OBJECT": GraphQLEnumValue(
            TypeKind.INPUT_OBJECT,
            description="Indicates this type is an input object."
            " `inputFields` is a valid field.",
        ),
        "LIST": GraphQLEnumValue(
            TypeKind.LIST,
            description="Indicates this type is a list. `ofType` is a valid field.",
        ),
        "NON_NULL": GraphQLEnumValue(
            TypeKind.NON_NULL,
            description="Indicates this type is a non-null. `ofType` is a valid field.",
        ),
    },
)


class MetaFields:
    @staticmethod
    def schema(_source, info):
        return info.schema

    @staticmethod
    def type(_source, info, **args):
        return info.schema.get_type(args["name"])

    @staticmethod
    def type_name(_source, info, **_args):
        return info.parent_type.name


SchemaMetaFieldDef = GraphQLField(
    GraphQLNonNull(_Schema),  # name = '__schema'
    description="Access the current type schema of this server.",
    args={},
    resolve=MetaFields.schema,
)


TypeMetaFieldDef = GraphQLField(
    _Type,  # name = '__type'
    description="Request the type information of a single type.",
    args={"name": GraphQLArgument(GraphQLNonNull(GraphQLString))},
    resolve=MetaFields.type,
)


TypeNameMetaFieldDef = GraphQLField(
    GraphQLNonNull(GraphQLString),  # name='__typename'
    description="The name of the current Object type at runtime.",
    args={},
    resolve=MetaFields.type_name,
)


# Since double underscore names are subject to name mangling in Python,
# the introspection classes are best imported via this dictionary:
introspection_types: Mapping[str, GraphQLNamedType] = {  # treat as read-only
    "__Schema": _Schema,
    "__Directive": _Directive,
    "__DirectiveLocation": _DirectiveLocation,
    "__Type": _Type,
    "__Field": _Field,
    "__InputValue": _InputValue,
    "__EnumValue": _EnumValue,
    "__TypeKind": _TypeKind,
}
"""A mapping containing all introspection types with their names as keys"""


def is_introspection_type(type_: GraphQLNamedType) -> bool:
    """Check whether the given named GraphQL type is an introspection type."""
    return type_.name in introspection_types


# register the introspection types to avoid redefinition
GraphQLNamedType.reserved_types.update(introspection_types)
