import pytest

from graphql import (
    GraphQLField,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
    parse,
    validate,
)

schema = GraphQLSchema(
    query=GraphQLObjectType(
        name="Query",
        fields={"hello": GraphQLField(GraphQLString)},
    )
)


@pytest.mark.parametrize("count", [100, 500, 1000, 2000, 3000])
def test_validate_many_repeated_fields(benchmark, count):
    document = parse(f"{{ {'hello ' * count}}}")
    result = benchmark(lambda: validate(schema, document))
    assert result == []
