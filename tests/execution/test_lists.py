from pytest import mark  # type: ignore

from graphql.execution import execute
from graphql.language import parse
from graphql.utilities import build_schema


class Data:
    def __init__(self, value):
        self.listField = value


async def get_async(value):
    return value


async def raise_async(msg):
    raise RuntimeError(msg)


def describe_execute_accepts_any_iterable_as_list_value():
    def _complete(list_field):
        return execute(
            build_schema("type Query { listField: [String] }"),
            parse("{ listField }"),
            Data(list_field),
        )

    def accepts_a_set_as_a_list_value():
        # We need to use a dict instead of a set,
        # since sets are not ordered in Python.
        list_field = dict.fromkeys(["apple", "banana", "coconut"])
        assert _complete(list_field) == (
            {"listField": ["apple", "banana", "coconut"]},
            None,
        )

    def accepts_a_generator_as_a_list_value():
        def yield_items():
            yield "one"
            yield 2
            yield True

        assert _complete(yield_items()) == (
            {"listField": ["one", "2", "true"]},
            None,
        )

    def accepts_function_arguments_as_a_list_value():
        def get_args(*args):
            return args  # actually just a tuple, nothing special in Python

        assert _complete(get_args("one", "two")) == (
            {"listField": ["one", "two"]},
            None,
        )

    def does_not_accept_iterable_string_literal_as_a_list_value():
        assert _complete("Singular") == (
            {"listField": None},
            [
                {
                    "message": "Expected Iterable,"
                    " but did not find one for field 'Query.listField'.",
                    "locations": [(1, 3)],
                    "path": ["listField"],
                }
            ],
        )


def describe_execute_handles_list_nullability():
    def describe_list():
        def _complete(list_field):
            return execute(
                build_schema("type Query { listField: [Int] }"),
                parse("{ listField }"),
                Data(list_field),
            )

        def describe_sync_list():
            def contains_values():
                assert _complete([1, 2]) == ({"listField": [1, 2]}, None)

            def contains_null():
                assert _complete([1, None, 2]) == ({"listField": [1, None, 2]}, None)

            def returns_null():
                assert _complete(None) == ({"listField": None}, None)

        def describe_async_list():
            @mark.asyncio
            async def contains_values():
                assert await _complete(get_async([1, 2])) == (
                    {"listField": [1, 2]},
                    None,
                )

            @mark.asyncio
            async def contains_null():
                assert await _complete(get_async([1, None, 2])) == (
                    {"listField": [1, None, 2]},
                    None,
                )

            @mark.asyncio
            async def returns_null():
                assert await _complete(get_async(None)) == ({"listField": None}, None)

            @mark.asyncio
            async def returns_error():
                assert await _complete(raise_async("bad")) == (
                    {"listField": None},
                    [
                        {
                            "message": "bad",
                            "locations": [(1, 3)],
                            "path": ["listField"],
                        }
                    ],
                )

        def describe_list_async():
            @mark.asyncio
            async def contains_values():
                assert await _complete([get_async(1), get_async(2)]) == (
                    {"listField": [1, 2]},
                    None,
                )

            @mark.asyncio
            async def contains_null():
                assert await _complete(
                    [get_async(1), get_async(None), get_async(2)]
                ) == ({"listField": [1, None, 2]}, None)

            @mark.asyncio
            async def contains_error():
                assert await _complete(
                    [get_async(1), raise_async("bad"), get_async(2)]
                ) == (
                    {"listField": [1, None, 2]},
                    [
                        {
                            "message": "bad",
                            "locations": [(1, 3)],
                            "path": ["listField", 1],
                        }
                    ],
                )

    def describe_not_null_list():
        def _complete(list_field):
            return execute(
                build_schema("type Query { listField: [Int]! }"),
                parse("{ listField }"),
                Data(list_field),
            )

        def describe_sync_list():
            def contains_values():
                assert _complete([1, 2]) == ({"listField": [1, 2]}, None)

            def contains_null():
                assert _complete([1, None, 2]) == ({"listField": [1, None, 2]}, None)

            def returns_null():
                assert _complete(None) == (
                    None,
                    [
                        {
                            "message": "Cannot return null"
                            " for non-nullable field Query.listField.",
                            "locations": [(1, 3)],
                            "path": ["listField"],
                        }
                    ],
                )

        def describe_async_list():
            @mark.asyncio
            async def contains_values():
                assert await _complete(get_async([1, 2])) == (
                    {"listField": [1, 2]},
                    None,
                )

            @mark.asyncio
            async def contains_null():
                assert await _complete(get_async([1, None, 2])) == (
                    {"listField": [1, None, 2]},
                    None,
                )

            @mark.asyncio
            async def returns_null():
                assert await _complete(get_async(None)) == (
                    None,
                    [
                        {
                            "message": "Cannot return null"
                            " for non-nullable field Query.listField.",
                            "locations": [(1, 3)],
                            "path": ["listField"],
                        }
                    ],
                )

            @mark.asyncio
            async def returns_error():
                assert await _complete(raise_async("bad")) == (
                    None,
                    [
                        {
                            "message": "bad",
                            "locations": [(1, 3)],
                            "path": ["listField"],
                        }
                    ],
                )

        def describe_list_async():
            @mark.asyncio
            async def contains_values():
                assert await _complete([get_async(1), get_async(2)]) == (
                    {"listField": [1, 2]},
                    None,
                )

            @mark.asyncio
            async def contains_null():
                assert await _complete(
                    [get_async(1), get_async(None), get_async(2)]
                ) == (
                    {"listField": [1, None, 2]},
                    None,
                )

            @mark.asyncio
            async def contains_error():
                assert await _complete(
                    [get_async(1), raise_async("bad"), get_async(2)]
                ) == (
                    {"listField": [1, None, 2]},
                    [
                        {
                            "message": "bad",
                            "locations": [(1, 3)],
                            "path": ["listField", 1],
                        }
                    ],
                )

    def describe_list_not_null():
        def _complete(list_field):
            return execute(
                build_schema("type Query { listField: [Int!] }"),
                parse("{ listField }"),
                Data(list_field),
            )

        def describe_sync_list():
            def contains_values():
                assert _complete([1, 2]) == ({"listField": [1, 2]}, None)

            def contains_null():
                assert _complete([1, None, 2]) == (
                    {"listField": None},
                    [
                        {
                            "message": "Cannot return null"
                            " for non-nullable field Query.listField.",
                            "locations": [(1, 3)],
                            "path": ["listField", 1],
                        }
                    ],
                )

            def returns_null():
                assert _complete(None) == ({"listField": None}, None)

        def describe_async_list():
            @mark.asyncio
            async def contains_values():
                assert await _complete(get_async([1, 2])) == (
                    {"listField": [1, 2]},
                    None,
                )

            @mark.asyncio
            async def contains_null():
                assert await _complete(get_async([1, None, 2])) == (
                    {"listField": None},
                    [
                        {
                            "message": "Cannot return null"
                            " for non-nullable field Query.listField.",
                            "locations": [(1, 3)],
                            "path": ["listField", 1],
                        }
                    ],
                )

            @mark.asyncio
            async def returns_null():
                assert await _complete(get_async(None)) == ({"listField": None}, None)

            @mark.asyncio
            async def returns_error():
                assert await _complete(raise_async("bad")) == (
                    {"listField": None},
                    [
                        {
                            "message": "bad",
                            "locations": [(1, 3)],
                            "path": ["listField"],
                        }
                    ],
                )

        def describe_list_async():
            @mark.asyncio
            async def contains_values():
                assert await _complete([get_async(1), get_async(2)]) == (
                    {"listField": [1, 2]},
                    None,
                )

            @mark.asyncio
            @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
            async def contains_null():
                assert await _complete(
                    [get_async(1), get_async(None), get_async(2)]
                ) == (
                    {"listField": None},
                    [
                        {
                            "message": "Cannot return null"
                            " for non-nullable field Query.listField.",
                            "locations": [(1, 3)],
                            "path": ["listField", 1],
                        }
                    ],
                )

            @mark.asyncio
            @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
            async def contains_error():
                assert await _complete(
                    [get_async(1), raise_async("bad"), get_async(2)]
                ) == (
                    {"listField": None},
                    [
                        {
                            "message": "bad",
                            "locations": [(1, 3)],
                            "path": ["listField", 1],
                        }
                    ],
                )

    def describe_not_null_list_not_null():
        def _complete(list_field):
            return execute(
                build_schema("type Query { listField: [Int!]! }"),
                parse("{ listField }"),
                Data(list_field),
            )

        def describe_sync_list():
            def contains_values():
                assert _complete([1, 2]) == ({"listField": [1, 2]}, None)

            def contains_null():
                assert _complete([1, None, 2]) == (
                    None,
                    [
                        {
                            "message": "Cannot return null"
                            " for non-nullable field Query.listField.",
                            "locations": [(1, 3)],
                            "path": ["listField", 1],
                        }
                    ],
                )

            def returns_null():
                assert _complete(None) == (
                    None,
                    [
                        {
                            "message": "Cannot return null"
                            " for non-nullable field Query.listField.",
                            "locations": [(1, 3)],
                            "path": ["listField"],
                        }
                    ],
                )

        def describe_async_list():
            @mark.asyncio
            async def contains_values():
                assert await _complete(get_async([1, 2])) == (
                    {"listField": [1, 2]},
                    None,
                )

            @mark.asyncio
            async def contains_null():
                assert await _complete(get_async([1, None, 2])) == (
                    None,
                    [
                        {
                            "message": "Cannot return null"
                            " for non-nullable field Query.listField.",
                            "locations": [(1, 3)],
                            "path": ["listField", 1],
                        }
                    ],
                )

            @mark.asyncio
            async def returns_null():
                assert await _complete(get_async(None)) == (
                    None,
                    [
                        {
                            "message": "Cannot return null"
                            " for non-nullable field Query.listField.",
                            "locations": [(1, 3)],
                            "path": ["listField"],
                        }
                    ],
                )

            @mark.asyncio
            async def returns_error():
                assert await _complete(raise_async("bad")) == (
                    None,
                    [
                        {
                            "message": "bad",
                            "locations": [(1, 3)],
                            "path": ["listField"],
                        }
                    ],
                )

        def describe_list_async():
            @mark.asyncio
            async def contains_values():
                assert await _complete([get_async(1), get_async(2)]) == (
                    {"listField": [1, 2]},
                    None,
                )

            @mark.asyncio
            @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
            async def contains_null():
                assert await _complete(
                    [get_async(1), get_async(None), get_async(2)]
                ) == (
                    None,
                    [
                        {
                            "message": "Cannot return null"
                            " for non-nullable field Query.listField.",
                            "locations": [(1, 3)],
                            "path": ["listField", 1],
                        }
                    ],
                )

            @mark.asyncio
            @mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning")
            async def contains__error():
                assert await _complete(
                    [get_async(1), raise_async("bad"), get_async(2)]
                ) == (
                    None,
                    [
                        {
                            "message": "bad",
                            "locations": [(1, 3)],
                            "path": ["listField", 1],
                        }
                    ],
                )
