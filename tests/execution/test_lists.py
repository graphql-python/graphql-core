from collections import namedtuple
from gc import collect

from pytest import mark  # type: ignore

from graphql.language import parse
from graphql.type import (
    GraphQLField,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)
from graphql.execution import execute

Data = namedtuple("Data", "test")


async def get_async(value):
    return value


async def raise_async(msg):
    raise RuntimeError(msg)


def get_response(test_type, test_data):
    data = Data(test=test_data)

    data_type = GraphQLObjectType(
        "DataType",
        lambda: {
            "test": GraphQLField(test_type),
            "nest": GraphQLField(data_type, resolve=lambda *_args: data),
        },
    )

    return execute(
        schema=GraphQLSchema(data_type),
        document=parse("{ nest { test } }"),
        context_value=data,
    )


def check_response(response, expected):
    if not response.errors:
        response = response.data
    assert response == expected


def check(test_type, test_data, expected):

    check_response(get_response(test_type, test_data), expected)


async def check_async(test_type, test_data, expected):
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
            {"nest": {"test": ["apple", "banana", "coconut"]}},
        )

    def accepts_a_generator_as_a_list_value():
        def yield_items():
            yield "one"
            yield 2
            yield True

        check(
            GraphQLList(GraphQLString),
            yield_items(),
            {"nest": {"test": ["one", "2", "true"]}},
        )

    def accepts_function_arguments_as_a_list_value():
        def get_args(*args):
            return args  # actually just a tuple, nothing special in Python

        check(
            GraphQLList(GraphQLString),
            get_args("one", "two"),
            {"nest": {"test": ["one", "two"]}},
        )

    def does_not_accept_iterable_string_literal_as_a_list_value():
        check(
            GraphQLList(GraphQLString),
            "Singular",
            (
                {"nest": {"test": None}},
                [
                    {
                        "message": "Expected Iterable,"
                        " but did not find one for field 'DataType.test'.",
                        "locations": [(1, 10)],
                        "path": ["nest", "test"],
                    }
                ],
            ),
        )


def describe_execute_handles_list_nullability():
    def describe_list():
        type_ = GraphQLList(GraphQLInt)

        def describe_sync_list():
            def contains_values():
                check(type_, [1, 2], {"nest": {"test": [1, 2]}})

            def contains_null():
                check(type_, [1, None, 2], {"nest": {"test": [1, None, 2]}})

            def returns_null():
                check(type_, None, {"nest": {"test": None}})

        def describe_async_list():
            @mark.asyncio
            async def contains_values():
                await check_async(type_, get_async([1, 2]), {"nest": {"test": [1, 2]}})

            @mark.asyncio
            async def contains_null():
                await check_async(
                    type_, get_async([1, None, 2]), {"nest": {"test": [1, None, 2]}}
                )

            @mark.asyncio
            async def returns_null():
                await check_async(type_, get_async(None), {"nest": {"test": None}})

            @mark.asyncio
            async def async_error():
                await check_async(
                    type_,
                    raise_async("bad"),
                    (
                        {"nest": {"test": None}},
                        [
                            {
                                "message": "bad",
                                "locations": [(1, 10)],
                                "path": ["nest", "test"],
                            }
                        ],
                    ),
                )

        def describe_list_async():
            @mark.asyncio
            async def contains_values():
                await check_async(
                    type_, [get_async(1), get_async(2)], {"nest": {"test": [1, 2]}}
                )

            @mark.asyncio
            async def contains_null():
                await check_async(
                    type_,
                    [get_async(1), get_async(None), get_async(2)],
                    {"nest": {"test": [1, None, 2]}},
                )

            @mark.asyncio
            async def contains_async_error():
                await check_async(
                    type_,
                    [get_async(1), raise_async("bad"), get_async(2)],
                    (
                        {"nest": {"test": [1, None, 2]}},
                        [
                            {
                                "message": "bad",
                                "locations": [(1, 10)],
                                "path": ["nest", "test", 1],
                            }
                        ],
                    ),
                )

    def describe_not_null_list():
        type_ = GraphQLNonNull(GraphQLList(GraphQLInt))

        def describe_sync_list():
            def contains_values():
                check(type_, [1, 2], {"nest": {"test": [1, 2]}})

            def contains_null():
                check(type_, [1, None, 2], {"nest": {"test": [1, None, 2]}})

            def returns_null():
                check(
                    type_,
                    None,
                    (
                        {"nest": None},
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field DataType.test.",
                                "locations": [(1, 10)],
                                "path": ["nest", "test"],
                            }
                        ],
                    ),
                )

        def describe_async_list():
            @mark.asyncio
            async def contains_values():
                await check_async(type_, get_async([1, 2]), {"nest": {"test": [1, 2]}})

            @mark.asyncio
            async def contains_null():
                await check_async(
                    type_, get_async([1, None, 2]), {"nest": {"test": [1, None, 2]}}
                )

            @mark.asyncio
            async def returns_null():
                await check_async(
                    type_,
                    get_async(None),
                    (
                        {"nest": None},
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field DataType.test.",
                                "locations": [(1, 10)],
                                "path": ["nest", "test"],
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
                        {"nest": None},
                        [
                            {
                                "message": "bad",
                                "locations": [(1, 10)],
                                "path": ["nest", "test"],
                            }
                        ],
                    ),
                )

        def describe_list_async():
            @mark.asyncio
            async def contains_values():
                await check_async(
                    type_, [get_async(1), get_async(2)], {"nest": {"test": [1, 2]}}
                )

            @mark.asyncio
            async def contains_null():
                await check_async(
                    type_,
                    [get_async(1), get_async(None), get_async(2)],
                    {"nest": {"test": [1, None, 2]}},
                )

            @mark.asyncio
            async def contains_async_error():
                await check_async(
                    type_,
                    [get_async(1), raise_async("bad"), get_async(2)],
                    (
                        {"nest": {"test": [1, None, 2]}},
                        [
                            {
                                "message": "bad",
                                "locations": [(1, 10)],
                                "path": ["nest", "test", 1],
                            }
                        ],
                    ),
                )

    def describe_list_not_null():
        type_ = GraphQLList(GraphQLNonNull(GraphQLInt))

        def describe_sync_list():
            def contains_values():
                check(type_, [1, 2], {"nest": {"test": [1, 2]}})

            def contains_null():
                check(
                    type_,
                    [1, None, 2],
                    (
                        {"nest": {"test": None}},
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field DataType.test.",
                                "locations": [(1, 10)],
                                "path": ["nest", "test", 1],
                            }
                        ],
                    ),
                )

            def returns_null():
                check(type_, None, {"nest": {"test": None}})

        def describe_async_list():
            @mark.asyncio
            async def contains_values():
                await check_async(type_, get_async([1, 2]), {"nest": {"test": [1, 2]}})

            @mark.asyncio
            async def contains_null():
                await check_async(
                    type_,
                    get_async([1, None, 2]),
                    (
                        {"nest": {"test": None}},
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field DataType.test.",
                                "locations": [(1, 10)],
                                "path": ["nest", "test", 1],
                            }
                        ],
                    ),
                )

            @mark.asyncio
            async def returns_null():
                await check_async(type_, get_async(None), {"nest": {"test": None}})

            @mark.asyncio
            async def async_error():
                await check_async(
                    type_,
                    raise_async("bad"),
                    (
                        {"nest": {"test": None}},
                        [
                            {
                                "message": "bad",
                                "locations": [(1, 10)],
                                "path": ["nest", "test"],
                            }
                        ],
                    ),
                )

        def describe_list_async():
            @mark.asyncio
            async def contains_values():
                await check_async(
                    type_, [get_async(1), get_async(2)], {"nest": {"test": [1, 2]}}
                )

            @mark.asyncio
            @mark.filterwarnings("ignore::RuntimeWarning")
            async def contains_null():
                await check_async(
                    type_,
                    [get_async(1), get_async(None), get_async(2)],
                    (
                        {"nest": {"test": None}},
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field DataType.test.",
                                "locations": [(1, 10)],
                                "path": ["nest", "test", 1],
                            }
                        ],
                    ),
                )

            @mark.asyncio
            @mark.filterwarnings("ignore::RuntimeWarning")
            async def contains_async_error():
                await check_async(
                    type_,
                    [get_async(1), raise_async("bad"), get_async(2)],
                    (
                        {"nest": {"test": None}},
                        [
                            {
                                "message": "bad",
                                "locations": [(1, 10)],
                                "path": ["nest", "test", 1],
                            }
                        ],
                    ),
                )

    def describe_not_null_list_not_null():
        type_ = GraphQLNonNull(GraphQLList(GraphQLNonNull(GraphQLInt)))

        def describe_sync_list():
            def contains_values():
                check(type_, [1, 2], {"nest": {"test": [1, 2]}})

            def contains_null():
                check(
                    type_,
                    [1, None, 2],
                    (
                        {"nest": None},
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field DataType.test.",
                                "locations": [(1, 10)],
                                "path": ["nest", "test", 1],
                            }
                        ],
                    ),
                )

            def returns_null():
                check(
                    type_,
                    None,
                    (
                        {"nest": None},
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field DataType.test.",
                                "locations": [(1, 10)],
                                "path": ["nest", "test"],
                            }
                        ],
                    ),
                )

        def describe_async_list():
            @mark.asyncio
            async def contains_values():
                await check_async(type_, get_async([1, 2]), {"nest": {"test": [1, 2]}})

            @mark.asyncio
            async def contains_null():
                await check_async(
                    type_,
                    get_async([1, None, 2]),
                    (
                        {"nest": None},
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field DataType.test.",
                                "locations": [(1, 10)],
                                "path": ["nest", "test", 1],
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
                        {"nest": None},
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field DataType.test.",
                                "locations": [(1, 10)],
                                "path": ["nest", "test"],
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
                        {"nest": None},
                        [
                            {
                                "message": "bad",
                                "locations": [(1, 10)],
                                "path": ["nest", "test"],
                            }
                        ],
                    ),
                )

        def describe_list_async():
            @mark.asyncio
            async def contains_values():
                await check_async(
                    type_, [get_async(1), get_async(2)], {"nest": {"test": [1, 2]}}
                )

            @mark.asyncio
            @mark.filterwarnings("ignore::RuntimeWarning")
            async def contains_null():
                await check_async(
                    type_,
                    [get_async(1), get_async(None), get_async(2)],
                    (
                        {"nest": None},
                        [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field DataType.test.",
                                "locations": [(1, 10)],
                                "path": ["nest", "test", 1],
                            }
                        ],
                    ),
                )

            @mark.asyncio
            @mark.filterwarnings("ignore::RuntimeWarning")
            async def contains_async_error():
                await check_async(
                    type_,
                    [get_async(1), raise_async("bad"), get_async(2)],
                    (
                        {"nest": None},
                        [
                            {
                                "message": "bad",
                                "locations": [(1, 10)],
                                "path": ["nest", "test", 1],
                            }
                        ],
                    ),
                )
