from __future__ import annotations

from asyncio import sleep
from typing import Any, AsyncGenerator, NamedTuple, cast

import pytest

from graphql.error import GraphQLError
from graphql.execution import (
    CompletedResult,
    DeferredFragmentRecord,
    ExecutionResult,
    ExperimentalIncrementalExecutionResults,
    IncrementalDeferResult,
    IncrementalResult,
    InitialIncrementalExecutionResult,
    PendingResult,
    SubsequentIncrementalExecutionResult,
    execute,
    experimental_execute_incrementally,
)
from graphql.language import DocumentNode, parse
from graphql.pyutils import Path, is_awaitable
from graphql.type import (
    GraphQLField,
    GraphQLID,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)

pytestmark = pytest.mark.anyio

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


friends = [Friend(2, "Han"), Friend(3, "Leia"), Friend(4, "C-3PO")]

deeper_object = GraphQLObjectType(
    "DeeperObject",
    {
        "foo": GraphQLField(GraphQLString),
        "bar": GraphQLField(GraphQLString),
        "baz": GraphQLField(GraphQLString),
        "bak": GraphQLField(GraphQLString),
    },
)

nested_object = GraphQLObjectType(
    "NestedObject",
    {"deeperObject": GraphQLField(deeper_object), "name": GraphQLField(GraphQLString)},
)

another_nested_object = GraphQLObjectType(
    "AnotherNestedObject", {"deeperObject": GraphQLField(deeper_object)}
)

hero = {
    "name": "Luke",
    "id": 1,
    "friends": friends,
    "nestedObject": nested_object,
    "AnotherNestedObject": another_nested_object,
}

c = GraphQLObjectType(
    "c",
    {
        "d": GraphQLField(GraphQLString),
        "nonNullErrorField": GraphQLField(GraphQLNonNull(GraphQLString)),
    },
)

e = GraphQLObjectType(
    "e",
    {
        "f": GraphQLField(GraphQLString),
    },
)

b = GraphQLObjectType(
    "b",
    {
        "c": GraphQLField(c),
        "e": GraphQLField(e),
    },
)

a = GraphQLObjectType(
    "a",
    {
        "b": GraphQLField(b),
        "someField": GraphQLField(GraphQLString),
    },
)

g = GraphQLObjectType(
    "g",
    {
        "h": GraphQLField(GraphQLString),
    },
)

hero_type = GraphQLObjectType(
    "Hero",
    {
        "id": GraphQLField(GraphQLID),
        "name": GraphQLField(GraphQLString),
        "nonNullName": GraphQLField(GraphQLNonNull(GraphQLString)),
        "friends": GraphQLField(GraphQLList(friend_type)),
        "nestedObject": GraphQLField(nested_object),
        "anotherNestedObject": GraphQLField(another_nested_object),
    },
)

query = GraphQLObjectType(
    "Query",
    {"hero": GraphQLField(hero_type), "a": GraphQLField(a), "g": GraphQLField(g)},
)

schema = GraphQLSchema(query)


class Resolvers:
    """Various resolver functions for testing"""

    @staticmethod
    def null(_info) -> None:
        """A resolver returning a null value synchronously"""
        return

    @staticmethod
    async def null_async(_info) -> None:
        """A resolver returning a null value asynchronously"""
        return

    @staticmethod
    async def slow(_info) -> str:
        """Simulate a slow async resolver returning a non-null value"""
        await sleep(0)
        return "slow"

    @staticmethod
    async def slow_null(_info) -> None:
        """Simulate a slow async resolver returning a null value"""
        await sleep(0)

    @staticmethod
    def bad(_info) -> str:
        """Simulate a bad resolver raising an error"""
        raise RuntimeError("bad")

    @staticmethod
    async def first_friend(_info) -> AsyncGenerator[Friend, None]:
        """An async generator yielding the first friend"""
        yield friends[0]


async def complete(document: DocumentNode, root_value: Any = None) -> Any:
    result = experimental_execute_incrementally(
        schema, document, root_value or {"hero": hero}
    )
    if is_awaitable(result):
        result = await result

    if isinstance(result, ExperimentalIncrementalExecutionResults):
        results: list[Any] = [result.initial_result.formatted]
        async for patch in result.subsequent_results:
            results.append(patch.formatted)
        return results

    assert isinstance(result, ExecutionResult)
    return result.formatted


def modified_args(args: dict[str, Any], **modifications: Any) -> dict[str, Any]:
    return {**args, **modifications}


def describe_execute_defer_directive():
    """Execute: Defer Directive"""

    def can_format_and_print_pending_result():
        """Can format and print a PendingResult"""
        result = PendingResult("foo", [])
        assert result.formatted == {"id": "foo", "path": []}
        assert str(result) == "PendingResult(id='foo', path=[])"

        result = PendingResult(id="foo", path=["bar", 1], label="baz")
        assert result.formatted == {"id": "foo", "path": ["bar", 1], "label": "baz"}
        assert str(result) == "PendingResult(id='foo', path=['bar', 1], label='baz')"

    def can_compare_pending_result():
        """Can compare a PendingResult"""
        args: dict[str, Any] = {"id": "foo", "path": ["bar", 1], "label": "baz"}
        result = PendingResult(**args)
        assert result == PendingResult(**args)
        assert result != PendingResult(**modified_args(args, id="bar"))
        assert result != PendingResult(**modified_args(args, path=["bar", 2]))
        assert result != PendingResult(**modified_args(args, label="bar"))
        assert result == tuple(args.values())
        assert result == tuple(args.values())[:2]
        assert result != tuple(args.values())[:1]
        assert result != (*tuple(args.values())[:1], ["bar", 2])
        assert result == args
        assert result != {**args, "id": "bar"}
        assert result != {**args, "path": ["bar", 2]}
        assert result != {**args, "label": "bar"}

    def can_format_and_print_completed_result():
        """Can format and print a CompletedResult"""
        result = CompletedResult("foo")
        assert result.formatted == {"id": "foo"}
        assert str(result) == "CompletedResult(id='foo')"

        result = CompletedResult(id="foo", errors=[GraphQLError("oops")])
        assert result.formatted == {"id": "foo", "errors": [{"message": "oops"}]}
        assert str(result) == "CompletedResult(id='foo', errors=[GraphQLError('oops')])"

    def can_compare_completed_result():
        """Can compare a CompletedResult"""
        args: dict[str, Any] = {"id": "foo", "errors": []}
        result = CompletedResult(**args)
        assert result == CompletedResult(**args)
        assert result != CompletedResult(**modified_args(args, id="bar"))
        assert result != CompletedResult(
            **modified_args(args, errors=[GraphQLError("oops")])
        )
        assert result == tuple(args.values())
        assert result != tuple(args.values())[:1]
        assert result != (*tuple(args.values())[:1], [GraphQLError("oops")])
        assert result == args
        assert result != {**args, "id": "bar"}
        assert result != {**args, "errors": [{"message": "oops"}]}

    def can_format_and_print_incremental_defer_result():
        """Can format and print an IncrementalDeferResult"""
        result = IncrementalDeferResult(data={}, id="foo")
        assert result.formatted == {"data": {}, "id": "foo"}
        assert str(result) == "IncrementalDeferResult(data={}, id='foo')"

        result = IncrementalDeferResult(
            data={"hello": "world"},
            id="foo",
            sub_path=["bar", 1],
            errors=[GraphQLError("oops")],
            extensions={"baz": 2},
        )
        assert result.formatted == {
            "data": {"hello": "world"},
            "id": "foo",
            "subPath": ["bar", 1],
            "errors": [{"message": "oops"}],
            "extensions": {"baz": 2},
        }
        assert (
            str(result) == "IncrementalDeferResult(data={'hello': 'world'},"
            " id='foo', sub_path=['bar', 1], errors=[GraphQLError('oops')],"
            " extensions={'baz': 2})"
        )

    def can_compare_incremental_defer_result():
        """Can compare an IncrementalDeferResult"""
        args: dict[str, Any] = {
            "data": {"hello": "world"},
            "id": "foo",
            "sub_path": ["bar", 1],
            "errors": [GraphQLError("oops")],
            "extensions": {"baz": 2},
        }
        result = IncrementalDeferResult(**args)
        assert result == IncrementalDeferResult(**args)
        assert result != IncrementalDeferResult(
            **modified_args(args, data={"hello": "foo"})
        )
        assert result != IncrementalDeferResult(**modified_args(args, id="bar"))
        assert result != IncrementalDeferResult(
            **modified_args(args, sub_path=["bar", 2])
        )
        assert result != IncrementalDeferResult(**modified_args(args, errors=[]))
        assert result != IncrementalDeferResult(
            **modified_args(args, extensions={"baz": 1})
        )
        assert result == tuple(args.values())
        assert result == tuple(args.values())[:4]
        assert result == tuple(args.values())[:3]
        assert result == tuple(args.values())[:2]
        assert result != tuple(args.values())[:1]
        assert result != ({"hello": "world"}, "bar")
        args["subPath"] = args.pop("sub_path")
        assert result == args
        assert result != {**args, "data": {"hello": "foo"}}
        assert result != {**args, "id": "bar"}
        assert result != {**args, "subPath": ["bar", 2]}
        assert result != {**args, "errors": []}
        assert result != {**args, "extensions": {"baz": 1}}

    def can_format_and_print_initial_incremental_execution_result():
        """Can format and print an InitialIncrementalExecutionResult"""
        result = InitialIncrementalExecutionResult()
        assert result.formatted == {"data": None, "hasNext": False, "pending": []}
        assert str(result) == "InitialIncrementalExecutionResult(data=None)"

        result = InitialIncrementalExecutionResult(has_next=True)
        assert result.formatted == {"data": None, "hasNext": True, "pending": []}
        assert str(result) == "InitialIncrementalExecutionResult(data=None, has_next)"

        result = InitialIncrementalExecutionResult(
            data={"hello": "world"},
            errors=[GraphQLError("msg")],
            pending=[PendingResult("foo", ["bar"])],
            has_next=True,
            extensions={"baz": 2},
        )
        assert result.formatted == {
            "data": {"hello": "world"},
            "errors": [{"message": "msg"}],
            "pending": [{"id": "foo", "path": ["bar"]}],
            "hasNext": True,
            "extensions": {"baz": 2},
        }
        assert (
            str(result) == "InitialIncrementalExecutionResult("
            "data={'hello': 'world'}, errors=[GraphQLError('msg')],"
            " pending=[PendingResult(id='foo', path=['bar'])], has_next,"
            " extensions={'baz': 2})"
        )

    def can_compare_initial_incremental_execution_result():
        """Can compare an InitialIncrementalExecutionResult"""
        args: dict[str, Any] = {
            "data": {"hello": "world"},
            "errors": [GraphQLError("msg")],
            "pending": [PendingResult("foo", ["bar"])],
            "has_next": True,
            "extensions": {"baz": 2},
        }
        result = InitialIncrementalExecutionResult(**args)
        assert result == InitialIncrementalExecutionResult(**args)
        assert result != InitialIncrementalExecutionResult(
            **modified_args(args, data={"hello": "foo"})
        )
        assert result != InitialIncrementalExecutionResult(
            **modified_args(args, errors=[])
        )
        assert result != InitialIncrementalExecutionResult(
            **modified_args(args, pending=[])
        )
        assert result != InitialIncrementalExecutionResult(
            **modified_args(args, has_next=False)
        )
        assert result != InitialIncrementalExecutionResult(
            **modified_args(args, extensions={"baz": 1})
        )
        assert result == tuple(args.values())
        assert result == tuple(args.values())[:5]
        assert result == tuple(args.values())[:4]
        assert result == tuple(args.values())[:3]
        assert result == tuple(args.values())[:2]
        assert result != tuple(args.values())[:1]
        assert result != ({"hello": "foo"}, [])

        assert result == {
            "data": {"hello": "world"},
            "errors": [GraphQLError("msg")],
            "pending": [PendingResult("foo", ["bar"])],
            "hasNext": True,
            "extensions": {"baz": 2},
        }
        assert result != {
            "errors": [GraphQLError("msg")],
            "pending": [PendingResult("foo", ["bar"])],
            "hasNext": True,
            "extensions": {"baz": 2},
        }
        assert result != {
            "data": {"hello": "world"},
            "pending": [PendingResult("foo", ["bar"])],
            "hasNext": True,
            "extensions": {"baz": 2},
        }
        assert result != {
            "data": {"hello": "world"},
            "errors": [GraphQLError("msg")],
            "hasNext": True,
            "extensions": {"baz": 2},
        }
        assert result != {
            "data": {"hello": "world"},
            "errors": [GraphQLError("msg")],
            "pending": [PendingResult("foo", ["bar"])],
            "extensions": {"baz": 2},
        }
        assert result != {
            "data": {"hello": "world"},
            "errors": [GraphQLError("msg")],
            "pending": [PendingResult("foo", ["bar"])],
            "hasNext": True,
        }

    def can_format_and_print_subsequent_incremental_execution_result():
        """Can format and print a SubsequentIncrementalExecutionResult"""
        result = SubsequentIncrementalExecutionResult()
        assert result.formatted == {"hasNext": False}
        assert str(result) == "SubsequentIncrementalExecutionResult()"

        result = SubsequentIncrementalExecutionResult(has_next=True)
        assert result.formatted == {"hasNext": True}
        assert str(result) == "SubsequentIncrementalExecutionResult(has_next)"

        pending = [PendingResult("foo", ["bar"])]
        incremental = [
            cast("IncrementalResult", IncrementalDeferResult({"foo": 1}, "bar"))
        ]
        completed = [CompletedResult("foo")]
        result = SubsequentIncrementalExecutionResult(
            has_next=True,
            pending=pending,
            incremental=incremental,
            completed=completed,
            extensions={"baz": 2},
        )
        assert result.formatted == {
            "hasNext": True,
            "pending": [{"id": "foo", "path": ["bar"]}],
            "incremental": [{"data": {"foo": 1}, "id": "bar"}],
            "completed": [{"id": "foo"}],
            "extensions": {"baz": 2},
        }
        assert (
            str(result) == "SubsequentIncrementalExecutionResult(has_next,"
            " pending[1], incremental[1], completed[1], extensions={'baz': 2})"
        )

    def can_compare_subsequent_incremental_execution_result():
        """Can compare a SubsequentIncrementalExecutionResult"""
        pending = [PendingResult("foo", ["bar"])]
        incremental = [
            cast("IncrementalResult", IncrementalDeferResult({"foo": 1}, "bar"))
        ]
        completed = [CompletedResult("foo")]
        args: dict[str, Any] = {
            "has_next": True,
            "pending": pending,
            "incremental": incremental,
            "completed": completed,
            "extensions": {"baz": 2},
        }
        result = SubsequentIncrementalExecutionResult(**args)
        assert result == SubsequentIncrementalExecutionResult(**args)
        assert result != SubsequentIncrementalExecutionResult(
            **modified_args(args, pending=[])
        )
        assert result != SubsequentIncrementalExecutionResult(
            **modified_args(args, incremental=[])
        )
        assert result != SubsequentIncrementalExecutionResult(
            **modified_args(args, has_next=False)
        )
        assert result != SubsequentIncrementalExecutionResult(
            **modified_args(args, extensions={"baz": 1})
        )
        assert result == tuple(args.values())
        assert result == tuple(args.values())[:3]
        assert result == tuple(args.values())[:2]
        assert result != tuple(args.values())[:1]
        assert result != (incremental, False)
        assert result == {
            "hasNext": True,
            "pending": pending,
            "incremental": incremental,
            "completed": completed,
            "extensions": {"baz": 2},
        }
        assert result != {
            "pending": pending,
            "incremental": incremental,
            "completed": completed,
            "extensions": {"baz": 2},
        }
        assert result != {
            "hasNext": True,
            "incremental": incremental,
            "completed": completed,
            "extensions": {"baz": 2},
        }
        assert result != {
            "hasNext": True,
            "pending": pending,
            "completed": completed,
            "extensions": {"baz": 2},
        }
        assert result != {
            "hasNext": True,
            "pending": pending,
            "incremental": incremental,
            "extensions": {"baz": 2},
        }
        assert result != {
            "hasNext": True,
            "pending": pending,
            "incremental": incremental,
            "completed": completed,
        }

    def can_print_deferred_fragment_record():
        """Can print a DeferredFragmentRecord"""
        record = DeferredFragmentRecord()
        assert str(record) == "DeferredFragmentRecord()"
        record = DeferredFragmentRecord(Path(None, "bar", "Bar"), "foo")
        assert str(record) == "DeferredFragmentRecord(path=['bar'], label='foo')"

    async def can_defer_fragments_containing_scalar_types():
        """Can defer fragments containing scalar types"""
        document = parse(
            """
            query HeroNameQuery {
              hero {
                id
                ...NameFragment @defer
              }
            }
            fragment NameFragment on Hero {
              name
            }
            """
        )
        result = await complete(document)

        assert result == [
            {
                "data": {"hero": {"id": "1"}},
                "pending": [{"id": "0", "path": ["hero"]}],
                "hasNext": True,
            },
            {
                "incremental": [{"data": {"name": "Luke"}, "id": "0"}],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def can_disable_defer_using_if_argument():
        """Can disable defer using if argument"""
        document = parse(
            """
            query HeroNameQuery {
              hero {
                id
                ...NameFragment @defer(if: false)
              }
            }
            fragment NameFragment on Hero {
              name
            }
            """
        )
        result = await complete(document)

        assert result == {"data": {"hero": {"id": "1", "name": "Luke"}}}

    async def does_not_disable_defer_with_null_if_argument():
        """Does not disable defer with null if argument"""
        document = parse(
            """
            query HeroNameQuery($shouldDefer: Boolean) {
              hero {
                id
                ...NameFragment @defer(if: $shouldDefer)
              }
            }
            fragment NameFragment on Hero {
              name
            }
            """
        )
        result = await complete(document)

        assert result == [
            {
                "data": {"hero": {"id": "1"}},
                "pending": [{"id": "0", "path": ["hero"]}],
                "hasNext": True,
            },
            {
                "incremental": [{"data": {"name": "Luke"}, "id": "0"}],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def throws_an_error_for_defer_directive_with_non_string_label():
        """Throws an error for @defer directive with non-string label"""
        document = parse(
            """
            query Deferred {
              ... @defer(label: 42) { hero { id } }
            }
            """
        )
        result = await complete(document)

        assert result == {
            "data": None,
            "errors": [
                {
                    "locations": [{"column": 33, "line": 3}],
                    "message": "Argument 'label' has invalid value 42.",
                }
            ],
        }

    async def can_defer_fragments_on_the_top_level_query_field():
        """Can defer fragments on the top level Query field"""
        document = parse(
            """
            query HeroNameQuery {
              ...QueryFragment @defer(label: "DeferQuery")
            }
            fragment QueryFragment on Query {
              hero {
                id
              }
            }
            """
        )
        result = await complete(document)

        assert result == [
            {
                "data": {},
                "pending": [{"id": "0", "path": [], "label": "DeferQuery"}],
                "hasNext": True,
            },
            {
                "incremental": [{"data": {"hero": {"id": "1"}}, "id": "0"}],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def can_defer_fragments_with_errors_on_the_top_level_query_field():
        """Can defer fragments with errors on the top level Query field"""
        document = parse(
            """
            query HeroNameQuery {
              ...QueryFragment @defer(label: "DeferQuery")
            }
            fragment QueryFragment on Query {
              hero {
                name
              }
            }
            """
        )
        result = await complete(document, {"hero": {**hero, "name": Resolvers.bad}})

        assert result == [
            {
                "data": {},
                "pending": [{"id": "0", "path": [], "label": "DeferQuery"}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "data": {"hero": {"name": None}},
                        "errors": [
                            {
                                "message": "bad",
                                "locations": [{"column": 17, "line": 7}],
                                "path": ["hero", "name"],
                            }
                        ],
                        "id": "0",
                    }
                ],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def can_defer_a_fragment_within_an_already_deferred_fragment():
        """Can defer a fragment within an already deferred fragment"""
        document = parse(
            """
            query HeroNameQuery {
              hero {
                ...TopFragment @defer(label: "DeferTop")
              }
            }
            fragment TopFragment on Hero {
              id
              ...NestedFragment @defer(label: "DeferNested")
            }
            fragment NestedFragment on Hero {
              friends {
                name
              }
            }
            """
        )
        result = await complete(document)

        assert result == [
            {
                "data": {"hero": {}},
                "pending": [{"id": "0", "path": ["hero"], "label": "DeferTop"}],
                "hasNext": True,
            },
            {
                "pending": [{"id": "1", "path": ["hero"], "label": "DeferNested"}],
                "incremental": [
                    {"data": {"id": "1"}, "id": "0"},
                ],
                "completed": [{"id": "0"}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "data": {
                            "friends": [
                                {"name": "Han"},
                                {"name": "Leia"},
                                {"name": "C-3PO"},
                            ]
                        },
                        "id": "1",
                    },
                ],
                "completed": [{"id": "1"}],
                "hasNext": False,
            },
        ]

    async def can_defer_a_fragment_that_is_also_not_deferred_with_deferred_first():
        """Can defer a fragment that is also not deferred, deferred fragment is first"""
        document = parse(
            """
            query HeroNameQuery {
              hero {
                ...TopFragment @defer(label: "DeferTop")
                ...TopFragment
              }
            }
            fragment TopFragment on Hero {
              name
            }
            """
        )
        result = await complete(document)

        assert result == {"data": {"hero": {"name": "Luke"}}}

    async def can_defer_a_fragment_that_is_also_not_deferred_with_non_deferred_first():
        """Can defer a fragment that is also not deferred, non-deferred first

        Can defer a fragment that is also not deferred, non-deferred fragment is first.
        """
        document = parse(
            """
            query HeroNameQuery {
              hero {
                ...TopFragment
                ...TopFragment @defer(label: "DeferTop")
              }
            }
            fragment TopFragment on Hero {
              name
            }
            """
        )
        result = await complete(document)

        assert result == {"data": {"hero": {"name": "Luke"}}}

    async def can_defer_an_inline_fragment():
        """Can defer an inline fragment"""
        document = parse(
            """
            query HeroNameQuery {
              hero {
                id
                ... on Hero @defer(label: "InlineDeferred") {
                  name
                }
              }
            }
            """
        )
        result = await complete(document)

        assert result == [
            {
                "data": {"hero": {"id": "1"}},
                "pending": [{"id": "0", "path": ["hero"], "label": "InlineDeferred"}],
                "hasNext": True,
            },
            {
                "incremental": [{"data": {"name": "Luke"}, "id": "0"}],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def does_not_emit_empty_defer_fragments():
        """Does not emit empty defer fragments"""
        document = parse(
            """
            query HeroNameQuery {
              hero {
                ... @defer {
                  name @skip(if: true)
                }
              }
            }
            fragment TopFragment on Hero {
              name
            }
            """
        )
        result = await complete(document)

        assert result == {"data": {"hero": {}}}

    async def emits_children_of_empty_defer_fragments():
        """Emits children of empty defer fragments"""
        document = parse(
            """
            query HeroNameQuery {
              hero {
                ... @defer {
                  ... @defer {
                    name
                  }
                }
              }
            }
            """
        )
        result = await complete(document)

        assert result == [
            {
                "data": {"hero": {}},
                "pending": [{"id": "0", "path": ["hero"]}],
                "hasNext": True,
            },
            {
                "incremental": [{"data": {"name": "Luke"}, "id": "0"}],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def separately_emits_defer_fragments_different_labels_varying_fields():
        """Separately emits defer fragments with different labels with varying fields

        Can separately emit defer fragments with different labels with varying fields.
        """
        document = parse(
            """
            query HeroNameQuery {
              hero {
                ... @defer(label: "DeferID") {
                  id
                }
                ... @defer(label: "DeferName") {
                  name
                }
              }
            }
            """
        )
        result = await complete(document)

        assert result == [
            {
                "data": {"hero": {}},
                "pending": [
                    {"id": "0", "path": ["hero"], "label": "DeferID"},
                    {"id": "1", "path": ["hero"], "label": "DeferName"},
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"data": {"id": "1"}, "id": "0"},
                    {"data": {"name": "Luke"}, "id": "1"},
                ],
                "completed": [{"id": "0"}, {"id": "1"}],
                "hasNext": False,
            },
        ]

    async def separately_emits_defer_fragments_different_labels_varying_subfields():
        """Separately emits defer fragments with different labels, varying subfields

        Can separately emit defer fragments with different labels with varying fields.
        """
        document = parse(
            """
            query HeroNameQuery {
              ... @defer(label: "DeferID") {
                hero {
                  id
                }
              }
              ... @defer(label: "DeferName") {
                hero {
                  name
                }
              }
            }
            """
        )
        result = await complete(document)

        assert result == [
            {
                "data": {},
                "pending": [
                    {"id": "0", "path": [], "label": "DeferID"},
                    {"id": "1", "path": [], "label": "DeferName"},
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"data": {"hero": {}}, "id": "0"},
                    {"data": {"id": "1"}, "id": "0", "subPath": ["hero"]},
                    {"data": {"name": "Luke"}, "id": "1", "subPath": ["hero"]},
                ],
                "completed": [{"id": "0"}, {"id": "1"}],
                "hasNext": False,
            },
        ]

    async def separately_emits_defer_fragments_different_labels_var_subfields_async():
        """Separately emits defer fragments, different labels, varying subfields, async

        Separately emits defer fragments with different labels with varying subfields
        that return awaitables.
        """
        document = parse(
            """
            query HeroNameQuery {
              ... @defer(label: "DeferID") {
                hero {
                  id
                }
              }
              ... @defer(label: "DeferName") {
                hero {
                  name
                }
              }
            }
            """
        )

        async def resolve(value):
            return value

        result = await complete(
            document,
            {
                "hero": {
                    "id": lambda _info: resolve(1),
                    "name": lambda _info: resolve("Luke"),
                }
            },
        )

        assert result == [
            {
                "data": {},
                "pending": [
                    {"id": "0", "path": [], "label": "DeferID"},
                    {"id": "1", "path": [], "label": "DeferName"},
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"data": {"hero": {}}, "id": "0"},
                    {"data": {"id": "1"}, "id": "0", "subPath": ["hero"]},
                    {"data": {"name": "Luke"}, "id": "1", "subPath": ["hero"]},
                ],
                "completed": [{"id": "0"}, {"id": "1"}],
                "hasNext": False,
            },
        ]

    async def separately_emits_defer_fragments_var_subfields_same_prio_diff_level():
        """Separately emits defer fragments, varying subfields, same prio, diff level

        Separately emits defer fragments with varying subfields of same priorities
        but different level of defers.
        """
        document = parse(
            """
            query HeroNameQuery {
              hero {
                ... @defer(label: "DeferID") {
                  id
                }
              }
              ... @defer(label: "DeferName") {
                hero {
                  name
                }
              }
            }
            """
        )
        result = await complete(document)

        assert result == [
            {
                "data": {"hero": {}},
                "pending": [
                    {"id": "0", "path": ["hero"], "label": "DeferID"},
                    {"id": "1", "path": [], "label": "DeferName"},
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"data": {"id": "1"}, "id": "0"},
                    {"data": {"name": "Luke"}, "id": "1", "subPath": ["hero"]},
                ],
                "completed": [{"id": "0"}, {"id": "1"}],
                "hasNext": False,
            },
        ]

    async def separately_emits_nested_defer_frags_var_subfields_same_prio_diff_level():
        """Separately emits nested defer frags, var subfields, same prio, diff level

        Separately emits nested defer fragments with varying subfields of same
        priorities but different level of defers.
        """
        document = parse(
            """
            query HeroNameQuery {
              ... @defer(label: "DeferName") {
                hero {
                  name
                  ... @defer(label: "DeferID") {
                    id
                  }
                }
              }
            }
            """
        )
        result = await complete(document)

        assert result == [
            {
                "data": {},
                "pending": [{"id": "0", "path": [], "label": "DeferName"}],
                "hasNext": True,
            },
            {
                "pending": [{"id": "1", "path": ["hero"], "label": "DeferID"}],
                "incremental": [{"data": {"hero": {"name": "Luke"}}, "id": "0"}],
                "completed": [{"id": "0"}],
                "hasNext": True,
            },
            {
                "incremental": [{"data": {"id": "1"}, "id": "1"}],
                "completed": [{"id": "1"}],
                "hasNext": False,
            },
        ]

    async def can_deduplicate_multiple_defers_on_the_same_object():
        """Can deduplicate multiple defers on the same object"""
        document = parse(
            """
            query {
              hero {
                friends {
                  ... @defer {
                    ...FriendFrag
                    ... @defer {
                      ...FriendFrag
                      ... @defer {
                        ...FriendFrag
                        ... @defer {
                          ...FriendFrag
                        }
                      }
                    }
                  }
                }
              }
            }

            fragment FriendFrag on Friend {
              id
              name
            }
            """
        )
        result = await complete(document)

        assert result == [
            {
                "data": {"hero": {"friends": [{}, {}, {}]}},
                "pending": [
                    {"id": "0", "path": ["hero", "friends", 0]},
                    {"id": "1", "path": ["hero", "friends", 1]},
                    {"id": "2", "path": ["hero", "friends", 2]},
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"data": {"id": "2", "name": "Han"}, "id": "0"},
                    {"data": {"id": "3", "name": "Leia"}, "id": "1"},
                    {"data": {"id": "4", "name": "C-3PO"}, "id": "2"},
                ],
                "completed": [{"id": "0"}, {"id": "1"}, {"id": "2"}],
                "hasNext": False,
            },
        ]

    async def deduplicates_fields_present_in_the_initial_payload():
        """Deduplicates fields present in the initial payload"""
        document = parse(
            """
            query {
              hero {
                nestedObject {
                  deeperObject {
                    foo
                  }
                }
                anotherNestedObject {
                  deeperObject {
                    foo
                  }
                }
                ... @defer {
                  nestedObject {
                    deeperObject {
                      bar
                    }
                  }
                  anotherNestedObject {
                    deeperObject {
                      foo
                    }
                  }
                }
              }
            }
            """
        )
        result = await complete(
            document,
            {
                "hero": {
                    "nestedObject": {"deeperObject": {"foo": "foo", "bar": "bar"}},
                    "anotherNestedObject": {"deeperObject": {"foo": "foo"}},
                }
            },
        )

        assert result == [
            {
                "data": {
                    "hero": {
                        "nestedObject": {"deeperObject": {"foo": "foo"}},
                        "anotherNestedObject": {"deeperObject": {"foo": "foo"}},
                    }
                },
                "pending": [{"id": "0", "path": ["hero"]}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "data": {"bar": "bar"},
                        "id": "0",
                        "subPath": ["nestedObject", "deeperObject"],
                    },
                ],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def deduplicates_fields_present_in_a_parent_defer_payload():
        """Deduplicates fields present in a parent defer payload"""
        document = parse(
            """
            query {
              hero {
                ... @defer {
                  nestedObject {
                    deeperObject {
                      foo
                      ... @defer {
                        foo
                        bar
                      }
                    }
                  }
                }
              }
            }
            """
        )
        result = await complete(
            document,
            {"hero": {"nestedObject": {"deeperObject": {"foo": "foo", "bar": "bar"}}}},
        )

        assert result == [
            {
                "data": {"hero": {}},
                "pending": [{"id": "0", "path": ["hero"]}],
                "hasNext": True,
            },
            {
                "pending": [
                    {"id": "1", "path": ["hero", "nestedObject", "deeperObject"]}
                ],
                "incremental": [
                    {
                        "data": {"nestedObject": {"deeperObject": {"foo": "foo"}}},
                        "id": "0",
                    },
                ],
                "completed": [{"id": "0"}],
                "hasNext": True,
            },
            {
                "incremental": [{"data": {"bar": "bar"}, "id": "1"}],
                "completed": [{"id": "1"}],
                "hasNext": False,
            },
        ]

    async def deduplicates_fields_with_deferred_fragments_at_multiple_levels():
        """Deduplicates fields with deferred fragments at multiple levels"""
        document = parse(
            """
            query {
              hero {
                nestedObject {
                  deeperObject {
                    foo
                  }
                }
                ... @defer {
                  nestedObject {
                    deeperObject {
                      foo
                      bar
                    }
                    ... @defer {
                      deeperObject {
                        foo
                        bar
                        baz
                        ... @defer {
                          foo
                          bar
                          baz
                          bak
                        }
                      }
                    }
                  }
                }
              }
            }
            """
        )
        result = await complete(
            document,
            {
                "hero": {
                    "nestedObject": {
                        "deeperObject": {
                            "foo": "foo",
                            "bar": "bar",
                            "baz": "baz",
                            "bak": "bak",
                        }
                    }
                }
            },
        )

        assert result == [
            {
                "data": {
                    "hero": {
                        "nestedObject": {
                            "deeperObject": {
                                "foo": "foo",
                            },
                        },
                    },
                },
                "pending": [{"id": "0", "path": ["hero"]}],
                "hasNext": True,
            },
            {
                "pending": [
                    {"id": "1", "path": ["hero", "nestedObject"]},
                ],
                "incremental": [
                    {
                        "data": {"bar": "bar"},
                        "id": "0",
                        "subPath": ["nestedObject", "deeperObject"],
                    },
                ],
                "completed": [{"id": "0"}],
                "hasNext": True,
            },
            {
                "pending": [
                    {"id": "2", "path": ["hero", "nestedObject", "deeperObject"]}
                ],
                "incremental": [
                    {
                        "data": {"baz": "baz"},
                        "id": "1",
                        "subPath": ["deeperObject"],
                    },
                ],
                "completed": [{"id": "1"}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "data": {"bak": "bak"},
                        "id": "2",
                    },
                ],
                "completed": [{"id": "2"}],
                "hasNext": False,
            },
        ]

    async def deduplicates_fields_from_deferred_fragments_branches_same_level():
        """Deduplicates multiple fields from deferred fragments, branches same level

        Deduplicates multiple fields from deferred fragments from different branches
        occurring at the same level.
        """
        document = parse(
            """
            query {
              hero {
                nestedObject {
                  deeperObject {
                    ... @defer {
                      foo
                    }
                  }
                }
                ... @defer {
                  nestedObject {
                    deeperObject {
                      ... @defer {
                        foo
                        bar
                      }
                    }
                  }
                }
              }
            }
            """
        )
        result = await complete(
            document,
            {"hero": {"nestedObject": {"deeperObject": {"foo": "foo", "bar": "bar"}}}},
        )

        assert result == [
            {
                "data": {"hero": {"nestedObject": {"deeperObject": {}}}},
                "pending": [
                    {"id": "0", "path": ["hero", "nestedObject", "deeperObject"]},
                    {"id": "1", "path": ["hero", "nestedObject", "deeperObject"]},
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"data": {"foo": "foo"}, "id": "0"},
                    {"data": {"bar": "bar"}, "id": "1"},
                ],
                "completed": [{"id": "0"}, {"id": "1"}],
                "hasNext": False,
            },
        ]

    async def deduplicates_fields_from_deferred_fragments_branches_multi_levels():
        """Deduplicates fields from deferred fragments, branches at multiple levels

        Deduplicate fields with deferred fragments in different branches at multiple
        non-overlapping levels.
        """
        document = parse(
            """
            query {
              a {
                b {
                  c {
                    d
                  }
                  ... @defer {
                    e {
                      f
                    }
                  }
                }
              }
              ... @defer {
                a {
                  b {
                    e {
                      f
                    }
                  }
                }
                g {
                  h
                }
              }
            }
            """
        )
        result = await complete(
            document,
            {"a": {"b": {"c": {"d": "d"}, "e": {"f": "f"}}}, "g": {"h": "h"}},
        )

        assert result == [
            {
                "data": {"a": {"b": {"c": {"d": "d"}}}},
                "pending": [{"id": "0", "path": ["a", "b"]}, {"id": "1", "path": []}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"data": {"e": {"f": "f"}}, "id": "0"},
                    {"data": {"g": {"h": "h"}}, "id": "1"},
                ],
                "completed": [{"id": "0"}, {"id": "1"}],
                "hasNext": False,
            },
        ]

    async def correctly_bundles_varying_subfields_ignore_masked():
        """Correctly bundles varying subfields, ignoring masked fields.

        Correctly bundles varying subfields into incremental data records
        unique by defer combination,
        ignoring fields in a fragment masked by a parent defer.
        """
        document = parse(
            """
            query HeroNameQuery {
              ... @defer {
              hero {
                  id
                }
              }
              ... @defer {
                hero {
                  name
                  shouldBeWithNameDespiteAdditionalDefer: name
                  ... @defer {
                    shouldBeWithNameDespiteAdditionalDefer: name
                  }
                }
              }
            }
            """
        )
        result = await complete(document)

        assert result == [
            {
                "data": {},
                "pending": [
                    {"id": "0", "path": []},
                    {"id": "1", "path": []},
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "data": {"hero": {}},
                        "id": "0",
                    },
                    {
                        "data": {"id": "1"},
                        "id": "0",
                        "subPath": ["hero"],
                    },
                    {
                        "data": {
                            "name": "Luke",
                            "shouldBeWithNameDespiteAdditionalDefer": "Luke",
                        },
                        "id": "1",
                        "subPath": ["hero"],
                    },
                ],
                "completed": [{"id": "0"}, {"id": "1"}],
                "hasNext": False,
            },
        ]

    async def nulls_cross_defer_boundaries_null_first():
        """Nulls cross defer boundaries, null first"""
        document = parse(
            """
            query {
              ... @defer {
                a {
                  someField
                  b {
                    c {
                      nonNullErrorField
                    }
                  }
                }
              }
              a {
                ... @defer {
                  b {
                    c {
                      d
                    }
                  }
                }
              }
            }
            """
        )
        result = await complete(
            document,
            {"a": {"b": {"c": {"d": "d"}}, "someField": "someField"}},
        )

        assert result == [
            {
                "data": {"a": {}},
                "pending": [{"id": "0", "path": []}, {"id": "1", "path": ["a"]}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"data": {"b": {"c": {}}}, "id": "1"},
                    {"data": {"d": "d"}, "id": "1", "subPath": ["b", "c"]},
                ],
                "completed": [
                    {
                        "id": "0",
                        "errors": [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field c.nonNullErrorField.",
                                "locations": [{"line": 8, "column": 23}],
                                "path": ["a", "b", "c", "nonNullErrorField"],
                            },
                        ],
                    },
                    {"id": "1"},
                ],
                "hasNext": False,
            },
        ]

    async def handles_multiple_erroring_deferred_grouped_field_sets():
        """Handles multiple erroring deferred grouped field sets"""
        document = parse(
            """
            query {
              ... @defer {
                a {
                  b {
                    c {
                      someError: nonNullErrorField
                    }
                  }
                }
              }
              ... @defer {
                a {
                  b {
                    c {
                      anotherError: nonNullErrorField
                    }
                  }
                }
              }
            }
            """
        )
        result = await complete(
            document,
            {"a": {"b": {"c": {"nonNullErrorField": None}}}},
        )
        assert result == [
            {
                "data": {},
                "pending": [
                    {"id": "0", "path": []},
                    {"id": "1", "path": []},
                ],
                "hasNext": True,
            },
            {
                "completed": [
                    {
                        "id": "0",
                        "errors": [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field c.nonNullErrorField.",
                                "locations": [{"line": 7, "column": 23}],
                                "path": ["a", "b", "c", "someError"],
                            },
                        ],
                    },
                    {
                        "id": "1",
                        "errors": [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field c.nonNullErrorField.",
                                "locations": [{"line": 16, "column": 23}],
                                "path": ["a", "b", "c", "anotherError"],
                            },
                        ],
                    },
                ],
                "hasNext": False,
            },
        ]

    async def handles_multiple_erroring_deferred_grouped_field_sets_for_same_fragment():
        """Handles multiple erroring deferred grouped field sets for same fragment"""
        document = parse(
            """
            query {
              ... @defer {
                a {
                  b {
                    someC: c {
                      d: d
                    }
                    anotherC: c {
                      d: d
                    }
                  }
                }
              }
              ... @defer {
                a {
                  b {
                    someC: c {
                      someError: nonNullErrorField
                    }
                    anotherC: c {
                      anotherError: nonNullErrorField
                    }
                  }
                }
              }
            }
            """
        )
        result = await complete(
            document,
            {"a": {"b": {"c": {"d": "d", "nonNullErrorField": None}}}},
        )
        assert result == [
            {
                "data": {},
                "pending": [
                    {"id": "0", "path": []},
                    {"id": "1", "path": []},
                ],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "data": {"a": {"b": {"someC": {}, "anotherC": {}}}},
                        "id": "0",
                    },
                    {
                        "data": {"d": "d"},
                        "id": "0",
                        "subPath": ["a", "b", "someC"],
                    },
                    {
                        "data": {"d": "d"},
                        "id": "0",
                        "subPath": ["a", "b", "anotherC"],
                    },
                ],
                "completed": [
                    {
                        "id": "1",
                        "errors": [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field c.nonNullErrorField.",
                                "locations": [{"line": 19, "column": 23}],
                                "path": ["a", "b", "someC", "someError"],
                            },
                        ],
                    },
                    {"id": "0"},
                ],
                "hasNext": False,
            },
        ]

    async def nulls_cross_defer_boundaries_value_first():
        """Nulls cross defer boundaries, value first"""
        document = parse(
            """
            query {
              ... @defer {
                a {
                  b {
                    c {
                      d
                    }
                  }
                }
              }
              a {
                ... @defer {
                  someField
                  b {
                    c {
                      nonNullErrorField
                    }
                  }
                }
              }
            }
            """
        )
        result = await complete(
            document,
            {
                "a": {
                    "b": {"c": {"d": "d"}, "nonNullErrorFIeld": None},
                    "someField": "someField",
                }
            },
        )

        assert result == [
            {
                "data": {"a": {}},
                "pending": [{"id": "0", "path": []}, {"id": "1", "path": ["a"]}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"data": {"b": {"c": {}}}, "id": "1"},
                    {"data": {"d": "d"}, "id": "0", "subPath": ["a", "b", "c"]},
                ],
                "completed": [
                    {"id": "0"},
                    {
                        "id": "1",
                        "errors": [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field c.nonNullErrorField.",
                                "locations": [{"line": 17, "column": 23}],
                                "path": ["a", "b", "c", "nonNullErrorField"],
                            },
                        ],
                    },
                ],
                "hasNext": False,
            },
        ]

    async def filters_a_payload_with_a_null_that_cannot_be_merged():
        """Filters a payload with a null that cannot be merged"""
        document = parse(
            """
            query {
              ... @defer {
                a {
                  someField
                  b {
                    c {
                      nonNullErrorField
                    }
                  }
                }
              }
              a {
                ... @defer {
                  b {
                    c {
                      d
                    }
                  }
                }
              }
            }
            """
        )

        result = await complete(
            document,
            {
                "a": {
                    "b": {"c": {"d": "d", "nonNullErrorField": Resolvers.slow_null}},
                    "someField": "someField",
                }
            },
        )

        assert result == [
            {
                "data": {"a": {}},
                "pending": [{"id": "0", "path": []}, {"id": "1", "path": ["a"]}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"data": {"b": {"c": {}}}, "id": "1"},
                    {"data": {"d": "d"}, "id": "1", "subPath": ["b", "c"]},
                ],
                "completed": [{"id": "1"}],
                "hasNext": True,
            },
            {
                "completed": [
                    {
                        "id": "0",
                        "errors": [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field c.nonNullErrorField.",
                                "locations": [{"line": 8, "column": 23}],
                                "path": ["a", "b", "c", "nonNullErrorField"],
                            },
                        ],
                    },
                ],
                "hasNext": False,
            },
        ]

    async def cancels_deferred_fields_when_initial_result_exhibits_null_bubbling():
        """Cancels deferred fields when initial result exhibits null bubbling"""
        document = parse(
            """
            query {
              hero {
                nonNullName
              }
              ... @defer {
                hero {
                  name
                }
              }
            }
            """
        )
        result = await complete(
            document, {"hero": {**hero, "nonNullName": lambda _info: None}}
        )

        assert result == {
            "data": {"hero": None},
            "errors": [
                {
                    "message": "Cannot return null"
                    " for non-nullable field Hero.nonNullName.",
                    "locations": [{"line": 4, "column": 17}],
                    "path": ["hero", "nonNullName"],
                },
            ],
        }

    async def cancels_deferred_fields_when_deferred_result_exhibits_null_bubbling():
        """Cancels deferred fields when deferred result exhibits null bubbling"""
        document = parse(
            """
            query {
              ... @defer {
                hero {
                  nonNullName
                  name
                }
              }
            }
            """
        )
        result = await complete(
            document, {"hero": {**hero, "nonNullName": lambda _info: None}}
        )

        assert result == [
            {
                "data": {},
                "pending": [{"id": "0", "path": []}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "data": {"hero": None},
                        "id": "0",
                        "errors": [
                            {
                                "message": "Cannot return null"
                                " for non-nullable field Hero.nonNullName.",
                                "locations": [{"line": 5, "column": 19}],
                                "path": ["hero", "nonNullName"],
                            },
                        ],
                    },
                ],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def deduplicates_list_fields():
        """Deduplicates list fields"""
        document = parse(
            """
            query {
              hero {
                friends {
                  name
                }
                ... @defer {
                  friends {
                    name
                  }
                }
              }
            }
            """
        )

        result = await complete(document)

        assert result == {
            "data": {
                "hero": {
                    "friends": [{"name": "Han"}, {"name": "Leia"}, {"name": "C-3PO"}]
                }
            },
        }

    async def deduplicates_async_iterable_list_fields():
        """Deduplicates async iterable list fields"""
        document = parse(
            """
            query {
              hero {
                friends {
                  name
                }
                ... @defer {
                  friends {
                    name
                  }
                }
              }
            }
            """
        )

        result = await complete(
            document, {"hero": {**hero, "friends": Resolvers.first_friend}}
        )

        assert result == {"data": {"hero": {"friends": [{"name": "Han"}]}}}

    async def deduplicates_empty_async_iterable_list_fields():
        """Deduplicates empty async iterable list fields"""
        document = parse(
            """
            query {
              hero {
                friends {
                  name
                }
                ... @defer {
                  friends {
                    name
                  }
                }
              }
            }
            """
        )

        async def resolve_friends(_info):
            await sleep(0)
            for friend in []:  # type: ignore
                yield friend  # pragma: no cover

        result = await complete(
            document, {"hero": {**hero, "friends": resolve_friends}}
        )

        assert result == {"data": {"hero": {"friends": []}}}

    async def does_not_deduplicate_list_fields_with_non_overlapping_fields():
        """Does not deduplicate list fields with non-overlapping fields"""
        document = parse(
            """
            query {
              hero {
                friends {
                  name
                }
                ... @defer {
                  friends {
                    id
                  }
                }
              }
            }
            """
        )
        result = await complete(document)

        assert result == [
            {
                "data": {
                    "hero": {
                        "friends": [
                            {"name": "Han"},
                            {"name": "Leia"},
                            {"name": "C-3PO"},
                        ]
                    }
                },
                "pending": [{"id": "0", "path": ["hero"]}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"data": {"id": "2"}, "id": "0", "subPath": ["friends", 0]},
                    {"data": {"id": "3"}, "id": "0", "subPath": ["friends", 1]},
                    {"data": {"id": "4"}, "id": "0", "subPath": ["friends", 2]},
                ],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def deduplicates_list_fields_that_return_empty_lists():
        """Deduplicates list fields that return empty lists"""
        document = parse(
            """
            query {
              hero {
                friends {
                  name
                }
                ... @defer {
                  friends {
                    name
                  }
                }
              }
            }
            """
        )
        result = await complete(
            document, {"hero": {**hero, "friends": lambda _info: []}}
        )

        assert result == {"data": {"hero": {"friends": []}}}

    async def deduplicates_null_object_fields():
        """Deduplicates null object fields"""
        document = parse(
            """
            query {
              hero {
                nestedObject {
                  name
                }
                ... @defer {
                  nestedObject {
                    name
                  }
                }
              }
            }
            """
        )
        result = await complete(
            document, {"hero": {**hero, "nestedObject": lambda _info: None}}
        )

        assert result == {"data": {"hero": {"nestedObject": None}}}

    async def deduplicates_async_object_fields():
        """Deduplicates async object fields"""
        document = parse(
            """
            query {
              hero {
                nestedObject {
                  name
                }
                ... @defer {
                  nestedObject {
                    name
                  }
                }
              }
            }
            """
        )

        async def resolve_nested_object(_info):
            return {"name": "foo"}

        result = await complete(
            document, {"hero": {"nestedObject": resolve_nested_object}}
        )

        assert result == {"data": {"hero": {"nestedObject": {"name": "foo"}}}}

    async def handles_errors_thrown_in_deferred_fragments():
        """Handles errors thrown in deferred fragments"""
        document = parse(
            """
            query HeroNameQuery {
              hero {
                id
                ...NameFragment @defer
              }
            }
            fragment NameFragment on Hero {
              name
            }
            """
        )
        result = await complete(document, {"hero": {**hero, "name": Resolvers.bad}})

        assert result == [
            {
                "data": {"hero": {"id": "1"}},
                "pending": [{"id": "0", "path": ["hero"]}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {
                        "data": {"name": None},
                        "id": "0",
                        "errors": [
                            {
                                "message": "bad",
                                "locations": [{"line": 9, "column": 15}],
                                "path": ["hero", "name"],
                            }
                        ],
                    },
                ],
                "completed": [{"id": "0"}],
                "hasNext": False,
            },
        ]

    async def handles_non_nullable_errors_thrown_in_deferred_fragments():
        """Handles non-nullable errors thrown in deferred fragments"""
        document = parse(
            """
            query HeroNameQuery {
              hero {
                id
                ...NameFragment @defer
              }
            }
            fragment NameFragment on Hero {
              nonNullName
            }
            """
        )
        result = await complete(
            document, {"hero": {**hero, "nonNullName": Resolvers.null}}
        )

        assert result == [
            {
                "data": {"hero": {"id": "1"}},
                "pending": [{"id": "0", "path": ["hero"]}],
                "hasNext": True,
            },
            {
                "completed": [
                    {
                        "id": "0",
                        "errors": [
                            {
                                "message": "Cannot return null for non-nullable field"
                                " Hero.nonNullName.",
                                "locations": [{"line": 9, "column": 15}],
                                "path": ["hero", "nonNullName"],
                            }
                        ],
                    },
                ],
                "hasNext": False,
            },
        ]

    async def handles_non_nullable_errors_thrown_outside_deferred_fragments():
        """Handles non-nullable errors thrown outside deferred fragments"""
        document = parse(
            """
            query HeroNameQuery {
              hero {
                nonNullName
                ...NameFragment @defer
              }
            }
            fragment NameFragment on Hero {
              id
            }
            """
        )
        result = await complete(
            document, {"hero": {**hero, "nonNullName": Resolvers.null}}
        )

        assert result == {
            "data": {"hero": None},
            "errors": [
                {
                    "message": "Cannot return null for non-nullable field"
                    " Hero.nonNullName.",
                    "locations": [{"line": 4, "column": 17}],
                    "path": ["hero", "nonNullName"],
                }
            ],
        }

    async def handles_async_non_nullable_errors_thrown_in_deferred_fragments():
        """Handles async non-nullable errors thrown in deferred fragments"""
        document = parse(
            """
            query HeroNameQuery {
              hero {
                id
                ...NameFragment @defer
              }
            }
            fragment NameFragment on Hero {
              nonNullName
            }
            """
        )
        result = await complete(
            document, {"hero": {**hero, "nonNullName": Resolvers.null_async}}
        )

        assert result == [
            {
                "data": {"hero": {"id": "1"}},
                "pending": [{"id": "0", "path": ["hero"]}],
                "hasNext": True,
            },
            {
                "completed": [
                    {
                        "id": "0",
                        "errors": [
                            {
                                "message": "Cannot return null for non-nullable field"
                                " Hero.nonNullName.",
                                "locations": [{"line": 9, "column": 15}],
                                "path": ["hero", "nonNullName"],
                            }
                        ],
                    },
                ],
                "hasNext": False,
            },
        ]

    async def returns_payloads_in_correct_order():
        """Returns payloads in correct order"""
        document = parse(
            """
            query HeroNameQuery {
              hero {
                id
                ...NameFragment @defer
              }
            }
            fragment NameFragment on Hero {
              name
              friends {
                ...NestedFragment @defer
              }
            }
            fragment NestedFragment on Friend {
              name
            }
            """
        )
        result = await complete(document, {"hero": {**hero, "name": Resolvers.slow}})

        assert result == [
            {
                "data": {"hero": {"id": "1"}},
                "pending": [{"id": "0", "path": ["hero"]}],
                "hasNext": True,
            },
            {
                "pending": [
                    {"id": "1", "path": ["hero", "friends", 0]},
                    {"id": "2", "path": ["hero", "friends", 1]},
                    {"id": "3", "path": ["hero", "friends", 2]},
                ],
                "incremental": [
                    {"data": {"name": "slow", "friends": [{}, {}, {}]}, "id": "0"}
                ],
                "completed": [{"id": "0"}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"data": {"name": "Han"}, "id": "1"},
                    {"data": {"name": "Leia"}, "id": "2"},
                    {"data": {"name": "C-3PO"}, "id": "3"},
                ],
                "completed": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
                "hasNext": False,
            },
        ]

    async def returns_payloads_from_synchronous_data_in_correct_order():
        """Returns payloads from synchronous data in correct order"""
        document = parse(
            """
            query HeroNameQuery {
              hero {
                id
                ...NameFragment @defer
              }
            }
            fragment NameFragment on Hero {
              name
              friends {
                ...NestedFragment @defer
              }
            }
            fragment NestedFragment on Friend {
              name
            }
            """
        )
        result = await complete(document)

        assert result == [
            {
                "data": {"hero": {"id": "1"}},
                "pending": [{"id": "0", "path": ["hero"]}],
                "hasNext": True,
            },
            {
                "pending": [
                    {"id": "1", "path": ["hero", "friends", 0]},
                    {"id": "2", "path": ["hero", "friends", 1]},
                    {"id": "3", "path": ["hero", "friends", 2]},
                ],
                "incremental": [
                    {"data": {"name": "Luke", "friends": [{}, {}, {}]}, "id": "0"}
                ],
                "completed": [{"id": "0"}],
                "hasNext": True,
            },
            {
                "incremental": [
                    {"data": {"name": "Han"}, "id": "1"},
                    {"data": {"name": "Leia"}, "id": "2"},
                    {"data": {"name": "C-3PO"}, "id": "3"},
                ],
                "completed": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
                "hasNext": False,
            },
        ]

    async def filters_deferred_payloads_when_list_item_from_async_iterable_nulled():
        """Filters deferred payloads when list item from async iterable is nulled

        Filters deferred payloads when a list item returned by an async iterable
        is nulled.
        """
        document = parse(
            """
            query {
              hero {
                friends {
                  nonNullName
                  ...NameFragment @defer
                }
              }
            }
            fragment NameFragment on Friend {
              name
            }
            """
        )

        result = await complete(
            document, {"hero": {**hero, "friends": Resolvers.first_friend}}
        )

        assert result == {
            "data": {"hero": {"friends": [None]}},
            "errors": [
                {
                    "message": "Cannot return null for non-nullable field"
                    " Friend.nonNullName.",
                    "locations": [{"line": 5, "column": 19}],
                    "path": ["hero", "friends", 0, "nonNullName"],
                }
            ],
        }

    async def original_execute_function_throws_error_if_deferred_and_all_is_sync():
        """Original execute function throws error if deferred and all is sync

        Original execute function throws error if anything is deferred and everything
        else is sync.
        """
        document = parse(
            """
            query Deferred {
              ... @defer { hero { id } }
            }
            """
        )

        with pytest.raises(GraphQLError) as exc_info:
            await execute(schema, document, {})  # type: ignore

        assert str(exc_info.value) == (
            "Executing this GraphQL operation would unexpectedly produce"
            " multiple payloads (due to @defer or @stream directive)"
        )

    async def original_execute_function_throws_error_if_deferred_and_not_all_is_sync():
        """Original execute function throws error if deferred and not all is sync

        Original execute function resolves to error if anything is deferred and
        something else is async.
        """
        document = parse(
            """
            query Deferred {
              hero { name }
              ... @defer { hero { id } }
            }
            """
        )

        root_value = {"hero": {**hero, "name": Resolvers.slow}}
        with pytest.raises(GraphQLError) as exc_info:
            await execute(schema, document, root_value)  # type: ignore

        assert str(exc_info.value) == (
            "Executing this GraphQL operation would unexpectedly produce"
            " multiple payloads (due to @defer or @stream directive)"
        )
