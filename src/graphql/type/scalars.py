from math import isfinite
from typing import Any

from ..error import INVALID
from ..pyutils import inspect, is_finite, is_integer, FrozenDict
from ..language.ast import (
    BooleanValueNode,
    FloatValueNode,
    IntValueNode,
    StringValueNode,
)
from .definition import GraphQLScalarType, is_scalar_type

__all__ = [
    "is_specified_scalar_type",
    "specified_scalar_types",
    "GraphQLInt",
    "GraphQLFloat",
    "GraphQLString",
    "GraphQLBoolean",
    "GraphQLID",
]


# As per the GraphQL Spec, Integers are only treated as valid when a valid
# 32-bit signed integer, providing the broadest support across platforms.
#
# n.b. JavaScript's integers are safe between -(2^53 - 1) and 2^53 - 1 because
# they are internally represented as IEEE 754 doubles,
# while Python's integers may be arbitrarily large.
MAX_INT = 2_147_483_647
MIN_INT = -2_147_483_648


def serialize_int(value: Any) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    try:
        if isinstance(value, int):
            num = value
        elif isinstance(value, float):
            num = int(value)
            if num != value:
                raise ValueError
        elif not value and isinstance(value, str):
            value = ""
            raise ValueError
        else:
            num = int(value)
            float_value = float(value)
            if num != float_value:
                raise ValueError
    except (OverflowError, ValueError, TypeError):
        raise TypeError(f"Int cannot represent non-integer value: {inspect(value)}")
    if not MIN_INT <= num <= MAX_INT:
        raise TypeError(
            f"Int cannot represent non 32-bit signed integer value: {inspect(value)}"
        )
    return num


def coerce_int(value: Any) -> int:
    if not is_integer(value):
        raise TypeError(f"Int cannot represent non-integer value: {inspect(value)}")
    if not MIN_INT <= value <= MAX_INT:
        raise TypeError(
            f"Int cannot represent non 32-bit signed integer value: {inspect(value)}"
        )
    return int(value)


def parse_int_literal(ast, _variables=None):
    """Parse an integer value node in the AST."""
    if isinstance(ast, IntValueNode):
        num = int(ast.value)
        if MIN_INT <= num <= MAX_INT:
            return num
    return INVALID


GraphQLInt = GraphQLScalarType(
    name="Int",
    description="The `Int` scalar type represents"
    " non-fractional signed whole numeric values."
    " Int can represent values between -(2^31) and 2^31 - 1.",
    serialize=serialize_int,
    parse_value=coerce_int,
    parse_literal=parse_int_literal,
)


def serialize_float(value: Any) -> float:
    if isinstance(value, bool):
        return 1 if value else 0
    try:
        if not value and isinstance(value, str):
            value = ""
            raise ValueError
        num = value if isinstance(value, float) else float(value)
        if not isfinite(num):
            raise ValueError
    except (ValueError, TypeError):
        raise TypeError(f"Float cannot represent non numeric value: {inspect(value)}")
    return num


def coerce_float(value: Any) -> float:
    if not is_finite(value):
        raise TypeError(f"Float cannot represent non numeric value: {inspect(value)}")
    return float(value)


def parse_float_literal(ast, _variables=None):
    """Parse a float value node in the AST."""
    if isinstance(ast, (FloatValueNode, IntValueNode)):
        return float(ast.value)
    return INVALID


GraphQLFloat = GraphQLScalarType(
    name="Float",
    description="The `Float` scalar type represents"
    " signed double-precision fractional values"
    " as specified by [IEEE 754]"
    "(https://en.wikipedia.org/wiki/IEEE_floating_point).",
    serialize=serialize_float,
    parse_value=coerce_float,
    parse_literal=parse_float_literal,
)


def serialize_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if is_finite(value):
        return str(value)
    # do not serialize builtin types as strings, but allow serialization of custom
    # types via their `__str__` method
    if type(value).__module__ == "builtins":
        raise TypeError(f"String cannot represent value: {inspect(value)}")
    return str(value)


def coerce_string(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError(f"String cannot represent a non string value: {inspect(value)}")
    return value


def parse_string_literal(ast, _variables=None):
    """Parse a string value node in the AST."""
    if isinstance(ast, StringValueNode):
        return ast.value
    return INVALID


GraphQLString = GraphQLScalarType(
    name="String",
    description="The `String` scalar type represents textual data,"
    " represented as UTF-8 character sequences."
    " The String type is most often used by GraphQL"
    " to represent free-form human-readable text.",
    serialize=serialize_string,
    parse_value=coerce_string,
    parse_literal=parse_string_literal,
)


def serialize_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if is_finite(value):
        return bool(value)
    raise TypeError(f"Boolean cannot represent a non boolean value: {inspect(value)}")


def coerce_boolean(value: Any) -> bool:
    if not isinstance(value, bool):
        raise TypeError(
            f"Boolean cannot represent a non boolean value: {inspect(value)}"
        )
    return value


def parse_boolean_literal(ast, _variables=None):
    """Parse a boolean value node in the AST."""
    if isinstance(ast, BooleanValueNode):
        return ast.value
    return INVALID


GraphQLBoolean = GraphQLScalarType(
    name="Boolean",
    description="The `Boolean` scalar type represents `true` or `false`.",
    serialize=serialize_boolean,
    parse_value=coerce_boolean,
    parse_literal=parse_boolean_literal,
)


def serialize_id(value: Any) -> str:
    if isinstance(value, str):
        return value
    if is_integer(value):
        return str(int(value))
    # do not serialize builtin types as IDs, but allow serialization of custom types
    # via their `__str__` method
    if type(value).__module__ == "builtins":
        raise TypeError(f"ID cannot represent value: {inspect(value)}")
    return str(value)


def coerce_id(value: Any) -> str:
    if not isinstance(value, str) and not is_integer(value):
        raise TypeError(f"ID cannot represent value: {inspect(value)}")
    if isinstance(value, float):
        value = int(value)
    return str(value)


def parse_id_literal(ast, _variables=None):
    """Parse an ID value node in the AST."""
    if isinstance(ast, (StringValueNode, IntValueNode)):
        return ast.value
    return INVALID


GraphQLID = GraphQLScalarType(
    name="ID",
    description="The `ID` scalar type represents a unique identifier,"
    " often used to refetch an object or as key for a cache."
    " The ID type appears in a JSON response as a String; however,"
    " it is not intended to be human-readable. When expected as an"
    ' input type, any string (such as `"4"`) or integer (such as'
    " `4`) input value will be accepted as an ID.",
    serialize=serialize_id,
    parse_value=coerce_id,
    parse_literal=parse_id_literal,
)


specified_scalar_types: FrozenDict[str, GraphQLScalarType] = FrozenDict(
    {
        type_.name: type_
        for type_ in (
            GraphQLString,
            GraphQLInt,
            GraphQLFloat,
            GraphQLBoolean,
            GraphQLID,
        )
    }
)


def is_specified_scalar_type(type_: Any) -> bool:
    return is_scalar_type(type_) and type_.name in specified_scalar_types
