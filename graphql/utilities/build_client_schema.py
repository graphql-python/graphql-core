from typing import cast, Callable, Dict, List, Sequence

from ..error import INVALID
from ..language import DirectiveLocation, parse_value
from ..type import (
    GraphQLArgument,
    GraphQLDirective,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInputType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLOutputType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLType,
    GraphQLUnionType,
    TypeKind,
    assert_interface_type,
    assert_nullable_type,
    assert_object_type,
    introspection_types,
    is_input_type,
    is_output_type,
    specified_scalar_types,
)
from .value_from_ast import value_from_ast

__all__ = ["build_client_schema"]


def build_client_schema(
    introspection: Dict, assume_valid: bool = False
) -> GraphQLSchema:
    """Build a GraphQLSchema for use by client tools.

    Given the result of a client running the introspection query, creates and
    returns a GraphQLSchema instance which can be then used with all
    GraphQL-core-next tools, but cannot be used to execute a query, as
    introspection does not represent the "resolver", "parse" or "serialize"
    functions or any other server-internal mechanisms.

    This function expects a complete introspection result. Don't forget to
    check the "errors" field of a server response before calling this function.
    """
    # Get the schema from the introspection result.
    schema_introspection = introspection["__schema"]

    # Converts the list of types into a dict based on the type names.
    type_introspection_map: Dict[str, Dict] = {
        type_["name"]: type_ for type_ in schema_introspection["types"]
    }

    # A cache to use to store the actual GraphQLType definition objects by
    # name. Initialize to the GraphQL built in scalars. All functions below are
    # inline so that this type def cache is within the scope of the closure.
    type_def_cache: Dict[str, GraphQLNamedType] = {
        **specified_scalar_types,
        **introspection_types,
    }

    # Given a type reference in introspection, return the GraphQLType instance.
    # preferring cached instances before building new instances.
    def get_type(type_ref: Dict) -> GraphQLType:
        kind = type_ref.get("kind")
        if kind == TypeKind.LIST.name:
            item_ref = type_ref.get("ofType")
            if not item_ref:
                raise TypeError("Decorated type deeper than introspection query.")
            return GraphQLList(get_type(item_ref))
        elif kind == TypeKind.NON_NULL.name:
            nullable_ref = type_ref.get("ofType")
            if not nullable_ref:
                raise TypeError("Decorated type deeper than introspection query.")
            nullable_type = get_type(nullable_ref)
            return GraphQLNonNull(assert_nullable_type(nullable_type))
        name = type_ref.get("name")
        if not name:
            raise TypeError(f"Unknown type reference: {type_ref!r}")
        return get_named_type(name)

    def get_named_type(type_name: str) -> GraphQLNamedType:
        cached_type = type_def_cache.get(type_name)
        if cached_type:
            return cached_type
        type_introspection = type_introspection_map.get(type_name)
        if not type_introspection:
            raise TypeError(
                f"Invalid or incomplete schema, unknown type: {type_name}."
                " Ensure that a full introspection query is used in order"
                " to build a client schema."
            )
        type_def = build_type(type_introspection)
        type_def_cache[type_name] = type_def
        return type_def

    def get_input_type(type_ref: Dict) -> GraphQLInputType:
        input_type = get_type(type_ref)
        if not is_input_type(input_type):
            raise TypeError("Introspection must provide input type for arguments.")
        return cast(GraphQLInputType, input_type)

    def get_output_type(type_ref: Dict) -> GraphQLOutputType:
        output_type = get_type(type_ref)
        if not is_output_type(output_type):
            raise TypeError("Introspection must provide output type for fields.")
        return cast(GraphQLOutputType, output_type)

    def get_object_type(type_ref: Dict) -> GraphQLObjectType:
        object_type = get_type(type_ref)
        return assert_object_type(object_type)

    def get_interface_type(type_ref: Dict) -> GraphQLInterfaceType:
        interface_type = get_type(type_ref)
        return assert_interface_type(interface_type)

    # Given a type's introspection result, construct the correct
    # GraphQLType instance.
    def build_type(type_: Dict) -> GraphQLNamedType:
        if type_ and "name" in type_ and "kind" in type_:
            builder = type_builders.get(cast(str, type_["kind"]))
            if builder:
                return cast(GraphQLNamedType, builder(type_))
        raise TypeError(
            "Invalid or incomplete introspection result."
            " Ensure that a full introspection query is used in order"
            f" to build a client schema: {type_!r}"
        )

    def build_scalar_def(scalar_introspection: Dict) -> GraphQLScalarType:
        return GraphQLScalarType(
            name=scalar_introspection["name"],
            description=scalar_introspection.get("description"),
            serialize=lambda value: value,
        )

    def build_object_def(object_introspection: Dict) -> GraphQLObjectType:
        interfaces = object_introspection.get("interfaces")
        if interfaces is None:
            raise TypeError(
                "Introspection result missing interfaces:" f" {object_introspection!r}"
            )
        return GraphQLObjectType(
            name=object_introspection["name"],
            description=object_introspection.get("description"),
            interfaces=lambda: [
                get_interface_type(interface)
                for interface in cast(List[Dict], interfaces)
            ],
            fields=lambda: build_field_def_map(object_introspection),
        )

    def build_interface_def(interface_introspection: Dict) -> GraphQLInterfaceType:
        return GraphQLInterfaceType(
            name=interface_introspection["name"],
            description=interface_introspection.get("description"),
            fields=lambda: build_field_def_map(interface_introspection),
        )

    def build_union_def(union_introspection: Dict) -> GraphQLUnionType:
        possible_types = union_introspection.get("possibleTypes")
        if possible_types is None:
            raise TypeError(
                "Introspection result missing possibleTypes:"
                f" {union_introspection!r}"
            )
        return GraphQLUnionType(
            name=union_introspection["name"],
            description=union_introspection.get("description"),
            types=lambda: [
                get_object_type(type_) for type_ in cast(List[Dict], possible_types)
            ],
        )

    def build_enum_def(enum_introspection: Dict) -> GraphQLEnumType:
        if enum_introspection.get("enumValues") is None:
            raise TypeError(
                "Introspection result missing enumValues:" f" {enum_introspection!r}"
            )
        return GraphQLEnumType(
            name=enum_introspection["name"],
            description=enum_introspection.get("description"),
            values={
                value_introspect["name"]: GraphQLEnumValue(
                    description=value_introspect.get("description"),
                    deprecation_reason=value_introspect.get("deprecationReason"),
                )
                for value_introspect in enum_introspection["enumValues"]
            },
        )

    def build_input_object_def(
        input_object_introspection: Dict
    ) -> GraphQLInputObjectType:
        if input_object_introspection.get("inputFields") is None:
            raise TypeError(
                "Introspection result missing inputFields:"
                f" {input_object_introspection!r}"
            )
        return GraphQLInputObjectType(
            name=input_object_introspection["name"],
            description=input_object_introspection.get("description"),
            fields=lambda: build_input_value_def_map(
                input_object_introspection["inputFields"]
            ),
        )

    type_builders: Dict[str, Callable[[Dict], GraphQLType]] = {
        TypeKind.SCALAR.name: build_scalar_def,
        TypeKind.OBJECT.name: build_object_def,
        TypeKind.INTERFACE.name: build_interface_def,
        TypeKind.UNION.name: build_union_def,
        TypeKind.ENUM.name: build_enum_def,
        TypeKind.INPUT_OBJECT.name: build_input_object_def,
    }

    def build_field(field_introspection: Dict) -> GraphQLField:
        if field_introspection.get("args") is None:
            raise TypeError(
                "Introspection result missing field args:" f" {field_introspection!r}"
            )
        return GraphQLField(
            get_output_type(field_introspection["type"]),
            args=build_arg_value_def_map(field_introspection["args"]),
            description=field_introspection.get("description"),
            deprecation_reason=field_introspection.get("deprecationReason"),
        )

    def build_field_def_map(type_introspection: Dict) -> Dict[str, GraphQLField]:
        if type_introspection.get("fields") is None:
            raise TypeError(
                "Introspection result missing fields:" f" {type_introspection!r}"
            )
        return {
            field_introspection["name"]: build_field(field_introspection)
            for field_introspection in type_introspection["fields"]
        }

    def build_arg_value(arg_introspection: Dict) -> GraphQLArgument:
        type_ = get_input_type(arg_introspection["type"])
        default_value = arg_introspection.get("defaultValue")
        default_value = (
            INVALID
            if default_value is None
            else value_from_ast(parse_value(default_value), type_)
        )
        return GraphQLArgument(
            type_,
            default_value=default_value,
            description=arg_introspection.get("description"),
        )

    def build_arg_value_def_map(arg_introspections: Dict) -> Dict[str, GraphQLArgument]:
        return {
            input_value_introspection["name"]: build_arg_value(
                input_value_introspection
            )
            for input_value_introspection in arg_introspections
        }

    def build_input_value(input_value_introspection: Dict) -> GraphQLInputField:
        type_ = get_input_type(input_value_introspection["type"])
        default_value = input_value_introspection.get("defaultValue")
        default_value = (
            INVALID
            if default_value is None
            else value_from_ast(parse_value(default_value), type_)
        )
        return GraphQLInputField(
            type_,
            default_value=default_value,
            description=input_value_introspection.get("description"),
        )

    def build_input_value_def_map(
        input_value_introspections: Dict
    ) -> Dict[str, GraphQLInputField]:
        return {
            input_value_introspection["name"]: build_input_value(
                input_value_introspection
            )
            for input_value_introspection in input_value_introspections
        }

    def build_directive(directive_introspection: Dict) -> GraphQLDirective:
        if directive_introspection.get("args") is None:
            raise TypeError(
                "Introspection result missing directive args:"
                f" {directive_introspection!r}"
            )
        if directive_introspection.get("locations") is None:
            raise TypeError(
                "Introspection result missing directive locations:"
                f" {directive_introspection!r}"
            )
        return GraphQLDirective(
            name=directive_introspection["name"],
            description=directive_introspection.get("description"),
            locations=list(
                cast(
                    Sequence[DirectiveLocation],
                    directive_introspection.get("locations"),
                )
            ),
            args=build_arg_value_def_map(directive_introspection["args"]),
        )

    # Iterate through all types, getting the type definition for each, ensuring
    # that any type not directly referenced by a field will get created.
    types = [get_named_type(name) for name in type_introspection_map]

    # Get the root Query, Mutation, and Subscription types.

    query_type_ref = schema_introspection.get("queryType")
    query_type = get_object_type(query_type_ref) if query_type_ref else None
    mutation_type_ref = schema_introspection.get("mutationType")
    mutation_type = get_object_type(mutation_type_ref) if mutation_type_ref else None
    subscription_type_ref = schema_introspection.get("subscriptionType")
    subscription_type = (
        get_object_type(subscription_type_ref) if subscription_type_ref else None
    )

    # Get the directives supported by Introspection, assuming empty-set if
    # directives were not queried for.
    directive_introspections = schema_introspection.get("directives")
    directives = (
        [
            build_directive(directive_introspection)
            for directive_introspection in directive_introspections
        ]
        if directive_introspections
        else []
    )

    return GraphQLSchema(
        query=query_type,
        mutation=mutation_type,
        subscription=subscription_type,
        types=types,
        directives=directives,
        assume_valid=assume_valid,
    )
