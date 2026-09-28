from graphql import (
    GraphQLArgument,
    GraphQLField,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    execute_sync,
    parse,
)

item = GraphQLObjectType(
    name="Item",
    fields={
        "value": GraphQLField(
            GraphQLNonNull(GraphQLInt),
            args={"multiplier": GraphQLArgument(GraphQLNonNull(GraphQLInt))},
            resolve=lambda obj, _info, multiplier: obj * multiplier,
        ),
    },
)

schema = GraphQLSchema(
    query=GraphQLObjectType(
        name="Query",
        fields={
            "items": GraphQLField(
                GraphQLNonNull(GraphQLList(GraphQLNonNull(item))),
                args={"count": GraphQLArgument(GraphQLNonNull(GraphQLInt))},
                resolve=lambda _obj, _info, count: range(count),
            )
        },
    )
)

document = parse(
    "query ($count: Int!) { items(count: $count) { value(multiplier: 2) } }"
)


def test_execute_field_arguments_sync(benchmark):
    result = benchmark(
        lambda: execute_sync(schema, document, variable_values={"count": 1000})
    )
    assert not result.errors
    assert result.data == {"items": [{"value": i * 2} for i in range(1000)]}
