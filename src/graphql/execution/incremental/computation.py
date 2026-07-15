"""Memoized abortable computation"""

from __future__ import annotations

from asyncio import CancelledError, ensure_future
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from ...pyutils.is_awaitable import is_awaitable

if TYPE_CHECKING:
    from asyncio import Future
    from collections.abc import Callable

    from ...pyutils import AwaitableOrValue

__all__ = ["Computation"]

T = TypeVar("T")

_PENDING = "pending"
_FULFILLED = "fulfilled"
_REJECTED = "rejected"


class Computation(Generic[T]):
    """A lazily primed, memoized, abortable computation.

    Runs the given function at most once, no matter how often the computation
    is primed or its result is requested. The outcome is memoized, whether the
    function returns a value, returns an awaitable, or raises. An awaitable
    result is scheduled as a future immediately, so that it can start running
    early and can be cancelled on abort.

    Aborting an unprimed computation poisons it so that the function never
    runs. Aborting a computation with a still pending future cancels the
    future, invokes the optional abort callback and returns its result.
    Aborting a settled computation has no effect. Requesting the result of a
    computation that was aborted without a reason raises a CancelledError.

    For internal use only.
    """

    __slots__ = "_fn", "_on_abort", "_status", "_value"

    _status: str | None
    _value: Any

    def __init__(
        self,
        fn: Callable[[], AwaitableOrValue[T]],
        on_abort: Callable[[BaseException | None], AwaitableOrValue[None]]
        | None = None,
    ) -> None:
        """Initialize the computation with a function and an abort callback."""
        self._fn = fn
        self._on_abort = on_abort
        self._status = None
        self._value = None

    def prime(self) -> None:
        """Run the computation if it has not been started or aborted yet."""
        if self._status is not None:
            return
        try:
            result = self._fn()
        except Exception as reason:
            self._status = _REJECTED
            self._value = reason
            return
        if is_awaitable(result):
            future = ensure_future(result)
            self._status = _PENDING
            self._value = future
            future.add_done_callback(self._settle)
        else:
            self._status = _FULFILLED
            self._value = result

    @property
    def pending_future(self) -> Future[T] | None:
        """Get the still pending future, or None if there is none."""
        return self._value if self._status is _PENDING else None

    def result(self) -> AwaitableOrValue[T]:
        """Get the memoized result, priming the computation if necessary.

        Returns the result or a future for it, or raises the reason why the
        computation failed or was aborted.
        """
        self.prime()
        status = self._status
        if status is _FULFILLED:
            return self._value
        if status is _REJECTED:
            reason = self._value
            if reason is None:
                raise CancelledError
            raise reason
        return self._value  # the pending future

    def abort(self, reason: BaseException | None = None) -> AwaitableOrValue[None]:
        """Abort the computation with an optional reason.

        Returns the result of the abort callback when the computation was
        still pending, None otherwise.
        """
        status = self._status
        if status is None:
            self._status = _REJECTED
            self._value = reason
        elif status is _PENDING:
            future = self._value
            self._status = _REJECTED
            self._value = reason
            future.cancel()
            on_abort = self._on_abort
            if on_abort is not None:
                return on_abort(reason)
        return None

    def _settle(self, future: Future[T]) -> None:
        """Memoize the outcome when the scheduled future is done."""
        if future.cancelled():
            if self._status is _PENDING:
                # cancelled externally, not via abort
                self._status = _REJECTED
                self._value = CancelledError()
            return
        reason = future.exception()  # always retrieve, avoiding warnings
        if self._status is not _PENDING:
            return  # aborted after the future had already completed
        if reason is not None:
            self._status = _REJECTED
            self._value = reason
        else:
            self._status = _FULFILLED
            self._value = future.result()
