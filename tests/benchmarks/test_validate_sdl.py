from graphql import parse
from graphql.validation.validate import validate_sdl

# noinspection PyUnresolvedReferences
from ..fixtures import big_schema_sdl  # noqa: F401


def test_validate_sdl_document(benchmark, big_schema_sdl):  # noqa: F811
    sdl_ast = parse(big_schema_sdl)
    result = benchmark(lambda: validate_sdl(sdl_ast))
    assert result == []
