from operator import attrgetter
from typing import Collection, Dict, List, cast

from ..type import (
    GraphQLArgument,
    GraphQLDirective,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLUnionType,
    is_enum_type,
    is_input_object_type,
    is_interface_type,
    is_introspection_type,
    is_list_type,
    is_non_null_type,
    is_object_type,
    is_scalar_type,
    is_specified_scalar_type,
    is_union_type,
)

__all__ = ["lexicographic_sort_schema"]


def lexicographic_sort_schema(schema: GraphQLSchema) -> GraphQLSchema:
    """Sort GraphQLSchema."""

    cache: Dict[str, GraphQLNamedType] = {}

    def sort_maybe_type(maybe_type):
        return maybe_type and sort_named_type(maybe_type)

    def sort_directive(directive):
        return GraphQLDirective(
            name=directive.name,
            description=directive.description,
            locations=sorted(directive.locations, key=attrgetter("name")),
            args=sort_args(directive.args),
            ast_node=directive.ast_node,
        )

    def sort_args(args):
        return {
            name: GraphQLArgument(
                sort_type(arg.type),
                default_value=arg.default_value,
                description=arg.description,
                ast_node=arg.ast_node,
            )
            for name, arg in sorted(args.items())
        }

    def sort_fields(fields_map):
        return {
            name: GraphQLField(
                sort_type(field.type),
                args=sort_args(field.args),
                resolve=field.resolve,
                subscribe=field.subscribe,
                description=field.description,
                deprecation_reason=field.deprecation_reason,
                ast_node=field.ast_node,
            )
            for name, field in sorted(fields_map.items())
        }

    def sort_input_fields(fields_map):
        return {
            name: GraphQLInputField(
                sort_type(field.type),
                description=field.description,
                default_value=field.default_value,
                ast_node=field.ast_node,
            )
            for name, field in sorted(fields_map.items())
        }

    def sort_type(type_):
        if is_list_type(type_):
            return GraphQLList(sort_type(type_.of_type))
        elif is_non_null_type(type_):
            return GraphQLNonNull(sort_type(type_.of_type))
        else:
            return sort_named_type(type_)

    def sort_named_type(type_: GraphQLNamedType) -> GraphQLNamedType:
        if is_specified_scalar_type(type_) or is_introspection_type(type_):
            return type_

        sorted_type = cache.get(type_.name)
        if not sorted_type:
            sorted_type = sort_named_type_impl(type_)
            cache[type_.name] = sorted_type
        return sorted_type

    def sort_types(arr: Collection[GraphQLNamedType]) -> List[GraphQLNamedType]:
        return [sort_named_type(type_) for type_ in sorted(arr, key=attrgetter("name"))]

    def sort_named_type_impl(type_: GraphQLNamedType) -> GraphQLNamedType:
        if is_scalar_type(type_):
            return type_
        elif is_object_type(type_):
            type1 = cast(GraphQLObjectType, type_)
            return GraphQLObjectType(
                type_.name,
                interfaces=lambda: cast(
                    List[GraphQLInterfaceType], sort_types(type1.interfaces)
                ),
                fields=lambda: sort_fields(type1.fields),
                is_type_of=type1.is_type_of,
                description=type_.description,
                ast_node=type1.ast_node,
                extension_ast_nodes=type1.extension_ast_nodes,
            )
        elif is_interface_type(type_):
            type2 = cast(GraphQLInterfaceType, type_)
            return GraphQLInterfaceType(
                type_.name,
                fields=lambda: sort_fields(type2.fields),
                resolve_type=type2.resolve_type,
                description=type_.description,
                ast_node=type2.ast_node,
                extension_ast_nodes=type2.extension_ast_nodes,
            )
        elif is_union_type(type_):
            type3 = cast(GraphQLUnionType, type_)
            return GraphQLUnionType(
                type_.name,
                types=lambda: cast(List[GraphQLObjectType], sort_types(type3.types)),
                resolve_type=type3.resolve_type,
                description=type_.description,
                ast_node=type3.ast_node,
            )
        elif is_enum_type(type_):
            type4 = cast(GraphQLEnumType, type_)
            return GraphQLEnumType(
                type_.name,
                values={
                    name: GraphQLEnumValue(
                        val.value,
                        description=val.description,
                        deprecation_reason=val.deprecation_reason,
                        ast_node=val.ast_node,
                    )
                    for name, val in sorted(type4.values.items())
                },
                description=type_.description,
                ast_node=type4.ast_node,
            )
        elif is_input_object_type(type_):
            type5 = cast(GraphQLInputObjectType, type_)
            return GraphQLInputObjectType(
                type_.name,
                sort_input_fields(type5.fields),
                description=type_.description,
                ast_node=type5.ast_node,
            )
        raise TypeError(f"Unknown type: '{type_}'")

    return GraphQLSchema(
        types=sort_types(schema.type_map.values()),
        directives=[
            sort_directive(directive)
            for directive in sorted(schema.directives, key=attrgetter("name"))
        ],
        query=sort_maybe_type(schema.query_type),
        mutation=sort_maybe_type(schema.mutation_type),
        subscription=sort_maybe_type(schema.subscription_type),
        ast_node=schema.ast_node,
    )
