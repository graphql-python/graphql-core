from graphql import build_schema, parse, validate
from graphql.utilities import get_introspection_query

from ..fixtures import big_schema_sdl  # noqa: F401


def test_validate_introspection_query(benchmark, big_schema_sdl):  # noqa: F811
    schema = build_schema(big_schema_sdl, assume_valid=True)
    query = parse(get_introspection_query())
    result = benchmark(lambda: validate(schema, query))
    assert result == []
