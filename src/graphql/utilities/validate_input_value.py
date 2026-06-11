"""Input value validation"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, NamedTuple, cast

from ..error import GraphQLError
from ..language import (
    ListValueNode,
    Node,
    NullValueNode,
    ObjectValueNode,
    ValueNode,
    VariableNode,
    print_ast,
)
from ..pyutils import (
    Path,
    Undefined,
    did_you_mean,
    inspect,
    is_iterable,
    suggestion_list,
)
from ..type import (
    GraphQLInputType,
    GraphQLScalarType,
    assert_leaf_type,
    is_enum_type,
    is_input_object_type,
    is_list_type,
    is_non_null_type,
    is_required_input_field,
)
from .replace_variables import replace_variables

if TYPE_CHECKING:
    from ..execution.values import FragmentVariableValues, VariableValues

__all__ = ["validate_input_literal", "validate_input_value"]


OnErrorCB = Callable[[GraphQLError, "list[str | int]"], None]


def validate_input_value(
    input_value: Any,
    type_: GraphQLInputType,
    on_error: OnErrorCB,
    hide_suggestions: bool = False,
) -> None:
    """Validate that the provided input value is allowed for this type.

    All errors are collected via a callback function.
    """
    validate_input_value_impl(input_value, type_, on_error, hide_suggestions, None)


def validate_input_value_impl(
    input_value: Any,
    type_: GraphQLInputType,
    on_error: OnErrorCB,
    hide_suggestions: bool,
    path: Path | None,
) -> None:
    if is_non_null_type(type_):
        if input_value is Undefined:
            report_invalid_value(
                on_error,
                f"Expected a value of non-null type '{type_}' to be provided.",
                path,
            )
            return
        if input_value is None:
            report_invalid_value(
                on_error,
                f"Expected value of non-null type '{type_}' not to be None.",
                path,
            )
            return
        validate_input_value_impl(
            input_value, type_.of_type, on_error, hide_suggestions, path
        )
        return

    if input_value is None or input_value is Undefined:
        return

    if is_list_type(type_):
        item_type = type_.of_type
        if not is_iterable(input_value):
            # Lists accept a non-list value as a list of one.
            validate_input_value_impl(
                input_value, item_type, on_error, hide_suggestions, path
            )
        else:
            for index, item_value in enumerate(input_value):
                validate_input_value_impl(
                    item_value,
                    item_type,
                    on_error,
                    hide_suggestions,
                    Path(path, index, None),
                )
    elif is_input_object_type(type_):
        if not isinstance(input_value, dict):
            report_invalid_value(
                on_error,
                f"Expected value of type '{type_}' to be an object,"
                f" found: {inspect(input_value)}.",
                path,
            )
            return

        field_defs = type_.fields

        for field_name, field in field_defs.items():
            field_value = input_value.get(field_name, Undefined)
            if field_value is Undefined:
                if is_required_input_field(field):
                    report_invalid_value(
                        on_error,
                        f"Expected value of type '{type_}' to include required"
                        f" field '{field_name}', found: {inspect(input_value)}.",
                        path,
                    )
            else:
                validate_input_value_impl(
                    field_value,
                    field.type,
                    on_error,
                    hide_suggestions,
                    Path(path, field_name, type_.name),
                )

        fields: list[str] = []
        # Ensure every provided field is defined.
        for field_name, field_value in input_value.items():
            if field_value is Undefined:
                continue
            fields.append(field_name)
            if field_name not in field_defs:
                suggestion = (
                    ""
                    if hide_suggestions
                    else did_you_mean(suggestion_list(field_name, list(field_defs)))
                )
                report_invalid_value(
                    on_error,
                    f"Expected value of type '{type_}' not to include unknown"
                    f" field '{field_name}'"
                    + (f".{suggestion} Found" if suggestion else ", found")
                    + f": {inspect(input_value)}.",
                    path,
                )

        if type_.is_one_of:
            if len(fields) != 1:
                report_invalid_value(
                    on_error,
                    get_one_of_input_object_error_message(type_),
                    path,
                )

            field_name = fields[0]
            value = input_value[field_name]
            if value is None:
                report_invalid_value(
                    on_error,
                    get_one_of_input_object_error_message(type_),
                    Path(path, field_name, type_.name),
                )
    else:
        assert_leaf_type(type_)

        result: Any = Undefined
        caught_error: Exception | None = None

        try:
            # Note: only enum types accept ``hide_suggestions``, since scalar
            # ``coerce_input_value`` functions are user-provided with a fixed
            # signature.
            if is_enum_type(type_):
                result = type_.coerce_input_value(input_value, hide_suggestions)
            else:
                scalar_type = cast("GraphQLScalarType", type_)
                result = scalar_type.coerce_input_value(input_value)
        except GraphQLError as error:
            on_error(error, path.as_list() if path else [])
            return
        except Exception as error:  # noqa: BLE001
            caught_error = error

        if result is Undefined:
            report_invalid_value(
                on_error,
                f"Expected value of type '{type_}'"
                + (
                    f", but encountered error '{caught_error}'; found"
                    if caught_error is not None
                    else ", found"
                )
                + f": {inspect(input_value)}.",
                path,
                caught_error,
            )


def report_invalid_value(
    on_error: OnErrorCB,
    message: str,
    path: Path | None,
    original_error: Exception | None = None,
) -> None:
    on_error(
        GraphQLError(message, original_error=original_error),
        path.as_list() if path else [],
    )


def validate_input_literal(
    value_node: ValueNode,
    type_: GraphQLInputType,
    on_error: OnErrorCB,
    variables: VariableValues | None = None,
    fragment_variable_values: FragmentVariableValues | None = None,
    hide_suggestions: bool = False,
) -> None:
    """Validate that the provided input literal is allowed for this type.

    All errors are collected via a callback function.

    If variable values are not provided, the literal is validated statically (not
    assuming that those variables are missing runtime values).
    """
    context = ValidationContext(
        static=not variables and not fragment_variable_values,
        on_error=on_error,
        variables=variables,
        fragment_variable_values=fragment_variable_values,
    )
    validate_input_literal_impl(context, value_node, type_, hide_suggestions, None)


class ValidationContext(NamedTuple):
    """Context for validating an input literal."""

    static: bool
    on_error: OnErrorCB
    variables: VariableValues | None
    fragment_variable_values: FragmentVariableValues | None


def validate_input_literal_impl(
    context: ValidationContext,
    value_node: ValueNode,
    type_: GraphQLInputType,
    hide_suggestions: bool,
    path: Path | None,
) -> None:
    if isinstance(value_node, VariableNode):
        if context.static:
            # If no variable values are provided, this is being validated
            # statically, and cannot yet produce any validation errors for
            # variables.
            return
        scoped_variable_values = get_scoped_variable_values(context, value_node)
        value = (
            scoped_variable_values.coerced.get(value_node.name.value, Undefined)
            if scoped_variable_values
            else Undefined
        )
        if is_non_null_type(type_):
            if value is Undefined:
                report_invalid_literal(
                    context.on_error,
                    f"Expected variable '${value_node.name.value}' provided"
                    f" to type '{type_}' to provide a runtime value.",
                    value_node,
                    path,
                )
            elif value is None:
                report_invalid_literal(
                    context.on_error,
                    f"Expected variable '${value_node.name.value}' provided"
                    f" to non-null type '{type_}' not to be None.",
                    value_node,
                    path,
                )
        # Note: This does no further checking that this variable is correct.
        # This assumes this variable usage has already been validated.
        return

    if is_non_null_type(type_):
        if isinstance(value_node, NullValueNode):
            report_invalid_literal(
                context.on_error,
                f"Expected value of non-null type '{type_}' not to be None.",
                value_node,
                path,
            )
            return
        validate_input_literal_impl(
            context, value_node, type_.of_type, hide_suggestions, path
        )
        return

    if isinstance(value_node, NullValueNode):
        return

    if is_list_type(type_):
        item_type = type_.of_type
        if not isinstance(value_node, ListValueNode):
            # Lists accept a non-list value as a list of one.
            validate_input_literal_impl(
                context, value_node, item_type, hide_suggestions, path
            )
        else:
            for index, item_node in enumerate(value_node.values):
                validate_input_literal_impl(
                    context,
                    item_node,
                    item_type,
                    hide_suggestions,
                    Path(path, index, None),
                )
    elif is_input_object_type(type_):
        if not isinstance(value_node, ObjectValueNode):
            report_invalid_literal(
                context.on_error,
                f"Expected value of type '{type_}' to be an object,"
                f" found: {print_ast(value_node)}.",
                value_node,
                path,
            )
            return

        field_defs = type_.fields
        field_nodes = {field.name.value: field for field in value_node.fields}

        for field_name, field in field_defs.items():
            field_node = field_nodes.get(field_name)
            if field_node is None:
                if is_required_input_field(field):
                    report_invalid_literal(
                        context.on_error,
                        f"Expected value of type '{type_}' to include required"
                        f" field '{field_name}', found: {print_ast(value_node)}.",
                        value_node,
                        path,
                    )
            else:
                field_value_node = field_node.value
                if isinstance(field_value_node, VariableNode) and not context.static:
                    scoped_variable_values = get_scoped_variable_values(
                        context, field_value_node
                    )
                    variable_name = field_value_node.name.value
                    value = (
                        scoped_variable_values.coerced.get(variable_name, Undefined)
                        if scoped_variable_values
                        else Undefined
                    )
                    if type_.is_one_of:
                        if value is Undefined:
                            report_invalid_literal(
                                context.on_error,
                                f"Expected variable '${variable_name}' provided"
                                f" to field '{field_name}' for OneOf Input Object"
                                f" type '{type_}' to provide a runtime value.",
                                value_node,
                                path,
                            )
                        elif value is None:
                            report_invalid_literal(
                                context.on_error,
                                f"Expected variable '${variable_name}' provided"
                                f" to field '{field_name}' for OneOf Input Object"
                                f" type '{type_}' not to be None.",
                                value_node,
                                path,
                            )
                    elif value is Undefined and not is_required_input_field(field):
                        continue

                validate_input_literal_impl(
                    context,
                    field_value_node,
                    field.type,
                    hide_suggestions,
                    Path(path, field_name, type_.name),
                )

        fields = value_node.fields
        # Ensure every provided field is defined.
        for field_node in fields:
            field_name = field_node.name.value
            if field_name not in field_defs:
                suggestion = (
                    ""
                    if hide_suggestions
                    else did_you_mean(suggestion_list(field_name, list(field_defs)))
                )
                report_invalid_literal(
                    context.on_error,
                    f"Expected value of type '{type_}' not to include unknown"
                    f" field '{field_name}'"
                    + (f".{suggestion} Found" if suggestion else ", found")
                    + f": {print_ast(value_node)}.",
                    field_node,
                    path,
                )

        if type_.is_one_of:
            is_not_exactly_one_field = len(fields) != 1
            if is_not_exactly_one_field:
                report_invalid_literal(
                    context.on_error,
                    get_one_of_input_object_error_message(type_),
                    value_node,
                    path,
                )
                return

            field_value_node = fields[0].value
            if isinstance(field_value_node, NullValueNode):
                field_name = fields[0].name.value
                report_invalid_literal(
                    context.on_error,
                    get_one_of_input_object_error_message(type_),
                    value_node,
                    Path(path, field_name, None),
                )
    else:
        leaf_type = assert_leaf_type(type_)

        result: Any = Undefined
        caught_error: Exception | None = None
        # Note: unlike GraphQL.js, which always replaces variables statically here
        # (without their runtime values), the available variable values are passed
        # through so that a leaf type coercing a literal that embeds variables sees
        # the same values used by ``coerce_input_literal``. This lets the runtime
        # argument-coercion fallback reproduce variable-dependent coercion errors.
        variables = context.variables
        fragment_variable_values = context.fragment_variable_values
        try:
            # Note: only enum types accept ``hide_suggestions``, since scalar
            # ``coerce_input_literal``/``parse_literal`` functions are
            # user-provided with a fixed signature.
            if is_enum_type(leaf_type):
                result = leaf_type.coerce_input_literal(
                    replace_variables(value_node, variables, fragment_variable_values),
                    hide_suggestions,
                )
            elif leaf_type.coerce_input_literal is not None:
                result = leaf_type.coerce_input_literal(
                    replace_variables(value_node, variables, fragment_variable_values)
                )
            else:
                result = leaf_type.parse_literal(
                    value_node, variables.coerced if variables else None
                )
        except GraphQLError as error:
            context.on_error(error, path.as_list() if path else [])
            return
        except Exception as error:  # noqa: BLE001
            caught_error = error

        if result is Undefined:
            report_invalid_literal(
                context.on_error,
                f"Expected value of type '{type_}'"
                + (
                    f", but encountered error '{caught_error}'; found"
                    if caught_error is not None
                    else ", found"
                )
                + f": {print_ast(value_node)}.",
                value_node,
                path,
                caught_error,
            )


def get_scoped_variable_values(
    context: ValidationContext, value_node: VariableNode
) -> VariableValues | FragmentVariableValues | None:
    """Select the variable values that provide the given variable node."""
    variable_name = value_node.name.value
    fragment_variable_values = context.fragment_variable_values
    if fragment_variable_values and variable_name in fragment_variable_values.sources:
        return fragment_variable_values
    return context.variables


def report_invalid_literal(
    on_error: OnErrorCB,
    message: str,
    value_node: Node,
    path: Path | None,
    original_error: Exception | None = None,
) -> None:
    on_error(
        GraphQLError(message, value_node, original_error=original_error),
        path.as_list() if path else [],
    )


def get_one_of_input_object_error_message(type_: GraphQLInputType) -> str:
    return (
        f"Within OneOf Input Object type '{type_}', exactly one field must be"
        " specified, and the value for that field must be non-null."
    )
