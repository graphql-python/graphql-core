import re
from typing import Optional

from ..error import GraphQLError

__all__ = ["assert_valid_name", "is_valid_name_error"]


re_name = re.compile("^[_a-zA-Z][_a-zA-Z0-9]*$")


def assert_valid_name(name: str) -> str:
    """Uphold the spec rules about naming."""
    error = is_valid_name_error(name)
    if error:
        raise error
    return name


def is_valid_name_error(name: str) -> Optional[GraphQLError]:
    """Return an Error if a name is invalid."""
    if not isinstance(name, str):
        raise TypeError("Expected name to be a string.")
    if name.startswith("__"):
        return GraphQLError(
            f"Name {name!r} must not begin with '__',"
            " which is reserved by GraphQL introspection."
        )
    if not re_name.match(name):
        return GraphQLError(
            f"Names must match /^[_a-zA-Z][_a-zA-Z0-9]*$/ but {name!r} does not."
        )
    return None
