"""Unit tests for the incremental executor.

These tests cover asyncio-specific seams of the incremental executor that
are not deterministically reachable via the defer/stream test suites,
especially the asynchronous cleanup paths.
"""

from __future__ import annotations

from asyncio import Event, sleep
from typing import TYPE_CHECKING, Any, cast

import pytest

from graphql import (
    GraphQLDeferDirective,
    GraphQLField,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
    parse,
    specified_directives,
)
from graphql.execution import experimental_execute_incrementally
from graphql.execution.incremental import (
    Computation,
    ExecutionGroup,
    IncrementalExecutor,
    ItemStream,
    StreamItemQueue,
    WorkResult,
)
from graphql.pyutils import RefSet, is_awaitable

if TYPE_CHECKING:
    from graphql.pyutils import Path

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


obj_type = GraphQLObjectType("Obj", {"echo": GraphQLField(GraphQLString)})

schema = GraphQLSchema(
    GraphQLObjectType("Query", {"echo": GraphQLField(GraphQLString)}),
    subscription=GraphQLObjectType(
        "Subscription",
        {
            "echo": GraphQLField(GraphQLString),
            "obj": GraphQLField(obj_type),
        },
    ),
    directives=[*specified_directives, GraphQLDeferDirective],
)


def build_executor(source: str) -> IncrementalExecutor:
    executor = IncrementalExecutor.build(schema, parse(source))
    assert isinstance(executor, IncrementalExecutor)
    return executor


def parked_stream_queue() -> StreamItemQueue:
    async def produce(_queue: StreamItemQueue) -> None:
        await Event().wait()  # park forever

    return StreamItemQueue(produce, eager=True)


def parked_execution_group(executor: IncrementalExecutor) -> ExecutionGroup:
    async def parked_work() -> WorkResult:
        await Event().wait()  # park forever
        return WorkResult(None)  # pragma: no cover

    async def cleanup(_reason: BaseException | None) -> None:
        await sleep(0)

    computation: Computation[WorkResult] = Computation(parked_work, cleanup)
    executor.prime_now(computation)
    return ExecutionGroup([], computation, None)


def describe_incremental_executor():
    def rejects_defer_on_subscription_root_fields():
        result = experimental_execute_incrementally(
            schema, parse("subscription { ... @defer { echo } }")
        )
        assert result == (
            None,
            [
                {
                    "message": "`@defer` directive not supported on subscription"
                    " operations. Disable `@defer` by setting the `if` argument"
                    " to `false`.",
                }
            ],
        )

    def rejects_defer_on_subscription_subfields():
        result = experimental_execute_incrementally(
            schema,
            parse("subscription { obj { ... @defer { echo } } }"),
            {"obj": {"echo": "hello"}},
        )
        assert result == (
            {"obj": None},
            [
                {
                    "message": "`@defer` directive not supported on subscription"
                    " operations. Disable `@defer` by setting the `if` argument"
                    " to `false`.",
                    "locations": [(1, 16)],
                    "path": ["obj"],
                }
            ],
        )

    async def aborting_incremental_work_awaits_asynchronous_cleanup():
        executor = build_executor("{ echo }")
        group = parked_execution_group(executor)
        executor.tasks.append(group)
        stream_queue = parked_stream_queue()
        await sleep(0)  # let the stream producer start
        executor.streams.append(ItemStream(cast("Path", None), None, stream_queue, 0))

        abort_result = executor.abort()
        assert is_awaitable(abort_result)
        await abort_result

    async def aborting_in_background_settles_asynchronous_cleanup():
        executor = build_executor("{ echo }")
        executor.tasks.append(parked_execution_group(executor))
        executor.abort_in_background()
        assert executor.background_futures
        await executor.cancel_incremental_work()

    async def cancelling_incremental_work_awaits_abort_cleanup():
        executor = build_executor("{ echo }")
        executor.tasks.append(parked_execution_group(executor))
        await executor.cancel_incremental_work()

    def memoizes_sub_execution_plans_per_defer_usage_set():
        executor = build_executor("{ echo }")
        defer_usage_set_1: RefSet = RefSet()
        defer_usage_set_2: RefSet = RefSet()
        sub_executor_1 = executor.create_sub_executor(defer_usage_set_1)
        sub_executor_2 = executor.create_sub_executor(defer_usage_set_2)
        grouped_field_set: dict = {}
        plan_1 = sub_executor_1.build_sub_execution_plan(grouped_field_set)
        # planned again under a different defer usage set
        plan_2 = sub_executor_2.build_sub_execution_plan(grouped_field_set)
        assert plan_2 is not plan_1
        # memoized for the same defer usage set
        assert sub_executor_1.build_sub_execution_plan(grouped_field_set) is plan_1
        assert sub_executor_2.build_sub_execution_plan(grouped_field_set) is plan_2

    async def failing_execution_group_awaits_asynchronous_abort_cleanup():
        executor = build_executor("{ echo }")
        sub_executor = executor.create_sub_executor()
        sub_executor.tasks.append(parked_execution_group(sub_executor))

        async def failing_fields() -> dict:
            raise RuntimeError("execution group failed")

        sub_executor.execute_fields = (  # type: ignore[method-assign]
            lambda *_args: failing_fields()
        )
        result = sub_executor.execute_execution_group(
            [],
            cast("Any", schema.query_type),
            None,
            None,
            {},
            cast("Any", None),
        )
        assert is_awaitable(result)
        with pytest.raises(RuntimeError, match="execution group failed"):
            await result

    async def failing_awaitable_stream_item_awaits_asynchronous_abort_cleanup():
        executor = build_executor("{ echo }")
        sub_executor = executor.create_sub_executor()
        sub_executor.tasks.append(parked_execution_group(sub_executor))

        async def failing_value() -> None:
            raise RuntimeError("stream item failed")

        async def failing_item() -> None:
            # never awaited, disposed via close() below
            raise RuntimeError("stream item failed")  # pragma: no cover

        sub_executor.complete_awaitable_value = (  # type: ignore[method-assign]
            lambda *_args: failing_value()
        )
        item = failing_item()
        result = sub_executor.complete_stream_item(
            cast("Path", None),
            item,
            [],
            cast("Any", None),
            cast("Any", None),
        )
        assert is_awaitable(result)
        with pytest.raises(RuntimeError, match="stream item failed"):
            await result
        item.close()  # dispose of the item that was never awaited

    async def failing_stream_item_completion_awaits_asynchronous_abort_cleanup():
        executor = build_executor("{ echo }")
        sub_executor = executor.create_sub_executor()
        sub_executor.tasks.append(parked_execution_group(sub_executor))

        async def failing_completion() -> None:
            raise RuntimeError("completion failed")

        def raise_error(raw_error: Exception, *_args: object) -> None:
            raise raw_error

        sub_executor.complete_value = (  # type: ignore[method-assign]
            lambda *_args: failing_completion()
        )
        sub_executor.handle_field_error = cast(  # type: ignore[method-assign]
            "Any", raise_error
        )
        result = sub_executor.complete_stream_item(
            cast("Path", None),
            "item",
            [],
            cast("Any", None),
            cast("Any", None),
        )
        assert is_awaitable(result)
        with pytest.raises(RuntimeError, match="completion failed"):
            await result
