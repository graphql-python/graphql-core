"""Create a GraphQL literal (AST) from a Python input value"""

from __future__ import annotations

import re
from collections.abc import Mapping
from math import isfinite
from typing import Any, cast

from ..language import (
    BooleanValueNode,
    ConstValueNode,
    FloatValueNode,
    IntValueNode,
    ListValueNode,
    NameNode,
    NullValueNode,
    ObjectFieldNode,
    ObjectValueNode,
    StringValueNode,
)
from ..pyutils import Undefined, inspect, is_iterable

# Import directly from the submodule (instead of the ``..type`` package) to avoid a
# circular import, since the scalar types in turn use
# ``default_scalar_value_to_literal``.
from ..type.definition import (
    GraphQLInputType,
    assert_leaf_type,
    is_input_object_type,
    is_list_type,
    is_non_null_type,
    is_required_input_field,
)

__all__ = ["default_scalar_value_to_literal", "value_to_literal"]

_re_integer_string = re.compile("^-?(?:0|[1-9][0-9]*)$")


def value_to_literal(value: Any, type_: GraphQLInputType) -> ConstValueNode | None:
    """Produce a GraphQL Value AST given a Python value and a GraphQL type.

    Scalar types are converted by calling the ``value_to_literal`` method on that
    type, otherwise the default scalar ``value_to_literal`` method is used, defined
    below.

    The provided value is a non-coerced "input" value. This function does not
    perform any coercion, however it does perform validation. Provided values
    which are invalid for the given type will result in a ``None`` return value.
    """
    if is_non_null_type(type_):
        if value is None or value is Undefined:
            return None  # Invalid: intentionally return no value.
        return value_to_literal(value, type_.of_type)

    # Like JSON, a null literal is produced for both null and undefined.
    if value is None or value is Undefined:
        return NullValueNode()

    if is_list_type(type_):
        item_type = type_.of_type
        if not is_iterable(value):
            return value_to_literal(value, item_type)
        values: list[ConstValueNode] = []
        for item_value in value:
            item_node = value_to_literal(item_value, item_type)
            if not item_node:
                return None  # Invalid: intentionally return no value.
            values.append(item_node)
        # gc3 builds plain value nodes and treats them as constant ones, exactly
        # as the parser does for const values (see ``parse_const_value_literal``).
        return cast("ConstValueNode", ListValueNode(values=tuple(values)))

    if is_input_object_type(type_):
        if not isinstance(value, Mapping):
            return None  # Invalid: intentionally return no value.
        field_defs = type_.fields
        if any(name not in field_defs for name in value):
            return None  # Invalid: intentionally return no value.
        fields: list[ObjectFieldNode] = []
        for field_name, field in field_defs.items():
            field_value = value.get(field_name, Undefined)
            if field_value is Undefined:
                if is_required_input_field(field):
                    return None  # Invalid: intentionally return no value.
            else:
                field_node = value_to_literal(field_value, field.type)
                if not field_node:
                    return None  # Invalid: intentionally return no value.
                fields.append(
                    ObjectFieldNode(name=NameNode(value=field_name), value=field_node)
                )
        return cast("ConstValueNode", ObjectValueNode(fields=tuple(fields)))

    leaf_type = assert_leaf_type(type_)

    if leaf_type.value_to_literal is not None:
        try:
            return leaf_type.value_to_literal(value)
        except Exception:  # noqa: BLE001
            return None  # Invalid: intentionally ignore error and return no value.

    return default_scalar_value_to_literal(value)


def default_scalar_value_to_literal(value: Any) -> ConstValueNode:
    """Convert a Python value to a literal (AST) using the default rules.

    ================= =======================
       Python Value         GraphQL Value
    ================= =======================
       Mapping            Input Object
       Iterable           List
       bool               Boolean
       str                String
       int / float        Int / Float
       None               Null
    ================= =======================

    .. internal::
    """
    # Like JSON, a null literal is produced for both null and undefined.
    if value is None or value is Undefined:
        return NullValueNode()

    if isinstance(value, bool):
        return BooleanValueNode(value=value)

    if isinstance(value, str):
        return StringValueNode(value=value, block=False)

    if isinstance(value, (int, float)):
        if isinstance(value, float) and not isfinite(value):
            # Like JSON, a null literal is produced for non-finite values.
            return NullValueNode()
        string_value = str(value)
        # Will parse as an IntValue if it has no fractional or exponent part.
        return (
            IntValueNode(value=string_value)
            if _re_integer_string.match(string_value)
            else FloatValueNode(value=string_value)
        )

    if is_iterable(value):
        return cast(
            "ConstValueNode",
            ListValueNode(
                values=tuple(default_scalar_value_to_literal(item) for item in value)
            ),
        )

    if isinstance(value, Mapping):
        fields: list[ObjectFieldNode] = []
        for field_name, field_value in value.items():
            # Like JSON, undefined fields are not included in the literal result.
            if field_value is not Undefined:
                fields.append(
                    ObjectFieldNode(
                        name=NameNode(value=field_name),
                        value=default_scalar_value_to_literal(field_value),
                    )
                )
        return cast("ConstValueNode", ObjectValueNode(fields=tuple(fields)))

    msg = f"Cannot convert value to AST: {inspect(value)}."
    raise TypeError(msg)
