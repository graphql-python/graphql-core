"""Types needed for GraphQL execution"""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Awaitable,
    Iterator,
    NamedTuple,
    Union,
)

try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict

if TYPE_CHECKING:
    from ..error import GraphQLError, GraphQLFormattedError
    from ..pyutils import AwaitableOrValue, Path

    try:
        from typing import TypeGuard
    except ImportError:  # Python < 3.10
        from typing_extensions import TypeGuard
    try:
        from typing import NotRequired
    except ImportError:  # Python < 3.11
        from typing_extensions import NotRequired

__all__ = [
    "BareDeferredGroupedFieldSetResult",
    "BareStreamItemsResult",
    "DeferredFragmentRecord",
    "ExecutionResult",
    "ExperimentalIncrementalExecutionResults",
    "FormattedExecutionResult",
    "FormattedIncrementalDeferResult",
    "FormattedIncrementalResult",
    "FormattedIncrementalStreamResult",
    "FormattedInitialIncrementalExecutionResult",
    "FormattedPendingResult",
    "FormattedSubsequentIncrementalExecutionResult",
    "IncrementalDataRecord",
    "IncrementalDeferResult",
    "IncrementalResult",
    "IncrementalStreamResult",
    "InitialIncrementalExecutionResult",
    "NonReconcilableStreamItemsResult",
    "PendingResult",
    "ReconcilableStreamItemsResult",
    "StreamItemsRecord",
    "StreamItemsResult",
    "SubsequentIncrementalExecutionResult",
    "SubsequentResultRecord",
    "TerminatingStreamItemsResult",
    "is_cancellable_stream_record",
    "is_deferred_fragment_record",
    "is_deferred_grouped_field_set_record",
    "is_deferred_grouped_field_set_result",
    "is_non_reconcilable_deferred_grouped_field_set_result",
    "is_reconcilable_stream_items_result",
]


class ExecutionResult:  # noqa: PLW1641
    """The result of GraphQL execution.

    - ``data`` is the result of a successful execution of the query.
    - ``errors`` is included when any errors occurred as a non-empty list.
    - ``extensions`` is reserved for adding non-standard properties.
    """

    data: dict[str, Any] | None
    errors: list[GraphQLError] | None
    extensions: dict[str, Any] | None

    __slots__ = "data", "errors", "extensions"

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
        ext = "" if self.extensions is None else f", extensions={self.extensions!r}"
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


class FormattedExecutionResult(TypedDict, total=False):
    """Formatted execution result"""

    data: dict[str, Any] | None
    errors: list[GraphQLFormattedError]
    extensions: dict[str, Any]


class ExperimentalIncrementalExecutionResults(NamedTuple):
    """Execution results when retrieved incrementally."""

    initial_result: InitialIncrementalExecutionResult
    subsequent_results: AsyncGenerator[SubsequentIncrementalExecutionResult, None]


class InitialIncrementalExecutionResult:  # noqa: PLW1641
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
        args: list[str] = [f"data={self.data!r}"]
        if self.errors:
            args.append(f"errors={self.errors!r}")
        if self.pending:
            args.append(f"pending={self.pending!r}")
        if self.has_next:
            args.append("has_next")
        if self.extensions:
            args.append(f"extensions={self.extensions!r}")
        return f"{name}({', '.join(args)})"

    @property
    def formatted(self) -> FormattedInitialIncrementalExecutionResult:
        """Get execution result formatted according to the specification."""
        formatted: FormattedInitialIncrementalExecutionResult = {"data": self.data}  # type: ignore
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


class FormattedIncrementalDeferResult(TypedDict):
    """Formatted incremental deferred execution result"""

    errors: NotRequired[list[GraphQLFormattedError]]
    data: dict[str, Any]
    id: str
    subPath: NotRequired[list[str | int]]
    extensions: NotRequired[dict[str, Any]]


class SubsequentIncrementalExecutionResult:  # noqa: PLW1641
    """Subsequent incremental execution result."""

    pending: list[PendingResult] | None
    incremental: list[IncrementalResult] | None
    completed: list[CompletedResult] | None
    has_next: bool
    extensions: dict[str, Any] | None

    __slots__ = "completed", "extensions", "has_next", "incremental", "pending"

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
            args.append(f"extensions={self.extensions!r}")
        return f"{name}({', '.join(args)})"

    @property
    def formatted(self) -> FormattedSubsequentIncrementalExecutionResult:
        """Get execution result formatted according to the specification."""
        formatted: FormattedSubsequentIncrementalExecutionResult = {
            "hasNext": self.has_next
        }
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


class FormattedPendingResult(TypedDict):
    """Formatted pending execution result"""

    id: str
    path: list[str | int]
    label: NotRequired[str]


class FormattedSubsequentIncrementalExecutionResult(TypedDict):
    """Formatted subsequent incremental execution result"""

    pending: NotRequired[list[FormattedPendingResult]]
    incremental: NotRequired[list[FormattedIncrementalResult]]
    completed: NotRequired[list[FormattedCompletedResult]]
    hasNext: bool
    extensions: NotRequired[dict[str, Any]]


class BareDeferredGroupedFieldSetResult:
    """Bare deferred grouped field set result."""

    errors: list[GraphQLError] | None
    data: dict[str, Any]

    __slots__ = "data", "errors"

    def __init__(
        self, data: dict[str, Any], errors: list[GraphQLError] | None = None
    ) -> None:
        self.data = data
        self.errors = errors


class IncrementalDeferResult(BareDeferredGroupedFieldSetResult):  # noqa: PLW1641
    """Incremental deferred execution result"""

    id: str
    sub_path: list[str | int] | None
    extensions: dict[str, Any] | None

    __slots__ = "extensions", "id", "sub_path"

    def __init__(
        self,
        data: dict[str, Any],
        id: str,  # noqa: A002
        sub_path: list[str | int] | None = None,
        errors: list[GraphQLError] | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> None:
        self.data = data
        self.id = id
        self.sub_path = sub_path
        self.errors = errors
        self.extensions = extensions

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = [f"data={self.data!r}, id={self.id!r}"]
        if self.sub_path is not None:
            args.append(f"sub_path={self.sub_path!r}")
        if self.errors is not None:
            args.append(f"errors={self.errors!r}")
        if self.extensions is not None:
            args.append(f"extensions={self.extensions!r}")
        return f"{name}({', '.join(args)})"

    @property
    def formatted(self) -> FormattedIncrementalDeferResult:
        """Get execution result formatted according to the specification."""
        formatted: FormattedIncrementalDeferResult = {
            "data": self.data,
            "id": self.id,
        }
        if self.sub_path is not None:
            formatted["subPath"] = self.sub_path
        if self.errors is not None:
            formatted["errors"] = [error.formatted for error in self.errors]
        if self.extensions is not None:
            formatted["extensions"] = self.extensions
        return formatted

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return (
                other.get("data") == self.data
                and other.get("id") == self.id
                and (other.get("subPath") or None) == (self.sub_path or None)
                and (other.get("errors") or None) == (self.errors or None)
                and (other.get("extensions") or None) == (self.extensions or None)
            )
        if isinstance(other, tuple):
            size = len(other)
            return (
                1 < size < 6
                and (self.data, self.id, self.sub_path, self.errors, self.extensions)[
                    :size
                ]
                == other
            )
        return (
            isinstance(other, self.__class__)
            and other.data == self.data
            and other.id == self.id
            and other.sub_path == self.sub_path
            and other.errors == self.errors
            and other.extensions == self.extensions
        )

    def __ne__(self, other: object) -> bool:
        return not self == other


class FormattedInitialIncrementalExecutionResult(TypedDict):
    """Formatted initial incremental execution result"""

    data: NotRequired[dict[str, Any] | None]
    errors: NotRequired[list[GraphQLFormattedError]]
    pending: list[FormattedPendingResult]
    hasNext: bool
    incremental: list[FormattedIncrementalResult]
    extensions: NotRequired[dict[str, Any]]


class BareStreamItemsResult:
    """Bare stream items result."""

    errors: list[GraphQLError] | None
    items: list[Any]

    __slots__ = "errors", "items"

    def __init__(
        self,
        items: list[Any],
        errors: list[GraphQLError] | None = None,
    ) -> None:
        self.items = items
        self.errors = errors


class IncrementalStreamResult(BareStreamItemsResult):
    """Incremental streamed execution result"""

    id: str
    sub_path: list[str | int] | None
    extensions: dict[str, Any] | None

    __slots__ = "extensions", "id", "sub_path"

    def __init__(
        self,
        items: list[Any],
        id: str,  # noqa: A002
        sub_path: list[str | int] | None = None,
        errors: list[GraphQLError] | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> None:
        self.items = items
        self.id = id
        self.sub_path = sub_path
        self.errors = errors
        self.extensions = extensions

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = [f"items={self.items!r}, id={self.id!r}"]
        if self.sub_path is not None:
            args.append(f"sub_path={self.sub_path!r}")
        if self.errors is not None:
            args.append(f"errors={self.errors!r}")
        if self.extensions is not None:
            args.append(f"extensions={self.extensions!r}")
        return f"{name}({', '.join(args)})"

    @property
    def formatted(self) -> FormattedIncrementalStreamResult:
        """Get execution result formatted according to the specification."""
        formatted: FormattedIncrementalStreamResult = {
            "items": self.items,
            "id": self.id,
        }
        if self.sub_path is not None:
            formatted["subPath"] = self.sub_path
        if self.errors is not None:
            formatted["errors"] = [error.formatted for error in self.errors]
        if self.extensions is not None:
            formatted["extensions"] = self.extensions
        return formatted

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return (
                other.get("items") == self.items
                and other.get("id") == self.id
                and (other.get("subPath", None) == (self.sub_path or None))
                and (other.get("errors") or None) == (self.errors or None)
                and (other.get("extensions", None) == (self.extensions or None))
            )
        if isinstance(other, tuple):
            size = len(other)
            return (
                1 < size < 6
                and (self.items, self.id, self.sub_path, self.errors, self.extensions)[
                    :size
                ]
                == other
            )
        return (
            isinstance(other, self.__class__)
            and other.items == self.items
            and other.id == self.id
            and other.sub_path == self.sub_path
            and other.errors == self.errors
            and other.extensions == self.extensions
        )

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __hash__(self) -> int:
        sub_path = self.sub_path
        errors = self.errors
        extensions = self.extensions
        return hash(
            (
                tuple(self.items),
                self.id,
                None if sub_path is None else tuple(sub_path),
                None if errors is None else tuple(errors),
                None if extensions is None else tuple(extensions.items()),
            )
        )


class FormattedIncrementalStreamResult(TypedDict):
    """Formatted incremental stream execution result"""

    errors: NotRequired[list[GraphQLFormattedError]]
    items: list[Any]
    id: str
    subPath: NotRequired[list[str | int]]
    extensions: NotRequired[dict[str, Any]]


IncrementalResult = Union[IncrementalDeferResult, IncrementalStreamResult]

FormattedIncrementalResult = Union[
    FormattedIncrementalDeferResult, FormattedIncrementalStreamResult
]


class PendingResult:  # noqa: PLW1641
    """Pending execution result"""

    id: str
    path: list[str | int]
    label: str | None

    __slots__ = "id", "label", "path"

    def __init__(
        self,
        id: str,  # noqa: A002
        path: list[str | int],
        label: str | None = None,
    ) -> None:
        self.id = id
        self.path = path
        self.label = label

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = [f"id={self.id!r}, path={self.path!r}"]
        if self.label:
            args.append(f"label={self.label!r}")
        return f"{name}({', '.join(args)})"

    @property
    def formatted(self) -> FormattedPendingResult:
        """Get pending result formatted according to the specification."""
        formatted: FormattedPendingResult = {"id": self.id, "path": self.path}
        if self.label is not None:
            formatted["label"] = self.label
        return formatted

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return (
                other.get("id") == self.id
                and (other.get("path") or None) == (self.path or None)
                and (other.get("label") or None) == (self.label or None)
            )

        if isinstance(other, tuple):
            size = len(other)
            return 1 < size < 4 and (self.id, self.path, self.label)[:size] == other
        return (
            isinstance(other, self.__class__)
            and other.id == self.id
            and other.path == self.path
            and other.label == self.label
        )

    def __ne__(self, other: object) -> bool:
        return not self == other


class CompletedResult:  # noqa: PLW1641
    """Completed execution result"""

    id: str
    errors: list[GraphQLError] | None

    __slots__ = "errors", "id"

    def __init__(
        self,
        id: str,  # noqa: A002
        errors: list[GraphQLError] | None = None,
    ) -> None:
        self.id = id
        self.errors = errors

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = [f"id={self.id!r}"]
        if self.errors:
            args.append(f"errors={self.errors!r}")
        return f"{name}({', '.join(args)})"

    @property
    def formatted(self) -> FormattedCompletedResult:
        """Get completed result formatted according to the specification."""
        formatted: FormattedCompletedResult = {"id": self.id}
        if self.errors is not None:
            formatted["errors"] = [error.formatted for error in self.errors]
        return formatted

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return other.get("id") == self.id and (other.get("errors") or None) == (
                self.errors or None
            )
        if isinstance(other, tuple):
            size = len(other)
            return 1 < size < 3 and (self.id, self.errors)[:size] == other
        return (
            isinstance(other, self.__class__)
            and other.id == self.id
            and other.errors == self.errors
        )

    def __ne__(self, other: object) -> bool:
        return not self == other


class FormattedCompletedResult(TypedDict):
    """Formatted completed execution result"""

    id: str
    errors: NotRequired[list[GraphQLFormattedError]]


def is_deferred_fragment_record(
    subsequent_result_record: SubsequentResultRecord,
) -> TypeGuard[DeferredFragmentRecord]:
    """Check if the subsequent result record is a deferred fragment record."""
    return isinstance(subsequent_result_record, DeferredFragmentRecord)


def is_deferred_grouped_field_set_record(
    incremental_data_record: IncrementalDataRecord,
) -> TypeGuard[DeferredGroupedFieldSetRecord]:
    """Check if the incremental data record is a deferred grouped field set record."""
    return isinstance(incremental_data_record, DeferredGroupedFieldSetRecord)


class ReconcilableDeferredGroupedFieldSetResult:
    """Reconcilable deferred grouped field set result"""

    deferred_fragment_records: list[DeferredFragmentRecord]
    path: list[str | int]
    result: BareDeferredGroupedFieldSetResult
    incremental_data_records: list[IncrementalDataRecord] | None
    sent: bool
    errors: None = None

    __slots__ = (
        "deferred_fragment_records",
        "incremental_data_records",
        "path",
        "result",
        "sent",
    )

    def __init__(
        self,
        deferred_fragment_records: list[DeferredFragmentRecord],
        path: list[str | int],
        result: BareDeferredGroupedFieldSetResult,
        incremental_data_records: list[IncrementalDataRecord] | None = None,
    ) -> None:
        self.deferred_fragment_records = deferred_fragment_records
        self.path = path
        self.result = result
        self.incremental_data_records = incremental_data_records
        self.sent = False


class NonReconcilableDeferredGroupedFieldSetResult:
    """Non-reconcilable deferred grouped field set result"""

    errors: list[GraphQLError]
    deferred_fragment_records: list[DeferredFragmentRecord]
    path: list[str | int]
    result: None = None

    __slots__ = "deferred_fragment_records", "errors", "path"

    def __init__(
        self,
        deferred_fragment_records: list[DeferredFragmentRecord],
        path: list[str | int],
        errors: list[GraphQLError],
    ) -> None:
        self.deferred_fragment_records = deferred_fragment_records
        self.path = path
        self.errors = errors


def is_non_reconcilable_deferred_grouped_field_set_result(
    deferred_grouped_field_set_result: DeferredGroupedFieldSetResult,
) -> TypeGuard[NonReconcilableDeferredGroupedFieldSetResult]:
    """Check if the deferred grouped field set result is non-reconcilable."""
    return isinstance(
        deferred_grouped_field_set_result, NonReconcilableDeferredGroupedFieldSetResult
    )


DeferredGroupedFieldSetResult = Union[
    ReconcilableDeferredGroupedFieldSetResult,
    NonReconcilableDeferredGroupedFieldSetResult,
]


def is_deferred_grouped_field_set_result(
    subsequent_result: DeferredGroupedFieldSetResult | StreamItemsResult,
) -> TypeGuard[DeferredGroupedFieldSetResult]:
    """Check if the subsequent result is a deferred grouped field set result."""
    return isinstance(
        subsequent_result,
        (
            ReconcilableDeferredGroupedFieldSetResult,
            NonReconcilableDeferredGroupedFieldSetResult,
        ),  # we could use the union type here in Python >= 3.10
    )


class DeferredGroupedFieldSetRecord:
    """Deferred grouped field set record"""

    deferred_fragment_records: list[DeferredFragmentRecord]
    result: AwaitableOrValue[DeferredGroupedFieldSetResult]

    __slots__ = "deferred_fragment_records", "result"

    def __init__(
        self,
        deferred_fragment_records: list[DeferredFragmentRecord],
        result: AwaitableOrValue[DeferredGroupedFieldSetResult],
    ) -> None:
        self.result = result
        self.deferred_fragment_records = deferred_fragment_records


class SubsequentResultRecord:
    """Subsequent result record"""

    path: Path | None
    label: str | None
    id: str | None

    __slots__ = "id", "label", "path"

    def __init__(self, path: Path | None, label: str | None = None) -> None:
        self.path = path
        self.label = label
        self.id = None

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: list[str] = []
        if self.path:
            args.append(f"path={self.path.as_list()!r}")
        if self.label:
            args.append(f"label={self.label!r}")
        return f"{name}({', '.join(args)})"


class DeferredFragmentRecord(SubsequentResultRecord):
    """Deferred fragment record

    For internal use only.
    """

    parent: DeferredFragmentRecord | None
    expected_reconcilable_results: int
    results: list[DeferredGroupedFieldSetResult]
    reconcilable_results: list[ReconcilableDeferredGroupedFieldSetResult]
    children: dict[DeferredFragmentRecord, None]

    __slots__ = (
        "children",
        "expected_reconcilable_results",
        "parent",
        "reconcilable_results",
        "results",
    )

    def __init__(
        self,
        path: Path | None = None,
        label: str | None = None,
        parent: DeferredFragmentRecord | None = None,
    ) -> None:
        super().__init__(path, label)
        self.parent = parent
        self.expected_reconcilable_results = 0
        self.results = []
        self.reconcilable_results = []
        self.children = {}


class CancellableStreamRecord(SubsequentResultRecord):
    """Cancellable stream record"""

    early_return: Awaitable[None]

    __slots__ = ("early_return",)

    def __init__(
        self,
        early_return: Awaitable[None],
        path: Path | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(path, label)
        self.early_return = early_return


def is_cancellable_stream_record(
    subsequent_result_record: SubsequentResultRecord,
) -> TypeGuard[CancellableStreamRecord]:
    """Check if the subsequent result record is a cancellable stream record."""
    return isinstance(subsequent_result_record, CancellableStreamRecord)


class ReconcilableStreamItemsResult(NamedTuple):
    """Reconcilable stream items result"""

    stream_record: SubsequentResultRecord
    result: BareStreamItemsResult
    incremental_data_records: list[IncrementalDataRecord] | None = None
    errors: None = None


def is_reconcilable_stream_items_result(
    stream_items_result: StreamItemsResult,
) -> TypeGuard[ReconcilableStreamItemsResult]:
    """Check if a stream items result is reconcilable."""
    return isinstance(stream_items_result, ReconcilableStreamItemsResult)


class TerminatingStreamItemsResult(NamedTuple):
    """Terminating stream items result"""

    stream_record: SubsequentResultRecord
    result: None = None
    incremental_data_record: None = None
    errors: None = None


class NonReconcilableStreamItemsResult(NamedTuple):
    """Non-reconcilable stream items result"""

    stream_record: SubsequentResultRecord
    errors: list[GraphQLError]
    result: None = None


StreamItemsResult = Union[
    ReconcilableStreamItemsResult,
    TerminatingStreamItemsResult,
    NonReconcilableStreamItemsResult,
]


class StreamItemsRecord:
    """Stream items record"""

    __slots__ = "result", "stream_record"

    stream_record: SubsequentResultRecord
    result: AwaitableOrValue[StreamItemsResult]

    def __init__(
        self,
        stream_record: SubsequentResultRecord,
        result: AwaitableOrValue[StreamItemsResult],
    ) -> None:
        self.stream_record = stream_record
        self.result = result


IncrementalDataRecord = Union[DeferredGroupedFieldSetRecord, StreamItemsRecord]

IncrementalDataRecordResult = Union[DeferredGroupedFieldSetResult, StreamItemsResult]
