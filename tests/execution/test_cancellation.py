"""Tests for cancelling execution via an abort signal."""

from __future__ import annotations

from asyncio import Event, Future, ensure_future, sleep
from collections.abc import AsyncIterator, Awaitable

import pytest

from graphql import (
    GraphQLField,
    GraphQLInterfaceType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
    build_schema,
)
from graphql.execution import (
    AbortedGraphQLExecutionError,
    ExperimentalIncrementalExecutionResults,
    execute,
    experimental_execute_incrementally,
    subscribe,
)
from graphql.language import parse
from graphql.pyutils import AbortController, AbortError, is_awaitable

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.filterwarnings("ignore:coroutine .* was never awaited:RuntimeWarning"),
    pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning"),
]


schema = build_schema(
    """
    type Todo {
      id: ID
      items: [String]
      author: User
    }

    type User {
      id: ID
      name: String
    }

    type Query {
      todo: Todo
      nonNullableTodo: Todo!
      blocker: String
      aborter: String
    }

    type Mutation {
      foo: String
      bar: String
    }

    type Subscription {
      foo: String
    }
    """
)


def must_not_be_called(*_args, **_kwargs):
    pytest.fail("Should not be called")  # pragma: no cover


def describe_abort_controller():
    def signal_is_not_aborted_initially():
        signal = AbortController().signal
        assert signal.aborted is False
        assert signal.reason is None

    def abort_sets_aborted_and_reason():
        controller = AbortController()
        controller.abort("Aborted")
        assert controller.signal.aborted is True
        assert controller.signal.reason == "Aborted"

    def abort_uses_a_default_reason_when_none_is_given():
        controller = AbortController()
        controller.abort()
        assert controller.signal.aborted is True
        assert isinstance(controller.signal.reason, AbortError)
        assert str(controller.signal.reason) == "This operation was aborted"

    def aborting_more_than_once_keeps_the_first_reason():
        controller = AbortController()
        controller.abort("first")
        controller.abort("second")
        assert controller.signal.reason == "first"

    async def signal_can_be_awaited_until_aborted():
        controller = AbortController()
        task = ensure_future(controller.signal.wait())
        await sleep(0)
        assert not task.done()
        controller.abort("Aborted")
        assert await task == "Aborted"


def describe_execute_cancellation():
    async def completes_the_execution_normally_when_never_aborted():
        abort_controller = AbortController()
        document = parse("{ todo { id } }")

        async def todo(_info):
            return {"id": "1"}

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"todo": todo},
        )
        assert isinstance(awaitable_result, Awaitable)

        result = await awaitable_result
        assert result == ({"todo": {"id": "1"}}, None)

    async def stops_the_execution_when_aborted_during_object_field_completion():
        abort_controller = AbortController()
        document = parse(
            """
      query {
        todo {
          id
          author {
            id
          }
        }
      }
    """
        )

        async def todo(_info):
            # never reached: a triggered abort signal cancels this resolver
            # before its body runs (unlike the eager resolvers in graphql-js)
            return {  # pragma: no cover
                "id": "1",
                "author": must_not_be_called,
            }

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"todo": todo},
        )
        assert isinstance(awaitable_result, Awaitable)

        abort_controller.abort()

        # Unlike graphql-js, which resolves to a partial response with a located
        # error, an aborted operation is rejected with an aborted execution error
        # that exposes the partial response.
        with pytest.raises(
            AbortedGraphQLExecutionError, match="This operation was aborted"
        ):
            await awaitable_result

    async def provides_access_to_the_abort_signal_within_resolvers():
        abort_controller = AbortController()
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
        seen_signal = None

        async def hanging_async_fn():
            await Future()  # will never resolve  # pragma: no cover

        # Contrary to JavaScript, where the abort signal is passed as an additional
        # argument to the resolvers, in GraphQL-Core it is available via the resolve
        # info, just like the context value.
        def resolve_id(info):
            nonlocal seen_signal
            seen_signal = info.abort_signal
            started.set()
            return hanging_async_fn()

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"todo": {"id": resolve_id}},
        )
        assert isinstance(awaitable_result, Awaitable)

        # Abort only once the resolver is in flight, so that it has had a chance to
        # access the abort signal via the resolve info.
        task = ensure_future(awaitable_result)
        await started.wait()
        abort_controller.abort()

        with pytest.raises(
            AbortedGraphQLExecutionError, match="This operation was aborted"
        ):
            await task

        assert seen_signal is abort_controller.signal

    async def stops_the_execution_when_aborted_during_completion_with_custom_error():
        abort_controller = AbortController()
        document = parse(
            """
      query {
        todo {
          id
          author {
            id
          }
        }
      }
    """
        )

        async def todo(_info):
            # never reached: a triggered abort signal cancels this resolver
            # before its body runs (unlike the eager resolvers in graphql-js)
            return {  # pragma: no cover
                "id": "1",
                "author": must_not_be_called,
            }

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"todo": todo},
        )
        assert isinstance(awaitable_result, Awaitable)

        custom_error = RuntimeError("Custom abort error")
        abort_controller.abort(custom_error)

        with pytest.raises(
            AbortedGraphQLExecutionError, match="Custom abort error"
        ) as exc_info:
            await awaitable_result
        assert exc_info.value.__cause__ is custom_error

    async def stops_the_execution_when_aborted_before_cancellation_is_wired():
        abort_controller = AbortController()
        document = parse(
            """
      query {
        blocker
      }
    """
        )

        custom_error = RuntimeError("Custom abort error")

        def blocker(_info):
            abort_controller.abort(custom_error)
            return Future()  # will never be resolved

        awaitable_result = execute(
            build_schema("type Query { blocker: String }"),
            document,
            abort_signal=abort_controller.signal,
            root_value={"blocker": blocker},
        )
        assert isinstance(awaitable_result, Awaitable)

        with pytest.raises(
            AbortedGraphQLExecutionError, match="Custom abort error"
        ) as exc_info:
            await awaitable_result
        assert exc_info.value.__cause__ is custom_error

    async def stops_the_execution_when_aborted_with_a_custom_string_reason():
        # gc3-specific: unlike graphql-js (which can reject with any value), a
        # non-exception abort reason is surfaced as an "unexpected error value".
        abort_controller = AbortController()
        document = parse("{ todo { id } }")
        abort_controller.abort("Custom abort error message")

        with pytest.raises(
            TypeError, match="Unexpected error value: 'Custom abort error message'"
        ):
            execute(
                schema,
                document,
                abort_signal=abort_controller.signal,
                root_value={"todo": must_not_be_called},
            )

    async def rejects_with_aborted_execution_error_while_initial_result_is_pending():
        abort_controller = AbortController()
        abort_reason = RuntimeError("Custom abort error")
        field_value: Future[str] = Future()
        field_started = Event()
        document = parse(
            """
      query {
        blocker
      }
    """
        )

        def blocker(_info):
            field_started.set()
            return field_value

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"blocker": blocker},
        )
        assert isinstance(awaitable_result, Awaitable)

        task = ensure_future(awaitable_result)
        await field_started.wait()
        abort_controller.abort(abort_reason)

        with pytest.raises(
            AbortedGraphQLExecutionError, match="Custom abort error"
        ) as exc_info:
            await task
        caught_error = exc_info.value
        assert caught_error.__cause__ is abort_reason

        aborted_result = caught_error.aborted_result
        assert is_awaitable(aborted_result)

        # Unlike graphql-js, where the partial result only settles once the pending
        # resolver does, the pending resolver is cancelled on abort, so the partial
        # result settles right away, with the abort reason as located field error
        # instead of a generic "Aborted!" error.
        result = await aborted_result
        assert result == (
            {"blocker": None},
            [
                {
                    "message": "Custom abort error",
                    "locations": [(3, 9)],
                    "path": ["blocker"],
                }
            ],
        )

    async def raises_with_a_completed_result_in_the_atypical_internal_abort_case():
        abort_controller = AbortController()
        abort_reason = RuntimeError("Custom abort error")
        document = parse(
            """
      query {
        aborter
      }
    """
        )

        def aborter(_info):
            abort_controller.abort(abort_reason)
            return "done"

        # The abort happens during otherwise synchronous execution, so the aborted
        # execution error is raised synchronously and exposes the already completed
        # result as a plain value.
        with pytest.raises(
            AbortedGraphQLExecutionError, match="Custom abort error"
        ) as exc_info:
            execute(
                schema,
                document,
                abort_signal=abort_controller.signal,
                root_value={"aborter": aborter},
            )
        caught_error = exc_info.value
        assert caught_error.__cause__ is abort_reason
        aborted_result = caught_error.aborted_result
        assert not is_awaitable(aborted_result)
        assert aborted_result == ({"aborter": "done"}, None)

    async def raises_the_aborted_execution_error_while_incremental_result_is_pending():
        abort_controller = AbortController()
        abort_reason = RuntimeError("Custom abort error")
        delayed_aborter: Future[str] = Future()
        field_started = Event()
        document = parse(
            """
      query {
        todo {
          id
          ... @defer {
            items
          }
        }
        aborter
      }
    """
        )

        def aborter(_info):
            field_started.set()
            return delayed_aborter

        execution_result = experimental_execute_incrementally(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={
                "aborter": aborter,
                "todo": {"id": "1", "items": ["a"]},
            },
        )
        assert isinstance(execution_result, Awaitable)

        task = ensure_future(execution_result)
        await field_started.wait()
        abort_controller.abort(abort_reason)

        with pytest.raises(
            AbortedGraphQLExecutionError, match="Custom abort error"
        ) as exc_info:
            await task
        caught_error = exc_info.value
        assert caught_error.__cause__ is abort_reason

        aborted_result = caught_error.aborted_result
        assert is_awaitable(aborted_result)
        result = await aborted_result
        assert isinstance(result, ExperimentalIncrementalExecutionResults)
        assert result.initial_result.data == {"todo": {"id": "1"}, "aborter": None}

        # closing the exposed subsequent results stream cleans up incremental work
        with pytest.raises(RuntimeError, match="Custom abort error"):
            await anext(result.subsequent_results)

    async def does_not_wrap_aborts_after_the_initial_result():
        abort_controller = AbortController()
        deferred_items: Future[list[str]] = Future()
        document = parse(
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
        )

        result = experimental_execute_incrementally(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"todo": {"id": "1", "items": lambda _info: deferred_items}},
            enable_early_execution=True,
        )
        assert isinstance(result, ExperimentalIncrementalExecutionResults)

        iterator = result.subsequent_results
        abort_controller.abort()

        with pytest.raises(AbortError, match="This operation was aborted") as exc_info:
            await anext(iterator)
        assert not isinstance(exc_info.value, AbortedGraphQLExecutionError)

    async def stops_the_execution_when_aborted_during_nested_object_completion():
        abort_controller = AbortController()
        document = parse(
            """
      query {
        todo {
          id
          author {
            id
          }
        }
      }
    """
        )

        async def author(_info):
            # never reached: the resolver is cancelled before its body runs
            return must_not_be_called  # pragma: no cover

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={
                "todo": {
                    "id": "1",
                    "author": author,
                }
            },
        )
        assert isinstance(awaitable_result, Awaitable)

        abort_controller.abort()

        with pytest.raises(
            AbortedGraphQLExecutionError, match="This operation was aborted"
        ):
            await awaitable_result

    async def stops_the_execution_when_aborted_despite_a_hanging_resolver():
        abort_controller = AbortController()
        document = parse(
            """
      query {
        todo {
          id
          author {
            id
          }
        }
      }
    """
        )

        started = Event()

        async def todo(_info):
            started.set()
            await Future()  # will never resolve

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"todo": todo},
        )
        assert isinstance(awaitable_result, Awaitable)

        # Abort only once the resolver is actually in flight, so that cancellation
        # must interrupt the hanging resolver instead of being caught up front.
        task = ensure_future(awaitable_result)
        await started.wait()
        abort_controller.abort()

        with pytest.raises(
            AbortedGraphQLExecutionError, match="This operation was aborted"
        ):
            await task

    async def stops_the_execution_when_aborted_despite_a_hanging_item():
        abort_controller = AbortController()
        document = parse(
            """
      query {
        todo {
          id
          items
        }
      }
    """
        )

        def todo(_info):
            return {
                "id": "1",
                "items": [Future()],  # will never resolve
            }

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"todo": todo},
        )
        assert isinstance(awaitable_result, Awaitable)

        abort_controller.abort()

        with pytest.raises(
            AbortedGraphQLExecutionError, match="This operation was aborted"
        ):
            await awaitable_result

    async def stops_the_execution_when_aborted_during_promised_list_item_completion():
        abort_controller = AbortController()
        document = parse(
            """
      query {
        todo {
          items
        }
      }
    """
        )

        item_future: Future[str] = Future()
        started = Event()

        def items(_info):
            started.set()
            return [item_future]

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"todo": {"items": items}},
        )
        assert isinstance(awaitable_result, Awaitable)

        task = ensure_future(awaitable_result)
        await started.wait()
        await sleep(0)
        abort_controller.abort()
        item_future.set_result("value")

        with pytest.raises(
            AbortedGraphQLExecutionError, match="This operation was aborted"
        ):
            await task

    async def stops_the_execution_when_aborted_despite_a_hanging_async_item():
        abort_controller = AbortController()
        document = parse(
            """
      query {
        todo {
          id
          items
        }
      }
    """
        )

        async def items(_info):
            # never reached: the iterator is cancelled before its body runs
            yield await Future()  # will never resolve  # pragma: no cover

        def todo(_info):
            return {"id": "1", "items": items}

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"todo": todo},
        )
        assert isinstance(awaitable_result, Awaitable)

        abort_controller.abort()

        with pytest.raises(
            AbortedGraphQLExecutionError, match="This operation was aborted"
        ):
            await awaitable_result

    async def stops_resolving_abstract_types_after_aborting():
        abort_controller = AbortController()

        resolve_type_future: Future[str] = Future()
        resolve_type_started = Event()

        def resolve_type(_value, _info, _type):
            resolve_type_started.set()
            return resolve_type_future

        node_interface = GraphQLInterfaceType(
            "Node",
            {"id": GraphQLField(GraphQLString)},
            resolve_type=resolve_type,
        )
        user_type = GraphQLObjectType(
            "User",
            {"id": GraphQLField(GraphQLString)},
            interfaces=[node_interface],
        )
        interface_schema = GraphQLSchema(
            query=GraphQLObjectType(
                "Query",
                {
                    "node": GraphQLField(
                        node_interface, resolve=lambda *_args: {"id": "1"}
                    )
                },
            ),
            types=[user_type],
        )

        document = parse("{ node { id } }")

        awaitable_result = execute(
            interface_schema, document, abort_signal=abort_controller.signal
        )
        assert isinstance(awaitable_result, Awaitable)

        task = ensure_future(awaitable_result)
        await resolve_type_started.wait()
        abort_controller.abort()
        resolve_type_future.set_result("User")

        with pytest.raises(
            AbortedGraphQLExecutionError, match="This operation was aborted"
        ):
            await task

    async def stops_resolving_is_type_of_after_aborting():
        abort_controller = AbortController()

        is_type_of_future: Future[bool] = Future()
        is_type_of_started = Event()

        def is_type_of(_value, _info):
            is_type_of_started.set()
            return is_type_of_future

        todo_type = GraphQLObjectType(
            "Todo",
            {"id": GraphQLField(GraphQLString)},
            is_type_of=is_type_of,
        )
        is_type_of_schema = GraphQLSchema(
            query=GraphQLObjectType(
                "Query",
                {"todo": GraphQLField(todo_type, resolve=lambda *_args: {"id": "1"})},
            )
        )

        document = parse("{ todo { id } }")

        awaitable_result = execute(
            is_type_of_schema, document, abort_signal=abort_controller.signal
        )
        assert isinstance(awaitable_result, Awaitable)

        task = ensure_future(awaitable_result)
        await is_type_of_started.wait()
        abort_controller.abort()
        is_type_of_future.set_result(True)

        with pytest.raises(
            AbortedGraphQLExecutionError, match="This operation was aborted"
        ):
            await task

    async def stops_the_execution_when_aborted_despite_a_hanging_iterator_no_close():
        # Like the hanging async item test, but the async iterator has no aclose()
        # method, so the cancellable wrapper has nothing to forward the close to.
        abort_controller = AbortController()
        document = parse(
            """
      query {
        todo {
          id
          items
        }
      }
    """
        )

        started = Event()
        hanging: Future[str] = Future()

        class Items:
            def __aiter__(self):
                return self

            def __anext__(self):
                started.set()
                return hanging  # will never resolve; the iterator has no aclose()

        def todo(_info):
            return {"id": "1", "items": Items()}

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"todo": todo},
        )
        assert isinstance(awaitable_result, Awaitable)

        # Abort only once the iterator is actually in flight, so the cancellable
        # wrapper closes a source that has no aclose() method.
        task = ensure_future(awaitable_result)
        await started.wait()
        abort_controller.abort()

        with pytest.raises(
            AbortedGraphQLExecutionError, match="This operation was aborted"
        ):
            await task

    async def stops_the_execution_when_aborted_with_proper_null_bubbling():
        abort_controller = AbortController()
        document = parse(
            """
      query {
        nonNullableTodo {
          id
          author {
            id
          }
        }
      }
    """
        )

        async def non_nullable_todo(_info):
            # never reached: a triggered abort signal cancels this resolver
            # before its body runs (unlike the eager resolvers in graphql-js)
            return {  # pragma: no cover
                "id": "1",
                "author": must_not_be_called,
            }

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"nonNullableTodo": non_nullable_todo},
        )
        assert isinstance(awaitable_result, Awaitable)

        abort_controller.abort()

        with pytest.raises(
            AbortedGraphQLExecutionError, match="This operation was aborted"
        ):
            await awaitable_result

    async def suppresses_sibling_errors_after_a_non_null_error_bubbles():
        boom_future: Future[str] = Future()
        side_future: Future[str] = Future()

        parent_type = GraphQLObjectType(
            "Parent",
            {
                "boom": GraphQLField(
                    GraphQLNonNull(GraphQLString), resolve=lambda *_args: boom_future
                ),
                "side": GraphQLField(GraphQLString, resolve=lambda *_args: side_future),
            },
        )
        bubble_schema = GraphQLSchema(
            query=GraphQLObjectType(
                "Query",
                {
                    "parent": GraphQLField(parent_type, resolve=lambda *_args: {}),
                    "other": GraphQLField(GraphQLString, resolve=lambda *_args: "ok"),
                },
            )
        )

        document = parse("{ parent { boom side } other }")
        awaitable_result = execute(bubble_schema, document)
        assert isinstance(awaitable_result, Awaitable)
        task = ensure_future(awaitable_result)

        boom_future.set_exception(RuntimeError("boom"))
        # wait for boom to bubble up
        for _ in range(3):
            await sleep(0)
        side_future.set_exception(RuntimeError("side"))

        result = await task
        assert result == (
            {"parent": None, "other": "ok"},
            [
                {
                    "message": "boom",
                    "locations": [(1, 12)],
                    "path": ["parent", "boom"],
                }
            ],
        )

    async def stops_late_sibling_object_completion_after_non_null_bubbling():
        boom_future: Future[str] = Future()
        side_event = Event()
        late_value_calls = 0

        def late_value(_info):  # pragma: no cover
            nonlocal late_value_calls
            late_value_calls += 1
            return "late value"

        async def side(*_args):
            # never resumed: completion of the pending sibling is cancelled
            # when the non-null error bubbles up
            await side_event.wait()
            return {"value": late_value}  # pragma: no cover

        side_type = GraphQLObjectType(
            "LateSide", {"value": GraphQLField(GraphQLString)}
        )
        parent_type = GraphQLObjectType(
            "LateParent",
            {
                "boom": GraphQLField(
                    GraphQLNonNull(GraphQLString), resolve=lambda *_args: boom_future
                ),
                "side": GraphQLField(side_type, resolve=side),
            },
        )
        bubble_schema = GraphQLSchema(
            query=GraphQLObjectType(
                "LateQuery",
                {
                    "parent": GraphQLField(parent_type, resolve=lambda *_args: {}),
                    "other": GraphQLField(GraphQLString, resolve=lambda *_args: "ok"),
                },
            )
        )

        document = parse("{ parent { boom side { value } } other }")
        awaitable_result = execute(bubble_schema, document)
        assert isinstance(awaitable_result, Awaitable)
        task = ensure_future(awaitable_result)

        boom_future.set_exception(RuntimeError("boom"))
        # wait for boom to bubble up
        for _ in range(3):
            await sleep(0)
        result = await task

        side_event.set()
        for _ in range(2):
            await sleep(0)
        assert late_value_calls == 0

        assert result == (
            {"parent": None, "other": "ok"},
            [
                {
                    "message": "boom",
                    "locations": [(1, 12)],
                    "path": ["parent", "boom"],
                }
            ],
        )

    async def stops_the_execution_when_aborted_mid_mutation():
        abort_controller = AbortController()
        document = parse(
            """
      mutation {
        foo
        bar
      }
    """
        )

        async def foo(_info):
            return "baz"

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"foo": foo, "bar": must_not_be_called},
        )
        assert isinstance(awaitable_result, Awaitable)

        # Let the first field resolve before aborting, so that the abort is only
        # observed when serially moving on to the second field (mirrors the
        # ``resolveOnNextTick`` calls in the GraphQL.js test).
        task = ensure_future(awaitable_result)
        for _ in range(3):
            await sleep(0)

        abort_controller.abort()

        with pytest.raises(
            AbortedGraphQLExecutionError, match="This operation was aborted"
        ):
            await task

    async def stops_the_execution_when_aborted_pre_execute():
        abort_controller = AbortController()
        document = parse(
            """
      query {
        todo {
          id
          author {
            id
          }
        }
      }
    """
        )
        abort_controller.abort()

        # The operation is rejected synchronously, before any resolver runs.
        with pytest.raises(AbortError, match="This operation was aborted"):
            execute(
                schema,
                document,
                abort_signal=abort_controller.signal,
                root_value={"todo": must_not_be_called},
            )

    async def stops_the_execution_when_aborted_prior_to_return_of_subscription():
        abort_controller = AbortController()
        document = parse(
            """
      subscription {
        foo
      }
    """
        )

        def foo(_info):
            return Future()  # will never resolve

        subscription_promise = subscribe(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"foo": foo},
        )
        assert isinstance(subscription_promise, Awaitable)

        abort_controller.abort()

        result = await subscription_promise

        assert result == (
            None,
            [
                {
                    "message": "This operation was aborted",
                    "locations": [(3, 9)],
                    "path": ["foo"],
                }
            ],
        )

    async def successfully_wraps_the_subscription():
        abort_controller = AbortController()
        document = parse(
            """
      subscription {
        foo
      }
    """
        )

        async def foo():
            yield {"foo": "foo"}

        async def resolve_foo(_info):
            return foo()

        subscription_promise = subscribe(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"foo": resolve_foo},
        )
        assert isinstance(subscription_promise, Awaitable)
        subscription = await subscription_promise

        assert isinstance(subscription, AsyncIterator)

        assert await anext(subscription) == ({"foo": "foo"}, None)

        with pytest.raises(StopAsyncIteration):
            await anext(subscription)

    async def stops_the_execution_when_aborted_during_subscription():
        abort_controller = AbortController()
        document = parse(
            """
      subscription {
        foo
      }
    """
        )

        async def foo():
            yield {"foo": "foo"}

        subscription = subscribe(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"foo": foo()},
        )

        assert isinstance(subscription, AsyncIterator)

        assert await anext(subscription) == ({"foo": "foo"}, None)

        abort_controller.abort()

        with pytest.raises(AbortError, match="This operation was aborted"):
            await anext(subscription)

    async def stops_the_execution_when_aborted_during_async_returned_subscription():
        abort_controller = AbortController()
        document = parse(
            """
      subscription {
        foo
      }
    """
        )

        async def foo():
            yield {"foo": "foo"}

        async def resolve_foo(_info):
            return foo()

        subscription_promise = subscribe(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"foo": resolve_foo},
        )
        assert isinstance(subscription_promise, Awaitable)
        subscription = await subscription_promise

        assert isinstance(subscription, AsyncIterator)

        assert await anext(subscription) == ({"foo": "foo"}, None)

        abort_controller.abort()

        with pytest.raises(AbortError, match="This operation was aborted"):
            await anext(subscription)

    async def ignores_async_iterator_return_errors_after_aborting_list_completion():
        abort_controller = AbortController()
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
        next_started = Event()
        return_called = False

        class AsyncIter:
            def __aiter__(self):
                return self

            def __anext__(self):
                next_started.set()
                return next_returned

            async def aclose(self):
                nonlocal return_called
                return_called = True
                raise RuntimeError("Return failed")

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"todo": {"items": AsyncIter()}},
        )
        assert isinstance(awaitable_result, Awaitable)

        task = ensure_future(awaitable_result)
        await next_started.wait()
        abort_controller.abort()
        next_returned.set_result("value")

        with pytest.raises(
            AbortedGraphQLExecutionError, match="This operation was aborted"
        ) as exc_info:
            await task
        # wait for the partial result so that the cleanup has settled
        await exc_info.value.aborted_result
        assert return_called is True

    async def ignores_async_iterator_return_rejections_after_aborting_list_completion():
        abort_controller = AbortController()
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
        next_started = Event()
        return_called = False

        class AsyncIter:
            def __aiter__(self):
                return self

            def __anext__(self):
                next_started.set()
                return next_returned

            async def aclose(self):
                nonlocal return_called
                return_called = True
                raise RuntimeError("Return failed")

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"todo": {"items": AsyncIter()}},
        )
        assert isinstance(awaitable_result, Awaitable)

        task = ensure_future(awaitable_result)
        await next_started.wait()
        abort_controller.abort()
        next_returned.set_result("value")

        with pytest.raises(
            AbortedGraphQLExecutionError, match="This operation was aborted"
        ) as exc_info:
            await task
        # wait for the partial result so that the cleanup has settled
        await exc_info.value.aborted_result
        assert return_called is True
