"""Building introspection queries from GraphQL schemas"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..error import GraphQLError
from ..language import parse
from .get_introspection_query import IntrospectionQuery, get_introspection_query

if TYPE_CHECKING:
    from ..type import GraphQLSchema

__all__ = ["introspection_from_schema"]


def introspection_from_schema(
    schema: GraphQLSchema,
    descriptions: bool = True,
    specified_by_url: bool = True,
    directive_is_repeatable: bool = True,
    schema_description: bool = True,
    input_value_deprecation: bool = True,
) -> IntrospectionQuery:
    """Build an IntrospectionQuery from a GraphQLSchema

    IntrospectionQuery is useful for utilities that care about type and field
    relationships, but do not need to traverse through those relationships.

    This is the inverse of build_client_schema. The primary use case is outside of the
    server context, for instance when doing schema comparisons.
    """
    document = parse(
        get_introspection_query(
            descriptions,
            specified_by_url,
            directive_is_repeatable,
            schema_description,
            input_value_deprecation,
        )
    )

    from ..execution.execute import ExecutionResult, execute_sync

    result = execute_sync(schema, document)
    if not isinstance(result, ExecutionResult):  # pragma: no cover
        msg = "Introspection cannot be executed"
        raise RuntimeError(msg)  # noqa: TRY004
    if result.errors:  # pragma: no cover
        raise result.errors[0]
    if not result.data:  # pragma: no cover
        msg = "Introspection did not return a result"
        raise GraphQLError(msg)
    return cast("IntrospectionQuery", result.data)
