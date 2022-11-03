from graphql import GraphQLSchema, build_schema, print_schema

from ..fixtures import big_schema_sdl  # noqa: F401


def test_recreate_a_graphql_schema(benchmark, big_schema_sdl):  # noqa: F811
    schema = build_schema(big_schema_sdl, assume_valid=True)
    recreated_schema: GraphQLSchema = benchmark(
        lambda: GraphQLSchema(**schema.to_kwargs())
    )
    assert print_schema(schema) == print_schema(recreated_schema)
