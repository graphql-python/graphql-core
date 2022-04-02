import anyio
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
        self.event = anyio.Event()
        self.number = number

    async def wait(self) -> bool:
        self.number -= 1
        if not self.number:
            self.event.set()
        await self.event.wait()
        return True


def describe_parallel_execution():
    @mark.anyio
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

        with anyio.fail_after(1.0):
            result = await awaitable_result

        assert result == ({"foo": True, "bar": True}, None)

    @mark.anyio
    async def cancel_resolve_fields_in_parallel():
        ast = parse("{foo, bar}")

        async def resolve(*_args):
            return await anyio.sleep(5)

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Type",
                {
                    "foo": GraphQLField(GraphQLString, resolve=resolve),
                    "bar": GraphQLField(GraphQLString, resolve=resolve),
                },
            )
        )

        awaitable_result = execute(schema, ast)
        assert isinstance(awaitable_result, Awaitable)
        cancelled = False
        with anyio.move_on_after(0.1):
            try:
                await awaitable_result
            except anyio.get_cancelled_exc_class():
                cancelled = True
                raise
        assert cancelled

    @mark.anyio
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
        with anyio.fail_after(1.0):
            result = await awaitable_result

        assert result == ({"foo": [True, True]}, None)

    @mark.anyio
    async def cancel_resolve_list_in_parallel():
        async def resolve(*_args):
            return await anyio.sleep(5)

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

        awaitable_result = execute(schema, ast)
        assert isinstance(awaitable_result, Awaitable)
        cancelled = False
        with anyio.move_on_after(0.1):
            try:
                await awaitable_result
            except anyio.get_cancelled_exc_class():
                cancelled = True
                raise
        assert cancelled

    @mark.anyio
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
        with anyio.fail_after(1.0):
            result = await awaitable_result

        assert result == (
            {"foo": [{"foo": "bar", "foobar": 1}, {"foo": "baz", "foobaz": 2}]},
            None,
        )

    @mark.anyio
    async def cancel_resolve_is_type_of_in_parallel():
        FooType = GraphQLInterfaceType("Foo", {"foo": GraphQLField(GraphQLString)})

        async def is_type_of_bar(obj, *_args):
            await anyio.sleep(5)

        BarType = GraphQLObjectType(
            "Bar",
            {"foo": GraphQLField(GraphQLString), "foobar": GraphQLField(GraphQLInt)},
            interfaces=[FooType],
            is_type_of=is_type_of_bar,
        )

        async def is_type_of_baz(obj, *_args):
            await anyio.sleep(5)

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
        cancelled = False
        with anyio.move_on_after(0.1):
            try:
                await awaitable_result
            except anyio.get_cancelled_exc_class():
                cancelled = True
                raise
        assert cancelled
