"""GraphQL scalar types"""

from __future__ import annotations

import re
from math import isfinite
from typing import TYPE_CHECKING, Any, TypeGuard

from ..error import GraphQLError
from ..language.ast import (
    BooleanValueNode,
    ConstValueNode,
    FloatValueNode,
    IntValueNode,
    StringValueNode,
    ValueNode,
)
from ..language.printer import print_ast
from ..pyutils import inspect
from ..utilities.value_to_literal import default_scalar_value_to_literal
from .definition import GraphQLNamedType, GraphQLScalarType

if TYPE_CHECKING:
    from collections.abc import Mapping

_re_integer_string = re.compile("^-?(?:0|[1-9][0-9]*)$")

__all__ = [
    "GRAPHQL_MAX_INT",
    "GRAPHQL_MIN_INT",
    "GraphQLBoolean",
    "GraphQLFloat",
    "GraphQLID",
    "GraphQLInt",
    "GraphQLString",
    "is_specified_scalar_type",
    "specified_scalar_types",
]

# As per the GraphQL Spec, Integers are only treated as valid
# when they can be represented as a 32-bit signed integer,
# providing the broadest support across platforms.
# n.b. JavaScript's numbers are safe between -(2^53 - 1) and 2^53 - 1
# because they are internally represented as IEEE 754 doubles,
# while Python's integers may be arbitrarily large.

GRAPHQL_MAX_INT = 2_147_483_647
"""Maximum possible Int value as per GraphQL Spec (32-bit signed integer)"""

GRAPHQL_MIN_INT = -2_147_483_648
"""Minimum possible Int value as per GraphQL Spec (32-bit signed integer)"""


def serialize_int(output_value: Any) -> int:
    if isinstance(output_value, bool):
        return 1 if output_value else 0
    if isinstance(output_value, (int, float)):
        return coerce_int_from_number(output_value)
    if isinstance(output_value, str):
        return coerce_int_from_string(output_value)
    msg = "Int cannot represent non-integer value: " + inspect(output_value)
    raise GraphQLError(msg)


def coerce_int(input_value: Any) -> int:
    if isinstance(input_value, (int, float)) and not isinstance(input_value, bool):
        return coerce_int_from_number(input_value)
    msg = "Int cannot represent non-integer value: " + inspect(input_value)
    raise GraphQLError(msg)


def parse_int_literal(value_node: ValueNode, _variables: Any = None) -> int:
    """Parse an integer value node in the AST."""
    if not isinstance(value_node, IntValueNode):
        msg = "Int cannot represent non-integer value: " + print_ast(value_node)
        raise GraphQLError(msg, value_node)
    num = int(value_node.value)
    if not GRAPHQL_MIN_INT <= num <= GRAPHQL_MAX_INT:
        msg = "Int cannot represent non 32-bit signed integer value: " + print_ast(
            value_node
        )
        raise GraphQLError(msg, value_node)
    return num


def int_value_to_literal(value: Any) -> ConstValueNode | None:
    """Convert an integer value to an Int literal in the AST."""
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
        and value == int(value)
        and GRAPHQL_MIN_INT <= value <= GRAPHQL_MAX_INT
    ):
        return IntValueNode(value=str(int(value)))
    return None


GraphQLInt = GraphQLScalarType(
    name="Int",
    description="The `Int` scalar type represents"
    " non-fractional signed whole numeric values."
    " Int can represent values between -(2^31) and 2^31 - 1.",
    coerce_output_value=serialize_int,
    coerce_input_value=coerce_int,
    coerce_input_literal=parse_int_literal,
    value_to_literal=int_value_to_literal,
)


def serialize_float(output_value: Any) -> float:
    if isinstance(output_value, bool):
        return 1 if output_value else 0
    if isinstance(output_value, (int, float)):
        return coerce_float_from_number(output_value)
    if isinstance(output_value, str):
        return coerce_float_from_string(output_value)
    msg = "Float cannot represent non numeric value: " + inspect(output_value)
    raise GraphQLError(msg)


def coerce_float(input_value: Any) -> float:
    if isinstance(input_value, (int, float)) and not isinstance(input_value, bool):
        return coerce_float_from_number(input_value)
    msg = "Float cannot represent non numeric value: " + inspect(input_value)
    raise GraphQLError(msg)


def parse_float_literal(value_node: ValueNode, _variables: Any = None) -> float:
    """Parse a float value node in the AST."""
    if not isinstance(value_node, (FloatValueNode, IntValueNode)):
        raise GraphQLError(
            "Float cannot represent non numeric value: " + print_ast(value_node),
            value_node,
        )
    return float(value_node.value)


def float_value_to_literal(value: Any) -> ConstValueNode | None:
    """Convert a float value to a Float literal in the AST."""
    literal = default_scalar_value_to_literal(value)
    if isinstance(literal, (FloatValueNode, IntValueNode)):
        return literal
    return None


GraphQLFloat = GraphQLScalarType(
    name="Float",
    description="The `Float` scalar type represents"
    " signed double-precision fractional values"
    " as specified by [IEEE 754]"
    "(https://en.wikipedia.org/wiki/IEEE_floating_point).",
    coerce_output_value=serialize_float,
    coerce_input_value=coerce_float,
    coerce_input_literal=parse_float_literal,
    value_to_literal=float_value_to_literal,
)


def serialize_string(output_value: Any) -> str:
    if isinstance(output_value, str):
        return output_value
    if isinstance(output_value, bool):
        return "true" if output_value else "false"
    if isinstance(output_value, (int, float)):
        return coerce_string_from_number(output_value)
    # do not serialize builtin types as strings, but allow serialization of custom
    # types via their `__str__` method
    if type(output_value).__module__ == "builtins":
        raise GraphQLError("String cannot represent value: " + inspect(output_value))
    return str(output_value)


def coerce_string(input_value: Any) -> str:
    if not isinstance(input_value, str):
        raise GraphQLError(
            "String cannot represent a non string value: " + inspect(input_value)
        )
    return input_value


def parse_string_literal(value_node: ValueNode, _variables: Any = None) -> str:
    """Parse a string value node in the AST."""
    if not isinstance(value_node, StringValueNode):
        raise GraphQLError(
            "String cannot represent a non string value: " + print_ast(value_node),
            value_node,
        )
    return value_node.value


def string_value_to_literal(value: Any) -> ConstValueNode | None:
    """Convert a string value to a String literal in the AST."""
    literal = default_scalar_value_to_literal(value)
    if isinstance(literal, StringValueNode):
        return literal
    return None


GraphQLString = GraphQLScalarType(
    name="String",
    description="The `String` scalar type represents textual data,"
    " represented as UTF-8 character sequences."
    " The String type is most often used by GraphQL"
    " to represent free-form human-readable text.",
    coerce_output_value=serialize_string,
    coerce_input_value=coerce_string,
    coerce_input_literal=parse_string_literal,
    value_to_literal=string_value_to_literal,
)


def serialize_boolean(output_value: Any) -> bool:
    if isinstance(output_value, bool):
        return output_value
    if isinstance(output_value, (int, float)):
        return coerce_boolean_from_number(output_value)
    raise GraphQLError(
        "Boolean cannot represent a non boolean value: " + inspect(output_value)
    )


def coerce_boolean(input_value: Any) -> bool:
    if not isinstance(input_value, bool):
        raise GraphQLError(
            "Boolean cannot represent a non boolean value: " + inspect(input_value)
        )
    return input_value


def parse_boolean_literal(value_node: ValueNode, _variables: Any = None) -> bool:
    """Parse a boolean value node in the AST."""
    if not isinstance(value_node, BooleanValueNode):
        raise GraphQLError(
            "Boolean cannot represent a non boolean value: " + print_ast(value_node),
            value_node,
        )
    return value_node.value


def boolean_value_to_literal(value: Any) -> ConstValueNode | None:
    """Convert a boolean value to a Boolean literal in the AST."""
    literal = default_scalar_value_to_literal(value)
    if isinstance(literal, BooleanValueNode):
        return literal
    return None


GraphQLBoolean = GraphQLScalarType(
    name="Boolean",
    description="The `Boolean` scalar type represents `true` or `false`.",
    coerce_output_value=serialize_boolean,
    coerce_input_value=coerce_boolean,
    coerce_input_literal=parse_boolean_literal,
    value_to_literal=boolean_value_to_literal,
)


def serialize_id(output_value: Any) -> str:
    if isinstance(output_value, str):
        return output_value
    if isinstance(output_value, (int, float)) and not isinstance(output_value, bool):
        return coerce_id_from_number(output_value)
    # do not serialize builtin types as IDs, but allow serialization of custom types
    # via their `__str__` method
    if type(output_value).__module__ == "builtins":
        raise GraphQLError("ID cannot represent value: " + inspect(output_value))
    return str(output_value)


def coerce_id(input_value: Any) -> str:
    if isinstance(input_value, str):
        return input_value
    if isinstance(input_value, (int, float)) and not isinstance(input_value, bool):
        return coerce_id_from_number(input_value)
    raise GraphQLError("ID cannot represent value: " + inspect(input_value))


def parse_id_literal(value_node: ValueNode, _variables: Any = None) -> str:
    """Parse an ID value node in the AST."""
    if not isinstance(value_node, (StringValueNode, IntValueNode)):
        raise GraphQLError(
            "ID cannot represent a non-string and non-integer value: "
            + print_ast(value_node),
            value_node,
        )
    return value_node.value


def id_value_to_literal(value: Any) -> ConstValueNode | None:
    """Convert an ID value to an Int or String literal in the AST."""
    # ID types can use number values and Int literals.
    if isinstance(value, str):
        # Will parse as an IntValue if it consists only of integer digits.
        return (
            IntValueNode(value=value)
            if _re_integer_string.match(value)
            else StringValueNode(value=value, block=False)
        )
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return IntValueNode(value=coerce_id_from_number(value))
    return None


GraphQLID = GraphQLScalarType(
    name="ID",
    description="The `ID` scalar type represents a unique identifier,"
    " often used to refetch an object or as key for a cache."
    " The ID type appears in a JSON response as a String; however,"
    " it is not intended to be human-readable. When expected as an"
    ' input type, any string (such as `"4"`) or integer (such as'
    " `4`) input value will be accepted as an ID.",
    coerce_output_value=serialize_id,
    coerce_input_value=coerce_id,
    coerce_input_literal=parse_id_literal,
    value_to_literal=id_value_to_literal,
)


def coerce_int_from_number(value: float) -> int:
    if isinstance(value, float) and (not isfinite(value) or int(value) != value):
        msg = "Int cannot represent non-integer value: " + inspect(value)
        raise GraphQLError(msg)
    if not GRAPHQL_MIN_INT <= value <= GRAPHQL_MAX_INT:
        msg = "Int cannot represent non 32-bit signed integer value: " + inspect(value)
        raise GraphQLError(msg)
    return int(value)


def coerce_int_from_string(value: str) -> int:
    try:
        if not value:
            raise ValueError  # noqa: TRY301
        num = int(value)
    except ValueError as error:
        msg = "Int cannot represent non-integer value: " + inspect(value)
        raise GraphQLError(msg) from error
    if not GRAPHQL_MIN_INT <= num <= GRAPHQL_MAX_INT:
        msg = "Int cannot represent non 32-bit signed integer value: " + inspect(value)
        raise GraphQLError(msg)
    return num


def coerce_float_from_number(value: float) -> float:
    if not isfinite(value):
        msg = "Float cannot represent non numeric value: " + inspect(value)
        raise GraphQLError(msg)
    return float(value)


def coerce_float_from_string(value: str) -> float:
    try:
        if not value:
            raise ValueError  # noqa: TRY301
        num = float(value)
    except ValueError as error:
        msg = "Float cannot represent non numeric value: " + inspect(value)
        raise GraphQLError(msg) from error
    if not isfinite(num):
        msg = "Float cannot represent non numeric value: " + inspect(value)
        raise GraphQLError(msg)
    return num


def coerce_string_from_number(value: float) -> str:
    if not isfinite(value):
        msg = "String cannot represent value: " + inspect(value)
        raise GraphQLError(msg)
    return str(value)


def coerce_boolean_from_number(value: float) -> bool:
    if not isfinite(value):
        msg = "Boolean cannot represent a non boolean value: " + inspect(value)
        raise GraphQLError(msg)
    return value != 0


def coerce_id_from_number(value: float) -> str:
    if isinstance(value, float) and (not isfinite(value) or int(value) != value):
        msg = "ID cannot represent value: " + inspect(value)
        raise GraphQLError(msg)
    return str(int(value))


specified_scalar_types: Mapping[str, GraphQLScalarType] = {
    type_.name: type_
    for type_ in (
        GraphQLString,
        GraphQLInt,
        GraphQLFloat,
        GraphQLBoolean,
        GraphQLID,
    )
}  # pyright: ignore


def is_specified_scalar_type(type_: GraphQLNamedType) -> TypeGuard[GraphQLScalarType]:
    """Check whether the given named GraphQL type is a specified scalar type."""
    return type_.name in specified_scalar_types


# register the scalar types to avoid redefinition
GraphQLNamedType.reserved_types |= specified_scalar_types  # type: ignore
