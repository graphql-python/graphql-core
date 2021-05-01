import asyncio
from typing import Awaitable

from pytest import mark

from graphql.execution import execute
from graphql.language import parse
from graphql.type import (
    GraphQLSchema,
    GraphQLObjectType,
    GraphQLField,
    GraphQLList,
    GraphQLInterfaceType,
    GraphQLBoolean,
    GraphQLInt,
    GraphQLString,
)


class Barrier:
    """Barrier that makes progress only after a certain number of waits."""

    def __init__(self, number: int):
        self.event = asyncio.Event()
        self.number = number

    async def wait(self) -> bool:
        self.number -= 1
        if not self.number:
            self.event.set()
        return await self.event.wait()


def describe_parallel_execution():
    @mark.asyncio
    async def resolve_fields_in_parallel():
        barrier = Barrier(2)

        async def resolve(*_args):
            return await barrier.wait()

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "foo": GraphQLField(GraphQLBoolean, resolve=resolve),
                    "bar": GraphQLField(GraphQLBoolean, resolve=resolve),
                },
            )
        )

        ast = parse("{foo, bar}")

        # raises TimeoutError if not parallel
        awaitable_result = execute(schema, ast)
        assert isinstance(awaitable_result, Awaitable)
        result = await asyncio.wait_for(awaitable_result, 1.0)

        assert result == ({"foo": True, "bar": True}, None)

    @mark.asyncio
    async def resolve_list_in_parallel():
        barrier = Barrier(2)

        async def resolve(*_args):
            return await barrier.wait()

        async def resolve_list(*args):
            return [resolve(*args), resolve(*args)]

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "foo": GraphQLField(
                        GraphQLList(GraphQLBoolean), resolve=resolve_list
                    )
                },
            )
        )

        ast = parse("{foo}")

        # raises TimeoutError if not parallel
        awaitable_result = execute(schema, ast)
        assert isinstance(awaitable_result, Awaitable)
        result = await asyncio.wait_for(awaitable_result, 1.0)

        assert result == ({"foo": [True, True]}, None)

    @mark.asyncio
    async def resolve_is_type_of_in_parallel():
        FooType = GraphQLInterfaceType("Foo", {"foo": GraphQLField(GraphQLString)})

        barrier = Barrier(4)

        async def is_type_of_bar(obj, *_args):
            await barrier.wait()
            return obj["foo"] == "bar"

        BarType = GraphQLObjectType(
            "Bar",
            {"foo": GraphQLField(GraphQLString), "foobar": GraphQLField(GraphQLInt)},
            interfaces=[FooType],
            is_type_of=is_type_of_bar,
        )

        async def is_type_of_baz(obj, *_args):
            await barrier.wait()
            return obj["foo"] == "baz"

        BazType = GraphQLObjectType(
            "Baz",
            {"foo": GraphQLField(GraphQLString), "foobaz": GraphQLField(GraphQLInt)},
            interfaces=[FooType],
            is_type_of=is_type_of_baz,
        )

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "foo": GraphQLField(
                        GraphQLList(FooType),
                        resolve=lambda *_args: [
                            {"foo": "bar", "foobar": 1},
                            {"foo": "baz", "foobaz": 2},
                        ],
                    )
                },
            ),
            types=[BarType, BazType],
        )

        ast = parse(
            """
            {
              foo {
                foo
                ... on Bar { foobar }
                ... on Baz { foobaz }
              }
            }
            """
        )

        # raises TimeoutError if not parallel
        awaitable_result = execute(schema, ast)
        assert isinstance(awaitable_result, Awaitable)
        result = await asyncio.wait_for(awaitable_result, 1.0)

        assert result == (
            {"foo": [{"foo": "bar", "foobar": 1}, {"foo": "baz", "foobaz": 2}]},
            None,
        )
