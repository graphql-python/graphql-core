"""Assertions for naming conventions"""

from ..error import GraphQLError
from ..language.character_classes import is_name_continue, is_name_start

__all__ = ["assert_name", "assert_enum_value_name"]


def assert_name(name: str) -> str:
    """Uphold the spec rules about naming."""
    if name is None:
        msg = "Must provide name."
        raise TypeError(msg)
    if not isinstance(name, str):
        msg = "Expected name to be a string."
        raise TypeError(msg)
    if not name:
        msg = "Expected name to be a non-empty string."
        raise GraphQLError(msg)
    if not all(is_name_continue(char) for char in name[1:]):
        msg = f"Names must only contain [_a-zA-Z0-9] but {name!r} does not."
        raise GraphQLError(msg)
    if not is_name_start(name[0]):
        msg = f"Names must start with [_a-zA-Z] but {name!r} does not."
        raise GraphQLError(msg)
    return name


def assert_enum_value_name(name: str) -> str:
    """Uphold the spec rules about naming enum values."""
    assert_name(name)
    if name in {"true", "false", "null"}:
        msg = f"Enum values cannot be named: {name}."
        raise GraphQLError(msg)
    return name
