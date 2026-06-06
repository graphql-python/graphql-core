"""Tests for cancelling execution via an abort signal."""

from __future__ import annotations

from asyncio import Event, Future, ensure_future, sleep
from collections.abc import AsyncIterator, Awaitable

import pytest

from graphql import build_schema
from graphql.execution import execute, subscribe
from graphql.language import parse
from graphql.pyutils import AbortController, AbortError

pytestmark = pytest.mark.anyio


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

        result = await awaitable_result

        assert result.errors is not None
        assert isinstance(result.errors[0].original_error, AbortError)
        assert result == (
            {"todo": None},
            [
                {
                    "message": "This operation was aborted",
                    "locations": [(3, 9)],
                    "path": ["todo"],
                }
            ],
        )

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

        async def cancellable_async_fn(abort_signal):
            # never reached: the resolver is cancelled before its body runs
            raise await abort_signal.wait()  # pragma: no cover

        # Contrary to JavaScript, where the abort signal is passed as an additional
        # argument to the resolvers, in GraphQL-Core it is available via the resolve
        # info, just like the context value.
        def resolve_id(info):
            return cancellable_async_fn(info.abort_signal)

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"todo": {"id": resolve_id}},
        )
        assert isinstance(awaitable_result, Awaitable)

        abort_controller.abort()

        result = await awaitable_result

        assert result.errors is not None
        assert isinstance(result.errors[0].original_error, AbortError)
        assert result == (
            {"todo": {"id": None}},
            [
                {
                    "message": "This operation was aborted",
                    "locations": [(4, 11)],
                    "path": ["todo", "id"],
                }
            ],
        )

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

        result = await awaitable_result

        assert result.errors is not None
        assert result.errors[0].original_error is custom_error
        assert result == (
            {"todo": None},
            [
                {
                    "message": "Custom abort error",
                    "locations": [(3, 9)],
                    "path": ["todo"],
                }
            ],
        )

    async def stops_the_execution_when_aborted_during_completion_with_custom_string():
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

        abort_controller.abort("Custom abort error message")

        result = await awaitable_result

        assert result == (
            {"todo": None},
            [
                {
                    "message": "Unexpected error value: 'Custom abort error message'",
                    "locations": [(3, 9)],
                    "path": ["todo"],
                }
            ],
        )

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

        result = await awaitable_result

        assert result == (
            {"todo": {"id": "1", "author": None}},
            [
                {
                    "message": "This operation was aborted",
                    "locations": [(5, 11)],
                    "path": ["todo", "author"],
                }
            ],
        )

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

        result = await task

        assert result.errors is not None
        assert isinstance(result.errors[0].original_error, AbortError)
        assert result == (
            {"todo": None},
            [
                {
                    "message": "This operation was aborted",
                    "locations": [(3, 9)],
                    "path": ["todo"],
                }
            ],
        )

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

        result = await awaitable_result

        assert result.errors is not None
        assert isinstance(result.errors[0].original_error, AbortError)
        assert result == (
            {"todo": {"id": "1", "items": [None]}},
            [
                {
                    "message": "This operation was aborted",
                    "locations": [(5, 11)],
                    "path": ["todo", "items", 0],
                }
            ],
        )

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

        result = await awaitable_result

        assert result.errors is not None
        assert isinstance(result.errors[0].original_error, AbortError)
        assert result == (
            {"todo": {"id": "1", "items": None}},
            [
                {
                    "message": "This operation was aborted",
                    "locations": [(5, 11)],
                    "path": ["todo", "items"],
                }
            ],
        )

    async def stops_the_execution_when_aborted_despite_a_hanging_iterator_no_close():
        # Like the test above, but the async iterator has no aclose() method, so
        # the cancellable wrapper has nothing to forward the close to.
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

        class Items:
            def __aiter__(self):
                return self

            async def __anext__(self):
                # never reached: the iterator is cancelled before its body runs
                return await Future()  # will never resolve  # pragma: no cover

        def todo(_info):
            return {"id": "1", "items": Items()}

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"todo": todo},
        )
        assert isinstance(awaitable_result, Awaitable)

        abort_controller.abort()

        result = await awaitable_result

        assert result.errors is not None
        assert isinstance(result.errors[0].original_error, AbortError)
        assert result == (
            {"todo": {"id": "1", "items": None}},
            [
                {
                    "message": "This operation was aborted",
                    "locations": [(5, 11)],
                    "path": ["todo", "items"],
                }
            ],
        )

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

        result = await awaitable_result

        assert result.errors is not None
        assert isinstance(result.errors[0].original_error, AbortError)
        assert result == (
            None,
            [
                {
                    "message": "This operation was aborted",
                    "locations": [(3, 9)],
                    "path": ["nonNullableTodo"],
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

        result = await task

        assert result == (
            {"foo": "baz", "bar": None},
            [
                {
                    "message": "This operation was aborted",
                    "locations": [(4, 9)],
                    "path": ["bar"],
                }
            ],
        )

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

        result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={"todo": must_not_be_called},
        )

        assert result == (None, [{"message": "This operation was aborted"}])

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
