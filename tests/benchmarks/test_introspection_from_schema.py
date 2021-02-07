from graphql import build_schema, parse, execute_sync
from graphql.utilities import get_introspection_query

from ..fixtures import big_schema_sdl  # noqa: F401


def test_execute_introspection_query(benchmark, big_schema_sdl):  # noqa: F811
    schema = build_schema(big_schema_sdl, assume_valid=True)
    document = parse(get_introspection_query())
    result = benchmark(lambda: execute_sync(schema=schema, document=document))
    assert result.errors is None
