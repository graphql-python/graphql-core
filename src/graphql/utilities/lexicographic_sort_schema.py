from typing import Dict, List, Tuple, cast

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
    is_union_type,
)

__all__ = ["lexicographic_sort_schema"]


def lexicographic_sort_schema(schema: GraphQLSchema) -> GraphQLSchema:
    """Sort GraphQLSchema."""

    def replace_type(type_):
        if is_list_type(type_):
            return GraphQLList(replace_type(type_.of_type))
        elif is_non_null_type(type_):
            return GraphQLNonNull(replace_type(type_.of_type))
        else:
            return replace_named_type(type_)

    def replace_named_type(type_: GraphQLNamedType) -> GraphQLNamedType:
        return type_map[type_.name]

    def replace_maybe_type(maybe_type):
        return maybe_type and replace_named_type(maybe_type)

    def sort_directive(directive):
        kwargs = directive.to_kwargs()
        kwargs.update(
            locations=sorted(directive.locations, key=sort_by_name_key),
            args=sort_args(directive.args),
        )
        return GraphQLDirective(**kwargs)

    def sort_args(args_map):
        args = {}
        for name, arg in sorted(args_map.items()):
            kwargs = arg.to_kwargs()
            kwargs.update(type_=replace_type(arg.type))
            args[name] = GraphQLArgument(**kwargs)
        return args

    def sort_fields(fields_map):
        fields = {}
        for name, field in sorted(fields_map.items()):
            kwargs = field.to_kwargs()
            kwargs.update(type_=replace_type(field.type), args=sort_args(field.args))
            fields[name] = GraphQLField(**kwargs)
        return fields

    def sort_input_fields(fields_map):
        return {
            name: GraphQLInputField(
                replace_type(field.type),
                description=field.description,
                default_value=field.default_value,
                ast_node=field.ast_node,
            )
            for name, field in sorted(fields_map.items())
        }

    def sort_types(arr: List[GraphQLNamedType]) -> List[GraphQLNamedType]:
        return [
            replace_named_type(type_) for type_ in sorted(arr, key=sort_by_name_key)
        ]

    def sort_named_type(type_: GraphQLNamedType) -> GraphQLNamedType:
        if is_scalar_type(type_) or is_introspection_type(type_):
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
            kwargs.update(fields=lambda: sort_input_fields(input_object_type.fields))
            return GraphQLInputObjectType(**kwargs)

        # Not reachable. All possible types have been considered.
        raise TypeError(f"Unexpected type: '{inspect(type_)}'.")  # pragma: no cover

    type_map: Dict[str, GraphQLNamedType] = {
        type_.name: sort_named_type(type_)
        for type_ in sorted(schema.type_map.values(), key=sort_by_name_key)
    }

    return GraphQLSchema(
        types=list(type_map.values()),
        directives=[
            sort_directive(directive)
            for directive in sorted(schema.directives, key=sort_by_name_key)
        ],
        query=replace_maybe_type(schema.query_type),
        mutation=replace_maybe_type(schema.mutation_type),
        subscription=replace_maybe_type(schema.subscription_type),
        ast_node=schema.ast_node,
    )


def sort_by_name_key(type_) -> Tuple[bool, str]:
    name = type_.name
    # GraphQL.JS sorts '_' first using localeCompare
    return not name.startswith("_"), name
