from asyncio import Event, Lock, gather, sleep
from typing import Any, Awaitable, Dict, List, NamedTuple

from pytest import mark, raises

from graphql.error import GraphQLError
from graphql.execution import (
    ExecutionContext,
    ExecutionResult,
    ExperimentalIncrementalExecutionResults,
    IncrementalStreamResult,
    experimental_execute_incrementally,
)
from graphql.execution.execute import StreamRecord
from graphql.language import DocumentNode, parse
from graphql.pyutils import Path
from graphql.type import (
    GraphQLField,
    GraphQLID,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)


try:  # pragma: no cover
    anext
except NameError:  # pragma: no cover (Python < 3.10)
    # noinspection PyShadowingBuiltins
    async def anext(iterator):
        """Return the next item from an async iterator."""
        return await iterator.__anext__()


friend_type = GraphQLObjectType(
    "Friend",
    {
        "id": GraphQLField(GraphQLID),
        "name": GraphQLField(GraphQLString),
        "nonNullName": GraphQLField(GraphQLNonNull(GraphQLString)),
    },
)


class Friend(NamedTuple):
    name: str
    id: int


friends = [Friend("Luke", 1), Friend("Han", 2), Friend("Leia", 3)]

query = GraphQLObjectType(
    "Query",
    {
        "scalarList": GraphQLField(GraphQLList(GraphQLString)),
        "scalarListList": GraphQLField(GraphQLList(GraphQLList(GraphQLString))),
        "friendList": GraphQLField(GraphQLList(friend_type)),
        "nonNullFriendList": GraphQLField(GraphQLList(GraphQLNonNull(friend_type))),
        "nestedObject": GraphQLField(
            GraphQLObjectType(
                "NestedObject",
                {
                    "scalarField": GraphQLField(GraphQLString),
                    "nonNullScalarField": GraphQLField(GraphQLNonNull(GraphQLString)),
                    "nestedFriendList": GraphQLField(GraphQLList(friend_type)),
                    "deeperNestedObject": GraphQLField(
                        GraphQLObjectType(
                            "DeeperNestedObject",
                            {
                                "nonNullScalarField": GraphQLField(
                                    GraphQLNonNull(GraphQLString)
                                ),
                                "deeperNestedFriendList": GraphQLField(
                                    GraphQLList(friend_type)
                                ),
                            },
                        )
                    ),
                },
            )
        ),
    },
)

schema = GraphQLSchema(query)


async def complete(document: DocumentNode, root_value: Any = None) -> Any:
    result = experimental_execute_incrementally(schema, document, root_value)
    if isinstance(result, Awaitable):
        result = await result

    if isinstance(result, ExperimentalIncrementalExecutionResults):
        results: List[Any] = [result.initial_result.formatted]
        async for patch in result.subsequent_results:
            results.append(patch.formatted)
        return results

    assert isinstance(result, ExecutionResult)
    return result.formatted


async def complete_async(
    document: DocumentNode, num_calls: int, root_value: Any = None
) -> Any:
    result = experimental_execute_incrementally(schema, document, root_value)
    assert isinstance(result, Awaitable)
    result = await result
    assert isinstance(result, ExperimentalIncrementalExecutionResults)

    class IteratorResult:
        """Iterator result with formatted output."""

        def __init__(self, value=None):
            self.value = value

        @property
        def formatted(self):
            if self.value is None:
                return {"done": True, "value": None}
            return {"done": False, "value": self.value.formatted}

    lock = Lock()
    iterator = result.subsequent_results

    async def locked_next():
        """Get next value with lock for concurrent access."""
        async with lock:
            try:
                next_value = await anext(iterator)
            except StopAsyncIteration:
                return None
        return next_value

    next_results = [locked_next() for _i in range(num_calls)]

    results = [result.initial_result]
    results.extend(await gather(*next_results))

    return [IteratorResult(result).formatted for result in results]


def modified_args(args: Dict[str, Any], **modifications: Any) -> Dict[str, Any]:
    return {**args, **modifications}


def describe_execute_stream_directive():
    def can_format_and_print_incremental_stream_result():
        result = IncrementalStreamResult()
        assert result.formatted == {"items": None}
        assert str(result) == "IncrementalStreamResult(items=None, errors=None)"

        result = IncrementalStreamResult(
            items=["hello", "world"],
            errors=[GraphQLError("msg")],
            path=["foo", 1],
            label="bar",
            extensions={"baz": 2},
        )
        assert result.formatted == {
            "items": ["hello", "world"],
            "errors": [{"message": "msg"}],
            "extensions": {"baz": 2},
            "label": "bar",
            "path": ["foo", 1],
        }
        assert (
            str(result) == "IncrementalStreamResult(items=['hello', 'world'],"
            " errors=[GraphQLError('msg')], path=['foo', 1], label='bar',"
            " extensions={'baz': 2})"
        )

    def can_print_stream_record():
        context = ExecutionContext.build(schema, parse("{ hero { id } }"))
        assert isinstance(context, ExecutionContext)
        record = StreamRecord(None, None, None, None, context)
        assert str(record) == "StreamRecord(path=[])"
        record = StreamRecord("foo", Path(None, "bar", "Bar"), None, record, context)
        assert (
            str(record) == "StreamRecord(" "path=['bar'], label='foo', parent_context)"
        )
        record.items = ["hello", "world"]
        assert (
            str(record) == "StreamRecord("
            "path=['bar'], label='foo', parent_context, items)"
        )

    # noinspection PyTypeChecker
    def can_compare_incremental_stream_result():
        args: Dict[str, Any] = {
            "items": ["hello", "world"],
            "errors": [GraphQLError("msg")],
            "path": ["foo", 1],
            "label": "bar",
            "extensions": {"baz": 2},
        }
        result = IncrementalStreamResult(**args)
        assert result == IncrementalStreamResult(**args)
        assert result != IncrementalStreamResult(
            **modified_args(args, items=["hello", "foo"])
        )
        assert result != IncrementalStreamResult(**modified_args(args, errors=[]))
        assert result != IncrementalStreamResult(**modified_args(args, path=["foo", 2]))
        assert result != IncrementalStreamResult(**modified_args(args, label="baz"))
        assert result != IncrementalStreamResult(
            **modified_args(args, extensions={"baz": 1})
        )
        assert result == tuple(args.values())
        assert result == tuple(args.values())[:4]
        assert result == tuple(args.values())[:3]
        assert result == tuple(args.values())[:2]
        assert result != tuple(args.values())[:1]
        assert result != (["hello", "world"], [])
        assert result == args
        assert result == dict(list(args.items())[:2])
        assert result == dict(list(args.items())[:3])
        assert result != dict(list(args.items())[:2] + [("path", ["foo", 2])])
        assert result != {**args, "label": "baz"}

    @mark.asyncio
    async def can_stream_a_list_field():
        document = parse("{ scalarList @stream(initialCount: 1) }")
        result = await complete(
            document, {"scalarList": ["apple", "banana", "coconut"]}
        )
        assert result == [
            {
                "data": {
                    "scalarList": ["apple"],
                },
                "hasNext": True,
            },
            {
                "incremental": [{"items": ["banana"], "path": ["scalarList", 1]}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": ["coconut"], "path": ["scalarList", 2]}],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def can_use_default_value_of_initial_count():
        document = parse("{ scalarList @stream }")
        result = await complete(
            document, {"scalarList": ["apple", "banana", "coconut"]}
        )
        assert result == [
            {
                "data": {
                    "scalarList": [],
                },
                "hasNext": True,
            },
            {
                "incremental": [{"items": ["apple"], "path": ["scalarList", 0]}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": ["banana"], "path": ["scalarList", 1]}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": ["coconut"], "path": ["scalarList", 2]}],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def negative_values_of_initial_count_throw_field_errors():
        document = parse("{ scalarList @stream(initialCount: -2) }")
        result = await complete(
            document, {"scalarList": ["apple", "banana", "coconut"]}
        )
        assert result == {
            "data": {
                "scalarList": None,
            },
            "errors": [
                {
                    "message": "initialCount must be a positive integer",
                    "locations": [{"line": 1, "column": 3}],
                    "path": ["scalarList"],
                }
            ],
        }

    @mark.asyncio
    async def non_integer_values_of_initial_count_throw_field_errors():
        document = parse("{ scalarList @stream(initialCount: 1.5) }")
        result = await complete(document, {"scalarList": ["apple", "half of a banana"]})
        assert result == {
            "data": {
                "scalarList": None,
            },
            "errors": [
                {
                    "message": "Argument 'initialCount' has invalid value 1.5.",
                    "locations": [{"line": 1, "column": 36}],
                    "path": ["scalarList"],
                }
            ],
        }

    @mark.asyncio
    async def returns_label_from_stream_directive():
        document = parse(
            '{ scalarList @stream(initialCount: 1, label: "scalar-stream") }'
        )
        result = await complete(
            document, {"scalarList": ["apple", "banana", "coconut"]}
        )
        assert result == [
            {
                "data": {
                    "scalarList": ["apple"],
                },
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": ["banana"],
                        "path": ["scalarList", 1],
                        "label": "scalar-stream",
                    }
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": ["coconut"],
                        "path": ["scalarList", 2],
                        "label": "scalar-stream",
                    }
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def throws_an_error_for_stream_directive_with_non_string_label():
        document = parse("{ scalarList @stream(initialCount: 1, label: 42) }")
        result = await complete(document, {"scalarList": ["some apples"]})
        assert result == {
            "data": {"scalarList": None},
            "errors": [
                {
                    "locations": [
                        {
                            "line": 1,
                            "column": 46,
                        }
                    ],
                    "message": "Argument 'label' has invalid value 42.",
                    "path": ["scalarList"],
                }
            ],
        }

    @mark.asyncio
    async def can_disable_stream_using_if_argument():
        document = parse("{ scalarList @stream(initialCount: 0, if: false) }")
        result = await complete(
            document, {"scalarList": ["apple", "banana", "coconut"]}
        )
        assert result == {
            "data": {
                "scalarList": ["apple", "banana", "coconut"],
            },
        }

    @mark.asyncio
    async def does_not_disable_stream_with_null_if_argument():
        document = parse(
            "query ($shouldStream: Boolean)"
            " { scalarList @stream(initialCount: 2, if: $shouldStream) }"
        )
        result = await complete(
            document, {"scalarList": ["apple", "banana", "coconut"]}
        )
        assert result == [
            {
                "data": {
                    "scalarList": ["apple", "banana"],
                },
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": ["coconut"],
                        "path": ["scalarList", 2],
                    }
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def can_stream_multi_dimensional_lists():
        document = parse("{ scalarListList @stream(initialCount: 1) }")
        result = await complete(
            document,
            {
                "scalarListList": lambda _info: [
                    ["apple", "apple", "apple"],
                    ["banana", "banana", "banana"],
                    ["coconut", "coconut", "coconut"],
                ]
            },
        )
        assert result == [
            {
                "data": {
                    "scalarListList": [["apple", "apple", "apple"]],
                },
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [["banana", "banana", "banana"]],
                        "path": ["scalarListList", 1],
                    }
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [["coconut", "coconut", "coconut"]],
                        "path": ["scalarListList", 2],
                    }
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def can_stream_a_field_that_returns_a_list_of_awaitables():
        document = parse(
            """
            query {
              friendList @stream(initialCount: 2) {
                name
                id
              }
            }
            """
        )

        async def await_friend(f):
            await sleep(0)
            return f

        result = await complete(
            document,
            {"friendList": lambda _info: [await_friend(f) for f in friends]},
        )
        assert result == [
            {
                "data": {
                    "friendList": [
                        {"name": "Luke", "id": "1"},
                        {"name": "Han", "id": "2"},
                    ],
                },
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [{"name": "Leia", "id": "3"}],
                        "path": ["friendList", 2],
                    }
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def can_stream_in_correct_order_with_list_of_awaitables():
        document = parse(
            """
            query {
              friendList @stream(initialCount: 0) {
                name
                id
              }
            }
            """
        )

        async def await_friend(f):
            await sleep(0)
            return f

        result = await complete(
            document,
            {"friendList": lambda _info: [await_friend(f) for f in friends]},
        )
        assert result == [
            {
                "data": {"friendList": []},
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [{"name": "Luke", "id": "1"}],
                        "path": ["friendList", 0],
                    }
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [{"name": "Han", "id": "2"}],
                        "path": ["friendList", 1],
                    }
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [{"name": "Leia", "id": "3"}],
                        "path": ["friendList", 2],
                    }
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def handles_error_in_list_of_awaitables_before_initial_count_reached():
        document = parse(
            """
            query {
              friendList @stream(initialCount: 2) {
                name
                id
              }
            }
            """
        )

        async def await_friend(f, i):
            await sleep(0)
            if i == 1:
                raise RuntimeError("bad")
            return f

        result = await complete(
            document,
            {
                "friendList": lambda _info: [
                    await_friend(f, i) for i, f in enumerate(friends)
                ]
            },
        )
        assert result == [
            {
                "data": {"friendList": [{"name": "Luke", "id": "1"}, None]},
                "errors": [
                    {
                        "message": "bad",
                        "locations": [{"line": 3, "column": 15}],
                        "path": ["friendList", 1],
                    }
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [{"name": "Leia", "id": "3"}],
                        "path": ["friendList", 2],
                    }
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def handles_error_in_list_of_awaitables_after_initial_count_reached():
        document = parse(
            """
            query {
              friendList @stream(initialCount: 1) {
                name
                id
              }
            }
            """
        )

        async def await_friend(f, i):
            await sleep(0)
            if i == 1:
                raise RuntimeError("bad")
            return f

        result = await complete(
            document,
            {
                "friendList": lambda _info: [
                    await_friend(f, i) for i, f in enumerate(friends)
                ]
            },
        )
        assert result == [
            {
                "data": {"friendList": [{"name": "Luke", "id": "1"}]},
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [None],
                        "path": ["friendList", 1],
                        "errors": [
                            {
                                "message": "bad",
                                "locations": [{"line": 3, "column": 15}],
                                "path": ["friendList", 1],
                            }
                        ],
                    }
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [{"name": "Leia", "id": "3"}],
                        "path": ["friendList", 2],
                    }
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def can_stream_a_field_that_returns_an_async_iterable():
        document = parse(
            """
            query {
              friendList @stream {
                name
                id
              }
            }
            """
        )

        async def friend_list(_info):
            for i in range(3):
                await sleep(0)
                yield friends[i]

        result = await complete(document, {"friendList": friend_list})
        assert result == [
            {
                "data": {"friendList": []},
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [{"name": "Luke", "id": "1"}],
                        "path": ["friendList", 0],
                    }
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [{"name": "Han", "id": "2"}],
                        "path": ["friendList", 1],
                    }
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [{"name": "Leia", "id": "3"}],
                        "path": ["friendList", 2],
                    }
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def can_stream_a_field_that_returns_an_async_iterable_with_initial_count():
        document = parse(
            """
            query {
              friendList @stream(initialCount: 2) {
                name
                id
              }
            }
            """
        )

        async def friend_list(_info):
            for i in range(3):
                await sleep(0)
                yield friends[i]

        result = await complete(document, {"friendList": friend_list})
        assert result == [
            {
                "data": {
                    "friendList": [
                        {"name": "Luke", "id": "1"},
                        {"name": "Han", "id": "2"},
                    ]
                },
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [{"name": "Leia", "id": "3"}],
                        "path": ["friendList", 2],
                    }
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def negative_initial_count_throw_error_on_field_returning_async_iterable():
        document = parse(
            """
            query {
              friendList @stream(initialCount: -2) {
                name
                id
              }
            }
            """
        )

        async def friend_list(_info):
            yield {}  # pragma: no cover

        result = await complete(document, {"friendList": friend_list})
        assert result == {
            "errors": [
                {
                    "message": "initialCount must be a positive integer",
                    "locations": [{"line": 3, "column": 15}],
                    "path": ["friendList"],
                }
            ],
            "data": {"friendList": None},
        }

    @mark.asyncio
    async def can_handle_concurrent_calls_to_next_without_waiting():
        document = parse(
            """
            query {
              friendList @stream(initialCount: 2) {
                name
                id
              }
            }
            """
        )

        async def friend_list(_info):
            for i in range(3):
                await sleep(0)
                yield friends[i]

        result = await complete_async(document, 3, {"friendList": friend_list})
        assert result == [
            {
                "done": False,
                "value": {
                    "data": {
                        "friendList": [
                            {"name": "Luke", "id": "1"},
                            {"name": "Han", "id": "2"},
                        ]
                    },
                    "hasNext": True,
                },
            },
            {
                "done": False,
                "value": {
                    "incremental": [
                        {
                            "items": [{"name": "Leia", "id": "3"}],
                            "path": ["friendList", 2],
                        }
                    ],
                    "hasNext": False,
                },
            },
            {"done": True, "value": None},
            {"done": True, "value": None},
        ]

    @mark.asyncio
    async def handles_error_in_async_iterable_before_initial_count_is_reached():
        document = parse(
            """
            query {
              friendList @stream(initialCount: 2) {
                name
                id
              }
            }
            """
        )

        async def friend_list(_info):
            await sleep(0)
            yield friends[0]
            await sleep(0)
            raise RuntimeError("bad")

        result = await complete(document, {"friendList": friend_list})
        assert result == {
            "errors": [
                {
                    "message": "bad",
                    "locations": [{"line": 3, "column": 15}],
                    "path": ["friendList", 1],
                }
            ],
            "data": {"friendList": [{"name": "Luke", "id": "1"}, None]},
        }

    @mark.asyncio
    async def handles_error_in_async_iterable_after_initial_count_is_reached():
        document = parse(
            """
            query {
              friendList @stream(initialCount: 1) {
                name
                id
              }
            }
            """
        )

        async def friend_list(_info):
            await sleep(0)
            yield friends[0]
            await sleep(0)
            raise RuntimeError("bad")

        result = await complete(document, {"friendList": friend_list})
        assert result == [
            {
                "data": {
                    "friendList": [{"name": "Luke", "id": "1"}],
                },
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [None],
                        "path": ["friendList", 1],
                        "errors": [
                            {
                                "message": "bad",
                                "locations": [{"line": 3, "column": 15}],
                                "path": ["friendList", 1],
                            },
                        ],
                    },
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def handles_null_for_non_null_list_items_after_initial_count_is_reached():
        document = parse(
            """
            query {
              nonNullFriendList @stream(initialCount: 1) {
                name
              }
            }
            """
        )

        result = await complete(
            document, {"nonNullFriendList": lambda _info: [friends[0], None]}
        )
        assert result == [
            {
                "data": {
                    "nonNullFriendList": [{"name": "Luke"}],
                },
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": None,
                        "path": ["nonNullFriendList", 1],
                        "errors": [
                            {
                                "message": "Cannot return null for non-nullable field"
                                " Query.nonNullFriendList.",
                                "locations": [{"line": 3, "column": 15}],
                                "path": ["nonNullFriendList", 1],
                            },
                        ],
                    },
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def handles_null_for_non_null_async_items_after_initial_count_is_reached():
        document = parse(
            """
            query {
              nonNullFriendList @stream(initialCount: 1) {
                name
              }
            }
            """
        )

        async def friend_list(_info):
            try:
                await sleep(0)
                yield friends[0]
                await sleep(0)
                yield None
            finally:
                raise RuntimeError("Oops")

        result = await complete(document, {"nonNullFriendList": friend_list})
        assert result == [
            {
                "data": {
                    "nonNullFriendList": [{"name": "Luke"}],
                },
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": None,
                        "path": ["nonNullFriendList", 1],
                        "errors": [
                            {
                                "message": "Cannot return null for non-nullable field"
                                " Query.nonNullFriendList.",
                                "locations": [{"line": 3, "column": 15}],
                                "path": ["nonNullFriendList", 1],
                            },
                        ],
                    },
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def handles_error_thrown_in_complete_value_after_initial_count_is_reached():
        document = parse(
            """
            query {
              scalarList @stream(initialCount: 1)
            }
            """
        )

        async def scalar_list(_info):
            return [friends[0].name, {}]

        result = await complete(document, {"scalarList": scalar_list})
        assert result == [
            {
                "data": {
                    "scalarList": ["Luke"],
                },
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [None],
                        "path": ["scalarList", 1],
                        "errors": [
                            {
                                "message": "String cannot represent value: {}",
                                "locations": [{"line": 3, "column": 15}],
                                "path": ["scalarList", 1],
                            },
                        ],
                    },
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def handles_async_error_in_complete_value_after_initial_count_is_reached():
        document = parse(
            """
            query {
              nonNullFriendList @stream(initialCount: 1) {
                nonNullName
              }
            }
            """
        )

        async def throw():
            raise RuntimeError("Oops")

        async def get_friend(i):
            await sleep(0)
            return {"nonNullName": throw() if i < 0 else friends[i].name}

        def get_friends(_info):
            return [get_friend(0), get_friend(-1), get_friend(1)]

        result = await complete(
            document,
            {
                "nonNullFriendList": get_friends,
            },
        )
        assert result == [
            {
                "data": {
                    "nonNullFriendList": [{"nonNullName": "Luke"}],
                },
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": None,
                        "path": ["nonNullFriendList", 1],
                        "errors": [
                            {
                                "message": "Oops",
                                "locations": [{"line": 4, "column": 17}],
                                "path": ["nonNullFriendList", 1, "nonNullName"],
                            },
                        ],
                    },
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def handles_async_error_after_initial_count_reached_from_async_iterable():
        document = parse(
            """
            query {
              friendList @stream(initialCount: 1) {
                nonNullName
              }
            }
            """
        )

        async def throw():
            raise RuntimeError("Oops")

        async def get_friend(i):
            await sleep(0)
            return {"nonNullName": throw() if i < 0 else friends[i].name}

        async def get_friends(_info):
            yield await get_friend(0)
            yield await get_friend(-1)
            yield await get_friend(1)

        result = await complete(
            document,
            {
                "friendList": get_friends,
            },
        )
        assert result == [
            {
                "data": {
                    "friendList": [{"nonNullName": "Luke"}],
                },
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [None],
                        "path": ["friendList", 1],
                        "errors": [
                            {
                                "message": "Oops",
                                "locations": [{"line": 4, "column": 17}],
                                "path": ["friendList", 1, "nonNullName"],
                            },
                        ],
                    },
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [{"nonNullName": "Han"}],
                        "path": ["friendList", 2],
                    },
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def filters_payloads_that_are_nulled():
        document = parse(
            """
            query {
              nestedObject {
                nonNullScalarField
                nestedFriendList @stream(initialCount: 0) {
                  name
                }
              }
            }
            """
        )

        async def resolve_null(_info):
            await sleep(0)
            return None

        async def friend_list(_info):
            await sleep(0)
            yield friends[0]

        result = await complete(
            document,
            {
                "nestedObject": {
                    "nonNullScalarField": resolve_null,
                    "nestedFriendList": friend_list,
                }
            },
        )

        assert result == {
            "errors": [
                {
                    "message": "Cannot return null for non-nullable field"
                    " NestedObject.nonNullScalarField.",
                    "locations": [
                        {
                            "line": 4,
                            "column": 17,
                        }
                    ],
                    "path": ["nestedObject", "nonNullScalarField"],
                },
            ],
            "data": {
                "nestedObject": None,
            },
        }

    @mark.asyncio
    async def does_not_filter_payloads_when_null_error_is_in_a_different_path():
        document = parse(
            """
            query {
              otherNestedObject: nestedObject {
                ... @defer {
                  scalarField
                }
              }
              nestedObject {
                nestedFriendList @stream(initialCount: 0) {
                  name
                }
              }
            }
            """
        )

        async def error_field(_info):
            await sleep(0)
            raise RuntimeError("Oops")

        async def friend_list(_info):
            await sleep(0)
            yield friends[0]

        result = await complete(
            document,
            {
                "nestedObject": {
                    "scalarField": error_field,
                    "nestedFriendList": friend_list,
                }
            },
        )

        assert result == [
            {
                "data": {
                    "otherNestedObject": {},
                    "nestedObject": {"nestedFriendList": []},
                },
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "data": {"scalarField": None},
                        "path": ["otherNestedObject"],
                        "errors": [
                            {
                                "message": "Oops",
                                "locations": [{"line": 5, "column": 19}],
                                "path": ["otherNestedObject", "scalarField"],
                            },
                        ],
                    },
                    {
                        "items": [{"name": "Luke"}],
                        "path": ["nestedObject", "nestedFriendList", 0],
                    },
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def filters_stream_payloads_that_are_nulled_in_a_deferred_payload():
        document = parse(
            """
            query {
              nestedObject {
                ... @defer {
                  deeperNestedObject {
                    nonNullScalarField
                    deeperNestedFriendList @stream(initialCount: 0) {
                      name
                    }
                  }
                }
              }
            }
            """
        )

        async def resolve_null(_info):
            await sleep(0)
            return None

        async def friend_list(_info):
            await sleep(0)
            yield friends[0]

        result = await complete(
            document,
            {
                "nestedObject": {
                    "deeperNestedObject": {
                        "nonNullScalarField": resolve_null,
                        "deeperNestedFriendList": friend_list,
                    }
                }
            },
        )

        assert result == [
            {
                "data": {
                    "nestedObject": {},
                },
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "data": {
                            "deeperNestedObject": None,
                        },
                        "path": ["nestedObject"],
                        "errors": [
                            {
                                "message": "Cannot return null for non-nullable field"
                                " DeeperNestedObject.nonNullScalarField.",
                                "locations": [{"line": 6, "column": 21}],
                                "path": [
                                    "nestedObject",
                                    "deeperNestedObject",
                                    "nonNullScalarField",
                                ],
                            },
                        ],
                    },
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def filters_defer_payloads_that_are_nulled_in_a_stream_response():
        document = parse(
            """
            query {
              friendList @stream(initialCount: 0) {
                nonNullName
                ... @defer {
                  name
                }
              }
            }
            """
        )

        async def resolve_null(_info):
            await sleep(0)
            return None

        async def friend():
            await sleep(0)
            return {
                "name": friends[0].name,
                "nonNullName": resolve_null,
            }

        async def friend_list(_info):
            await sleep(0)
            yield await friend()

        result = await complete(document, {"friendList": friend_list})

        assert result == [
            {
                "data": {
                    "friendList": [],
                },
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [None],
                        "path": ["friendList", 0],
                        "errors": [
                            {
                                "message": "Cannot return null for non-nullable field"
                                " Friend.nonNullName.",
                                "locations": [{"line": 4, "column": 17}],
                                "path": ["friendList", 0, "nonNullName"],
                            },
                        ],
                    },
                ],
                "hasNext": False,
            },
        ]

    @mark.timeout(1)
    @mark.asyncio
    async def returns_iterator_and_ignores_error_when_stream_payloads_are_filtered():
        finished = False

        async def resolve_null(_info):
            await sleep(0)
            return None

        async def iterable(_info):
            nonlocal finished
            for i in range(3):
                await sleep(0)
                friend = friends[i]
                yield {"name": friend.name, "nonNullName": None}
            finished = True  # pragma: no cover

        document = parse(
            """
            query {
              nestedObject {
                ... @defer {
                  deeperNestedObject {
                    nonNullScalarField
                    deeperNestedFriendList @stream(initialCount: 0) {
                      name
                    }
                  }
                }
              }
            }
            """
        )

        execute_result = experimental_execute_incrementally(
            schema,
            document,
            {
                "nestedObject": {
                    "deeperNestedObject": {
                        "nonNullScalarField": resolve_null,
                        "deeperNestedFriendList": iterable,
                    }
                }
            },
        )

        assert isinstance(execute_result, ExperimentalIncrementalExecutionResults)
        iterator = execute_result.subsequent_results

        result1 = execute_result.initial_result
        assert result1 == {"data": {"nestedObject": {}}, "hasNext": True}

        result2 = await anext(iterator)
        assert result2.formatted == {
            "incremental": [
                {
                    "data": {"deeperNestedObject": None},
                    "path": ["nestedObject"],
                    "errors": [
                        {
                            "message": "Cannot return null for non-nullable field"
                            " DeeperNestedObject.nonNullScalarField.",
                            "locations": [{"line": 6, "column": 21}],
                            "path": [
                                "nestedObject",
                                "deeperNestedObject",
                                "nonNullScalarField",
                            ],
                        },
                    ],
                },
            ],
            "hasNext": False,
        }

        with raises(StopAsyncIteration):
            await anext(iterator)

        assert not finished  # running iterator cannot be canceled

    @mark.asyncio
    async def handles_awaitables_from_complete_value_after_initial_count_is_reached():
        document = parse(
            """
            query {
              friendList @stream(initialCount: 1) {
                id
                name
              }
            }
            """
        )

        async def get_friend_name(i):
            await sleep(0)
            return friends[i].name

        async def get_friend(i):
            await sleep(0)
            if i < 2:
                return friends[i]
            return {"id": friends[2].id, "name": get_friend_name(i)}

        async def get_friends(_info):
            for i in range(3):
                yield await get_friend(i)

        result = await complete(
            document,
            {
                "friendList": get_friends,
            },
        )
        assert result == [
            {
                "data": {
                    "friendList": [{"id": "1", "name": "Luke"}],
                },
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [{"id": "2", "name": "Han"}],
                        "path": ["friendList", 1],
                    }
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [{"id": "3", "name": "Leia"}],
                        "path": ["friendList", 2],
                    }
                ],
                "hasNext": False,
            },
        ]

    @mark.asyncio
    async def returns_payloads_properly_when_parent_deferred_slower_than_stream():
        resolve_slow_field = Event()

        async def slow_field(_info):
            await resolve_slow_field.wait()
            return "slow"

        document = parse(
            """
              query {
                nestedObject {
                  ... DeferFragment @defer
                }
              }
              fragment DeferFragment on NestedObject {
                scalarField
                nestedFriendList @stream(initialCount: 0) {
                  name
                }
              }
            """
        )

        async def get_friends(_info):
            for i in range(2):
                await sleep(0)
                yield friends[i]

        execute_result = experimental_execute_incrementally(
            schema,
            document,
            {
                "nestedObject": {
                    "scalarField": slow_field,
                    "nestedFriendList": get_friends,
                }
            },
        )

        assert isinstance(execute_result, ExperimentalIncrementalExecutionResults)
        iterator = execute_result.subsequent_results

        result1 = execute_result.initial_result
        assert result1 == {"data": {"nestedObject": {}}, "hasNext": True}

        resolve_slow_field.set()
        result2 = await anext(iterator)
        assert result2.formatted == {
            "incremental": [
                {
                    "data": {"scalarField": "slow", "nestedFriendList": []},
                    "path": ["nestedObject"],
                },
            ],
            "hasNext": True,
        }
        result3 = await anext(iterator)
        assert result3.formatted == {
            "incremental": [
                {
                    "items": [{"name": "Luke"}],
                    "path": ["nestedObject", "nestedFriendList", 0],
                },
            ],
            "hasNext": True,
        }
        result4 = await anext(iterator)
        assert result4.formatted == {
            "incremental": [
                {
                    "items": [{"name": "Han"}],
                    "path": ["nestedObject", "nestedFriendList", 1],
                },
            ],
            "hasNext": False,
        }

        with raises(StopAsyncIteration):
            await anext(iterator)

    @mark.timeout(1)
    @mark.asyncio
    async def can_defer_fields_that_are_resolved_after_async_iterable_is_complete():
        resolve_slow_field = Event()
        resolve_iterable = Event()

        async def slow_field(_info):
            await resolve_slow_field.wait()
            return "Han"

        document = parse(
            """
            query {
              friendList @stream(initialCount: 1, label:"stream-label") {
                ...NameFragment @defer(label: "DeferName") @defer(label: "DeferName")
                id
              }
            }
            fragment NameFragment on Friend {
              name
            }
            """
        )

        async def get_friends(_info):
            await sleep(0)
            yield friends[0]
            await sleep(0)
            yield {"id": friends[1].id, "name": slow_field}
            await resolve_iterable.wait()

        execute_result = await experimental_execute_incrementally(  # type: ignore
            schema,
            document,
            {
                "friendList": get_friends,
            },
        )

        assert isinstance(execute_result, ExperimentalIncrementalExecutionResults)
        iterator = execute_result.subsequent_results

        result1 = execute_result.initial_result
        assert result1 == {"data": {"friendList": [{"id": "1"}]}, "hasNext": True}

        resolve_iterable.set()
        result2 = await anext(iterator)
        assert result2.formatted == {
            "incremental": [
                {
                    "data": {"name": "Luke"},
                    "path": ["friendList", 0],
                    "label": "DeferName",
                },
                {
                    "items": [{"id": "2"}],
                    "path": ["friendList", 1],
                    "label": "stream-label",
                },
            ],
            "hasNext": True,
        }

        resolve_slow_field.set()
        result3 = await anext(iterator)
        assert result3.formatted == {
            "incremental": [
                {
                    "data": {"name": "Han"},
                    "path": ["friendList", 1],
                    "label": "DeferName",
                },
            ],
            "hasNext": False,
        }

        with raises(StopAsyncIteration):
            await anext(iterator)

    @mark.asyncio
    async def can_defer_fields_that_are_resolved_before_async_iterable_is_complete():
        resolve_slow_field = Event()
        resolve_iterable = Event()

        async def slow_field(_info):
            await resolve_slow_field.wait()
            return "Han"

        document = parse(
            """
            query {
              friendList @stream(initialCount: 1, label:"stream-label") {
                ...NameFragment @defer(label: "DeferName") @defer(label: "DeferName")
                id
              }
            }
            fragment NameFragment on Friend {
              name
            }
            """
        )

        async def get_friends(_info):
            await sleep(0)
            yield friends[0]
            await sleep(0)
            yield {"id": friends[1].id, "name": slow_field}
            await sleep(0)
            await resolve_iterable.wait()

        execute_result = await experimental_execute_incrementally(  # type: ignore
            schema,
            document,
            {
                "friendList": get_friends,
            },
        )

        assert isinstance(execute_result, ExperimentalIncrementalExecutionResults)
        iterator = execute_result.subsequent_results

        result1 = execute_result.initial_result
        assert result1 == {"data": {"friendList": [{"id": "1"}]}, "hasNext": True}

        resolve_slow_field.set()
        result2 = await anext(iterator)
        assert result2.formatted == {
            "incremental": [
                {
                    "data": {"name": "Luke"},
                    "path": ["friendList", 0],
                    "label": "DeferName",
                },
                {
                    "items": [{"id": "2"}],
                    "path": ["friendList", 1],
                    "label": "stream-label",
                },
            ],
            "hasNext": True,
        }

        result3 = await anext(iterator)
        assert result3.formatted == {
            "incremental": [
                {
                    "data": {"name": "Han"},
                    "path": ["friendList", 1],
                    "label": "DeferName",
                },
            ],
            "hasNext": True,
        }

        resolve_iterable.set()
        result4 = await anext(iterator)
        assert result4.formatted == {
            "hasNext": False,
        }

        with raises(StopAsyncIteration):
            await anext(iterator)

    @mark.asyncio
    async def finishes_async_iterable_when_returned_generator_is_closed():
        finished = False

        async def iterable(_info):
            nonlocal finished
            for i in range(3):
                await sleep(0)
                yield friends[i]
            finished = True

        document = parse(
            """
            query {
              friendList @stream(initialCount: 1) {
                id
                ... @defer {
                  name
                }
              }
            }
            """
        )

        execute_result = await experimental_execute_incrementally(  # type: ignore
            schema, document, {"friendList": iterable}
        )
        assert isinstance(execute_result, ExperimentalIncrementalExecutionResults)
        iterator = execute_result.subsequent_results

        result1 = execute_result.initial_result
        assert result1 == {"data": {"friendList": [{"id": "1"}]}, "hasNext": True}

        await iterator.aclose()
        with raises(StopAsyncIteration):
            await anext(iterator)

        assert finished

    @mark.asyncio
    async def finishes_async_iterable_when_underlying_iterator_has_no_close_method():
        class Iterable:
            def __init__(self):
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                await sleep(0)
                index = self.index
                self.index = index + 1
                try:
                    return friends[index]
                except IndexError:
                    raise StopAsyncIteration

        iterable = Iterable()

        document = parse(
            """
            query {
              friendList @stream(initialCount: 1) {
                name
                id
              }
            }
            """
        )

        execute_result = await experimental_execute_incrementally(  # type: ignore
            schema, document, {"friendList": iterable}
        )
        assert isinstance(execute_result, ExperimentalIncrementalExecutionResults)
        iterator = execute_result.subsequent_results

        result1 = execute_result.initial_result
        assert result1 == {
            "data": {"friendList": [{"id": "1", "name": "Luke"}]},
            "hasNext": True,
        }

        await iterator.aclose()
        with raises(StopAsyncIteration):
            await anext(iterator)

        assert iterable.index == 4

    @mark.asyncio
    async def finishes_async_iterable_when_error_is_raised_in_returned_generator():
        finished = False

        async def iterable(_info):
            nonlocal finished
            for i in range(3):
                await sleep(0)
                yield friends[i]
            finished = True

        document = parse(
            """
            query {
              friendList @stream(initialCount: 1) {
                ... @defer {
                  name
                }
                id
              }
            }
            """
        )

        execute_result = await experimental_execute_incrementally(  # type: ignore
            schema, document, {"friendList": iterable}
        )
        assert isinstance(execute_result, ExperimentalIncrementalExecutionResults)
        iterator = execute_result.subsequent_results

        result1 = execute_result.initial_result
        assert result1 == {"data": {"friendList": [{"id": "1"}]}, "hasNext": True}

        with raises(RuntimeError, match="bad"):
            await iterator.athrow(RuntimeError("bad"))

        with raises(StopAsyncIteration):
            await anext(iterator)

        assert finished
