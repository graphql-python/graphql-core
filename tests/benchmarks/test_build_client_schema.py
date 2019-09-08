from graphql import build_client_schema, GraphQLSchema

# noinspection PyUnresolvedReferences
from ..fixtures import big_schema_introspection_result  # noqa: F401


def test_build_schema_from_introspection(
    benchmark, big_schema_introspection_result  # noqa: F811
):
    schema: GraphQLSchema = benchmark(
        lambda: build_client_schema(
            big_schema_introspection_result["data"], assume_valid=True
        )
    )
    assert schema.query_type is not None
