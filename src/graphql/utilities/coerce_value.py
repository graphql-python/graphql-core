from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Union, cast

from ..error import GraphQLError, INVALID
from ..language import Node
from ..pyutils import did_you_mean, inspect, is_invalid, suggestion_list
from ..type import (
    GraphQLEnumType,
    GraphQLInputObjectType,
    GraphQLInputType,
    GraphQLList,
    GraphQLScalarType,
    is_enum_type,
    is_input_object_type,
    is_list_type,
    is_non_null_type,
    is_scalar_type,
    GraphQLNonNull,
)

__all__ = ["coerce_value", "CoercedValue"]


class CoercedValue(NamedTuple):
    errors: Optional[List[GraphQLError]]
    value: Any


class Path(NamedTuple):
    prev: Any  # Optional['Path'] (python/mypy/issues/731)
    key: Union[str, int]


def coerce_value(
    value: Any, type_: GraphQLInputType, blame_node: Node = None, path: Path = None
) -> CoercedValue:
    """Coerce a Python value given a GraphQL Type.

    Returns either a value which is valid for the provided type or a list of encountered
    coercion errors.
    """
    # A value must be provided if the type is non-null.
    if is_non_null_type(type_):
        if value is None or value is INVALID:
            return of_errors(
                [
                    coercion_error(
                        f"Expected non-nullable type {type_} not to be null",
                        blame_node,
                        path,
                    )
                ]
            )
        type_ = cast(GraphQLNonNull, type_)
        return coerce_value(value, type_.of_type, blame_node, path)

    if value is None or value is INVALID:
        # Explicitly return the value null.
        return of_value(None)

    if is_scalar_type(type_):
        # Scalars determine if a value is valid via `parse_value()`, which can throw to
        # indicate failure. If it throws, maintain a reference to the original error.
        type_ = cast(GraphQLScalarType, type_)
        try:
            parse_result = type_.parse_value(value)
            if is_invalid(parse_result):
                return of_errors(
                    [coercion_error(f"Expected type {type_.name}", blame_node, path)]
                )
            return of_value(parse_result)
        except (TypeError, ValueError) as error:
            return of_errors(
                [
                    coercion_error(
                        f"Expected type {type_.name}",
                        blame_node,
                        path,
                        f" {error}",
                        error,
                    )
                ]
            )

    if is_enum_type(type_):
        type_ = cast(GraphQLEnumType, type_)
        values = type_.values
        if isinstance(value, str):
            enum_value = values.get(value)
            if enum_value:
                return of_value(value if enum_value.value is None else enum_value.value)
        suggestions = suggestion_list(str(value), values)
        return of_errors(
            [
                coercion_error(
                    f"Expected type {type_.name}",
                    blame_node,
                    path,
                    did_you_mean(suggestions),
                )
            ]
        )

    if is_list_type(type_):
        type_ = cast(GraphQLList, type_)
        item_type = type_.of_type
        if isinstance(value, Iterable) and not isinstance(value, str):
            errors = None
            coerced_value_list: List[Any] = []
            append_item = coerced_value_list.append
            for index, item_value in enumerate(value):
                coerced_item = coerce_value(
                    item_value, item_type, blame_node, at_path(path, index)
                )
                if coerced_item.errors:
                    errors = add(errors, *coerced_item.errors)
                elif not errors:
                    append_item(coerced_item.value)
            return of_errors(errors) if errors else of_value(coerced_value_list)
        # Lists accept a non-list value as a list of one.
        coerced_item = coerce_value(value, item_type, blame_node)
        return coerced_item if coerced_item.errors else of_value([coerced_item.value])

    if is_input_object_type(type_):
        type_ = cast(GraphQLInputObjectType, type_)
        if not isinstance(value, dict):
            return of_errors(
                [
                    coercion_error(
                        f"Expected type {type_.name} to be a dict", blame_node, path
                    )
                ]
            )
        errors = None
        coerced_value_dict: Dict[str, Any] = {}
        fields = type_.fields

        # Ensure every defined field is valid.
        for field_name, field in fields.items():
            field_value = value.get(field_name, INVALID)
            if is_invalid(field_value):
                if not is_invalid(field.default_value):
                    # Use out name as name if it exists (extension of GraphQL.js).
                    coerced_value_dict[
                        field.out_name or field_name
                    ] = field.default_value
                elif is_non_null_type(field.type):
                    errors = add(
                        errors,
                        coercion_error(
                            f"Field {print_path(at_path(path, field_name))}"
                            f" of required type {field.type} was not provided",
                            blame_node,
                        ),
                    )
            else:
                coerced_field = coerce_value(
                    field_value, field.type, blame_node, at_path(path, field_name)
                )
                if coerced_field.errors:
                    errors = add(errors, *coerced_field.errors)
                else:
                    coerced_value_dict[
                        field.out_name or field_name
                    ] = coerced_field.value

        # Ensure every provided field is defined.
        for field_name in value:
            if field_name not in fields:
                suggestions = suggestion_list(field_name, fields)
                errors = add(
                    errors,
                    coercion_error(
                        f"Field '{field_name}' is not defined by type {type_.name}",
                        blame_node,
                        path,
                        did_you_mean(suggestions),
                    ),
                )

        return (
            of_errors(errors)
            if errors
            else of_value(type_.out_type(coerced_value_dict))
        )

    # Not reachable. All possible input types have been considered.
    raise TypeError(f"Unexpected input type: '{inspect(type_)}'.")  # pragma: no cover


def of_value(value: Any) -> CoercedValue:
    return CoercedValue(None, value)


def of_errors(errors: List[GraphQLError]) -> CoercedValue:
    return CoercedValue(errors, INVALID)


def add(
    errors: Optional[List[GraphQLError]], *more_errors: GraphQLError
) -> List[GraphQLError]:
    return (errors or []) + list(more_errors)


def at_path(prev: Optional[Path], key: Union[str, int]) -> Path:
    return Path(prev, key)


def coercion_error(
    message: str,
    blame_node: Node = None,
    path: Path = None,
    sub_message: str = None,
    original_error: Exception = None,
) -> GraphQLError:
    """Return a GraphQLError instance"""
    path_str = print_path(path)
    if path_str:
        message += f" at {path_str}"
    message += "."
    if sub_message:
        message += sub_message
    # noinspection PyArgumentEqualDefault
    return GraphQLError(message, blame_node, None, None, None, original_error)


def print_path(path: Optional[Path]) -> str:
    """Build string describing the path into the value where error was found"""
    path_str = ""
    current_path: Optional[Path] = path
    while current_path:
        path_str = (
            f".{current_path.key}"
            if isinstance(current_path.key, str)
            else f"[{current_path.key}]"
        ) + path_str
        current_path = current_path.prev
    return f"value{path_str}" if path_str else ""
