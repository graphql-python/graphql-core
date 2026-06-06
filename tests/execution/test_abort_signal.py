"""Tests for cancelling execution via an abort signal."""

from __future__ import annotations

from asyncio import ensure_future, sleep
from collections.abc import Awaitable

import pytest

from graphql import build_schema
from graphql.execution import execute
from graphql.language import parse
from graphql.pyutils import AbortController, AbortError

pytestmark = pytest.mark.anyio


schema = build_schema(
    """
    type Todo {
      id: ID
      text: String
      author: User
    }

    type User {
      id: ID
      name: String
    }

    type Query {
      todo: Todo
    }

    type Mutation {
      foo: String
      bar: String
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
            return {
                "id": "1",
                "text": "Hello, World!",
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
            return {
                "id": "1",
                "text": "Hello, World!",
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
            return {
                "id": "1",
                "text": "Hello, World!",
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
            return must_not_be_called

        awaitable_result = execute(
            schema,
            document,
            abort_signal=abort_controller.signal,
            root_value={
                "todo": {
                    "id": "1",
                    "text": "Hello, World!",
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

        abort_controller.abort()

        result = await awaitable_result

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
