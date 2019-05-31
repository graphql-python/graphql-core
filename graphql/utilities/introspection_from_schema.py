from typing import Any, Dict

from ..error import GraphQLError
from ..language import parse
from ..type import GraphQLSchema
from .introspection_query import get_introspection_query

__all__ = ["introspection_from_schema"]


IntrospectionSchema = Dict[str, Any]


def introspection_from_schema(
    schema: GraphQLSchema, descriptions: bool = True
) -> IntrospectionSchema:
    """Build an IntrospectionQuery from a GraphQLSchema

    IntrospectionQuery is useful for utilities that care about type and field
    relationships, but do not need to traverse through those relationships.

    This is the inverse of build_client_schema. The primary use case is outside of the
    server context, for instance when doing schema comparisons.
    """
    query_ast = parse(get_introspection_query(descriptions))

    from ..execution.execute import execute, ExecutionResult

    result = execute(schema, query_ast)
    if not isinstance(result, ExecutionResult):
        raise RuntimeError("Introspection cannot be executed")
    if result.errors or not result.data:
        raise result.errors[0] if result.errors else GraphQLError(
            "Introspection did not return a result"
        )
    return result.data
