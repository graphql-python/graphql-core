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
        kwargs = directive.to_kwargs()
        kwargs.update(
            locations=sorted(directive.locations, key=attrgetter("name")),
            args=sort_args(directive.args),
        )
        return GraphQLDirective(**kwargs)

    def sort_args(args_map):
        args = {}
        for name, arg in sorted(args_map.items()):
            kwargs = arg.to_kwargs()
            kwargs.update(type_=sort_type(arg.type))
            args[name] = GraphQLArgument(**kwargs)
        return args

    def sort_fields(fields_map):
        fields = {}
        for name, field in sorted(fields_map.items()):
            kwargs = field.to_kwargs()
            kwargs.update(type_=sort_type(field.type), args=sort_args(field.args))
            fields[name] = GraphQLField(**kwargs)
        return fields

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
            kwargs = type_.to_kwargs()
            object_type = cast(GraphQLObjectType, type_)
            kwargs.update(
                interfaces=lambda: sort_types(object_type.interfaces),
                fields=lambda: sort_fields(object_type.fields),
            )
            return GraphQLObjectType(**kwargs)
        elif is_interface_type(type_):
            kwargs = type_.to_kwargs()
            interface_type = cast(GraphQLInterfaceType, type_)
            kwargs.update(fields=lambda: sort_fields(interface_type.fields))
            return GraphQLInterfaceType(**kwargs)
        elif is_union_type(type_):
            kwargs = type_.to_kwargs()
            union_type = cast(GraphQLUnionType, type_)
            kwargs.update(types=lambda: sort_types(union_type.types))
            return GraphQLUnionType(**kwargs)
        elif is_enum_type(type_):
            kwargs = type_.to_kwargs()
            enum_type = cast(GraphQLEnumType, type_)
            kwargs.update(
                values={
                    name: GraphQLEnumValue(
                        val.value,
                        description=val.description,
                        deprecation_reason=val.deprecation_reason,
                        ast_node=val.ast_node,
                    )
                    for name, val in sorted(enum_type.values.items())
                }
            )
            return GraphQLEnumType(**kwargs)
        elif is_input_object_type(type_):
            kwargs = type_.to_kwargs()
            input_object_type = cast(GraphQLInputObjectType, type_)
            kwargs.update(fields=sort_input_fields(input_object_type.fields))
            return GraphQLInputObjectType(**kwargs)
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
