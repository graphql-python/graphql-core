"""Abort signal for cancelling the execution of a GraphQL operation."""

from __future__ import annotations

from asyncio import Event
from typing import Any

__all__ = ["AbortController", "AbortError", "AbortSignal"]


class AbortError(Exception):
    """Error used as the default reason when an operation is aborted.

    This is the Python counterpart of the ``AbortError`` ``DOMException`` that the
    JavaScript ``AbortController.abort()`` uses when called without a reason.
    """


class AbortSignal:
    """A signal object that communicates an abort request to the executor.

    This mirrors the JavaScript ``AbortSignal`` Web API. The executor only ever
    inspects the synchronous :attr:`aborted` flag (and :attr:`reason`) at field
    boundaries, so any object exposing these two attributes can be used in place of
    this class. In addition to that pollable interface, this implementation is also
    *awaitable* via :meth:`wait`, allowing resolvers to react to an abort of a
    running operation immediately instead of only at the next field boundary.

    The signal is created and controlled through an :class:`AbortController`.

    >>> from graphql.pyutils import AbortController
    >>> signal = AbortController().signal
    >>> signal.aborted, signal.reason
    (False, None)
    """

    aborted: bool
    """Whether the operation has been aborted."""
    reason: Any
    """The reason given when aborting, or None if not aborted yet."""

    def __init__(self) -> None:
        self.aborted = False
        self.reason = None
        self._event = Event()

    async def wait(self) -> Any:
        """Wait until the signal is aborted and return the abort reason.

        :returns: the abort reason

        >>> import asyncio
        >>> from graphql.pyutils import AbortController
        >>> async def main():
        ...     controller = AbortController()
        ...     asyncio.get_running_loop().call_soon(controller.abort, 'timeout')
        ...     return await controller.signal.wait()
        >>> asyncio.run(main())
        'timeout'
        """
        await self._event.wait()
        return self.reason


class AbortController:
    """A controller object for aborting the execution of a GraphQL operation.

    This mirrors the JavaScript ``AbortController`` Web API. Pass its
    :attr:`signal` as the ``abort_signal`` argument to ``execute`` (and related
    functions) and call :meth:`abort` to cancel the execution.

    >>> from graphql.pyutils import AbortController
    >>> controller = AbortController()
    >>> controller.signal.aborted
    False
    >>> controller.abort()
    >>> controller.signal.aborted
    True
    >>> controller.signal.reason
    AbortError('This operation was aborted')
    """

    signal: AbortSignal
    """The signal controlled by this controller."""

    def __init__(self) -> None:
        self.signal = AbortSignal()

    def abort(self, reason: Any = None) -> None:
        """Abort the operation, optionally specifying a reason.

        The reason becomes the resulting GraphQL error: an exception is used as its
        original error, while any other value is wrapped by ``located_error`` as an
        "Unexpected error value". If no reason is given, an :class:`AbortError` with
        a generic message is used. Aborting more than once has no further effect.

        :param reason: the reason for aborting, by default an :class:`AbortError`

        >>> from graphql.pyutils import AbortController
        >>> controller = AbortController()
        >>> controller.abort(RuntimeError('Cancelled by user'))
        >>> controller.abort(RuntimeError('Ignored'))
        >>> controller.signal.reason
        RuntimeError('Cancelled by user')
        """
        signal = self.signal
        if signal.aborted:
            return
        signal.aborted = True
        signal.reason = (
            AbortError("This operation was aborted") if reason is None else reason
        )
        signal._event.set()  # noqa: SLF001
