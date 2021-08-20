from typing import Dict, List, Optional, Tuple, Union, cast

from ..language import DirectiveLocation
from ..pyutils import inspect, natural_comparison_key, FrozenList
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
    """Sort GraphQLSchema.

    This function returns a sorted copy of the given GraphQLSchema.
    """

    def replace_type(
        type_: Union[GraphQLList, GraphQLNonNull, GraphQLNamedType]
    ) -> Union[GraphQLList, GraphQLNonNull, GraphQLNamedType]:
        if is_list_type(type_):
            return GraphQLList(replace_type(cast(GraphQLList, type_).of_type))
        if is_non_null_type(type_):
            return GraphQLNonNull(replace_type(cast(GraphQLNonNull, type_).of_type))
        return replace_named_type(cast(GraphQLNamedType, type_))

    def replace_named_type(type_: GraphQLNamedType) -> GraphQLNamedType:
        return type_map[type_.name]

    def replace_maybe_type(
        maybe_type: Optional[GraphQLNamedType],
    ) -> Optional[GraphQLNamedType]:
        return maybe_type and replace_named_type(maybe_type)

    def sort_directive(directive: GraphQLDirective) -> GraphQLDirective:
        kwargs = directive.to_kwargs()
        kwargs.update(
            locations=sorted(directive.locations, key=sort_by_name_key),
            args=sort_args(directive.args),
        )
        return GraphQLDirective(**kwargs)

    def sort_args(args_map: Dict[str, GraphQLArgument]) -> Dict[str, GraphQLArgument]:
        args = {}
        for name, arg in sorted(args_map.items()):
            kwargs = arg.to_kwargs()
            kwargs.update(type_=replace_type(cast(GraphQLNamedType, arg.type)))
            args[name] = GraphQLArgument(**kwargs)
        return args

    def sort_fields(fields_map: Dict[str, GraphQLField]) -> Dict[str, GraphQLField]:
        fields = {}
        for name, field in sorted(fields_map.items()):
            kwargs = field.to_kwargs()
            kwargs.update(
                type_=replace_type(cast(GraphQLNamedType, field.type)),
                args=sort_args(field.args),
            )
            fields[name] = GraphQLField(**kwargs)
        return fields

    def sort_input_fields(
        fields_map: Dict[str, GraphQLInputField]
    ) -> Dict[str, GraphQLInputField]:
        return {
            name: GraphQLInputField(
                cast(
                    GraphQLInputType, replace_type(cast(GraphQLNamedType, field.type))
                ),
                description=field.description,
                default_value=field.default_value,
                ast_node=field.ast_node,
            )
            for name, field in sorted(fields_map.items())
        }

    def sort_types(arr: FrozenList[GraphQLNamedType]) -> List[GraphQLNamedType]:
        return [
            replace_named_type(type_) for type_ in sorted(arr, key=sort_by_name_key)
        ]

    def sort_named_type(type_: GraphQLNamedType) -> GraphQLNamedType:
        if is_scalar_type(type_) or is_introspection_type(type_):
            return type_
        if is_object_type(type_):
            kwargs = type_.to_kwargs()
            type_ = cast(GraphQLObjectType, type_)
            kwargs.update(
                interfaces=lambda: sort_types(type_.interfaces),
                fields=lambda: sort_fields(type_.fields),
            )
            return GraphQLObjectType(**kwargs)
        if is_interface_type(type_):
            kwargs = type_.to_kwargs()
            type_ = cast(GraphQLInterfaceType, type_)
            kwargs.update(
                interfaces=lambda: sort_types(type_.interfaces),
                fields=lambda: sort_fields(type_.fields),
            )
            return GraphQLInterfaceType(**kwargs)
        if is_union_type(type_):
            kwargs = type_.to_kwargs()
            type_ = cast(GraphQLUnionType, type_)
            kwargs.update(types=lambda: sort_types(type_.types))
            return GraphQLUnionType(**kwargs)
        if is_enum_type(type_):
            kwargs = type_.to_kwargs()
            type_ = cast(GraphQLEnumType, type_)
            kwargs.update(
                values={
                    name: GraphQLEnumValue(
                        val.value,
                        description=val.description,
                        deprecation_reason=val.deprecation_reason,
                        ast_node=val.ast_node,
                    )
                    for name, val in sorted(type_.values.items())
                }
            )
            return GraphQLEnumType(**kwargs)
        if is_input_object_type(type_):
            kwargs = type_.to_kwargs()
            type_ = cast(GraphQLInputObjectType, type_)
            kwargs.update(fields=lambda: sort_input_fields(type_.fields))
            return GraphQLInputObjectType(**kwargs)

        # Not reachable. All possible types have been considered.
        raise TypeError(f"Unexpected type: {inspect(type_)}.")

    type_map: Dict[str, GraphQLNamedType] = {
        type_.name: sort_named_type(type_)
        for type_ in sorted(schema.type_map.values(), key=sort_by_name_key)
    }

    return GraphQLSchema(
        types=type_map.values(),
        directives=[
            sort_directive(directive)
            for directive in sorted(schema.directives, key=sort_by_name_key)
        ],
        query=cast(Optional[GraphQLObjectType], replace_maybe_type(schema.query_type)),
        mutation=cast(
            Optional[GraphQLObjectType], replace_maybe_type(schema.mutation_type)
        ),
        subscription=cast(
            Optional[GraphQLObjectType], replace_maybe_type(schema.subscription_type)
        ),
        ast_node=schema.ast_node,
    )


def sort_by_name_key(
    type_: Union[GraphQLNamedType, GraphQLDirective, DirectiveLocation]
) -> Tuple:
    return natural_comparison_key(type_.name)
