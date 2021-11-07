import asyncio
from graphql import (
    GraphQLSchema,
    GraphQLObjectType,
    GraphQLField,
    GraphQLString,
    graphql,
)


user = GraphQLObjectType(
    name="User",
    fields={
        "id": GraphQLField(GraphQLString),
        "name": GraphQLField(GraphQLString),
    },
)


async def resolve_user(obj, info):
    return {
        "id": "1",
        "name": "Sarah",
    }


schema = GraphQLSchema(
    query=GraphQLObjectType(
        name="Query",
        fields={
            "user": GraphQLField(
                user,
                resolve=resolve_user,
            )
        },
    )
)


def test_execute_basic_async(benchmark):
    try:
        run = asyncio.run
    except AttributeError:  # Python < 3.7
        loop = asyncio.get_event_loop()
        run = loop.run_until_complete  # type: ignore
    result = benchmark(lambda: run(graphql(schema, "query { user { id, name }}")))
    assert not result.errors
    assert result.data == {
        "user": {
            "id": "1",
            "name": "Sarah",
        },
    }
