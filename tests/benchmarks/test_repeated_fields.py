from graphql import (
    GraphQLField,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
    graphql_sync,
)

schema = GraphQLSchema(
    query=GraphQLObjectType(
        name="Query",
        fields={
            "hello": GraphQLField(
                GraphQLString,
                resolve=lambda _obj, _info: "world",
            )
        },
    )
)
source = f"{{ {'hello ' * 250}}}"


def test_many_repeated_fields(benchmark):
    result = benchmark(lambda: graphql_sync(schema, source))
    assert result == ({"hello": "world"}, None)
