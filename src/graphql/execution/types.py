"""Types needed for GraphQL execution"""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    NamedTuple,
    TypeAlias,
    TypedDict,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator

    from ..error import GraphQLError, GraphQLFormattedError

    try:
        from typing import NotRequired
    except ImportError:  # Python < 3.11
        from typing_extensions import NotRequired

__all__ = [
    "CompletedResult",
    "ExecutionResult",
    "ExperimentalIncrementalExecutionResults",
    "FormattedCompletedResult",
    "FormattedExecutionResult",
    "FormattedIncrementalDeferResult",
    "FormattedIncrementalResult",
    "FormattedIncrementalStreamResult",
    "FormattedInitialIncrementalExecutionResult",
    "FormattedPendingResult",
    "FormattedSubsequentIncrementalExecutionResult",
    "IncrementalDeferResult",
    "IncrementalResult",
    "IncrementalStreamResult",
    "InitialIncrementalExecutionResult",
    "PendingResult",
    "SubsequentIncrementalExecutionResult",
]


class ExecutionResult:  # noqa: PLW1641
    """The result of GraphQL execution.

    Represents the response produced by executing a GraphQL operation.

    - ``data`` is the result of a successful execution of the query.
    - ``errors`` is included when any errors occurred as a non-empty list.
    - ``extensions`` is reserved for adding non-standard properties.

    :param data: Data returned by execution, or None when execution could not produce
        data.
    :param errors: Errors raised while parsing, validating, or executing the operation.
    :param extensions: Extension fields to include in the formatted result.

    >>> from graphql import ExecutionResult, GraphQLError
    >>> result = ExecutionResult(
    ...     data={'greeting': None},
    ...     errors=[GraphQLError('Resolver failed.', path=['greeting'])],
    ...     extensions={'cost': 1},
    ... )
    >>> result.data
    {'greeting': None}
    >>> result.formatted
    {'data': {'greeting': None},
     'errors': [{'message': 'Resolver failed.', 'path': ['greeting']}],
     'extensions': {'cost': 1}}

    For backward compatibility, the result can also be unpacked as a tuple:

    >>> data, errors = result
    >>> errors[0].message
    'Resolver failed.'
    """

    data: dict[str, Any] | None
    """Data returned by execution, or None when execution could not produce data."""

    errors: list[GraphQLError] | None
    """Errors raised while parsing, validating, or executing the operation."""

    extensions: dict[str, Any] | None
    """Extension fields to include in the formatted result."""

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
    """Formatted execution result

    A JSON-serializable GraphQL execution result.
    """

    data: dict[str, Any] | None
    """Data returned by execution, or None when execution could not produce data."""

    errors: list[GraphQLFormattedError]
    """Errors raised while parsing, validating, or executing the operation."""

    extensions: dict[str, Any]
    """Extension fields to include in the formatted result."""


class ExperimentalIncrementalExecutionResults(NamedTuple):
    """Execution results when retrieved incrementally.

    Results for an operation that produced incremental payloads.
    """

    initial_result: InitialIncrementalExecutionResult
    """Initial execution result delivered before subsequent incremental payloads."""

    subsequent_results: AsyncGenerator[SubsequentIncrementalExecutionResult, None]
    """Async stream of incremental payloads delivered after the initial result."""


class InitialIncrementalExecutionResult:  # noqa: PLW1641
    """Initial incremental execution result.

    Initial execution result for an operation that produced incremental payloads.

    :param data: Data produced by the initial execution payload.
    :param errors: Errors raised while parsing, validating, or executing the operation.
    :param pending: Incremental payloads that are still pending after the initial
        result.
    :param has_next: Indicates that subsequent incremental payloads will follow.
    :param extensions: Additional non-standard metadata included in the initial
        result.

    >>> from graphql import InitialIncrementalExecutionResult
    >>> from graphql.execution import PendingResult
    >>> result = InitialIncrementalExecutionResult(
    ...     data={'greeting': 'Hello'},
    ...     pending=[PendingResult(id='0', path=[])],
    ...     has_next=True,
    ... )
    >>> result.formatted
    {'data': {'greeting': 'Hello'}, 'pending': [{'id': '0', 'path': []}],
     'hasNext': True}
    """

    data: dict[str, Any] | None
    """Data produced by the initial execution payload."""

    errors: list[GraphQLError] | None
    """Errors raised while parsing, validating, or executing the operation."""

    pending: list[PendingResult]
    """Incremental payloads that are still pending after the initial result."""

    has_next: bool
    """Indicates that subsequent incremental payloads will follow."""

    extensions: dict[str, Any] | None
    """Additional non-standard metadata included in the initial result."""

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
    """Formatted incremental deferred execution result

    JSON-serializable form of a deferred fragment payload.
    """

    errors: NotRequired[list[GraphQLFormattedError]]
    """Formatted errors raised while executing the deferred fragment."""

    data: dict[str, Any]
    """Formatted data produced by the deferred fragment."""

    id: str
    """Identifier matching this payload to a pending deferred fragment."""

    subPath: NotRequired[list[str | int]]
    """Path from the deferred fragment location to this payload."""

    extensions: NotRequired[dict[str, Any]]
    """Additional non-standard metadata included in this formatted payload."""


class SubsequentIncrementalExecutionResult:  # noqa: PLW1641
    """Subsequent incremental execution result.

    Subsequent payload produced by incremental execution.

    :param has_next: Indicates whether more incremental payloads will follow.
    :param pending: Incremental payloads that became pending with this response.
    :param incremental: Deferred or streamed payloads delivered by this response.
    :param completed: Incremental payloads that completed with this response.
    :param extensions: Additional non-standard metadata included in this payload.

    >>> from graphql import IncrementalDeferResult, SubsequentIncrementalExecutionResult
    >>> from graphql.execution import CompletedResult
    >>> result = SubsequentIncrementalExecutionResult(
    ...     has_next=False,
    ...     incremental=[IncrementalDeferResult(data={'name': 'Ada'}, id='0')],
    ...     completed=[CompletedResult(id='0')],
    ... )
    >>> result.formatted
    {'hasNext': False, 'incremental': [{'data': {'name': 'Ada'}, 'id': '0'}],
     'completed': [{'id': '0'}]}
    """

    pending: list[PendingResult] | None
    """Incremental payloads that became pending with this response."""

    incremental: list[IncrementalResult] | None
    """Deferred or streamed payloads delivered by this response."""

    completed: list[CompletedResult] | None
    """Incremental payloads that completed with this response."""

    has_next: bool
    """Indicates whether more incremental payloads will follow."""

    extensions: dict[str, Any] | None
    """Additional non-standard metadata included in this payload."""

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
    """Formatted pending execution result

    JSON-serializable form of a pending incremental payload.
    """

    id: str
    """Identifier of the pending deferred fragment or stream."""

    path: list[str | int]
    """Path to the location of the deferred fragment or streamed list field."""

    label: NotRequired[str]
    """Label of the ``@defer`` or ``@stream`` directive, if one was supplied."""


class FormattedSubsequentIncrementalExecutionResult(TypedDict):
    """Formatted subsequent incremental execution result

    JSON-serializable form of a subsequent incremental execution payload.
    """

    pending: NotRequired[list[FormattedPendingResult]]
    """Formatted incremental payloads that became pending with this response."""

    incremental: NotRequired[list[FormattedIncrementalResult]]
    """Formatted deferred or streamed payloads delivered by this response."""

    completed: NotRequired[list[FormattedCompletedResult]]
    """Formatted incremental payloads that completed with this response."""

    hasNext: bool
    """Indicates whether more incremental payloads will follow."""

    extensions: NotRequired[dict[str, Any]]
    """Additional non-standard metadata included in this formatted payload."""


class IncrementalDeferResult:  # noqa: PLW1641
    """Incremental deferred execution result

    Incremental payload produced by a deferred fragment.

    :param data: Data produced by the deferred fragment.
    :param id: Identifier matching this payload to a pending deferred fragment.
    :param sub_path: Path from the deferred fragment location to this payload.
    :param errors: Errors raised while executing the deferred fragment.
    :param extensions: Additional non-standard metadata included in this payload.

    >>> from graphql import IncrementalDeferResult
    >>> result = IncrementalDeferResult(
    ...     data={'name': 'Ada'}, id='0', sub_path=['viewer']
    ... )
    >>> result.formatted
    {'data': {'name': 'Ada'}, 'id': '0', 'subPath': ['viewer']}
    """

    data: dict[str, Any]
    """Data produced by the deferred fragment."""

    id: str
    """Identifier matching this payload to a pending deferred fragment."""

    sub_path: list[str | int] | None
    """Path from the deferred fragment location to this payload."""

    errors: list[GraphQLError] | None
    """Errors raised while executing the deferred fragment."""

    extensions: dict[str, Any] | None
    """Additional non-standard metadata included in this payload."""

    __slots__ = "data", "errors", "extensions", "id", "sub_path"

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
    """Formatted initial incremental execution result

    JSON-serializable form of an initial incremental execution result.
    """

    data: NotRequired[dict[str, Any] | None]
    """Formatted data produced by the initial execution payload."""

    errors: NotRequired[list[GraphQLFormattedError]]
    """Errors raised while parsing, validating, or executing the operation."""

    pending: list[FormattedPendingResult]
    """Formatted list of incremental payloads still pending after the initial result."""

    hasNext: bool
    """Indicates whether subsequent incremental payloads will follow."""

    extensions: NotRequired[dict[str, Any]]
    """Additional non-standard metadata included in the formatted initial result."""


class IncrementalStreamResult:
    """Incremental streamed execution result

    Incremental payload produced by a streamed list field.

    :param items: Streamed list items delivered by this payload.
    :param id: Identifier matching this payload to a pending stream.
    :param sub_path: Path from the streamed field location to these items.
    :param errors: Errors raised while producing streamed items.
    :param extensions: Additional non-standard metadata included in this payload.

    >>> from graphql import IncrementalStreamResult
    >>> result = IncrementalStreamResult(items=['b', 'c'], id='0')
    >>> result.formatted
    {'items': ['b', 'c'], 'id': '0'}
    """

    items: list[Any]
    """Streamed list items delivered by this payload."""

    id: str
    """Identifier matching this payload to a pending stream."""

    sub_path: list[str | int] | None
    """Path from the streamed field location to these items."""

    errors: list[GraphQLError] | None
    """Errors raised while producing streamed items."""

    extensions: dict[str, Any] | None
    """Additional non-standard metadata included in this payload."""

    __slots__ = "errors", "extensions", "id", "items", "sub_path"

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
    """Formatted incremental stream execution result

    JSON-serializable form of a streamed list payload.
    """

    errors: NotRequired[list[GraphQLFormattedError]]
    """Formatted errors raised while producing streamed items."""

    items: list[Any]
    """Formatted streamed list items delivered by this payload."""

    id: str
    """Identifier matching this payload to a pending stream."""

    subPath: NotRequired[list[str | int]]
    """Path from the streamed field location to these items."""

    extensions: NotRequired[dict[str, Any]]
    """Additional non-standard metadata included in this formatted payload."""


IncrementalResult: TypeAlias = IncrementalDeferResult | IncrementalStreamResult

FormattedIncrementalResult: TypeAlias = (
    FormattedIncrementalDeferResult | FormattedIncrementalStreamResult
)


class PendingResult:  # noqa: PLW1641
    """Pending execution result

    A deferred fragment or stream that became pending, announced in the
    ``pending`` list of an initial or subsequent incremental execution result.

    :param id: Identifier of the pending deferred fragment or stream.
    :param path: Path to the location of the deferred fragment or streamed list
        field.
    :param label: Label of the ``@defer`` or ``@stream`` directive, if one was
        supplied.

    >>> from graphql.execution import PendingResult
    >>> result = PendingResult(id='0', path=['names'], label='NamesStream')
    >>> result.formatted
    {'id': '0', 'path': ['names'], 'label': 'NamesStream'}
    """

    id: str
    """Identifier of the pending deferred fragment or stream."""

    path: list[str | int]
    """Path to the location of the deferred fragment or streamed list field."""

    label: str | None
    """Label of the ``@defer`` or ``@stream`` directive, if one was supplied."""

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
    """Completed execution result

    A deferred fragment or stream that completed, announced in the ``completed``
    list of a subsequent incremental execution result.

    :param id: Identifier matching this result to a pending deferred fragment or
        stream.
    :param errors: Errors that caused the deferred fragment or stream to fail, if
        any.

    >>> from graphql import GraphQLError
    >>> from graphql.execution import CompletedResult
    >>> result = CompletedResult(id='0', errors=[GraphQLError('Stream failed.')])
    >>> result.formatted
    {'id': '0', 'errors': [{'message': 'Stream failed.'}]}
    """

    id: str
    """Identifier matching this result to a pending deferred fragment or stream."""

    errors: list[GraphQLError] | None
    """Errors that caused the deferred fragment or stream to fail, if any."""

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
    """Formatted completed execution result

    JSON-serializable form of a completed incremental payload.
    """

    id: str
    """Identifier matching this result to a pending deferred fragment or stream."""

    errors: NotRequired[list[GraphQLFormattedError]]
    """Formatted errors that caused the deferred fragment or stream to fail."""
