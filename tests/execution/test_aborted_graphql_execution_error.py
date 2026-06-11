"""Tests for the aborted GraphQL execution error."""

from __future__ import annotations

from asyncio import Future

import pytest

from graphql.execution import AbortedGraphQLExecutionError

pytestmark = pytest.mark.anyio


def describe_aborted_graphql_execution_error():
    def uses_the_original_exception_reason_message_and_cause():
        reason = RuntimeError("Original reason")
        result = {"data": {"ok": True}}

        error = AbortedGraphQLExecutionError(reason, result)

        assert isinstance(error, Exception)
        assert isinstance(error, AbortedGraphQLExecutionError)
        assert str(error) == "Original reason"
        assert error.__cause__ is reason
        assert error.reason is reason
        assert error.aborted_result is result

    async def uses_the_message_property_from_non_exception_reasons():
        class Reason:
            message = "Object reason"

        reason = Reason()
        result: Future[dict] = Future()
        result.set_result({"data": None})

        error = AbortedGraphQLExecutionError(reason, result)

        assert str(error) == "Object reason"
        assert error.__cause__ is None
        assert error.reason is reason
        assert error.aborted_result is result
        assert await error.aborted_result == {"data": None}

    def stringifies_reasons_without_a_message():
        error = AbortedGraphQLExecutionError("String reason", {"data": None})

        assert str(error) == "String reason"
        assert error.__cause__ is None
        assert error.reason == "String reason"

    def stringifies_none_reasons():
        error = AbortedGraphQLExecutionError(None, {"data": None})

        assert str(error) == "None"
        assert error.__cause__ is None
        assert error.reason is None
