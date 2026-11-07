"""Assertions for naming conventions"""

from ..error import GraphQLError

__all__ = ["assert_enum_value_name", "assert_name"]


def assert_name(name: str) -> str:
    """Uphold the spec rules about naming.

    :param name: the GraphQL name to validate
    :returns: the validated GraphQL name

    >>> from graphql import assert_name
    >>> assert_name('User')
    'User'
    >>> assert_name('123User')
    Traceback (most recent call last):
    ...
    graphql.error.graphql_error.GraphQLError: Names must start with [_a-zA-Z] ...
    """
    # an ASCII identifier is exactly a GraphQL name: [_a-zA-Z][_a-zA-Z0-9]*
    if isinstance(name, str) and name.isascii() and name.isidentifier():
        return name
    # only invalid names get here, so find out what is wrong with them
    if name is None:
        msg = "Must provide name."
        raise TypeError(msg)
    if not isinstance(name, str):
        msg = "Expected name to be a string."
        raise TypeError(msg)
    if not name:
        msg = "Expected name to be a non-empty string."
        raise GraphQLError(msg)
    # report a bad tail first, since a valid tail implies a bad first char
    tail = name[1:].replace("_", "")
    if tail and not (tail.isascii() and tail.isalnum()):
        msg = f"Names must only contain [_a-zA-Z0-9] but {name!r} does not."
        raise GraphQLError(msg)
    msg = f"Names must start with [_a-zA-Z] but {name!r} does not."
    raise GraphQLError(msg)


def assert_enum_value_name(name: str) -> str:
    """Uphold the spec rules about naming enum values.

    :param name: the GraphQL name to validate
    :returns: the validated GraphQL name

    >>> from graphql import assert_enum_value_name
    >>> assert_enum_value_name('ACTIVE')
    'ACTIVE'
    >>> assert_enum_value_name('true')
    Traceback (most recent call last):
    ...
    graphql.error.graphql_error.GraphQLError: Enum values cannot be named: true.
    """
    assert_name(name)
    if name in {"true", "false", "null"}:
        msg = f"Enum values cannot be named: {name}."
        raise GraphQLError(msg)
    return name
