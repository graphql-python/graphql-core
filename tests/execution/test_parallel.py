import asyncio
from typing import Awaitable

import pytest

from graphql.execution import execute
from graphql.language import parse
from graphql.type import (
    GraphQLBoolean,
    GraphQLField,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)

pytestmark = pytest.mark.anyio


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
    async def resolve_single_field():
        # make sure that the special case of resolving a single field works
        async def resolve(*_args):
            return True

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "foo": GraphQLField(GraphQLBoolean, resolve=resolve),
                },
            )
        )

        awaitable_result = execute(schema, parse("{foo}"))
        assert isinstance(awaitable_result, Awaitable)
        result = await awaitable_result

        assert result == ({"foo": True}, None)

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
        result = await asyncio.wait_for(awaitable_result, 1)

        assert result == ({"foo": True, "bar": True}, None)

    async def resolve_single_element_list():
        # make sure that the special case of resolving a single element list works
        async def resolve(*_args):
            return [True]

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {"foo": GraphQLField(GraphQLList(GraphQLBoolean), resolve=resolve)},
            )
        )

        awaitable_result = execute(schema, parse("{foo}"))
        assert isinstance(awaitable_result, Awaitable)
        result = await awaitable_result

        assert result == ({"foo": [True]}, None)

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
        result = await asyncio.wait_for(awaitable_result, 1)

        assert result == ({"foo": [True, True]}, None)

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
        result = await asyncio.wait_for(awaitable_result, 1)

        assert result == (
            {"foo": [{"foo": "bar", "foobar": 1}, {"foo": "baz", "foobaz": 2}]},
            None,
        )

    def describe_cancel_on_exception():
        """Tests for cancellation of parallel execution on exception.

        These tests are specifically targeted at the Python asyncio implementation.
        """

        async def cancel_selection_sets():
            barrier = Barrier(2)
            completed = False

            async def succeed(*_args):
                nonlocal completed
                await barrier.wait()
                completed = True  # pragma: no cover

            async def fail(*_args):
                raise RuntimeError("Oops")

            schema = GraphQLSchema(
                GraphQLObjectType(
                    "Query",
                    {
                        "foo": GraphQLField(
                            GraphQLNonNull(GraphQLBoolean), resolve=fail
                        ),
                        "bar": GraphQLField(GraphQLBoolean, resolve=succeed),
                    },
                )
            )

            ast = parse("{foo, bar}")

            awaitable_result = execute(schema, ast)
            assert isinstance(awaitable_result, Awaitable)
            result = await asyncio.wait_for(awaitable_result, 1)

            assert result == (
                None,
                [{"message": "Oops", "locations": [(1, 2)], "path": ["foo"]}],
            )

            assert not completed

            # Unblock succeed() and check that it does not complete
            await barrier.wait()
            await asyncio.sleep(0)
            assert not completed

        async def cancel_lists():
            barrier = Barrier(2)
            completed = False

            async def succeed(*_args):
                nonlocal completed
                await barrier.wait()
                completed = True  # pragma: no cover

            async def fail(*_args):
                raise RuntimeError("Oops")

            async def resolve_list(*args):
                return [fail(*args), succeed(*args)]

            schema = GraphQLSchema(
                GraphQLObjectType(
                    "Query",
                    {
                        "foo": GraphQLField(
                            GraphQLList(GraphQLNonNull(GraphQLBoolean)),
                            resolve=resolve_list,
                        )
                    },
                )
            )

            ast = parse("{foo}")

            awaitable_result = execute(schema, ast)
            assert isinstance(awaitable_result, Awaitable)
            result = await asyncio.wait_for(awaitable_result, 1)

            assert result == (
                {"foo": None},
                [{"message": "Oops", "locations": [(1, 2)], "path": ["foo", 0]}],
            )

            assert not completed

            # Unblock succeed() and check that it does not complete
            await barrier.wait()
            await asyncio.sleep(0)
            assert not completed

        async def cancel_async_iterators():
            barrier = Barrier(2)
            completed = False

            async def succeed(*_args):
                nonlocal completed
                await barrier.wait()
                completed = True  # pragma: no cover

            async def fail(*_args):
                raise RuntimeError("Oops")

            async def resolve_iterator(*args):
                yield fail(*args)
                yield succeed(*args)

            schema = GraphQLSchema(
                GraphQLObjectType(
                    "Query",
                    {
                        "foo": GraphQLField(
                            GraphQLList(GraphQLNonNull(GraphQLBoolean)),
                            resolve=resolve_iterator,
                        )
                    },
                )
            )

            ast = parse("{foo}")

            awaitable_result = execute(schema, ast)
            assert isinstance(awaitable_result, Awaitable)
            result = await asyncio.wait_for(awaitable_result, 1)

            assert result == (
                {"foo": None},
                [{"message": "Oops", "locations": [(1, 2)], "path": ["foo", 0]}],
            )

            assert not completed

            # Unblock succeed() and check that it does not complete
            await barrier.wait()
            await asyncio.sleep(0)
            assert not completed

        async def cancel_type_resolver():
            FooType = GraphQLInterfaceType("Foo", {"foo": GraphQLField(GraphQLString)})

            barrier = Barrier(3)
            completed = False

            async def is_type_of_bar(*_args):
                raise RuntimeError("Oops")

            BarType = GraphQLObjectType(
                "Bar",
                {
                    "foo": GraphQLField(GraphQLString),
                },
                interfaces=[FooType],
                is_type_of=is_type_of_bar,
            )

            async def is_type_of_baz(*_args):
                nonlocal completed
                await barrier.wait()
                completed = True  # pragma: no cover

            BazType = GraphQLObjectType(
                "Baz",
                {
                    "foo": GraphQLField(GraphQLString),
                },
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
                                {"foo": "bar"},
                                {"foo": "baz"},
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
            result = await asyncio.wait_for(awaitable_result, 1)

            assert result == (
                {"foo": [None, None]},
                [
                    {"message": "Oops", "locations": [(3, 17)], "path": ["foo", 0]},
                    {"message": "Oops", "locations": [(3, 17)], "path": ["foo", 1]},
                ],
            )

            assert not completed

            # Unblock succeed() and check that it does not complete
            await barrier.wait()
            await asyncio.sleep(0)
            assert not completed
