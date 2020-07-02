from graphql import parse, build_ast_schema, GraphQLSchema

from ..fixtures import big_schema_sdl  # noqa: F401


def test_build_schema_from_ast(benchmark, big_schema_sdl):  # noqa: F811
    schema_ast = parse(big_schema_sdl)
    schema: GraphQLSchema = benchmark(
        lambda: build_ast_schema(schema_ast, assume_valid=True)
    )
    assert schema.query_type is not None
