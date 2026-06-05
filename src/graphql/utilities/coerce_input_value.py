"""Input value coercion"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeAlias, cast

from ..error import GraphQLError
from ..language import (
    ListValueNode,
    NullValueNode,
    ObjectValueNode,
    ValueNode,
    VariableNode,
)
from ..pyutils import (
    Path,
    Undefined,
    did_you_mean,
    inspect,
    is_iterable,
    print_path_list,
    suggestion_list,
)
from ..type import (
    GraphQLDefaultValueUsage,
    GraphQLInputType,
    GraphQLScalarType,
    assert_leaf_type,
    is_input_object_type,
    is_leaf_type,
    is_list_type,
    is_non_null_type,
    is_required_input_field,
)

if TYPE_CHECKING:
    from ..execution.collect_fields import FragmentVariables

__all__ = ["coerce_default_value", "coerce_input_literal", "coerce_input_value"]


OnErrorCB: TypeAlias = Callable[[list[str | int], Any, GraphQLError], None]


def default_on_error(
    path: list[str | int], invalid_value: Any, error: GraphQLError
) -> None:
    error_prefix = "Invalid value " + inspect(invalid_value)
    if path:
        error_prefix += f" at 'value{print_path_list(path)}'"
    error.message = error_prefix + ": " + error.message
    raise error


def coerce_input_value(
    input_value: Any,
    type_: GraphQLInputType,
    on_error: OnErrorCB = default_on_error,
    path: Path | None = None,
) -> Any:
    """Coerce a Python value given a GraphQL Input Type."""
    if is_non_null_type(type_):
        if input_value is not None and input_value is not Undefined:
            return coerce_input_value(input_value, type_.of_type, on_error, path)
        on_error(
            path.as_list() if path else [],
            input_value,
            GraphQLError(
                f"Expected non-nullable type '{inspect(type_)}' not to be None."
            ),
        )
        return Undefined

    if input_value is None or input_value is Undefined:
        # Explicitly return the value null.
        return None

    if is_list_type(type_):
        item_type = type_.of_type
        if is_iterable(input_value):
            coerced_list: list[Any] = []
            append_item = coerced_list.append
            for index, item_value in enumerate(input_value):
                append_item(
                    coerce_input_value(
                        item_value, item_type, on_error, Path(path, index, None)
                    )
                )
            return coerced_list
        # Lists accept a non-list value as a list of one.
        return [coerce_input_value(input_value, item_type, on_error, path)]

    if is_input_object_type(type_):
        if not isinstance(input_value, dict):
            on_error(
                path.as_list() if path else [],
                input_value,
                GraphQLError(f"Expected type '{type_}' to be a mapping."),
            )
            return Undefined

        coerced_dict: dict[str, Any] = {}
        fields = type_.fields

        for field_name, field in fields.items():
            field_value = input_value.get(field_name, Undefined)

            if field_value is Undefined:
                if field.default_value:
                    # Use out name as name if it exists (extension of GraphQL.js).
                    coerced_dict[field.out_name or field_name] = coerce_default_value(
                        field.default_value, field.type
                    )
                elif is_non_null_type(field.type):  # pragma: no branch
                    type_str = inspect(field.type)
                    on_error(
                        path.as_list() if path else [],
                        input_value,
                        GraphQLError(
                            f"Field '{type_}.{field_name}' of required type"
                            f" '{type_str}' was not provided."
                        ),
                    )
                continue

            coerced_dict[field.out_name or field_name] = coerce_input_value(
                field_value, field.type, on_error, Path(path, field_name, type_.name)
            )

        # Ensure every provided field is defined.
        for field_name in input_value:
            if field_name not in fields:
                suggestions = suggestion_list(field_name, fields)
                on_error(
                    path.as_list() if path else [],
                    input_value,
                    GraphQLError(
                        f"Field '{field_name}' is not defined by type '{type_}'."
                        + did_you_mean(suggestions)
                    ),
                )

        if type_.is_one_of:
            keys = list(coerced_dict)
            if len(keys) != 1:
                on_error(
                    path.as_list() if path else [],
                    input_value,
                    GraphQLError(
                        f"Exactly one key must be specified for OneOf type '{type_}'.",
                    ),
                )
            else:
                key = keys[0]
                value = coerced_dict[key]
                if value is None:
                    on_error(
                        (path.as_list() if path else []) + [key],
                        value,
                        GraphQLError(
                            f"Field '{key}' must be non-null.",
                        ),
                    )

        return type_.out_type(coerced_dict)

    if is_leaf_type(type_):
        # Scalars and Enums determine if an input value is valid via `parse_value()`,
        # which can throw to indicate failure. If it throws, maintain a reference
        # to the original error.
        type_ = cast("GraphQLScalarType", type_)
        try:
            parse_result = type_.parse_value(input_value)
        except GraphQLError as error:
            on_error(path.as_list() if path else [], input_value, error)
            return Undefined
        except Exception as error:  # noqa: BLE001
            on_error(
                path.as_list() if path else [],
                input_value,
                GraphQLError(f"Expected type '{type_}'. {error}", original_error=error),
            )
            return Undefined
        if parse_result is Undefined:
            on_error(
                path.as_list() if path else [],
                input_value,
                GraphQLError(f"Expected type '{type_}'."),
            )
        return parse_result

    # Not reachable. All possible input types have been considered.
    msg = f"Unexpected input type: {inspect(type_)}."  # pragma: no cover
    raise TypeError(msg)  # pragma: no cover


def coerce_input_literal(
    value_node: ValueNode,
    type_: GraphQLInputType,
    variable_values: dict[str, Any] | None = None,
    fragment_variable_values: FragmentVariables | None = None,
) -> Any:
    """Produce a coerced Python value given a GraphQL Value AST.

    Returns ``Undefined`` when the value could not be validly coerced according
    to the provided type.

    Unlike :func:`~graphql.utilities.value_from_ast`, this properly supports
    fragment variables in addition to operation variables.
    """
    if isinstance(value_node, VariableNode):
        variable_value = get_variable_value(
            value_node, variable_values, fragment_variable_values
        )
        if (variable_value is None or variable_value is Undefined) and is_non_null_type(
            type_
        ):
            return Undefined  # Invalid: intentionally return no value.
        # Note: This does no further checking that this variable is correct.
        # This assumes validation has checked this variable is of the correct type.
        return variable_value

    if is_non_null_type(type_):
        if isinstance(value_node, NullValueNode):
            return Undefined  # Invalid: intentionally return no value.
        return coerce_input_literal(
            value_node, type_.of_type, variable_values, fragment_variable_values
        )

    if isinstance(value_node, NullValueNode):
        return None  # Explicitly return the value null.

    if is_list_type(type_):
        item_type = type_.of_type
        if not isinstance(value_node, ListValueNode):
            # Lists accept a non-list value as a list of one.
            item_value = coerce_input_literal(
                value_node, item_type, variable_values, fragment_variable_values
            )
            if item_value is Undefined:
                return Undefined  # Invalid: intentionally return no value.
            return [item_value]
        coerced_list: list[Any] = []
        for item_node in value_node.values:
            item_value = coerce_input_literal(
                item_node, item_type, variable_values, fragment_variable_values
            )
            if item_value is Undefined:
                if (
                    isinstance(item_node, VariableNode)
                    and not is_non_null_type(item_type)
                    and _variable_value_is_null(
                        item_node, variable_values, fragment_variable_values
                    )
                ):
                    # A missing variable within a list is coerced to null.
                    coerced_list.append(None)
                    continue
                return Undefined  # Invalid: intentionally return no value.
            coerced_list.append(item_value)
        return coerced_list

    if is_input_object_type(type_):
        if not isinstance(value_node, ObjectValueNode):
            return Undefined  # Invalid: intentionally return no value.

        coerced_dict: dict[str, Any] = {}
        field_defs = type_.fields
        field_nodes = {field.name.value: field for field in value_node.fields}
        # Ensure every provided field is defined.
        if any(field_name not in field_defs for field_name in field_nodes):
            return Undefined  # Invalid: intentionally return no value.
        for field_name, field in field_defs.items():
            field_node = field_nodes.get(field_name)
            if field_node is None or (
                isinstance(field_node.value, VariableNode)
                and _variable_value_is_null(
                    field_node.value, variable_values, fragment_variable_values
                )
            ):
                if is_required_input_field(field):
                    return Undefined  # Invalid: intentionally return no value.
                if field.default_value:
                    # Use out name as name if it exists (extension of GraphQL.js).
                    coerced_dict[field.out_name or field_name] = coerce_default_value(
                        field.default_value, field.type
                    )
            else:
                field_value = coerce_input_literal(
                    field_node.value,
                    field.type,
                    variable_values,
                    fragment_variable_values,
                )
                if field_value is Undefined:
                    return Undefined  # Invalid: intentionally return no value.
                coerced_dict[field.out_name or field_name] = field_value

        if type_.is_one_of:
            keys = list(coerced_dict)
            if len(keys) != 1:
                # Invalid: not exactly one key, intentionally return no value.
                return Undefined
            if coerced_dict[keys[0]] is None:
                # Invalid: value not non-null, intentionally return no value.
                return Undefined

        return type_.out_type(coerced_dict)

    leaf_type = assert_leaf_type(type_)
    try:
        if variable_values:
            return leaf_type.parse_literal(value_node, variable_values)
        return leaf_type.parse_literal(value_node)
    except Exception:  # noqa: BLE001
        # Invalid: ignore error and intentionally return no value.
        return Undefined


def coerce_default_value(
    default_value: GraphQLDefaultValueUsage, type_: GraphQLInputType
) -> Any:
    """Coerce a default value usage to a Python value.

    .. internal::
    """
    # Memoize the result of coercing the default value in a hidden field.
    coerced_value = default_value._memoized_coerced_value  # noqa: SLF001
    if coerced_value is Undefined:
        coerced_value = (
            coerce_input_literal(default_value.literal, type_)
            if default_value.literal is not None
            else default_value.value
        )
        default_value._memoized_coerced_value = coerced_value  # noqa: SLF001
    return coerced_value


def get_variable_value(
    variable_node: VariableNode,
    variable_values: dict[str, Any] | None,
    fragment_variable_values: FragmentVariables | None,
) -> Any:
    """Retrieve the variable value for the given variable node."""
    var_name = variable_node.name.value
    if fragment_variable_values and fragment_variable_values.signatures.get(var_name):
        return fragment_variable_values.values.get(var_name, Undefined)
    if variable_values:
        return variable_values.get(var_name, Undefined)
    return Undefined


def _variable_value_is_null(
    variable_node: VariableNode,
    variable_values: dict[str, Any] | None,
    fragment_variable_values: FragmentVariables | None,
) -> bool:
    """Check whether the given variable node resolves to null or undefined."""
    variable_value = get_variable_value(
        variable_node, variable_values, fragment_variable_values
    )
    return variable_value is None or variable_value is Undefined
