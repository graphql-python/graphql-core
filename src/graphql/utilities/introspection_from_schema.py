from typing import Any, Dict

from ..error import GraphQLError
from ..language import parse
from ..type import GraphQLSchema
from .get_introspection_query import get_introspection_query

__all__ = ["introspection_from_schema"]


IntrospectionSchema = Dict[str, Any]


def introspection_from_schema(
    schema: GraphQLSchema,
    descriptions: bool = True,
    directive_is_repeatable: bool = True,
    schema_description: bool = True,
) -> IntrospectionSchema:
    """Build an IntrospectionQuery from a GraphQLSchema

    IntrospectionQuery is useful for utilities that care about type and field
    relationships, but do not need to traverse through those relationships.

    This is the inverse of build_client_schema. The primary use case is outside of the
    server context, for instance when doing schema comparisons.
    """
    document = parse(
        get_introspection_query(
            descriptions, directive_is_repeatable, schema_description
        )
    )

    from ..execution.execute import execute, ExecutionResult

    result = execute(schema, document)
    if not isinstance(result, ExecutionResult):  # pragma: no cover
        raise RuntimeError("Introspection cannot be executed")
    if result.errors:  # pragma: no cover
        raise result.errors[0]
    if not result.data:  # pragma: no cover
        raise GraphQLError("Introspection did not return a result")
    return result.data
