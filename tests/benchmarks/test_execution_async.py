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
    # Note: we are creating the async loop outside of the benchmark code so that
    # the setup is not included in the benchmark timings
    loop = asyncio.events.new_event_loop()
    asyncio.events.set_event_loop(loop)
    result = benchmark(
        lambda: loop.run_until_complete(graphql(schema, "query { user { id, name }}"))
    )
    asyncio.events.set_event_loop(None)
    loop.close()
    assert not result.errors
    assert result.data == {
        "user": {
            "id": "1",
            "name": "Sarah",
        },
    }
