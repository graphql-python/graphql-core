from __future__ import annotations

from asyncio import Event, Lock, gather, sleep
from typing import Any, Awaitable, NamedTuple

import pytest

from graphql.error import GraphQLError
from graphql.execution import (
    ExecutionResult,
    ExperimentalIncrementalExecutionResults,
    IncrementalStreamResult,
    experimental_execute_incrementally,
)
from graphql.language import DocumentNode, parse
from graphql.type import (
    GraphQLField,
    GraphQLID,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.filterwarnings("ignore:.* was never awaited:RuntimeWarning"),
    pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning"),
]

try:  # pragma: no cover
    anext  # noqa: B018
except NameError:  # pragma: no cover (Python < 3.10)
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
    id: int
    name: str


friends = [Friend(1, "Luke"), Friend(2, "Han"), Friend(3, "Leia")]

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
        results: list[Any] = [result.initial_result.formatted]
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


def modified_args(args: dict[str, Any], **modifications: Any) -> dict[str, Any]:
    return {**args, **modifications}


def describe_execute_stream_directive():
    """Execute: stream directive"""

    def can_format_and_print_incremental_stream_result():
        """Can format and print an IncrementalStreamResult"""
        result = IncrementalStreamResult(items=["hello", "world"], id="foo")
        assert result.formatted == {"items": ["hello", "world"], "id": "foo"}
        assert (
            str(result) == "IncrementalStreamResult(items=['hello', 'world'], id='foo')"
        )

        result = IncrementalStreamResult(
            items=["hello", "world"],
            id="foo",
            sub_path=["bar", 1],
            errors=[GraphQLError("oops")],
            extensions={"baz": 2},
        )
        assert result.formatted == {
            "items": ["hello", "world"],
            "id": "foo",
            "subPath": ["bar", 1],
            "errors": [{"message": "oops"}],
            "extensions": {"baz": 2},
        }
        assert (
            str(result) == "IncrementalStreamResult(items=['hello', 'world'],"
            " id='foo', sub_path=['bar', 1], errors=[GraphQLError('oops')],"
            " extensions={'baz': 2})"
        )

    def can_compare_incremental_stream_result():
        """Can compare an IncrementalStreamResult"""
        args: dict[str, Any] = {
            "items": ["hello", "world"],
            "id": "foo",
            "sub_path": ["bar", 1],
            "errors": [GraphQLError("oops")],
            "extensions": {"baz": 2},
        }
        result = IncrementalStreamResult(**args)
        assert result == IncrementalStreamResult(**args)
        assert result != IncrementalStreamResult(
            **modified_args(args, items=["hello", "foo"])
        )
        assert result != IncrementalStreamResult(**modified_args(args, id="bar"))
        assert result != IncrementalStreamResult(
            **modified_args(args, sub_path=["bar", 2])
        )
        assert result != IncrementalStreamResult(**modified_args(args, errors=[]))
        assert result != IncrementalStreamResult(
            **modified_args(args, extensions={"baz": 1})
        )
        assert result == tuple(args.values())
        assert result == tuple(args.values())[:4]
        assert result == tuple(args.values())[:3]
        assert result == tuple(args.values())[:2]
        assert result != tuple(args.values())[:1]
        assert result != (["hello", "world"], "bar")
        args["subPath"] = args.pop("sub_path")
        assert result == args
        assert result != {**args, "items": ["hello", "foo"]}
        assert result != {**args, "id": "bar"}
        assert result != {**args, "subPath": ["bar", 2]}
        assert result != {**args, "errors": []}
        assert result != {**args, "extensions": {"baz": 1}}

    def can_hash_incremental_stream_result():
        """Can hash an IncrementalStreamResult"""
        args: dict[str, Any] = {
            "items": ["hello", "world"],
            "id": "foo",
            "sub_path": ["bar", 1],
            "errors": [GraphQLError("oops")],
            "extensions": {"baz": 2},
        }
        result = IncrementalStreamResult(**args)
        assert hash(result) == hash(IncrementalStreamResult(**args))
        assert hash(result) != hash(
            IncrementalStreamResult(**modified_args(args, items=["hello", "foo"]))
        )
        assert hash(result) != hash(
            IncrementalStreamResult(**modified_args(args, id="bar"))
        )
        assert hash(result) != hash(
            IncrementalStreamResult(**modified_args(args, sub_path=["bar", 2]))
        )
        assert hash(result) != hash(
            IncrementalStreamResult(**modified_args(args, errors=[]))
        )
        assert hash(result) != hash(
            IncrementalStreamResult(**modified_args(args, extensions={"baz": 1}))
        )

    async def can_stream_a_list_field():
        """Can stream a list field"""
        document = parse("{ scalarList @stream(initialCount: 1) }")
        result = await complete(
            document, {"scalarList": ["apple", "banana", "coconut"]}
        )
        assert result == [
            {
                "data": {"scalarList": ["apple"]},
                "pending": [{"id": "0", "path": ["scalarList"]}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"items": ["banana"], "id": "0"},
                    {"items": ["coconut"], "id": "0"},
                ],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def can_use_default_value_of_initial_count():
        """Can use default value of initialCount"""
        document = parse("{ scalarList @stream }")
        result = await complete(
            document, {"scalarList": ["apple", "banana", "coconut"]}
        )
        assert result == [
            {
                "data": {"scalarList": []},
                "pending": [{"id": "0", "path": ["scalarList"]}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"items": ["apple"], "id": "0"},
                    {"items": ["banana"], "id": "0"},
                    {"items": ["coconut"], "id": "0"},
                ],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def negative_values_of_initial_count_throw_field_errors():
        """Negative values of initialCount throw field errors"""
        document = parse("{ scalarList @stream(initialCount: -2) }")
        result = await complete(
            document, {"scalarList": ["apple", "banana", "coconut"]}
        )
        assert result == {
            "data": {"scalarList": None},
            "errors": [
                {
                    "message": "initialCount must be a positive integer",
                    "locations": [{"line": 1, "column": 3}],
                    "path": ["scalarList"],
                }
            ],
        }

    async def non_integer_values_of_initial_count_throw_field_errors():
        """Non-integer values of initialCount throw field errors"""
        document = parse("{ scalarList @stream(initialCount: 1.5) }")
        result = await complete(document, {"scalarList": ["apple", "half of a banana"]})
        assert result == {
            "data": {"scalarList": None},
            "errors": [
                {
                    "message": "Argument 'initialCount' has invalid value 1.5.",
                    "locations": [{"line": 1, "column": 36}],
                    "path": ["scalarList"],
                }
            ],
        }

    async def returns_label_from_stream_directive():
        """Returns label from stream directive"""
        document = parse(
            '{ scalarList @stream(initialCount: 1, label: "scalar-stream") }'
        )
        result = await complete(
            document, {"scalarList": ["apple", "banana", "coconut"]}
        )
        assert result == [
            {
                "data": {"scalarList": ["apple"]},
                "pending": [
                    {"id": "0", "path": ["scalarList"], "label": "scalar-stream"}
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"items": ["banana"], "id": "0"},
                    {"items": ["coconut"], "id": "0"},
                ],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def throws_an_error_for_stream_directive_with_non_string_label():
        """Throws an error for stream directive with non-string label"""
        document = parse("{ scalarList @stream(initialCount: 1, label: 42) }")
        result = await complete(document, {"scalarList": ["some apples"]})
        assert result == {
            "data": {"scalarList": None},
            "errors": [
                {
                    "locations": [{"line": 1, "column": 46}],
                    "message": "Argument 'label' has invalid value 42.",
                    "path": ["scalarList"],
                }
            ],
        }

    async def can_disable_stream_using_if_argument():
        """Can disable @stream using if argument"""
        document = parse("{ scalarList @stream(initialCount: 0, if: false) }")
        result = await complete(
            document, {"scalarList": ["apple", "banana", "coconut"]}
        )
        assert result == {"data": {"scalarList": ["apple", "banana", "coconut"]}}

    async def does_not_disable_stream_with_null_if_argument():
        """Does not disable stream with null if argument"""
        document = parse(
            "query ($shouldStream: Boolean)"
            " { scalarList @stream(initialCount: 2, if: $shouldStream) }"
        )
        result = await complete(
            document, {"scalarList": ["apple", "banana", "coconut"]}
        )
        assert result == [
            {
                "data": {"scalarList": ["apple", "banana"]},
                "pending": [{"id": "0", "path": ["scalarList"]}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": ["coconut"], "id": "0"}],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def can_stream_multi_dimensional_lists():
        """Can stream multi-dimensional lists"""
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
                "data": {"scalarListList": [["apple", "apple", "apple"]]},
                "pending": [{"id": "0", "path": ["scalarListList"]}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"items": [["banana", "banana", "banana"]], "id": "0"},
                    {"items": [["coconut", "coconut", "coconut"]], "id": "0"},
                ],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def can_stream_a_field_that_returns_a_list_of_awaitables():
        """Can stream a field that returns a list of awaitables"""
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
                "pending": [{"id": "0", "path": ["friendList"]}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": [{"name": "Leia", "id": "3"}], "id": "0"}],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def can_stream_in_correct_order_with_list_of_awaitables():
        """Can stream in correct order with list of awaitables"""
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
            return f

        result = await complete(
            document,
            {"friendList": lambda _info: [await_friend(f) for f in friends]},
        )
        assert result == [
            {
                "data": {"friendList": []},
                "pending": [{"id": "0", "path": ["friendList"]}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": [{"name": "Luke", "id": "1"}], "id": "0"}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": [{"name": "Han", "id": "2"}], "id": "0"}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": [{"name": "Leia", "id": "3"}], "id": "0"}],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def can_stream_a_field_that_returns_a_list_with_nested_async_fields():
        """Can stream a field that returns a list with nested async fields"""
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

        async def get_name(f):
            return f.name

        async def get_id(f):
            return f.id

        result = await complete(
            document,
            {
                "friendList": lambda _info: [
                    {"name": get_name(f), "id": get_id(f)} for f in friends
                ]
            },
        )
        assert result == [
            {
                "data": {
                    "friendList": [
                        {"name": "Luke", "id": "1"},
                        {"name": "Han", "id": "2"},
                    ]
                },
                "pending": [{"id": "0", "path": ["friendList"]}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": [{"name": "Leia", "id": "3"}], "id": "0"}],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def handles_error_in_list_of_awaitables_before_initial_count_reached():
        """Handles error in list of awaitables before initial count reached

        Handles exceptions in a field that returns a list of awaitables before
        initialCount is reached.
        """
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
                "pending": [{"id": "0", "path": ["friendList"]}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": [{"name": "Leia", "id": "3"}], "id": "0"}],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def handles_error_in_list_of_awaitables_after_initial_count_reached():
        """Handles error in list of awaitables after initial count reached

        Handles exceptions in a field that returns a list of awaitables after
        initialCount is reached.
        """
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
                "pending": [{"id": "0", "path": ["friendList"]}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [None],
                        "id": "0",
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
                "incremental": [{"items": [{"name": "Leia", "id": "3"}], "id": "0"}],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def can_stream_a_field_that_returns_an_async_iterable():
        """Can stream a field that returns an async iterable"""
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
                yield friends[i]

        result = await complete(document, {"friendList": friend_list})
        assert result == [
            {
                "data": {"friendList": []},
                "pending": [{"id": "0", "path": ["friendList"]}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": [{"name": "Luke", "id": "1"}], "id": "0"}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": [{"name": "Han", "id": "2"}], "id": "0"}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": [{"name": "Leia", "id": "3"}], "id": "0"}],
                "hasNext": True,
            },
            {"completed": [{"id": "0"}], "hasNext": False},
        ]

    async def can_stream_a_field_that_returns_an_async_iterable_with_initial_count():
        """Can stream a field that returns an async iterable, with initialCount

        Can stream a field that returns an async iterable, using a non-zero
        initialCount.
        """
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
                "pending": [{"id": "0", "path": ["friendList"]}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": [{"name": "Leia", "id": "3"}], "id": "0"}],
                "hasNext": True,
            },
            {"completed": [{"id": "0"}], "hasNext": False},
        ]

    async def negative_initial_count_throw_error_on_field_returning_async_iterable():
        """Negative initialCount throw error on field returning async iterable

        Negative values of initialCount throw field errors on a field that returns an
        async iterable.
        """
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

    async def can_handle_concurrent_calls_to_next_without_waiting():
        """Can handle concurrent calls to next() without waiting"""
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
                    "pending": [{"id": "0", "path": ["friendList"]}],
                    "hasNext": True,
                },
            },
            {
                "done": False,
                "value": {
                    "incremental": [
                        {"items": [{"name": "Leia", "id": "3"}], "id": "0"}
                    ],
                    "hasNext": True,
                },
            },
            {
                "done": False,
                "value": {"completed": [{"id": "0"}], "hasNext": False},
            },
            {"done": True, "value": None},
        ]

    async def handles_error_in_async_iterable_before_initial_count_is_reached():
        """Handles error raised in async iterable before initialCount is reached"""
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
            yield friends[0]
            raise RuntimeError("bad")

        result = await complete(document, {"friendList": friend_list})
        assert result == {
            "errors": [
                {
                    "message": "bad",
                    "locations": [{"line": 3, "column": 15}],
                    "path": ["friendList"],
                }
            ],
            "data": {"friendList": None},
        }

    async def handles_error_in_async_iterable_after_initial_count_is_reached():
        """Handles error thrown in async iterable after initialCount is reached"""
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
            yield friends[0]
            raise RuntimeError("bad")

        result = await complete(document, {"friendList": friend_list})
        assert result == [
            {
                "data": {"friendList": [{"name": "Luke", "id": "1"}]},
                "pending": [{"id": "0", "path": ["friendList"]}],
                "hasNext": True,
            },
            {
                "completed": [
                    {
                        "id": "0",
                        "errors": [
                            {
                                "message": "bad",
                                "locations": [{"line": 3, "column": 15}],
                                "path": ["friendList"],
                            },
                        ],
                    },
                ],
                "hasNext": False,
            },
        ]

    async def handles_null_for_non_null_list_items_after_initial_count_is_reached():
        """Handles null returned in non-null list items after initialCount is reached"""
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
            document,
            {"nonNullFriendList": lambda _info: [friends[0], None, friends[1]]},
        )
        assert result == [
            {
                "data": {"nonNullFriendList": [{"name": "Luke"}]},
                "pending": [{"id": "0", "path": ["nonNullFriendList"]}],
                "hasNext": True,
            },
            {
                "completed": [
                    {
                        "id": "0",
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

    async def handles_null_for_non_null_async_items_after_initial_count_is_reached():
        """Handles null in non-null async iterable items after initialCount is reached

        Handles null returned in non-null async iterable list items after initialCount
        is reached
        """
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
                yield friends[0]
                yield None
            finally:
                raise RuntimeError("Oops")

        result = await complete(document, {"nonNullFriendList": friend_list})
        assert result == [
            {
                "data": {"nonNullFriendList": [{"name": "Luke"}]},
                "pending": [{"id": "0", "path": ["nonNullFriendList"]}],
                "hasNext": True,
            },
            {
                "completed": [
                    {
                        "id": "0",
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

    async def handles_error_thrown_in_complete_value_after_initial_count_is_reached():
        """Handles errors thrown by completeValue after initialCount is reached"""
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
                "data": {"scalarList": ["Luke"]},
                "pending": [{"id": "0", "path": ["scalarList"]}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [None],
                        "id": "0",
                        "errors": [
                            {
                                "message": "String cannot represent value: {}",
                                "locations": [{"line": 3, "column": 15}],
                                "path": ["scalarList", 1],
                            },
                        ],
                    },
                ],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def handles_async_error_in_complete_value_after_initial_count_is_reached():
        """Handles async errors thrown by completeValue after initialCount is reached"""
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
            return {"nonNullName": throw() if i < 0 else friends[i].name}

        def get_friends(_info):
            return [get_friend(i) for i in (0, -1, 1)]

        result = await complete(
            document,
            {
                "friendList": get_friends,
            },
        )
        assert result == [
            {
                "data": {"friendList": [{"nonNullName": "Luke"}]},
                "pending": [{"id": "0", "path": ["friendList"]}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [None],
                        "id": "0",
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
                "incremental": [{"items": [{"nonNullName": "Han"}], "id": "0"}],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def handles_nested_async_error_in_complete_value_after_initial_count():
        """Handles nested async error thrown in completeValue after initialCount

        Handles nested async errors thrown by completeValue after initialCount is
        reached.
        """
        document = parse(
            """
            query {
              friendList @stream(initialCount: 1) {
                nonNullName
              }
            }
            """
        )

        async def get_friend_name(i):
            if i < 0:
                raise RuntimeError("Oops")
            return friends[i].name

        def get_friends(_info):
            return [{"nonNullName": get_friend_name(i)} for i in (0, -1, 1)]

        result = await complete(
            document,
            {
                "friendList": get_friends,
            },
        )
        assert result == [
            {
                "data": {"friendList": [{"nonNullName": "Luke"}]},
                "pending": [{"id": "0", "path": ["friendList"]}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [None],
                        "id": "0",
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
                "incremental": [{"items": [{"nonNullName": "Han"}], "id": "0"}],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def handles_async_error_in_complete_value_after_initial_count_non_null():
        """Handles async errors in completeValue after initialCount, non-null list

        Handles async errors thrown by completeValue after initialCount is reached for
        a non-nullable list.
        """
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
            return {"nonNullName": throw() if i < 0 else friends[i].name}

        def get_friends(_info):
            return [get_friend(i) for i in (0, -1, 1)]

        result = await complete(
            document,
            {
                "nonNullFriendList": get_friends,
            },
        )
        assert result == [
            {
                "data": {"nonNullFriendList": [{"nonNullName": "Luke"}]},
                "pending": [{"id": "0", "path": ["nonNullFriendList"]}],
                "hasNext": True,
            },
            {
                "completed": [
                    {
                        "id": "0",
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

    async def handles_nested_async_error_in_complete_value_after_initial_non_null():
        """Handles nested async error in completeValue after initialCount, non-null list

        Handles nested async errors thrown by completeValue after initialCount is
        reached for a non-nullable list.
        """
        document = parse(
            """
            query {
              nonNullFriendList @stream(initialCount: 1) {
                nonNullName
              }
            }
            """
        )

        async def get_friend_name(i):
            if i < 0:
                raise RuntimeError("Oops")
            return friends[i].name

        def get_friends(_info):
            return [{"nonNullName": get_friend_name(i)} for i in (0, -1, 1)]

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
                "pending": [{"id": "0", "path": ["nonNullFriendList"]}],
                "hasNext": True,
            },
            {
                "completed": [
                    {
                        "id": "0",
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

    async def handles_async_error_in_complete_value_after_initial_from_async_iterable():
        """Handles async error in completeValue after initialCount from async iterable

        Handles async errors thrown by completeValue after initialCount is reached
        from async iterable.
        """
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
            return {"nonNullName": throw() if i < 0 else friends[i].name}

        async def get_friends(_info):
            for i in 0, -1, 1:
                yield await get_friend(i)

        result = await complete(
            document,
            {
                "friendList": get_friends,
            },
        )
        assert result == [
            {
                "data": {"friendList": [{"nonNullName": "Luke"}]},
                "pending": [{"id": "0", "path": ["friendList"]}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [None],
                        "id": "0",
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
                "incremental": [{"items": [{"nonNullName": "Han"}], "id": "0"}],
                "hasNext": True,
            },
            {"completed": [{"id": "0"}], "hasNext": False},
        ]

    async def handles_async_error_in_complete_value_from_async_generator_non_null():
        """Handles async error in completeValue from async generator, non-null list

        Handles async errors thrown by completeValue after initialCount is reached
        from async generator for a non-nullable list.
        """
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
            return {"nonNullName": throw() if i < 0 else friends[i].name}

        async def get_friends(_info):
            for i in 0, -1, 1:  # pragma: no cover exit
                yield await get_friend(i)

        result = await complete(
            document,
            {"nonNullFriendList": get_friends},
        )
        assert result == [
            {
                "data": {"nonNullFriendList": [{"nonNullName": "Luke"}]},
                "pending": [{"id": "0", "path": ["nonNullFriendList"]}],
                "hasNext": True,
            },
            {
                "completed": [
                    {
                        "id": "0",
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

    async def handles_async_errors_in_complete_value_after_initial_count_no_aclose():
        """Handles async errors in completeValue after initialCount, without aclose

        Handles async errors thrown by completeValue after initialCount is reached
        from async iterable for a non-nullable list when the async iterable does not
        provide an aclose() method.
        """
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

        class AsyncIterableWithoutAclose:
            def __init__(self):
                self.count = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                count = self.count
                self.count += 1
                if count == 1:
                    name = throw()
                else:
                    if count:
                        count -= 1  # pragma: no cover
                    name = friends[count].name
                return {"nonNullName": name}

        async_iterable = AsyncIterableWithoutAclose()
        result = await complete(document, {"nonNullFriendList": async_iterable})
        assert result == [
            {
                "data": {"nonNullFriendList": [{"nonNullName": "Luke"}]},
                "pending": [{"id": "0", "path": ["nonNullFriendList"]}],
                "hasNext": True,
            },
            {
                "completed": [
                    {
                        "id": "0",
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

    async def handles_async_errors_in_complete_value_after_initial_count_slow_aclose():
        """Handles async errors in completeValue after initialCount, with slow aclose

        Handles async errors thrown by completeValue after initialCount is reached
        from async iterable for a non-nullable list when the async iterable provides
        concurrent next/return methods and has a slow aclose() method.
        """
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

        class AsyncIterableWithSlowAclose:
            def __init__(self):
                self.count = 0
                self.finished = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.finished:
                    raise StopAsyncIteration  # pragma: no cover
                count = self.count
                self.count += 1
                if count == 1:
                    name = throw()
                else:
                    if count:
                        count -= 1  # pragma: no cover
                    name = friends[count].name
                return {"nonNullName": name}

            async def aclose(self):
                await sleep(0)
                self.finished = True

        async_iterable = AsyncIterableWithSlowAclose()
        result = await complete(document, {"nonNullFriendList": async_iterable})
        assert result == [
            {
                "data": {"nonNullFriendList": [{"nonNullName": "Luke"}]},
                "pending": [{"id": "0", "path": ["nonNullFriendList"]}],
                "hasNext": True,
            },
            {
                "completed": [
                    {
                        "id": "0",
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
        assert async_iterable.finished

    async def filters_payloads_that_are_nulled():
        """Filters payloads that are nulled"""
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
            return None

        async def friend_list(_info):
            yield friends[0]  # pragma: no cover

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
                    "locations": [{"line": 4, "column": 17}],
                    "path": ["nestedObject", "nonNullScalarField"],
                },
            ],
            "data": {"nestedObject": None},
        }

    async def filters_payloads_that_are_nulled_by_a_later_synchronous_error():
        """Filters payloads that are nulled by a later synchronous error"""
        document = parse(
            """
            query {
              nestedObject {
                nestedFriendList @stream(initialCount: 0) {
                  name
                }
                nonNullScalarField
              }
            }
            """
        )

        async def friend_list(_info):
            yield friends[0]  # pragma: no cover

        result = await complete(
            document,
            {
                "nestedObject": {
                    "nestedFriendList": friend_list,
                    "nonNullScalarField": lambda _info: None,
                }
            },
        )

        assert result == {
            "errors": [
                {
                    "message": "Cannot return null for non-nullable field"
                    " NestedObject.nonNullScalarField.",
                    "locations": [{"line": 7, "column": 17}],
                    "path": ["nestedObject", "nonNullScalarField"],
                },
            ],
            "data": {"nestedObject": None},
        }

    async def does_not_filter_payloads_when_null_error_is_in_a_different_path():
        """Does not filter payloads when null error is in a different path"""
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
            raise RuntimeError("Oops")

        async def friend_list(_info):
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
                "pending": [
                    {"id": "0", "path": ["otherNestedObject"]},
                    {"id": "1", "path": ["nestedObject", "nestedFriendList"]},
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "data": {"scalarField": None},
                        "id": "0",
                        "errors": [
                            {
                                "message": "Oops",
                                "locations": [{"line": 5, "column": 19}],
                                "path": ["otherNestedObject", "scalarField"],
                            },
                        ],
                    },
                    {"items": [{"name": "Luke"}], "id": "1"},
                ],
                "completed": [{"id": "0"}],
                "hasNext": True,
            },
            {"completed": [{"id": "1"}], "hasNext": False},
        ]

    async def filters_stream_payloads_that_are_nulled_in_a_deferred_payload():
        """Filters stream payloads that are nulled in a deferred payload"""
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
            return None

        async def friend_list(_info):
            yield friends[0]  # pragma: no cover

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
                "data": {"nestedObject": {}},
                "pending": [{"id": "0", "path": ["nestedObject"]}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "data": {"deeperNestedObject": None},
                        "id": "0",
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
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def filters_defer_payloads_that_are_nulled_in_a_stream_response():
        """Filters defer payloads that are nulled in a stream response"""
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
            return None

        async def friend():
            return {
                "name": friends[0].name,
                "nonNullName": resolve_null,
            }

        async def friend_list(_info):
            yield await friend()

        result = await complete(document, {"friendList": friend_list})

        assert result == [
            {
                "data": {"friendList": []},
                "pending": [{"id": "0", "path": ["friendList"]}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "items": [None],
                        "id": "0",
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
                "hasNext": True,
            },
            {"completed": [{"id": "0"}], "hasNext": False},
        ]

    @pytest.mark.timeout(1)
    async def returns_iterator_and_ignores_error_when_stream_payloads_are_filtered():
        """Returns iterator and ignores errors when stream payloads are filtered"""
        iterated = False

        async def resolve_null(_info):
            return None

        async def iterable(_info):  # pragma: no cover
            nonlocal iterated
            iterated = True
            yield {"name": friends[0].name, "nonNullName": None}

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
        assert result1 == {
            "data": {"nestedObject": {}},
            "pending": [{"id": "0", "path": ["nestedObject"]}],
            "hasNext": True,
        }

        result2 = await anext(iterator)
        assert result2.formatted == {
            "incremental": [
                {
                    "data": {"deeperNestedObject": None},
                    "id": "0",
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
            "completed": [{"id": "0"}],
            "hasNext": False,
        }

        with pytest.raises(StopAsyncIteration):
            await anext(iterator)

        assert not iterated

    async def handles_awaitables_from_complete_value_after_initial_count_is_reached():
        """Handles awaitables returned by completeValue after initialCount is reached"""
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
            return friends[i].name

        async def get_friend(i):
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
                "data": {"friendList": [{"id": "1", "name": "Luke"}]},
                "pending": [{"id": "0", "path": ["friendList"]}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": [{"id": "2", "name": "Han"}], "id": "0"}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": [{"id": "3", "name": "Leia"}], "id": "0"}],
                "hasNext": True,
            },
            {"completed": [{"id": "0"}], "hasNext": False},
        ]

    async def handles_overlapping_deferred_and_non_deferred_streams():
        """Handles overlapping deferred and non-deferred streams"""
        document = parse(
            """
            query {
              nestedObject {
                nestedFriendList @stream(initialCount: 0) {
                  id
                }
              }
              nestedObject {
                ... @defer {
                  nestedFriendList @stream(initialCount: 0) {
                    id
                    name
                  }
                }
              }
            }
            """
        )

        async def get_nested_friend_list(_info):
            for i in range(2):
                yield friends[i]

        result = await complete(
            document,
            {
                "nestedObject": {
                    "nestedFriendList": get_nested_friend_list,
                }
            },
        )

        assert result == [
            {
                "data": {"nestedObject": {"nestedFriendList": []}},
                "pending": [
                    {"id": "0", "path": ["nestedObject", "nestedFriendList"]},
                ],
                "hasNext": True,
            },
            {
                "incremental": [{"items": [{"id": "1", "name": "Luke"}], "id": "0"}],
                "hasNext": True,
            },
            {
                "incremental": [{"items": [{"id": "2", "name": "Han"}], "id": "0"}],
                "hasNext": True,
            },
            {"completed": [{"id": "0"}], "hasNext": False},
        ]

    async def returns_payloads_properly_when_parent_deferred_slower_than_stream():
        """Returns payloads in correct order when parent deferred slower than stream

        Returns payloads in correct order when parent deferred fragment resolves
        slower than stream.
        """
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
        assert result1 == {
            "data": {"nestedObject": {}},
            "pending": [{"id": "0", "path": ["nestedObject"]}],
            "hasNext": True,
        }

        resolve_slow_field.set()
        result2 = await anext(iterator)
        assert result2.formatted == {
            "pending": [{"id": "1", "path": ["nestedObject", "nestedFriendList"]}],
            "incremental": [
                {"data": {"scalarField": "slow", "nestedFriendList": []}, "id": "0"},
            ],
            "completed": [{"id": "0"}],
            "hasNext": True,
        }
        result3 = await anext(iterator)
        assert result3.formatted == {
            "incremental": [{"items": [{"name": "Luke"}], "id": "1"}],
            "hasNext": True,
        }
        result4 = await anext(iterator)
        assert result4.formatted == {
            "incremental": [{"items": [{"name": "Han"}], "id": "1"}],
            "hasNext": True,
        }
        result5 = await anext(iterator)
        assert result5.formatted == {"completed": [{"id": "1"}], "hasNext": False}

        with pytest.raises(StopAsyncIteration):
            await anext(iterator)

    @pytest.mark.timeout(1)
    async def can_defer_fields_that_are_resolved_after_async_iterable_is_complete():
        """Can @defer fields that are resolved after async iterable is complete"""
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
            yield friends[0]
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
        assert result1 == {
            "data": {"friendList": [{"id": "1"}]},
            "pending": [
                {"id": "0", "path": ["friendList", 0], "label": "DeferName"},
                {"id": "1", "path": ["friendList"], "label": "stream-label"},
            ],
            "hasNext": True,
        }

        result2 = await anext(iterator)
        assert result2.formatted == {
            "pending": [{"id": "2", "path": ["friendList", 1], "label": "DeferName"}],
            "incremental": [
                {"data": {"name": "Luke"}, "id": "0"},
                {"items": [{"id": "2"}], "id": "1"},
            ],
            "completed": [{"id": "0"}],
            "hasNext": True,
        }

        resolve_iterable.set()
        result3 = await anext(iterator)
        assert result3.formatted == {
            "completed": [{"id": "1"}],
            "hasNext": True,
        }

        resolve_slow_field.set()
        result4 = await anext(iterator)
        assert result4.formatted == {
            "incremental": [{"data": {"name": "Han"}, "id": "2"}],
            "completed": [{"id": "2"}],
            "hasNext": False,
        }

        with pytest.raises(StopAsyncIteration):
            await anext(iterator)

    async def can_defer_fields_that_are_resolved_before_async_iterable_is_complete():
        """Can @defer fields that are resolved before async iterable is complete"""
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
            yield friends[0]
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
        assert result1 == {
            "data": {"friendList": [{"id": "1"}]},
            "pending": [
                {"id": "0", "path": ["friendList", 0], "label": "DeferName"},
                {"id": "1", "path": ["friendList"], "label": "stream-label"},
            ],
            "hasNext": True,
        }

        result2 = await anext(iterator)
        assert result2.formatted == {
            "pending": [{"id": "2", "path": ["friendList", 1], "label": "DeferName"}],
            "incremental": [
                {"data": {"name": "Luke"}, "id": "0"},
                {"items": [{"id": "2"}], "id": "1"},
            ],
            "completed": [{"id": "0"}],
            "hasNext": True,
        }

        resolve_iterable.set()
        result3 = await anext(iterator)
        assert result3.formatted == {
            "completed": [{"id": "1"}],
            "hasNext": True,
        }

        resolve_slow_field.set()
        result4 = await anext(iterator)
        assert result4.formatted == {
            "incremental": [
                {"data": {"name": "Han"}, "id": "2"},
            ],
            "completed": [{"id": "2"}],
            "hasNext": False,
        }

        with pytest.raises(StopAsyncIteration):
            await anext(iterator)

    async def finishes_async_iterable_when_finished_generator_is_closed():
        """Finishes underlying async iterables when returned generator is closed"""
        finished = False

        async def iterable(_info):
            nonlocal finished
            try:
                for i in range(3):  # pragma: no cover exit
                    yield friends[i]
            finally:
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
        assert result1 == {
            "data": {"friendList": [{"id": "1"}]},
            "pending": [
                {"id": "0", "path": ["friendList", 0]},
                {"id": "1", "path": ["friendList"]},
            ],
            "hasNext": True,
        }

        # we need to run the iterator once before we can close it
        result2 = await anext(iterator)
        assert result2 == {
            "pending": [{"id": "2", "path": ["friendList", 1]}],
            "incremental": [
                {"data": {"name": "Luke"}, "id": "0"},
                {"items": [{"id": "2"}], "id": "1"},
            ],
            "completed": [{"id": "0"}],
            "hasNext": True,
        }

        await iterator.aclose()
        with pytest.raises(StopAsyncIteration):
            await anext(iterator)

        assert finished

    async def finishes_async_iterable_when_underlying_iterator_has_no_aclose_method():
        """Finishes async iterable when underlying iterable has not aclose method"""

        class Iterable:
            def __init__(self):
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                index = self.index
                self.index = index + 1
                try:
                    return friends[index]
                except IndexError:  # pragma: no cover
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
            "pending": [{"id": "0", "path": ["friendList"]}],
            "hasNext": True,
        }

        await iterator.aclose()
        with pytest.raises(StopAsyncIteration):
            await anext(iterator)

        await sleep(0)
        assert iterable.index == 2

    async def finishes_async_iterable_when_error_is_raised_in_finished_generator():
        """Finishes underlying async iterables when an error is raised in generator"""
        finished = False

        async def iterable(_info):
            nonlocal finished
            try:
                for i in range(3):  # pragma: no cover exit
                    yield friends[i]
            finally:
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
        assert result1 == {
            "data": {"friendList": [{"id": "1"}]},
            "pending": [
                {"id": "0", "path": ["friendList", 0]},
                {"id": "1", "path": ["friendList"]},
            ],
            "hasNext": True,
        }

        with pytest.raises(RuntimeError, match="bad"):
            await iterator.athrow(RuntimeError("bad"))

        with pytest.raises(StopAsyncIteration):
            await anext(iterator)

        # the stream iterators are not finished in this case, since the main iterator
        # is actually a generator that cannot do the cleanup in case of an athrow()
        await sleep(0)
        assert not finished
