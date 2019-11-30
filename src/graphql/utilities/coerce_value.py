from typing import Any, List, NamedTuple, Optional, Union

from ..error import GraphQLError, INVALID
from ..language import Node
from ..pyutils import Path, inspect, print_path_list
from ..type import GraphQLInputType
from .coerce_input_value import coerce_input_value

__all__ = ["coerce_value", "CoercedValue"]


class CoercedValue(NamedTuple):
    errors: Optional[List[GraphQLError]]
    value: Any


def coerce_value(
    input_value: Any,
    type_: GraphQLInputType,
    blame_node: Node = None,
    path: Path = None,
) -> CoercedValue:
    """Coerce a Python value given a GraphQL Type.

    Deprecated. Use coerce_input_value() directly for richer information.
    """
    errors = []

    def on_error(
        error_path: List[Union[str, int]], invalid_value: Any, error: GraphQLError
    ) -> None:
        error_prefix = "Invalid value " + inspect(invalid_value)
        path_list = [*path.as_list(), *error_path] if path else error_path
        if path_list:
            error_prefix += f" at 'value{print_path_list(path_list)}': "
        errors.append(
            GraphQLError(
                error_prefix + ": " + error.message,
                blame_node,
                original_error=error.original_error,
            )
        )

    value = coerce_input_value(input_value, type_, on_error)
    return CoercedValue(errors, INVALID) if errors else CoercedValue(None, value)
