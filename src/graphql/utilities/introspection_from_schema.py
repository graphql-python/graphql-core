from typing import cast

from ..error import GraphQLError
from ..language import parse
from ..type import GraphQLSchema
from .get_introspection_query import get_introspection_query, IntrospectionQuery

__all__ = ["introspection_from_schema"]


def introspection_from_schema(
    schema: GraphQLSchema,
    descriptions: bool = True,
    specified_by_url: bool = True,
    directive_is_repeatable: bool = True,
    schema_description: bool = True,
    input_value_deprecation: bool = True,
    experimental_directive_deprecation: bool = True,
    input_object_one_of: bool = True,
) -> IntrospectionQuery:
    """Build an IntrospectionQuery from a GraphQLSchema

    IntrospectionQuery is useful for utilities that care about type and field
    relationships, but do not need to traverse through those relationships.

    This is the inverse of build_client_schema. The primary use case is outside of the
    server context, for instance when doing schema comparisons.

    :param schema: The GraphQL schema to introspect.
    :param descriptions: Whether to include descriptions in the introspection result.
    :param specified_by_url: Whether to include ``specifiedByURL`` in the
        introspection result.
    :param directive_is_repeatable: Whether to include the ``isRepeatable`` flag on
        directives.
    :param schema_description: Whether to include the ``description`` field on the
        schema.
    :param input_value_deprecation: Whether to include deprecation information of
        input values.
    :param experimental_directive_deprecation: Whether to include deprecation
        information of directives.
    :param input_object_one_of: Whether to include the ``isOneOf`` flag on input
        objects.
    :returns: Introspection result data for the schema.

    Include schema metadata using the default introspection options:

    >>> from graphql import build_schema, introspection_from_schema
    >>> schema = build_schema('''
    ...     scalar Url @specifiedBy(url: "https://url.spec.whatwg.org/")
    ...
    ...     type Query {
    ...       homepage: Url
    ...     }
    ... ''')
    >>> introspection = introspection_from_schema(schema)
    >>> url_type = next(type_ for type_ in introspection['__schema']['types']
    ...                 if type_['name'] == 'Url')
    >>> url_type['specifiedByURL']
    'https://url.spec.whatwg.org/'

    This variant disables optional introspection metadata:

    >>> introspection = introspection_from_schema(
    ...     schema,
    ...     descriptions=False,
    ...     specified_by_url=False,
    ...     directive_is_repeatable=False,
    ...     schema_description=False,
    ...     input_value_deprecation=False,
    ...     experimental_directive_deprecation=False,
    ...     input_object_one_of=False,
    ... )
    >>> url_type = next(type_ for type_ in introspection['__schema']['types']
    ...                 if type_['name'] == 'Url')
    >>> deprecated_directive = next(
    ...     directive for directive in introspection['__schema']['directives']
    ...     if directive['name'] == 'deprecated')
    >>> 'specifiedByURL' in url_type
    False
    >>> 'description' in url_type
    False
    >>> 'description' in introspection['__schema']
    False
    >>> 'isRepeatable' in deprecated_directive
    False
    """
    document = parse(
        get_introspection_query(
            descriptions,
            specified_by_url,
            directive_is_repeatable,
            schema_description,
            input_value_deprecation,
            experimental_directive_deprecation,
            input_object_one_of,
        )
    )

    from ..execution.execute import execute_sync, ExecutionResult

    result = execute_sync(schema, document)
    if not isinstance(result, ExecutionResult):  # pragma: no cover
        raise RuntimeError("Introspection cannot be executed")
    if result.errors:  # pragma: no cover
        raise result.errors[0]
    if not result.data:  # pragma: no cover
        raise GraphQLError("Introspection did not return a result")
    return cast(IntrospectionQuery, result.data)
