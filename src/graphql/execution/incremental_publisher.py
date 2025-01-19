"""Incremental Publisher"""

from __future__ import annotations

from asyncio import Event, ensure_future, gather, sleep
from contextlib import suppress
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Collection,
    Iterator,
    NamedTuple,
    Union,
)

try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict

from ..pyutils import RefSet

if TYPE_CHECKING:
    from ..error import GraphQLError, GraphQLFormattedError
    from ..pyutils import Path
    from .collect_fields import GroupedFieldSet

__all__ = [
    "ASYNC_DELAY",
    "DeferredFragmentRecord",
    "ExecutionResult",
    "ExperimentalIncrementalExecutionResults",
    "FormattedExecutionResult",
    "FormattedIncrementalDeferResult",
    "FormattedIncrementalResult",
    "FormattedIncrementalStreamResult",
    "FormattedInitialIncrementalExecutionResult",
    "FormattedSubsequentIncrementalExecutionResult",
    "IncrementalDataRecord",
    "IncrementalDeferResult",
    "IncrementalPublisher",
    "IncrementalResult",
    "IncrementalStreamResult",
    "InitialIncrementalExecutionResult",
    "InitialResultRecord",
    "StreamItemsRecord",
    "SubsequentIncrementalExecutionResult",
]


ASYNC_DELAY = 1 / 512  # wait time in seconds for deferring execution

suppress_key_error = suppress(KeyError)


class FormattedPendingResult(TypedDict, total=False):
    """Formatted pending execution result"""

    path: list[str | int]
    label: str


class PendingResult:
    """Pending execution result"""

    path: list[str | int]
    label: str | None

    __slots__ = "label", "path"

    def __init__(
        self,
        path: list[str | int],
        label: str | None = None,
    ) -> None:
        self.path = path
        self.label = label

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = [f"path={self.path!r}"]
        if self.label:
            args.append(f"label={self.label!r}")
        return f"{name}({', '.join(args)})"

    @property
    def formatted(self) -> FormattedPendingResult:
        """Get pending result formatted according to the specification."""
        formatted: FormattedPendingResult = {"path": self.path}
        if self.label is not None:
            formatted["label"] = self.label
        return formatted

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return (other.get("path") or None) == (self.path or None) and (
                other.get("label") or None
            ) == (self.label or None)

        if isinstance(other, tuple):
            size = len(other)
            return 1 < size < 3 and (self.path, self.label)[:size] == other
        return (
            isinstance(other, self.__class__)
            and other.path == self.path
            and other.label == self.label
        )

    def __ne__(self, other: object) -> bool:
        return not self == other


class FormattedCompletedResult(TypedDict, total=False):
    """Formatted completed execution result"""

    path: list[str | int]
    label: str
    errors: list[GraphQLFormattedError]


class CompletedResult:
    """Completed execution result"""

    path: list[str | int]
    label: str | None
    errors: list[GraphQLError] | None

    __slots__ = "errors", "label", "path"

    def __init__(
        self,
        path: list[str | int],
        label: str | None = None,
        errors: list[GraphQLError] | None = None,
    ) -> None:
        self.path = path
        self.label = label
        self.errors = errors

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = [f"path={self.path!r}"]
        if self.label:
            args.append(f"label={self.label!r}")
        if self.errors:
            args.append(f"errors={self.errors!r}")
        return f"{name}({', '.join(args)})"

    @property
    def formatted(self) -> FormattedCompletedResult:
        """Get completed result formatted according to the specification."""
        formatted: FormattedCompletedResult = {"path": self.path}
        if self.label is not None:
            formatted["label"] = self.label
        if self.errors is not None:
            formatted["errors"] = [error.formatted for error in self.errors]
        return formatted

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return (
                (other.get("path") or None) == (self.path or None)
                and (other.get("label") or None) == (self.label or None)
                and (other.get("errors") or None) == (self.errors or None)
            )
        if isinstance(other, tuple):
            size = len(other)
            return 1 < size < 4 and (self.path, self.label, self.errors)[:size] == other
        return (
            isinstance(other, self.__class__)
            and other.path == self.path
            and other.label == self.label
            and other.errors == self.errors
        )

    def __ne__(self, other: object) -> bool:
        return not self == other


class IncrementalUpdate(NamedTuple):
    """Incremental update"""

    pending: list[PendingResult]
    incremental: list[IncrementalResult]
    completed: list[CompletedResult]


class FormattedExecutionResult(TypedDict, total=False):
    """Formatted execution result"""

    data: dict[str, Any] | None
    errors: list[GraphQLFormattedError]
    extensions: dict[str, Any]


class ExecutionResult:
    """The result of GraphQL execution.

    - ``data`` is the result of a successful execution of the query.
    - ``errors`` is included when any errors occurred as a non-empty list.
    - ``extensions`` is reserved for adding non-standard properties.
    """

    __slots__ = "data", "errors", "extensions"

    data: dict[str, Any] | None
    errors: list[GraphQLError] | None
    extensions: dict[str, Any] | None

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        errors: list[GraphQLError] | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> None:
        self.data = data
        self.errors = errors
        self.extensions = extensions

    def __repr__(self) -> str:
        name = self.__class__.__name__
        ext = "" if self.extensions is None else f", extensions={self.extensions}"
        return f"{name}(data={self.data!r}, errors={self.errors!r}{ext})"

    def __iter__(self) -> Iterator[Any]:
        return iter((self.data, self.errors))

    @property
    def formatted(self) -> FormattedExecutionResult:
        """Get execution result formatted according to the specification."""
        formatted: FormattedExecutionResult = {"data": self.data}
        if self.errors is not None:
            formatted["errors"] = [error.formatted for error in self.errors]
        if self.extensions is not None:
            formatted["extensions"] = self.extensions
        return formatted

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return (
                (other.get("data") == self.data)
                and (other.get("errors") or None) == (self.errors or None)
                and (other.get("extensions") or None) == (self.extensions or None)
            )
        if isinstance(other, tuple):
            if len(other) == 2:
                return other == (self.data, self.errors)
            return other == (self.data, self.errors, self.extensions)
        return (
            isinstance(other, self.__class__)
            and other.data == self.data
            and other.errors == self.errors
            and other.extensions == self.extensions
        )

    def __ne__(self, other: object) -> bool:
        return not self == other


class FormattedInitialIncrementalExecutionResult(TypedDict, total=False):
    """Formatted initial incremental execution result"""

    data: dict[str, Any] | None
    errors: list[GraphQLFormattedError]
    pending: list[FormattedPendingResult]
    hasNext: bool
    incremental: list[FormattedIncrementalResult]
    extensions: dict[str, Any]


class InitialIncrementalExecutionResult:
    """Initial incremental execution result."""

    data: dict[str, Any] | None
    errors: list[GraphQLError] | None
    pending: list[PendingResult]
    has_next: bool
    extensions: dict[str, Any] | None

    __slots__ = "data", "errors", "extensions", "has_next", "pending"

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        errors: list[GraphQLError] | None = None,
        pending: list[PendingResult] | None = None,
        has_next: bool = False,
        extensions: dict[str, Any] | None = None,
    ) -> None:
        self.data = data
        self.errors = errors
        self.pending = pending or []
        self.has_next = has_next
        self.extensions = extensions

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = [f"data={self.data!r}, errors={self.errors!r}"]
        if self.pending:
            args.append(f"pending={self.pending!r}")
        if self.has_next:
            args.append("has_next")
        if self.extensions:
            args.append(f"extensions={self.extensions}")
        return f"{name}({', '.join(args)})"

    @property
    def formatted(self) -> FormattedInitialIncrementalExecutionResult:
        """Get execution result formatted according to the specification."""
        formatted: FormattedInitialIncrementalExecutionResult = {"data": self.data}
        if self.errors is not None:
            formatted["errors"] = [error.formatted for error in self.errors]
        formatted["pending"] = [pending.formatted for pending in self.pending]
        formatted["hasNext"] = self.has_next
        if self.extensions is not None:
            formatted["extensions"] = self.extensions
        return formatted

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return (
                other.get("data") == self.data
                and (other.get("errors") or None) == (self.errors or None)
                and (other.get("pending") or None) == (self.pending or None)
                and (other.get("hasNext") or None) == (self.has_next or None)
                and (other.get("extensions") or None) == (self.extensions or None)
            )
        if isinstance(other, tuple):
            size = len(other)
            return (
                1 < size < 6
                and (
                    self.data,
                    self.errors,
                    self.pending,
                    self.has_next,
                    self.extensions,
                )[:size]
                == other
            )
        return (
            isinstance(other, self.__class__)
            and other.data == self.data
            and other.errors == self.errors
            and other.pending == self.pending
            and other.has_next == self.has_next
            and other.extensions == self.extensions
        )

    def __ne__(self, other: object) -> bool:
        return not self == other


class ExperimentalIncrementalExecutionResults(NamedTuple):
    """Execution results when retrieved incrementally."""

    initial_result: InitialIncrementalExecutionResult
    subsequent_results: AsyncGenerator[SubsequentIncrementalExecutionResult, None]


class FormattedIncrementalDeferResult(TypedDict, total=False):
    """Formatted incremental deferred execution result"""

    data: dict[str, Any] | None
    errors: list[GraphQLFormattedError]
    path: list[str | int]
    extensions: dict[str, Any]


class IncrementalDeferResult:
    """Incremental deferred execution result"""

    data: dict[str, Any] | None
    errors: list[GraphQLError] | None
    path: list[str | int] | None
    extensions: dict[str, Any] | None

    __slots__ = "data", "errors", "extensions", "path"

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        errors: list[GraphQLError] | None = None,
        path: list[str | int] | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> None:
        self.data = data
        self.errors = errors
        self.path = path
        self.extensions = extensions

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = [f"data={self.data!r}, errors={self.errors!r}"]
        if self.path:
            args.append(f"path={self.path!r}")
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
        if self.extensions is not None:
            formatted["extensions"] = self.extensions
        return formatted

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return (
                other.get("data") == self.data
                and (other.get("errors") or None) == (self.errors or None)
                and (other.get("path") or None) == (self.path or None)
                and (other.get("extensions") or None) == (self.extensions or None)
            )
        if isinstance(other, tuple):
            size = len(other)
            return (
                1 < size < 5
                and (self.data, self.errors, self.path, self.extensions)[:size] == other
            )
        return (
            isinstance(other, self.__class__)
            and other.data == self.data
            and other.errors == self.errors
            and other.path == self.path
            and other.extensions == self.extensions
        )

    def __ne__(self, other: object) -> bool:
        return not self == other


class FormattedIncrementalStreamResult(TypedDict, total=False):
    """Formatted incremental stream execution result"""

    items: list[Any] | None
    errors: list[GraphQLFormattedError]
    path: list[str | int]
    extensions: dict[str, Any]


class IncrementalStreamResult:
    """Incremental streamed execution result"""

    items: list[Any] | None
    errors: list[GraphQLError] | None
    path: list[str | int] | None
    extensions: dict[str, Any] | None

    __slots__ = "errors", "extensions", "items", "label", "path"

    def __init__(
        self,
        items: list[Any] | None = None,
        errors: list[GraphQLError] | None = None,
        path: list[str | int] | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> None:
        self.items = items
        self.errors = errors
        self.path = path
        self.extensions = extensions

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = [f"items={self.items!r}, errors={self.errors!r}"]
        if self.path:
            args.append(f"path={self.path!r}")
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
        if self.extensions is not None:
            formatted["extensions"] = self.extensions
        return formatted

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return (
                (other.get("items") or None) == (self.items or None)
                and (other.get("errors") or None) == (self.errors or None)
                and (other.get("path", None) == (self.path or None))
                and (other.get("extensions", None) == (self.extensions or None))
            )
        if isinstance(other, tuple):
            size = len(other)
            return (
                1 < size < 5
                and (self.items, self.errors, self.path, self.extensions)[:size]
                == other
            )
        return (
            isinstance(other, self.__class__)
            and other.items == self.items
            and other.errors == self.errors
            and other.path == self.path
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

    hasNext: bool
    pending: list[FormattedPendingResult]
    incremental: list[FormattedIncrementalResult]
    completed: list[FormattedCompletedResult]
    extensions: dict[str, Any]


class SubsequentIncrementalExecutionResult:
    """Subsequent incremental execution result."""

    __slots__ = "completed", "extensions", "has_next", "incremental", "pending"

    has_next: bool
    pending: list[PendingResult] | None
    incremental: list[IncrementalResult] | None
    completed: list[CompletedResult] | None
    extensions: dict[str, Any] | None

    def __init__(
        self,
        has_next: bool = False,
        pending: list[PendingResult] | None = None,
        incremental: list[IncrementalResult] | None = None,
        completed: list[CompletedResult] | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> None:
        self.has_next = has_next
        self.pending = pending or []
        self.incremental = incremental
        self.completed = completed
        self.extensions = extensions

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = []
        if self.has_next:
            args.append("has_next")
        if self.pending:
            args.append(f"pending[{len(self.pending)}]")
        if self.incremental:
            args.append(f"incremental[{len(self.incremental)}]")
        if self.completed:
            args.append(f"completed[{len(self.completed)}]")
        if self.extensions:
            args.append(f"extensions={self.extensions}")
        return f"{name}({', '.join(args)})"

    @property
    def formatted(self) -> FormattedSubsequentIncrementalExecutionResult:
        """Get execution result formatted according to the specification."""
        formatted: FormattedSubsequentIncrementalExecutionResult = {}
        formatted["hasNext"] = self.has_next
        if self.pending:
            formatted["pending"] = [result.formatted for result in self.pending]
        if self.incremental:
            formatted["incremental"] = [result.formatted for result in self.incremental]
        if self.completed:
            formatted["completed"] = [result.formatted for result in self.completed]
        if self.extensions is not None:
            formatted["extensions"] = self.extensions
        return formatted

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return (
                (other.get("hasNext") or None) == (self.has_next or None)
                and (other.get("pending") or None) == (self.pending or None)
                and (other.get("incremental") or None) == (self.incremental or None)
                and (other.get("completed") or None) == (self.completed or None)
                and (other.get("extensions") or None) == (self.extensions or None)
            )
        if isinstance(other, tuple):
            size = len(other)
            return (
                1 < size < 6
                and (
                    self.has_next,
                    self.pending,
                    self.incremental,
                    self.completed,
                    self.extensions,
                )[:size]
                == other
            )
        return (
            isinstance(other, self.__class__)
            and other.has_next == self.has_next
            and self.pending == other.pending
            and other.incremental == self.incremental
            and other.completed == self.completed
            and other.extensions == self.extensions
        )

    def __ne__(self, other: object) -> bool:
        return not self == other


class InitialResult(NamedTuple):
    """The state of the initial result"""

    children: dict[IncrementalDataRecord, None]
    is_completed: bool


class IncrementalPublisher:
    """Publish incremental results.

    This class is used to publish incremental results to the client, enabling
    semi-concurrent execution while preserving result order.

    The internal publishing state is managed as follows:

    ``_released``: the set of Subsequent Result records that are ready to be sent to the
    client, i.e. their parents have completed and they have also completed.

    ``_pending``: the set of Subsequent Result records that are definitely pending, i.e.
    their parents have completed so that they can no longer be filtered. This includes
    all Subsequent Result records in `released`, as well as the records that have not
    yet completed.

    Note: Instead of sets we use dicts (with values set to None) which preserve order
    and thereby achieve more deterministic results.
    """

    _released: dict[SubsequentResultRecord, None]
    _pending: dict[SubsequentResultRecord, None]
    _resolve: Event | None

    def __init__(self) -> None:
        self._released = {}
        self._pending = {}
        self._resolve = None  # lazy initialization
        self._tasks: set[Awaitable] = set()

    @staticmethod
    def report_new_defer_fragment_record(
        deferred_fragment_record: DeferredFragmentRecord,
        parent_incremental_result_record: InitialResultRecord
        | DeferredFragmentRecord
        | StreamItemsRecord,
    ) -> None:
        """Report a new deferred fragment record."""
        parent_incremental_result_record.children[deferred_fragment_record] = None

    @staticmethod
    def report_new_deferred_grouped_filed_set_record(
        deferred_grouped_field_set_record: DeferredGroupedFieldSetRecord,
    ) -> None:
        """Report a new deferred grouped field set record."""
        for (
            deferred_fragment_record
        ) in deferred_grouped_field_set_record.deferred_fragment_records:
            deferred_fragment_record._pending[deferred_grouped_field_set_record] = None  # noqa: SLF001
            deferred_fragment_record.deferred_grouped_field_set_records[
                deferred_grouped_field_set_record
            ] = None

    @staticmethod
    def report_new_stream_items_record(
        stream_items_record: StreamItemsRecord,
        parent_incremental_data_record: IncrementalDataRecord,
    ) -> None:
        """Report a new stream items record."""
        if isinstance(parent_incremental_data_record, DeferredGroupedFieldSetRecord):
            for parent in parent_incremental_data_record.deferred_fragment_records:
                parent.children[stream_items_record] = None
        else:
            parent_incremental_data_record.children[stream_items_record] = None

    def complete_deferred_grouped_field_set(
        self,
        deferred_grouped_field_set_record: DeferredGroupedFieldSetRecord,
        data: dict[str, Any],
    ) -> None:
        """Complete the given deferred grouped field set record with the given data."""
        deferred_grouped_field_set_record.data = data
        for (
            deferred_fragment_record
        ) in deferred_grouped_field_set_record.deferred_fragment_records:
            pending = deferred_fragment_record._pending  # noqa: SLF001
            del pending[deferred_grouped_field_set_record]
            if not pending:
                self.complete_deferred_fragment_record(deferred_fragment_record)

    def mark_errored_deferred_grouped_field_set(
        self,
        deferred_grouped_field_set_record: DeferredGroupedFieldSetRecord,
        error: GraphQLError,
    ) -> None:
        """Mark the given deferred grouped field set record as errored."""
        for (
            deferred_fragment_record
        ) in deferred_grouped_field_set_record.deferred_fragment_records:
            deferred_fragment_record.errors.append(error)
            self.complete_deferred_fragment_record(deferred_fragment_record)

    def complete_deferred_fragment_record(
        self, deferred_fragment_record: DeferredFragmentRecord
    ) -> None:
        """Complete the given deferred fragment record."""
        self._release(deferred_fragment_record)

    def complete_stream_items_record(
        self,
        stream_items_record: StreamItemsRecord,
        items: list[Any],
    ) -> None:
        """Complete the given stream items record."""
        stream_items_record.items = items
        stream_items_record.is_completed = True
        self._release(stream_items_record)

    def mark_errored_stream_items_record(
        self, stream_items_record: StreamItemsRecord, error: GraphQLError
    ) -> None:
        """Mark the given stream items record as errored."""
        stream_items_record.stream_record.errors.append(error)
        self.set_is_final_record(stream_items_record)
        stream_items_record.is_completed = True
        early_return = stream_items_record.stream_record.early_return
        if early_return:
            self._add_task(early_return())
        self._release(stream_items_record)

    @staticmethod
    def set_is_final_record(stream_items_record: StreamItemsRecord) -> None:
        """Mark stream items record as final."""
        stream_items_record.is_final_record = True

    def set_is_completed_async_iterator(
        self, stream_items_record: StreamItemsRecord
    ) -> None:
        """Mark async iterator for stream items as completed."""
        stream_items_record.is_completed_async_iterator = True
        self.set_is_final_record(stream_items_record)

    def add_field_error(
        self, incremental_data_record: IncrementalDataRecord, error: GraphQLError
    ) -> None:
        """Add a field error to the given incremental data record."""
        incremental_data_record.errors.append(error)

    def build_data_response(
        self, initial_result_record: InitialResultRecord, data: dict[str, Any] | None
    ) -> ExecutionResult | ExperimentalIncrementalExecutionResults:
        """Build response for the given data."""
        for child in initial_result_record.children:
            if child.filtered:
                continue
            self._publish(child)

        errors = initial_result_record.errors or None
        if errors:
            errors.sort(
                key=lambda error: (
                    error.locations or [],
                    error.path or [],
                    error.message,
                )
            )
        pending = self._pending
        if pending:
            pending_sources: RefSet[DeferredFragmentRecord | StreamRecord] = RefSet(
                subsequent_result_record.stream_record
                if isinstance(subsequent_result_record, StreamItemsRecord)
                else subsequent_result_record
                for subsequent_result_record in pending
            )
            return ExperimentalIncrementalExecutionResults(
                initial_result=InitialIncrementalExecutionResult(
                    data,
                    errors,
                    pending=self._pending_sources_to_results(pending_sources),
                    has_next=True,
                ),
                subsequent_results=self._subscribe(),
            )
        return ExecutionResult(data, errors)

    def build_error_response(
        self, initial_result_record: InitialResultRecord, error: GraphQLError
    ) -> ExecutionResult:
        """Build response for the given error."""
        errors = initial_result_record.errors
        errors.append(error)
        # Sort the error list in order to make it deterministic, since we might have
        # been using parallel execution.
        errors.sort(
            key=lambda error: (error.locations or [], error.path or [], error.message)
        )
        return ExecutionResult(None, errors)

    def filter(
        self,
        null_path: Path | None,
        erroring_incremental_data_record: IncrementalDataRecord,
    ) -> None:
        """Filter out the given erroring incremental data record."""
        null_path_list = null_path.as_list() if null_path else []

        streams: list[StreamRecord] = []

        children = self._get_children(erroring_incremental_data_record)
        descendants = self._get_descendants(children)

        for child in descendants:
            if not self._nulls_child_subsequent_result_record(child, null_path_list):
                continue

            child.filtered = True

            if isinstance(child, StreamItemsRecord):
                streams.append(child.stream_record)

        early_returns = []
        for stream in streams:
            early_return = stream.early_return
            if early_return:
                early_returns.append(early_return())
        if early_returns:
            self._add_task(gather(*early_returns))

    def _pending_sources_to_results(
        self,
        pending_sources: RefSet[DeferredFragmentRecord | StreamRecord],
    ) -> list[PendingResult]:
        """Convert pending sources to pending results."""
        pending_results: list[PendingResult] = []
        for pending_source in pending_sources:
            pending_source.pending_sent = True
            pending_results.append(
                PendingResult(pending_source.path, pending_source.label)
            )
        return pending_results

    async def _subscribe(
        self,
    ) -> AsyncGenerator[SubsequentIncrementalExecutionResult, None]:
        """Subscribe to the incremental results."""
        is_done = False
        pending = self._pending

        await sleep(0)  # execute pending tasks

        try:
            while not is_done:
                released = self._released
                for item in released:
                    with suppress_key_error:
                        del pending[item]
                self._released = {}

                result = self._get_incremental_result(released)

                if not self._pending:
                    is_done = True

                if result is not None:
                    yield result
                else:
                    resolve = self._resolve
                    if resolve is None:
                        self._resolve = resolve = Event()
                    await resolve.wait()
        finally:
            streams: list[StreamRecord] = []
            descendants = self._get_descendants(pending)
            for subsequent_result_record in descendants:  # pragma: no cover
                if isinstance(subsequent_result_record, StreamItemsRecord):
                    streams.append(subsequent_result_record.stream_record)
            early_returns = []
            for stream in streams:  # pragma: no cover
                early_return = stream.early_return
                if early_return:
                    early_returns.append(early_return())
            if early_returns:  # pragma: no cover
                await gather(*early_returns)

    def _trigger(self) -> None:
        """Trigger the resolve event."""
        resolve = self._resolve
        if resolve is not None:
            resolve.set()
        self._resolve = Event()

    def _introduce(self, item: SubsequentResultRecord) -> None:
        """Introduce a new IncrementalDataRecord."""
        self._pending[item] = None

    def _release(self, item: SubsequentResultRecord) -> None:
        """Release the given IncrementalDataRecord."""
        if item in self._pending:
            self._released[item] = None
            self._trigger()

    def _push(self, item: SubsequentResultRecord) -> None:
        """Push the given IncrementalDataRecord."""
        self._released[item] = None
        self._pending[item] = None
        self._trigger()

    def _get_incremental_result(
        self, completed_records: Collection[SubsequentResultRecord]
    ) -> SubsequentIncrementalExecutionResult | None:
        """Get the incremental result with the completed records."""
        update = self._process_pending(completed_records)
        pending, incremental, completed = (
            update.pending,
            update.incremental,
            update.completed,
        )

        has_next = bool(self._pending)
        if not incremental and not completed and has_next:
            return None

        return SubsequentIncrementalExecutionResult(
            has_next, pending or None, incremental or None, completed or None
        )

    def _process_pending(
        self,
        completed_records: Collection[SubsequentResultRecord],
    ) -> IncrementalUpdate:
        """Process the pending records."""
        new_pending_sources: RefSet[DeferredFragmentRecord | StreamRecord] = RefSet()
        incremental_results: list[IncrementalResult] = []
        completed_results: list[CompletedResult] = []
        to_result = self._completed_record_to_result
        for subsequent_result_record in completed_records:
            for child in subsequent_result_record.children:
                if child.filtered:
                    continue
                pending_source: DeferredFragmentRecord | StreamRecord = (
                    child.stream_record
                    if isinstance(child, StreamItemsRecord)
                    else child
                )
                if not pending_source.pending_sent:
                    new_pending_sources.add(pending_source)
                self._publish(child)
            incremental_result: IncrementalResult
            if isinstance(subsequent_result_record, StreamItemsRecord):
                if subsequent_result_record.is_final_record:
                    stream_record = subsequent_result_record.stream_record
                    new_pending_sources.discard(stream_record)
                    completed_results.append(to_result(stream_record))
                if subsequent_result_record.is_completed_async_iterator:
                    # async iterable resolver finished but there may be pending payload
                    continue
                if subsequent_result_record.stream_record.errors:
                    continue
                incremental_result = IncrementalStreamResult(
                    subsequent_result_record.items,
                    subsequent_result_record.errors or None,
                    subsequent_result_record.stream_record.path,
                )
                incremental_results.append(incremental_result)
            else:
                new_pending_sources.discard(subsequent_result_record)
                completed_results.append(to_result(subsequent_result_record))
                if subsequent_result_record.errors:
                    continue
                for (
                    deferred_grouped_field_set_record
                ) in subsequent_result_record.deferred_grouped_field_set_records:
                    if not deferred_grouped_field_set_record.sent:
                        deferred_grouped_field_set_record.sent = True
                        incremental_result = IncrementalDeferResult(
                            deferred_grouped_field_set_record.data,
                            deferred_grouped_field_set_record.errors or None,
                            deferred_grouped_field_set_record.path,
                        )
                        incremental_results.append(incremental_result)
        return IncrementalUpdate(
            self._pending_sources_to_results(new_pending_sources),
            incremental_results,
            completed_results,
        )

    @staticmethod
    def _completed_record_to_result(
        completed_record: DeferredFragmentRecord | StreamRecord,
    ) -> CompletedResult:
        """Convert the completed record to a result."""
        return CompletedResult(
            completed_record.path,
            completed_record.label or None,
            completed_record.errors or None,
        )

    def _publish(self, subsequent_result_record: SubsequentResultRecord) -> None:
        """Publish the given incremental data record."""
        if isinstance(subsequent_result_record, StreamItemsRecord):
            if subsequent_result_record.is_completed:
                self._push(subsequent_result_record)
            else:
                self._introduce(subsequent_result_record)
        elif subsequent_result_record._pending:  # noqa: SLF001
            self._introduce(subsequent_result_record)
        else:
            self._push(subsequent_result_record)

    @staticmethod
    def _get_children(
        erroring_incremental_data_record: IncrementalDataRecord,
    ) -> dict[SubsequentResultRecord, None]:
        """Get the children of the given erroring incremental data record."""
        children: dict[SubsequentResultRecord, None] = {}
        if isinstance(erroring_incremental_data_record, DeferredGroupedFieldSetRecord):
            for (
                erroring_incremental_result_record
            ) in erroring_incremental_data_record.deferred_fragment_records:
                for child in erroring_incremental_result_record.children:
                    children[child] = None
        else:
            for child in erroring_incremental_data_record.children:
                children[child] = None
        return children

    def _get_descendants(
        self,
        children: dict[SubsequentResultRecord, None],
        descendants: dict[SubsequentResultRecord, None] | None = None,
    ) -> dict[SubsequentResultRecord, None]:
        """Get the descendants of the given children."""
        if descendants is None:
            descendants = {}
        for child in children:
            descendants[child] = None
            self._get_descendants(child.children, descendants)
        return descendants

    def _nulls_child_subsequent_result_record(
        self,
        subsequent_result_record: SubsequentResultRecord,
        null_path: list[str | int],
    ) -> bool:
        """Check whether the given subsequent result record is nulled."""
        incremental_data_records: (
            list[SubsequentResultRecord] | dict[DeferredGroupedFieldSetRecord, None]
        ) = (
            [subsequent_result_record]
            if isinstance(subsequent_result_record, StreamItemsRecord)
            else subsequent_result_record.deferred_grouped_field_set_records
        )
        return any(
            self._matches_path(incremental_data_record.path, null_path)
            for incremental_data_record in incremental_data_records
        )

    def _matches_path(
        self, test_path: list[str | int], base_path: list[str | int]
    ) -> bool:
        """Get whether the given test path matches the base path."""
        return all(item == test_path[i] for i, item in enumerate(base_path))

    def _add_task(self, awaitable: Awaitable[Any]) -> None:
        """Add the given task to the tasks set for later execution."""
        tasks = self._tasks
        task = ensure_future(awaitable)
        tasks.add(task)
        task.add_done_callback(tasks.discard)


class InitialResultRecord:
    """Initial result record"""

    errors: list[GraphQLError]
    children: dict[SubsequentResultRecord, None]

    def __init__(self) -> None:
        self.errors = []
        self.children = {}


class DeferredGroupedFieldSetRecord:
    """Deferred grouped field set record"""

    path: list[str | int]
    deferred_fragment_records: list[DeferredFragmentRecord]
    grouped_field_set: GroupedFieldSet
    should_initiate_defer: bool
    errors: list[GraphQLError]
    data: dict[str, Any] | None
    sent: bool

    def __init__(
        self,
        deferred_fragment_records: list[DeferredFragmentRecord],
        grouped_field_set: GroupedFieldSet,
        should_initiate_defer: bool,
        path: Path | None = None,
    ) -> None:
        self.path = path.as_list() if path else []
        self.deferred_fragment_records = deferred_fragment_records
        self.grouped_field_set = grouped_field_set
        self.should_initiate_defer = should_initiate_defer
        self.errors = []
        self.sent = False

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = [
            f"deferred_fragment_records={self.deferred_fragment_records!r}",
            f"grouped_field_set={self.grouped_field_set!r}",
        ]
        if self.path:
            args.append(f"path={self.path!r}")
        return f"{name}({', '.join(args)})"


class DeferredFragmentRecord:
    """Deferred fragment record"""

    path: list[str | int]
    label: str | None
    children: dict[SubsequentResultRecord, None]
    deferred_grouped_field_set_records: dict[DeferredGroupedFieldSetRecord, None]
    errors: list[GraphQLError]
    filtered: bool
    pending_sent: bool
    _pending: dict[DeferredGroupedFieldSetRecord, None]

    def __init__(self, path: Path | None = None, label: str | None = None) -> None:
        self.path = path.as_list() if path else []
        self.label = label
        self.children = {}
        self.filtered = False
        self.pending_sent = False
        self.deferred_grouped_field_set_records = {}
        self.errors = []
        self._pending = {}

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = []
        if self.path:
            args.append(f"path={self.path!r}")
        if self.label:
            args.append(f"label={self.label!r}")
        return f"{name}({', '.join(args)})"


class StreamRecord:
    """Stream record"""

    label: str | None
    path: list[str | int]
    errors: list[GraphQLError]
    early_return: Callable[[], Awaitable[Any]] | None
    pending_sent: bool

    def __init__(
        self,
        path: Path,
        label: str | None = None,
        early_return: Callable[[], Awaitable[Any]] | None = None,
    ) -> None:
        self.path = path.as_list()
        self.label = label
        self.errors = []
        self.early_return = early_return
        self.pending_sent = False

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = []
        if self.path:
            args.append(f"path={self.path!r}")
        if self.label:
            args.append(f"label={self.label!r}")
        return f"{name}({', '.join(args)})"


class StreamItemsRecord:
    """Stream items record"""

    errors: list[GraphQLError]
    stream_record: StreamRecord
    path: list[str | int]
    items: list[str]
    children: dict[SubsequentResultRecord, None]
    is_final_record: bool
    is_completed_async_iterator: bool
    is_completed: bool
    filtered: bool

    def __init__(
        self,
        stream_record: StreamRecord,
        path: Path | None = None,
    ) -> None:
        self.stream_record = stream_record
        self.path = path.as_list() if path else []
        self.children = {}
        self.errors = []
        self.is_completed_async_iterator = self.is_completed = False
        self.is_final_record = self.filtered = False
        self.items = []

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = [f"stream_record={self.stream_record!r}"]
        if self.path:
            args.append(f"path={self.path!r}")
        return f"{name}({', '.join(args)})"


IncrementalDataRecord = Union[
    InitialResultRecord, DeferredGroupedFieldSetRecord, StreamItemsRecord
]

SubsequentResultRecord = Union[DeferredFragmentRecord, StreamItemsRecord]
