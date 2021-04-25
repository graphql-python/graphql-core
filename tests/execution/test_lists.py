from collections import namedtuple
from gc import collect
from typing import Any

from pytest import mark  # type: ignore

from graphql.language import parse
from graphql.type import (
    GraphQLField,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLOutputType,
    GraphQLSchema,
    GraphQLString,
)
from graphql.execution import execute

Data = namedtuple("Data", "listField")


async def get_async(value):
    return value


async def raise_async(msg):
    raise RuntimeError(msg)


def get_response(test_type, test_data):
    data = Data(listField=test_data)

    schema = GraphQLSchema(
        GraphQLObjectType(
            "Query",
            lambda: {
                "listField": GraphQLField(test_type),
            },
        )
    )

    return execute(schema, parse("{ listField }"), data)


def check_response(response: Any, expected: Any) -> None:
    if not response.errors:
        response = response.data
    assert response == expected


def check(test_type: GraphQLOutputType, test_data: Any, expected: Any) -> None:

    check_response(get_response(test_type, test_data), expected)


async def check_async(
    test_type: GraphQLOutputType, test_data: Any, expected: Any
) -> None:
    check_response(await get_response(test_type, test_data), expected)

    # Note: When Array values are rejected asynchronously,
    # the remaining values may not be awaited any more.
    # We manually run a garbage collection after each test so that
    # these warnings appear immediately and can be filtered out.
    collect()


def describe_execute_accepts_any_iterable_as_list_value():
    def accepts_a_set_as_a_list_value():
        # We need to use a dict instead of a set,
        # since sets are not ordered in Python.
        check(
            GraphQLList(GraphQLString),
            dict.fromkeys(["apple", "banana", "coconut"]),
            {"listField": ["apple", "banana", "coconut"]},
        )

    def accepts_a_generator_as_a_list_value():
        def yield_items():
            yield "one"
            yield 2
            yield True

        check(
            GraphQLList(GraphQLString),
            yield_items(),
            {"listField": ["one", "2", "true"]},
        )

    def accepts_function_arguments_as_a_list_value():
        def get_args(*args):
            return args  # actually just a tuple, nothing special in Python

        check(
            GraphQLList(GraphQLString),
            get_args("one", "two"),
            {"listField": ["one", "two"]},
        )

    def does_not_accept_iterable_string_literal_as_a_list_value():
        check(
            GraphQLList(GraphQLString),
            "Singular",
            (
                {"listField": None},
                [
                    {
                        "message": "Expected Iterable,"
                        " but did not find one for field 'Query.listField'.",
                        "locations": [(1, 3)],
                        "path": ["listField"],
                    }
                ],
            ),
        )


def describe_execute_handles_list_nullability():
    def describe_list():
        type_ = GraphQLList(GraphQLInt)

        def describe_sync_list():
            def contains_values():
                check(type_, [1, 2], {"listField": [1, 2]})

            def contains_null():
                check(type_, [1, None, 2], {"listField": [1, None, 2]})

            def returns_null():
                check(type_, None, {"listField": None})

        def describe_async_list():
            @mark.asyncio
            async def contains_values():
                await check_async(type_, get_async([1, 2]), {"listField": [1, 2]})

            @mark.asyncio
            async def contains_null():
                await check_async(
                    type_, get_async([1, None, 2]), {"listField": [1, None, 2]}
                )

            @mark.asyncio
            async def returns_null():
                await check_async(type_, get_async(None), {"listField": None})

            @mark.asyncio
            async def async_error():
                await check_async(
                    type_,
                    raise_async("bad"),
                    (
                        {"listField": None},
                        [
                            {
                                "message": "bad",
                                "locations": [(1, 3)],
                                "path": ["listField"],
                            }
                        ],
                    ),
                )

        def describe_list_async():
            @mark.asyncio
            async def contains_values():
                await check_async(
                    type_, [get_async(1), get_async(2)], {"listField": [1, 2]}
                )

            @mark.asyncio
            async def contains_null():
                await check_async(
                    type_,
                    [get_async(1), get_async(None), get_async(2)],
                    {"listField": [1, None, 2]},
                )

            @mark.asyncio
            async def contains_async_error():
                await check_async(
                    type_,
                    [get_async(1), raise_async("bad"), get_async(2)],
                    (
                        {"listField": [1, None, 2]},
                        [
                            {
                                "message": "bad",
                                "locations": [(1, 3)],
                                "path": ["listField", 1],
                            }
                        ],
                    ),
                )

    def describe_not_null_list():
        type_ = GraphQLNonNull(GraphQLList(GraphQLInt))

        def describe_sync_list():
            def contains_values():
                check(type_, [1, 2], {"listField": [1, 2]})

            def contains_null():
                check(type_, [1, None, 2], {"listField": [1, None, 2]})

            def returns_null():
                check(
                    type_,
                    None,
                    (
                        None,
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field Query.listField.",
                                "locations": [(1, 3)],
                                "path": ["listField"],
                            }
                        ],
                    ),
                )

        def describe_async_list():
            @mark.asyncio
            async def contains_values():
                await check_async(type_, get_async([1, 2]), {"listField": [1, 2]})

            @mark.asyncio
            async def contains_null():
                await check_async(
                    type_, get_async([1, None, 2]), {"listField": [1, None, 2]}
                )

            @mark.asyncio
            async def returns_null():
                await check_async(
                    type_,
                    get_async(None),
                    (
                        None,
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field Query.listField.",
                                "locations": [(1, 3)],
                                "path": ["listField"],
                            }
                        ],
                    ),
                )

            @mark.asyncio
            async def async_error():
                await check_async(
                    type_,
                    raise_async("bad"),
                    (
                        None,
                        [
                            {
                                "message": "bad",
                                "locations": [(1, 3)],
                                "path": ["listField"],
                            }
                        ],
                    ),
                )

        def describe_list_async():
            @mark.asyncio
            async def contains_values():
                await check_async(
                    type_, [get_async(1), get_async(2)], {"listField": [1, 2]}
                )

            @mark.asyncio
            async def contains_null():
                await check_async(
                    type_,
                    [get_async(1), get_async(None), get_async(2)],
                    {"listField": [1, None, 2]},
                )

            @mark.asyncio
            async def contains_async_error():
                await check_async(
                    type_,
                    [get_async(1), raise_async("bad"), get_async(2)],
                    (
                        {"listField": [1, None, 2]},
                        [
                            {
                                "message": "bad",
                                "locations": [(1, 3)],
                                "path": ["listField", 1],
                            }
                        ],
                    ),
                )

    def describe_list_not_null():
        type_ = GraphQLList(GraphQLNonNull(GraphQLInt))

        def describe_sync_list():
            def contains_values():
                check(type_, [1, 2], {"listField": [1, 2]})

            def contains_null():
                check(
                    type_,
                    [1, None, 2],
                    (
                        {"listField": None},
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field Query.listField.",
                                "locations": [(1, 3)],
                                "path": ["listField", 1],
                            }
                        ],
                    ),
                )

            def returns_null():
                check(type_, None, {"listField": None})

        def describe_async_list():
            @mark.asyncio
            async def contains_values():
                await check_async(type_, get_async([1, 2]), {"listField": [1, 2]})

            @mark.asyncio
            async def contains_null():
                await check_async(
                    type_,
                    get_async([1, None, 2]),
                    (
                        {"listField": None},
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field Query.listField.",
                                "locations": [(1, 3)],
                                "path": ["listField", 1],
                            }
                        ],
                    ),
                )

            @mark.asyncio
            async def returns_null():
                await check_async(type_, get_async(None), {"listField": None})

            @mark.asyncio
            async def async_error():
                await check_async(
                    type_,
                    raise_async("bad"),
                    (
                        {"listField": None},
                        [
                            {
                                "message": "bad",
                                "locations": [(1, 3)],
                                "path": ["listField"],
                            }
                        ],
                    ),
                )

        def describe_list_async():
            @mark.asyncio
            async def contains_values():
                await check_async(
                    type_, [get_async(1), get_async(2)], {"listField": [1, 2]}
                )

            @mark.asyncio
            @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
            async def contains_null():
                await check_async(
                    type_,
                    [get_async(1), get_async(None), get_async(2)],
                    (
                        {"listField": None},
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field Query.listField.",
                                "locations": [(1, 3)],
                                "path": ["listField", 1],
                            }
                        ],
                    ),
                )

            @mark.asyncio
            @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
            async def contains_async_error():
                await check_async(
                    type_,
                    [get_async(1), raise_async("bad"), get_async(2)],
                    (
                        {"listField": None},
                        [
                            {
                                "message": "bad",
                                "locations": [(1, 3)],
                                "path": ["listField", 1],
                            }
                        ],
                    ),
                )

    def describe_not_null_list_not_null():
        type_ = GraphQLNonNull(GraphQLList(GraphQLNonNull(GraphQLInt)))

        def describe_sync_list():
            def contains_values():
                check(type_, [1, 2], {"listField": [1, 2]})

            def contains_null():
                check(
                    type_,
                    [1, None, 2],
                    (
                        None,
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field Query.listField.",
                                "locations": [(1, 3)],
                                "path": ["listField", 1],
                            }
                        ],
                    ),
                )

            def returns_null():
                check(
                    type_,
                    None,
                    (
                        None,
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field Query.listField.",
                                "locations": [(1, 3)],
                                "path": ["listField"],
                            }
                        ],
                    ),
                )

        def describe_async_list():
            @mark.asyncio
            async def contains_values():
                await check_async(type_, get_async([1, 2]), {"listField": [1, 2]})

            @mark.asyncio
            async def contains_null():
                await check_async(
                    type_,
                    get_async([1, None, 2]),
                    (
                        None,
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field Query.listField.",
                                "locations": [(1, 3)],
                                "path": ["listField", 1],
                            }
                        ],
                    ),
                )

            @mark.asyncio
            async def returns_null():
                await check_async(
                    type_,
                    get_async(None),
                    (
                        None,
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field Query.listField.",
                                "locations": [(1, 3)],
                                "path": ["listField"],
                            }
                        ],
                    ),
                )

            @mark.asyncio
            async def async_error():
                await check_async(
                    type_,
                    raise_async("bad"),
                    (
                        None,
                        [
                            {
                                "message": "bad",
                                "locations": [(1, 3)],
                                "path": ["listField"],
                            }
                        ],
                    ),
                )

        def describe_list_async():
            @mark.asyncio
            async def contains_values():
                await check_async(
                    type_, [get_async(1), get_async(2)], {"listField": [1, 2]}
                )

            @mark.asyncio
            @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
            async def contains_null():
                await check_async(
                    type_,
                    [get_async(1), get_async(None), get_async(2)],
                    (
                        None,
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field Query.listField.",
                                "locations": [(1, 3)],
                                "path": ["listField", 1],
                            }
                        ],
                    ),
                )

            @mark.asyncio
            @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
            async def contains_async_error():
                await check_async(
                    type_,
                    [get_async(1), raise_async("bad"), get_async(2)],
                    (
                        None,
                        [
                            {
                                "message": "bad",
                                "locations": [(1, 3)],
                                "path": ["listField", 1],
                            }
                        ],
                    ),
                )
