from graphql import build_schema, parse, execute
from graphql.utilities import introspection_query

# noinspection PyUnresolvedReferences
from ..fixtures import big_schema_sdl  # noqa: F401


def test_execute_introspection_query(benchmark, big_schema_sdl):  # noqa: F811
    schema = build_schema(big_schema_sdl, assume_valid=True)
    query = parse(introspection_query.get_introspection_query())
    result = benchmark(lambda: execute(schema, query))
    assert result.errors is None
