"""Aborted GraphQL execution error"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..pyutils import AwaitableOrValue

__all__ = ["AbortedGraphQLExecutionError"]


class AbortedGraphQLExecutionError(Exception):
    """An error raised when execution is aborted while work is still resolving.

    The message is derived from the abort reason, which is also available via the
    ``reason`` attribute (and as ``__cause__`` when it is an exception). The partial
    result that the aborted execution can still produce while unwinding is exposed
    as ``aborted_result``. It is usually provided as an awaitable, since execution
    has not finished when the error is raised; it is provided as a plain value when
    the execution was aborted internally during synchronous execution.
    """

    reason: Any
    aborted_result: AwaitableOrValue[Any]

    def __init__(self, reason: Any, result: AwaitableOrValue[Any]) -> None:
        super().__init__(get_abort_reason_message(reason))
        self.reason = reason
        self.aborted_result = result
        if isinstance(reason, BaseException):
            self.__cause__ = reason


def get_abort_reason_message(reason: Any) -> str:
    """Get the error message for the given abort reason."""
    if isinstance(reason, BaseException):
        return str(reason)
    message = getattr(reason, "message", None)
    if isinstance(message, str):
        return message
    return str(reason)
