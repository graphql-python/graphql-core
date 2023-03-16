from typing import Any, AsyncGenerator

from pytest import mark

from graphql.execution import ExecutionResult, execute, execute_sync
from graphql.language import parse
from graphql.pyutils import is_awaitable
from graphql.type import (
    GraphQLField,
    GraphQLFieldResolver,
    GraphQLList,
    GraphQLObjectType,
    GraphQLResolveInfo,
    GraphQLSchema,
    GraphQLString,
)
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

    def accepts_a_list_as_a_list_value():
        result = _complete([])
        assert result == ({"listField": []}, None)
        list_field = ["just an apple"]
        result = _complete(list_field)
        assert result == ({"listField": list_field}, None)
        list_field = ["apple", "banana", "coconut"]
        result = _complete(list_field)
        assert result == ({"listField": list_field}, None)

    def accepts_a_tuple_as_a_list_value():
        list_field = ("apple", "banana", "coconut")
        result = _complete(list_field)
        assert result == ({"listField": list(list_field)}, None)

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

    def accepts_a_custom_iterable_as_a_list_value():
        class ListField:
            def __iter__(self):
                self.last = "hello"
                return self

            def __next__(self):
                last = self.last
                if last == "stop":
                    raise StopIteration
                self.last = "world" if last == "hello" else "stop"
                return last

        assert _complete(ListField()) == (
            {"listField": ["hello", "world"]},
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


def describe_execute_accepts_async_iterables_as_list_value():
    async def _complete(list_field, as_: str = "[String]"):
        result = execute(
            build_schema(f"type Query {{ listField: {as_} }}"),
            parse("{ listField }"),
            Data(list_field),
        )
        assert is_awaitable(result)
        return await result

    class _IndexData:
        def __init__(self, index: int):
            self.index = index

    async def _complete_object_lists(
        resolve: GraphQLFieldResolver, count=3
    ) -> ExecutionResult:
        async def _list_field(
            obj_: Any, info_: GraphQLResolveInfo
        ) -> AsyncGenerator[_IndexData, None]:
            for index in range(count):
                yield _IndexData(index)

        schema = GraphQLSchema(
            GraphQLObjectType(
                "Query",
                {
                    "listField": GraphQLField(
                        GraphQLList(
                            GraphQLObjectType(
                                "ObjectWrapper",
                                {"index": GraphQLField(GraphQLString, resolve=resolve)},
                            )
                        ),
                        resolve=_list_field,
                    )
                },
            )
        )
        result = execute(schema, document=parse("{ listField { index } }"))
        assert is_awaitable(result)
        return await result

    @mark.asyncio
    async def accepts_an_async_generator_as_a_list_value():
        async def list_field():
            yield "two"
            yield 4
            yield False

        assert await _complete(list_field()) == (
            {"listField": ["two", "4", "false"]},
            None,
        )

    @mark.asyncio
    async def accepts_a_custom_async_iterable_as_a_list_value():
        class ListField:
            def __aiter__(self):
                self.last = "hello"
                return self

            async def __anext__(self):
                last = self.last
                if last == "stop":
                    raise StopAsyncIteration
                self.last = "world" if last == "hello" else "stop"
                return last

        assert await _complete(ListField()) == (
            {"listField": ["hello", "world"]},
            None,
        )

    @mark.asyncio
    async def handles_an_async_generator_that_throws():
        async def list_field():
            yield "two"
            yield 4
            raise RuntimeError("bad")

        assert await _complete(list_field()) == (
            {"listField": ["two", "4", None]},
            [{"message": "bad", "locations": [(1, 3)], "path": ["listField", 2]}],
        )

    @mark.asyncio
    async def handles_an_async_generator_where_intermediate_value_triggers_an_error():
        async def list_field():
            yield "two"
            yield {}
            yield 4

        assert await _complete(list_field()) == (
            {"listField": ["two", None, "4"]},
            [
                {
                    "message": "String cannot represent value: {}",
                    "locations": [(1, 3)],
                    "path": ["listField", 1],
                }
            ],
        )

    @mark.asyncio
    async def handles_errors_from_complete_value_in_async_iterables():
        async def list_field():
            yield "two"
            yield {}

        assert await _complete(list_field()) == (
            {"listField": ["two", None]},
            [
                {
                    "message": "String cannot represent value: {}",
                    "locations": [(1, 3)],
                    "path": ["listField", 1],
                }
            ],
        )

    @mark.asyncio
    async def handles_async_functions_from_complete_value_in_async_iterables():
        async def resolve(data: _IndexData, info_: GraphQLResolveInfo) -> int:
            return data.index

        assert await _complete_object_lists(resolve) == (
            {"listField": [{"index": "0"}, {"index": "1"}, {"index": "2"}]},
            None,
        )

    @mark.asyncio
    async def handles_single_async_functions_from_complete_value_in_async_iterables():
        async def resolve(data: _IndexData, info_: GraphQLResolveInfo) -> int:
            return data.index

        assert await _complete_object_lists(resolve, 1) == (
            {"listField": [{"index": "0"}]},
            None,
        )

    @mark.asyncio
    async def handles_async_errors_from_complete_value_in_async_iterables():
        async def resolve(data: _IndexData, info_: GraphQLResolveInfo) -> int:
            index = data.index
            if index == 2:
                raise RuntimeError("bad")
            return index

        assert await _complete_object_lists(resolve) == (
            {"listField": [{"index": "0"}, {"index": "1"}, {"index": None}]},
            [
                {
                    "message": "bad",
                    "locations": [(1, 15)],
                    "path": ["listField", 2, "index"],
                }
            ],
        )

    @mark.asyncio
    async def handles_nulls_yielded_by_async_generator():
        async def list_field():
            yield 1
            yield None
            yield 2

        data = {"listField": [1, None, 2]}
        message = "Cannot return null for non-nullable field Query.listField."
        errors = [{"message": message, "locations": [(1, 3)], "path": ["listField", 1]}]

        assert await _complete(list_field(), "[Int]") == (data, None)
        assert await _complete(list_field(), "[Int]!") == (data, None)
        assert await _complete(list_field(), "[Int!]") == ({"listField": None}, errors)
        assert await _complete(list_field(), "[Int!]!") == (None, errors)


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
