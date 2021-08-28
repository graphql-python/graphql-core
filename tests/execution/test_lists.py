from typing import Any

from pytest import mark

from graphql.execution import execute, execute_sync, ExecutionResult
from graphql.language import parse
from graphql.utilities import build_schema


class Data:
    def __init__(self, value):
        self.listField = value


async def get_async(value):
    return value


def describe_execute_accepts_any_iterable_as_list_value():
    def _complete(list_field):
        return execute_sync(
            build_schema("type Query { listField: [String] }"),
            parse("{ listField }"),
            Data(list_field),
        )

    def accepts_a_set_as_a_list_value():
        # Note that sets are not ordered in Python.
        list_field = {"apple", "banana", "coconut"}
        result = _complete(list_field)
        assert result.errors is None
        assert isinstance(result.data, dict)
        assert list(result.data) == ["listField"]
        assert isinstance(result.data["listField"], list)
        assert set(result.data["listField"]) == list_field

    def accepts_a_generator_as_a_list_value():
        def list_field():
            yield "one"
            yield 2
            yield True

        assert _complete(list_field()) == (
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

    def does_not_accept_a_dict_as_a_list_value():
        assert _complete({1: "one", 2: "two"}) == (
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
    async def _complete(list_field: Any, as_type: str) -> ExecutionResult:
        schema = build_schema(f"type Query {{ listField: {as_type} }}")
        document = parse("{ listField }")

        def execute_query(list_value: Any) -> Any:
            return execute(schema, document, Data(list_value))

        result = execute_query(list_field)
        assert isinstance(result, ExecutionResult)
        assert await execute_query(get_async(list_field)) == result
        if isinstance(list_field, list):
            assert await execute_query(list(map(get_async, list_field))) == result
            assert await execute_query(get_async(list_field)) == result

        return result

    @mark.asyncio
    async def contains_values():
        list_field = [1, 2]
        assert await _complete(list_field, "[Int]") == ({"listField": [1, 2]}, None)
        assert await _complete(list_field, "[Int]!") == ({"listField": [1, 2]}, None)
        assert await _complete(list_field, "[Int!]") == ({"listField": [1, 2]}, None)
        assert await _complete(list_field, "[Int!]!") == ({"listField": [1, 2]}, None)

    @mark.asyncio
    async def contains_null():
        list_field = [1, None, 2]
        errors = [
            {
                "message": "Cannot return null for non-nullable field Query.listField.",
                "locations": [(1, 3)],
                "path": ["listField", 1],
            }
        ]
        assert await _complete(list_field, "[Int]") == (
            {"listField": [1, None, 2]},
            None,
        )
        assert await _complete(list_field, "[Int]!") == (
            {"listField": [1, None, 2]},
            None,
        )
        assert await _complete(list_field, "[Int!]") == ({"listField": None}, errors)
        assert await _complete(list_field, "[Int!]!") == (None, errors)

    @mark.asyncio
    async def returns_null():
        list_field = None
        errors = [
            {
                "message": "Cannot return null for non-nullable field Query.listField.",
                "locations": [(1, 3)],
                "path": ["listField"],
            }
        ]
        assert await _complete(list_field, "[Int]") == ({"listField": None}, None)
        assert await _complete(list_field, "[Int]!") == (None, errors)
        assert await _complete(list_field, "[Int!]") == ({"listField": None}, None)
        assert await _complete(list_field, "[Int!]!") == (None, errors)

    @mark.asyncio
    async def contains_error():
        list_field = [1, RuntimeError("bad"), 2]
        errors = [
            {
                "message": "bad",
                "locations": [(1, 3)],
                "path": ["listField", 1],
            }
        ]
        assert await _complete(list_field, "[Int]") == (
            {"listField": [1, None, 2]},
            errors,
        )
        assert await _complete(list_field, "[Int]!") == (
            {"listField": [1, None, 2]},
            errors,
        )
        assert await _complete(list_field, "[Int!]") == (
            {"listField": None},
            errors,
        )
        assert await _complete(list_field, "[Int!]!") == (
            None,
            errors,
        )

    @mark.asyncio
    async def results_in_errors():
        list_field = RuntimeError("bad")
        errors = [
            {
                "message": "bad",
                "locations": [(1, 3)],
                "path": ["listField"],
            }
        ]
        assert await _complete(list_field, "[Int]") == (
            {"listField": None},
            errors,
        )
        assert await _complete(list_field, "[Int]!") == (
            None,
            errors,
        )
        assert await _complete(list_field, "[Int!]") == (
            {"listField": None},
            errors,
        )
        assert await _complete(list_field, "[Int!]!") == (
            None,
            errors,
        )
