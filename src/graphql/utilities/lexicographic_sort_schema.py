"""Sorting GraphQL schemas"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar, cast

from ..pyutils import natural_comparison_key
from ..type import GraphQLSchema
from .map_schema_config import SchemaElementKind, map_schema_config

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping

    from .map_schema_config import ConfigMapperMap, MappedSchemaContext

__all__ = ["lexicographic_sort_schema"]

T = TypeVar("T")


def lexicographic_sort_schema(schema: GraphQLSchema) -> GraphQLSchema:
    """Sort GraphQLSchema.

    This function returns a sorted copy of the given GraphQLSchema.
    """

    def config_mapper_map_fn(_context: MappedSchemaContext) -> ConfigMapperMap:
        return cast(
            "ConfigMapperMap",
            {
                SchemaElementKind.OBJECT: lambda config: {
                    **config,
                    "interfaces": lambda: sort_by_name(config["interfaces"]()),
                    "fields": lambda: sort_obj_map(config["fields"]()),
                },
                SchemaElementKind.FIELD: lambda config, *_args: {
                    **config,
                    "args": sort_obj_map(config["args"]),
                },
                SchemaElementKind.INTERFACE: lambda config: {
                    **config,
                    "interfaces": lambda: sort_by_name(config["interfaces"]()),
                    "fields": lambda: sort_obj_map(config["fields"]()),
                },
                SchemaElementKind.UNION: lambda config: {
                    **config,
                    "types": lambda: sort_by_name(config["types"]()),
                },
                SchemaElementKind.ENUM: lambda config: {
                    **config,
                    "values": lambda: sort_obj_map(config["values"]()),
                },
                SchemaElementKind.INPUT_OBJECT: lambda config: {
                    **config,
                    "fields": lambda: sort_obj_map(config["fields"]()),
                },
                SchemaElementKind.DIRECTIVE: lambda config: {
                    **config,
                    "locations": sort_by(config["locations"], lambda x: x.name),
                    "args": sort_obj_map(config["args"]),
                },
                SchemaElementKind.SCHEMA: lambda config: {
                    **config,
                    "types": sort_by_name(config["types"]),
                    "directives": sort_by_name(config["directives"]),
                },
            },
        )

    return GraphQLSchema(**map_schema_config(schema.to_kwargs(), config_mapper_map_fn))


def sort_obj_map(map_: Mapping[str, T]) -> dict[str, T]:
    """Sort the values of an object map by their keys in natural sort order."""
    return {key: map_[key] for key in sorted(map_, key=natural_comparison_key)}


def sort_by_name(array: Collection[Any]) -> list[Any]:
    """Sort a collection of named objects by their name in natural sort order."""
    return sort_by(array, lambda obj: obj.name)


def sort_by(array: Collection[T], map_to_key: Callable[[T], str]) -> list[T]:
    """Sort a collection by a derived key in natural sort order."""
    return sorted(array, key=lambda item: natural_comparison_key(map_to_key(item)))
