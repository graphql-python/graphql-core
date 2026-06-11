"""Tests for execution hooks."""

from __future__ import annotations

from asyncio import Event, Future, ensure_future, sleep
from collections.abc import Awaitable

import pytest

from graphql.execution import (
    AsyncWorkFinishedInfo,
    ExecutionHooks,
    ExecutionResult,
    Executor,
    ExperimentalIncrementalExecutionResults,
    execute,
    experimental_execute_incrementally,
)
from graphql.language import parse
from graphql.pyutils import AbortController, AbortError, is_awaitable
from graphql.type import (
    GraphQLField,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)
from graphql.utilities import build_schema

pytestmark = pytest.mark.anyio


execute_hook_schema = GraphQLSchema(
    query=GraphQLObjectType(
        "Query",
        {"test": GraphQLField(GraphQLString, resolve=lambda *_args: "ok")},
    )
)

cancellation_hook_schema = build_schema(
    """
    type Todo {
      id: ID
      items: [String]
    }

    type Query {
      todo: Todo
    }
    """
)


def execute_and_wait_for_async_work_finished(schema, document, root_value=None):
    """Execute and resolve only after the async work finished hook has fired."""
    hook_has_fired = Event()

    def async_work_finished(_info):
        hook_has_fired.set()

    result = execute(
        schema,
        document,
        root_value,
        hooks=ExecutionHooks(async_work_finished=async_work_finished),
    )

    if hook_has_fired.is_set():
        return result

    async def wait_for_hook():
        await hook_has_fired.wait()
        return await result if is_awaitable(result) else result

    return wait_for_hook()


def describe_execute_hooks():
    def ignores_errors_raised_by_hooks():
        calls: list[str] = []

        def async_work_finished(_info):
            calls.append("asyncWork")
            raise RuntimeError("asyncWorkFinished failed")

        result = execute(
            execute_hook_schema,
            parse("{ test }"),
            hooks=ExecutionHooks(async_work_finished=async_work_finished),
        )

        assert result == ({"test": "ok"}, None)
        assert calls == ["asyncWork"]

    def runs_post_execution_hooks_synchronously_when_no_async_work_is_tracked():
        calls: list[str] = []

        def async_work_finished(info):
            assert isinstance(info, AsyncWorkFinishedInfo)
            assert isinstance(info.executor, Executor)
            calls.append("asyncWork")

        result = execute(
            execute_hook_schema,
            parse("{ test }"),
            hooks=ExecutionHooks(async_work_finished=async_work_finished),
        )

        assert result == ({"test": "ok"}, None)
        assert calls == ["asyncWork"]

    def accepts_hooks_without_async_work_finished():
        result = execute(execute_hook_schema, parse("{ test }"), hooks=ExecutionHooks())

        assert result == ({"test": "ok"}, None)

    async def runs_post_execution_hooks_for_asynchronous_execution():
        resolved_value: Future[str] = Future()
        calls: list[str] = []
        hooks_finished = Event()

        async_schema = GraphQLSchema(
            query=GraphQLObjectType(
                "Query",
                {
                    "test": GraphQLField(
                        GraphQLString, resolve=lambda *_args: resolved_value
                    )
                },
            )
        )

        def async_work_finished(_info):
            calls.append("asyncWork")
            hooks_finished.set()

        awaitable_result = execute(
            async_schema,
            parse("{ test }"),
            hooks=ExecutionHooks(async_work_finished=async_work_finished),
        )
        assert isinstance(awaitable_result, Awaitable)

        assert calls == []
        resolved_value.set_result("ok")

        result = await awaitable_result
        assert result == ({"test": "ok"}, None)
        await hooks_finished.wait()
        assert calls == ["asyncWork"]

    async def gather_helper_cancels_pending_work_when_one_of_the_values_fails():
        pending_cleanup: Future[str] = Future()
        calls: list[str] = []

        async def fail():
            raise RuntimeError("bad")

        def resolve_test(_source, info):
            return info.async_helpers.gather([fail(), pending_cleanup])

        gathering_schema = GraphQLSchema(
            query=GraphQLObjectType(
                "Query",
                {"test": GraphQLField(GraphQLString, resolve=resolve_test)},
            )
        )

        def async_work_finished(_info):
            calls.append("asyncWork")

        awaitable_result = execute(
            gathering_schema,
            parse("{ test }"),
            hooks=ExecutionHooks(async_work_finished=async_work_finished),
        )
        assert isinstance(awaitable_result, Awaitable)

        result = await awaitable_result
        assert result.data == {"test": None}
        assert result.errors
        assert result.errors[0].message == "bad"

        # Unlike the JavaScript promiseAll helper, which tracks the still pending
        # values when one of them fails, the gather helper cancels and settles
        # them before the error is propagated, so the hook needed not wait.
        assert pending_cleanup.cancelled()
        assert calls == ["asyncWork"]

    async def waits_for_track_helper_usage_before_async_work_finished():
        pending_cleanup: Future[str] = Future()
        async_work_finished = Event()

        def resolve_test(_source, info):
            info.async_helpers.track([pending_cleanup])
            return "ok"

        tracking_schema = GraphQLSchema(
            query=GraphQLObjectType(
                "Query",
                {"test": GraphQLField(GraphQLString, resolve=resolve_test)},
            )
        )

        result = execute(
            tracking_schema,
            parse("{ test }"),
            hooks=ExecutionHooks(
                async_work_finished=lambda _info: async_work_finished.set()
            ),
        )

        assert result == ({"test": "ok"}, None)

        await sleep(0)
        assert not async_work_finished.is_set()

        pending_cleanup.set_result("done")
        await async_work_finished.wait()

    async def keeps_waiting_when_tracked_work_is_followed_by_more_tracked_work():
        first_cleanup: Future[str] = Future()
        second_cleanup: Future[str] = Future()
        async_work_finished = Event()

        def resolve_test(_source, info):
            async def track_second_cleanup():
                await first_cleanup
                info.async_helpers.track([second_cleanup])

            info.async_helpers.track([track_second_cleanup()])
            return "ok"

        tracking_schema = GraphQLSchema(
            query=GraphQLObjectType(
                "Query",
                {"test": GraphQLField(GraphQLString, resolve=resolve_test)},
            )
        )

        result = execute(
            tracking_schema,
            parse("{ test }"),
            hooks=ExecutionHooks(
                async_work_finished=lambda _info: async_work_finished.set()
            ),
        )

        assert result == ({"test": "ok"}, None)

        first_cleanup.set_result("done")
        await sleep(0)
        await sleep(0)
        assert not async_work_finished.is_set()

        second_cleanup.set_result("done")
        await async_work_finished.wait()

    def wrapper_returns_synchronously_when_hook_fires_during_execute():
        wrapped_result = execute_and_wait_for_async_work_finished(
            execute_hook_schema, parse("{ test }")
        )

        assert not is_awaitable(wrapped_result)
        assert wrapped_result == ({"test": "ok"}, None)

    async def wrapper_resolves_after_async_work_finished_for_tracked_side_effects():
        pending_cleanup: Future[str] = Future()

        def resolve_test(_source, info):
            info.async_helpers.track([pending_cleanup])
            return "ok"

        tracking_schema = GraphQLSchema(
            query=GraphQLObjectType(
                "Query",
                {"test": GraphQLField(GraphQLString, resolve=resolve_test)},
            )
        )

        wrapped_result = execute_and_wait_for_async_work_finished(
            tracking_schema, parse("{ test }")
        )
        assert is_awaitable(wrapped_result)

        task = ensure_future(wrapped_result)
        await sleep(0)
        assert not task.done()

        pending_cleanup.set_result("done")
        result = await task
        assert result == ({"test": "ok"}, None)

    def runs_post_execution_hooks_when_sync_errors_bubble_to_the_root():
        calls: list[str] = []

        def resolve_error(*_args):
            raise RuntimeError("Oops")

        erroring_schema = GraphQLSchema(
            query=GraphQLObjectType(
                "Query",
                {
                    "test": GraphQLField(
                        GraphQLNonNull(GraphQLString), resolve=resolve_error
                    )
                },
            )
        )

        result = execute(
            erroring_schema,
            parse("{ test }"),
            hooks=ExecutionHooks(
                async_work_finished=lambda _info: calls.append("asyncWork")
            ),
        )

        assert isinstance(result, ExecutionResult)
        assert result.data is None
        assert result.errors
        assert result.errors[0].message == "Oops"
        assert calls == ["asyncWork"]

    async def runs_post_execution_hooks_when_async_errors_bubble_to_the_root():
        calls: list[str] = []

        async def resolve_error(*_args):
            raise RuntimeError("Oops")

        erroring_schema = GraphQLSchema(
            query=GraphQLObjectType(
                "Query",
                {
                    "test": GraphQLField(
                        GraphQLNonNull(GraphQLString), resolve=resolve_error
                    )
                },
            )
        )

        awaitable_result = execute(
            erroring_schema,
            parse("{ test }"),
            hooks=ExecutionHooks(
                async_work_finished=lambda _info: calls.append("asyncWork")
            ),
        )
        assert isinstance(awaitable_result, Awaitable)

        result = await awaitable_result
        assert result.data is None
        assert result.errors
        assert result.errors[0].message == "Oops"
        assert calls == ["asyncWork"]

    def runs_post_execution_hooks_when_aborted_before_execution_starts():
        abort_controller = AbortController()
        abort_controller.abort()
        calls: list[str] = []

        with pytest.raises(AbortError, match="This operation was aborted"):
            execute(
                execute_hook_schema,
                parse("{ test }"),
                abort_signal=abort_controller.signal,
                hooks=ExecutionHooks(
                    async_work_finished=lambda _info: calls.append("asyncWork")
                ),
            )

        assert calls == ["asyncWork"]

    async def runs_post_execution_hooks_for_aborted_execution():
        abort_controller = AbortController()
        pending_cleanup: Future[str] = Future()
        async_work_finished = Event()
        calls: list[str] = []
        document = parse(
            """
            query {
              todo {
                id
              }
            }
            """
        )

        started = Event()

        async def hanging():
            started.set()
            await Future()

        def todo(info):
            # JavaScript uses the promiseAll helper here; in GraphQL-core pending
            # work is cancelled on abort, so cleanup that must keep running after
            # the abort needs to be tracked instead.
            info.async_helpers.track([pending_cleanup])
            return hanging()

        def async_work_finished_hook(_info):
            calls.append("asyncWork")
            async_work_finished.set()

        awaitable_result = execute(
            cancellation_hook_schema,
            document,
            root_value={"todo": todo},
            abort_signal=abort_controller.signal,
            hooks=ExecutionHooks(async_work_finished=async_work_finished_hook),
        )
        assert isinstance(awaitable_result, Awaitable)

        task = ensure_future(awaitable_result)
        await started.wait()  # let the execution start before aborting
        abort_controller.abort()
        with pytest.raises(AbortError, match="This operation was aborted"):
            await task
        assert calls == []

        pending_cleanup.set_result("done")
        await async_work_finished.wait()
        assert calls == ["asyncWork"]

    async def fires_async_work_finished_after_async_iterator_return_cleanup():
        abort_controller = AbortController()
        async_work_finished = Event()
        document = parse(
            """
            query {
              todo {
                items
              }
            }
            """
        )

        next_returned: Future[str] = Future()
        return_finished: Future[None] = Future()
        next_started = Event()
        return_started = Event()

        class AsyncIter:
            def __aiter__(self):
                return self

            def __anext__(self):
                next_started.set()
                return next_returned

            async def aclose(self):
                return_started.set()
                await return_finished

        awaitable_result = execute(
            cancellation_hook_schema,
            document,
            root_value={"todo": {"items": AsyncIter()}},
            abort_signal=abort_controller.signal,
            hooks=ExecutionHooks(
                async_work_finished=lambda _info: async_work_finished.set()
            ),
        )
        assert isinstance(awaitable_result, Awaitable)

        task = ensure_future(awaitable_result)
        await next_started.wait()
        abort_controller.abort()
        next_returned.set_result("value")

        await return_started.wait()

        with pytest.raises(AbortError, match="This operation was aborted"):
            await task

        # Unlike JavaScript, where the result rejects immediately and the hook
        # waits for the still running cleanup, the pending cleanup is cancelled
        # and settled before the result rejects, so the hook has already fired.
        assert return_finished.cancelled()
        assert async_work_finished.is_set()

    async def fires_async_work_finished_after_all_incremental_payloads_are_delivered():
        deferred_items: Future[list[str]] = Future()
        async_work_finished = Event()
        hook_calls = 0

        def async_work_finished_hook(_info):
            nonlocal hook_calls
            hook_calls += 1
            async_work_finished.set()

        result = experimental_execute_incrementally(
            cancellation_hook_schema,
            parse(
                """
                query {
                  todo {
                    id
                    ... @defer {
                      items
                    }
                  }
                }
                """
            ),
            root_value={"todo": {"id": "1", "items": lambda _info: deferred_items}},
            enable_early_execution=True,
            hooks=ExecutionHooks(async_work_finished=async_work_finished_hook),
        )
        assert isinstance(result, ExperimentalIncrementalExecutionResults)
        assert result.initial_result.has_next is True

        iterator = result.subsequent_results
        next_task = ensure_future(anext(iterator))
        await sleep(0)
        assert not next_task.done()
        assert not async_work_finished.is_set()

        deferred_items.set_result(["a"])
        next_result = await next_task
        assert next_result.has_next is False

        # exhaust the subsequent results so that the publisher finishes
        with pytest.raises(StopAsyncIteration):
            await anext(iterator)

        await async_work_finished.wait()
        assert hook_calls == 1
