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
                resolve=lambda obj, info: "world",
            )
        },
    )
)
source = "query {{ {fields} }}".format(fields="hello " * 250)


def test_many_repeated_fields(benchmark):
    print(source)
    result = benchmark(lambda: graphql_sync(schema, source))
    assert not result.errors
