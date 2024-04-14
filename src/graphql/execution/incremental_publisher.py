"""Incremental Publisher"""

from __future__ import annotations

from asyncio import Event, as_completed, sleep
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Generator,
    Sequence,
    Union,
)

try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict
try:
    from typing import TypeGuard
except ImportError:  # Python < 3.10
    from typing_extensions import TypeGuard


if TYPE_CHECKING:
    from ..error import GraphQLError, GraphQLFormattedError
    from ..pyutils import AwaitableOrValue, Path

__all__ = [
    "ASYNC_DELAY",
    "DeferredFragmentRecord",
    "FormattedIncrementalDeferResult",
    "FormattedIncrementalResult",
    "FormattedIncrementalStreamResult",
    "FormattedSubsequentIncrementalExecutionResult",
    "IncrementalDataRecord",
    "IncrementalDeferResult",
    "IncrementalPublisherMixin",
    "IncrementalResult",
    "IncrementalStreamResult",
    "StreamItemsRecord",
    "SubsequentIncrementalExecutionResult",
]


ASYNC_DELAY = 1 / 512  # wait time in seconds for deferring execution


class FormattedIncrementalDeferResult(TypedDict, total=False):
    """Formatted incremental deferred execution result"""

    data: dict[str, Any] | None
    errors: list[GraphQLFormattedError]
    path: list[str | int]
    label: str
    extensions: dict[str, Any]


class IncrementalDeferResult:
    """Incremental deferred execution result"""

    data: dict[str, Any] | None
    errors: list[GraphQLError] | None
    path: list[str | int] | None
    label: str | None
    extensions: dict[str, Any] | None

    __slots__ = "data", "errors", "path", "label", "extensions"

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        errors: list[GraphQLError] | None = None,
        path: list[str | int] | None = None,
        label: str | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> None:
        self.data = data
        self.errors = errors
        self.path = path
        self.label = label
        self.extensions = extensions

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = [f"data={self.data!r}, errors={self.errors!r}"]
        if self.path:
            args.append(f"path={self.path!r}")
        if self.label:
            args.append(f"label={self.label!r}")
        if self.extensions:
            args.append(f"extensions={self.extensions}")
        return f"{name}({', '.join(args)})"

    @property
    def formatted(self) -> FormattedIncrementalDeferResult:
        """Get execution result formatted according to the specification."""
        formatted: FormattedIncrementalDeferResult = {"data": self.data}
        if self.errors is not None:
            formatted["errors"] = [error.formatted for error in self.errors]
        if self.path is not None:
            formatted["path"] = self.path
        if self.label is not None:
            formatted["label"] = self.label
        if self.extensions is not None:
            formatted["extensions"] = self.extensions
        return formatted

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return (
                other.get("data") == self.data
                and other.get("errors") == self.errors
                and ("path" not in other or other["path"] == self.path)
                and ("label" not in other or other["label"] == self.label)
                and (
                    "extensions" not in other or other["extensions"] == self.extensions
                )
            )
        if isinstance(other, tuple):
            size = len(other)
            return (
                1 < size < 6
                and (self.data, self.errors, self.path, self.label, self.extensions)[
                    :size
                ]
                == other
            )
        return (
            isinstance(other, self.__class__)
            and other.data == self.data
            and other.errors == self.errors
            and other.path == self.path
            and other.label == self.label
            and other.extensions == self.extensions
        )

    def __ne__(self, other: object) -> bool:
        return not self == other


class FormattedIncrementalStreamResult(TypedDict, total=False):
    """Formatted incremental stream execution result"""

    items: list[Any] | None
    errors: list[GraphQLFormattedError]
    path: list[str | int]
    label: str
    extensions: dict[str, Any]


class IncrementalStreamResult:
    """Incremental streamed execution result"""

    items: list[Any] | None
    errors: list[GraphQLError] | None
    path: list[str | int] | None
    label: str | None
    extensions: dict[str, Any] | None

    __slots__ = "items", "errors", "path", "label", "extensions"

    def __init__(
        self,
        items: list[Any] | None = None,
        errors: list[GraphQLError] | None = None,
        path: list[str | int] | None = None,
        label: str | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> None:
        self.items = items
        self.errors = errors
        self.path = path
        self.label = label
        self.extensions = extensions

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = [f"items={self.items!r}, errors={self.errors!r}"]
        if self.path:
            args.append(f"path={self.path!r}")
        if self.label:
            args.append(f"label={self.label!r}")
        if self.extensions:
            args.append(f"extensions={self.extensions}")
        return f"{name}({', '.join(args)})"

    @property
    def formatted(self) -> FormattedIncrementalStreamResult:
        """Get execution result formatted according to the specification."""
        formatted: FormattedIncrementalStreamResult = {"items": self.items}
        if self.errors is not None:
            formatted["errors"] = [error.formatted for error in self.errors]
        if self.path is not None:
            formatted["path"] = self.path
        if self.label is not None:
            formatted["label"] = self.label
        if self.extensions is not None:
            formatted["extensions"] = self.extensions
        return formatted

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return (
                other.get("items") == self.items
                and other.get("errors") == self.errors
                and ("path" not in other or other["path"] == self.path)
                and ("label" not in other or other["label"] == self.label)
                and (
                    "extensions" not in other or other["extensions"] == self.extensions
                )
            )
        if isinstance(other, tuple):
            size = len(other)
            return (
                1 < size < 6
                and (self.items, self.errors, self.path, self.label, self.extensions)[
                    :size
                ]
                == other
            )
        return (
            isinstance(other, self.__class__)
            and other.items == self.items
            and other.errors == self.errors
            and other.path == self.path
            and other.label == self.label
            and other.extensions == self.extensions
        )

    def __ne__(self, other: object) -> bool:
        return not self == other


FormattedIncrementalResult = Union[
    FormattedIncrementalDeferResult, FormattedIncrementalStreamResult
]

IncrementalResult = Union[IncrementalDeferResult, IncrementalStreamResult]


class FormattedSubsequentIncrementalExecutionResult(TypedDict, total=False):
    """Formatted subsequent incremental execution result"""

    incremental: list[FormattedIncrementalResult]
    hasNext: bool
    extensions: dict[str, Any]


class SubsequentIncrementalExecutionResult:
    """Subsequent incremental execution result.

    - ``has_next`` is True if a future payload is expected.
    - ``incremental`` is a list of the results from defer/stream directives.
    """

    __slots__ = "has_next", "incremental", "extensions"

    incremental: Sequence[IncrementalResult] | None
    has_next: bool
    extensions: dict[str, Any] | None

    def __init__(
        self,
        incremental: Sequence[IncrementalResult] | None = None,
        has_next: bool = False,
        extensions: dict[str, Any] | None = None,
    ) -> None:
        self.incremental = incremental
        self.has_next = has_next
        self.extensions = extensions

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = []
        if self.incremental:
            args.append(f"incremental[{len(self.incremental)}]")
        if self.has_next:
            args.append("has_next")
        if self.extensions:
            args.append(f"extensions={self.extensions}")
        return f"{name}({', '.join(args)})"

    @property
    def formatted(self) -> FormattedSubsequentIncrementalExecutionResult:
        """Get execution result formatted according to the specification."""
        formatted: FormattedSubsequentIncrementalExecutionResult = {}
        if self.incremental:
            formatted["incremental"] = [result.formatted for result in self.incremental]
        formatted["hasNext"] = self.has_next
        if self.extensions is not None:
            formatted["extensions"] = self.extensions
        return formatted

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return (
                ("incremental" not in other or other["incremental"] == self.incremental)
                and ("hasNext" in other and other["hasNext"] == self.has_next)
                and (
                    "extensions" not in other or other["extensions"] == self.extensions
                )
            )
        if isinstance(other, tuple):
            size = len(other)
            return (
                1 < size < 4
                and (
                    self.incremental,
                    self.has_next,
                    self.extensions,
                )[:size]
                == other
            )
        return (
            isinstance(other, self.__class__)
            and other.incremental == self.incremental
            and other.has_next == self.has_next
            and other.extensions == self.extensions
        )

    def __ne__(self, other: object) -> bool:
        return not self == other


class IncrementalPublisherMixin:
    """Mixin to add incremental publishing to the ExecutionContext."""

    _canceled_iterators: set[AsyncIterator]
    subsequent_payloads: dict[IncrementalDataRecord, None]  # used as ordered set

    is_awaitable: Callable[[Any], TypeGuard[Awaitable]]

    def filter_subsequent_payloads(
        self,
        null_path: Path,
        current_incremental_data_record: IncrementalDataRecord | None = None,
    ) -> None:
        """Filter subsequent payloads."""
        null_path_list = null_path.as_list()
        for incremental_data_record in list(self.subsequent_payloads):
            if incremental_data_record is current_incremental_data_record:
                # don't remove payload from where error originates
                continue
            if incremental_data_record.path[: len(null_path_list)] != null_path_list:
                # incremental_data_record points to a path unaffected by this payload
                continue
            # incremental_data_record path points to nulled error field
            if (
                isinstance(incremental_data_record, StreamItemsRecord)
                and incremental_data_record.async_iterator
            ):
                self._canceled_iterators.add(incremental_data_record.async_iterator)
            del self.subsequent_payloads[incremental_data_record]

    def get_completed_incremental_results(self) -> list[IncrementalResult]:
        """Get completed incremental results."""
        incremental_results: list[IncrementalResult] = []
        append_result = incremental_results.append
        subsequent_payloads = list(self.subsequent_payloads)
        for incremental_data_record in subsequent_payloads:
            incremental_result: IncrementalResult
            if not incremental_data_record.completed.is_set():
                continue
            del self.subsequent_payloads[incremental_data_record]
            if isinstance(incremental_data_record, StreamItemsRecord):
                items = incremental_data_record.items
                if incremental_data_record.is_completed_async_iterator:
                    # async iterable resolver finished but there may be pending payload
                    continue  # pragma: no cover
                incremental_result = IncrementalStreamResult(
                    items,
                    incremental_data_record.errors
                    if incremental_data_record.errors
                    else None,
                    incremental_data_record.path,
                    incremental_data_record.label,
                )
            else:
                data = incremental_data_record.data
                incremental_result = IncrementalDeferResult(
                    data,
                    incremental_data_record.errors
                    if incremental_data_record.errors
                    else None,
                    incremental_data_record.path,
                    incremental_data_record.label,
                )

            append_result(incremental_result)

        return incremental_results

    async def yield_subsequent_payloads(
        self,
    ) -> AsyncGenerator[SubsequentIncrementalExecutionResult, None]:
        """Yield subsequent payloads."""
        payloads = self.subsequent_payloads
        has_next = bool(payloads)

        while has_next:
            for awaitable in as_completed(payloads):
                await awaitable

                incremental = self.get_completed_incremental_results()

                has_next = bool(payloads)

                if incremental or not has_next:
                    yield SubsequentIncrementalExecutionResult(
                        incremental=incremental or None, has_next=has_next
                    )

                if not has_next:
                    break


class DeferredFragmentRecord:
    """A record collecting data marked with the defer directive"""

    errors: list[GraphQLError]
    label: str | None
    path: list[str | int]
    data: dict[str, Any] | None
    parent_context: IncrementalDataRecord | None
    completed: Event
    _publisher: IncrementalPublisherMixin
    _data: AwaitableOrValue[dict[str, Any] | None]
    _data_added: Event

    def __init__(
        self,
        label: str | None,
        path: Path | None,
        parent_context: IncrementalDataRecord | None,
        context: IncrementalPublisherMixin,
    ) -> None:
        self.label = label
        self.path = path.as_list() if path else []
        self.parent_context = parent_context
        self.errors = []
        self._publisher = context
        context.subsequent_payloads[self] = None
        self.data = self._data = None
        self.completed = Event()
        self._data_added = Event()

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = [f"path={self.path!r}"]
        if self.label:
            args.append(f"label={self.label!r}")
        if self.parent_context:
            args.append("parent_context")
        if self.data is not None:
            args.append("data")
        return f"{name}({', '.join(args)})"

    def __await__(self) -> Generator[Any, None, dict[str, Any] | None]:
        return self.wait().__await__()

    async def wait(self) -> dict[str, Any] | None:
        """Wait until data is ready."""
        if self.parent_context:
            await self.parent_context.completed.wait()
        _data = self._data
        data = (
            await _data  # type: ignore
            if self._publisher.is_awaitable(_data)
            else _data
        )
        await sleep(ASYNC_DELAY)  # always defer completion a little bit
        self.completed.set()
        self.data = data
        return data

    def add_data(self, data: AwaitableOrValue[dict[str, Any] | None]) -> None:
        """Add data to the record."""
        self._data = data
        self._data_added.set()


class StreamItemsRecord:
    """A record collecting items marked with the stream directive"""

    errors: list[GraphQLError]
    label: str | None
    path: list[str | int]
    items: list[str] | None
    parent_context: IncrementalDataRecord | None
    async_iterator: AsyncIterator[Any] | None
    is_completed_async_iterator: bool
    completed: Event
    _publisher: IncrementalPublisherMixin
    _items: AwaitableOrValue[list[Any] | None]
    _items_added: Event

    def __init__(
        self,
        label: str | None,
        path: Path | None,
        async_iterator: AsyncIterator[Any] | None,
        parent_context: IncrementalDataRecord | None,
        context: IncrementalPublisherMixin,
    ) -> None:
        self.label = label
        self.path = path.as_list() if path else []
        self.parent_context = parent_context
        self.async_iterator = async_iterator
        self.errors = []
        self._publisher = context
        context.subsequent_payloads[self] = None
        self.items = self._items = None
        self.completed = Event()
        self._items_added = Event()
        self.is_completed_async_iterator = False

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = [f"path={self.path!r}"]
        if self.label:
            args.append(f"label={self.label!r}")
        if self.parent_context:
            args.append("parent_context")
        if self.items is not None:
            args.append("items")
        return f"{name}({', '.join(args)})"

    def __await__(self) -> Generator[Any, None, list[str] | None]:
        return self.wait().__await__()

    async def wait(self) -> list[str] | None:
        """Wait until data is ready."""
        await self._items_added.wait()
        if self.parent_context:
            await self.parent_context.completed.wait()
        _items = self._items
        items = (
            await _items  # type: ignore
            if self._publisher.is_awaitable(_items)
            else _items
        )
        await sleep(ASYNC_DELAY)  # always defer completion a little bit
        self.items = items
        self.completed.set()
        return items

    def add_items(self, items: AwaitableOrValue[list[Any] | None]) -> None:
        """Add items to the record."""
        self._items = items
        self._items_added.set()

    def set_is_completed_async_iterator(self) -> None:
        """Mark as completed."""
        self.is_completed_async_iterator = True
        self._items_added.set()


IncrementalDataRecord = Union[DeferredFragmentRecord, StreamItemsRecord]
