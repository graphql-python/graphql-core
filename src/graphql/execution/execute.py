from __future__ import annotations  # Python < 3.10

from asyncio import Event, as_completed, ensure_future, gather, shield, sleep, wait_for
from collections.abc import Mapping
from contextlib import suppress
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
    cast,
)


try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict
try:
    from typing import TypeAlias, TypeGuard
except ImportError:  # Python < 3.10
    from typing_extensions import TypeAlias, TypeGuard
try:  # only needed for Python < 3.11
    # noinspection PyCompatibility
    from asyncio.exceptions import TimeoutError
except ImportError:  # Python < 3.7
    from concurrent.futures import TimeoutError  # type: ignore

from ..error import GraphQLError, GraphQLFormattedError, located_error
from ..language import (
    DocumentNode,
    FieldNode,
    FragmentDefinitionNode,
    OperationDefinitionNode,
    OperationType,
)
from ..pyutils import AwaitableOrValue, Path, Undefined, async_reduce, inspect
from ..pyutils import is_awaitable as default_is_awaitable
from ..pyutils import is_iterable
from ..type import (
    GraphQLAbstractType,
    GraphQLField,
    GraphQLFieldResolver,
    GraphQLLeafType,
    GraphQLList,
    GraphQLObjectType,
    GraphQLOutputType,
    GraphQLResolveInfo,
    GraphQLSchema,
    GraphQLStreamDirective,
    GraphQLTypeResolver,
    assert_valid_schema,
    is_abstract_type,
    is_leaf_type,
    is_list_type,
    is_non_null_type,
    is_object_type,
)
from .async_iterables import flatten_async_iterable, map_async_iterable
from .collect_fields import FieldsAndPatches, collect_fields, collect_subfields
from .middleware import MiddlewareManager
from .values import get_argument_values, get_directive_values, get_variable_values


ASYNC_DELAY = 1 / 512  # wait time in seconds for deferring execution


try:  # pragma: no cover
    anext
except NameError:  # pragma: no cover (Python < 3.10)
    # noinspection PyShadowingBuiltins
    async def anext(iterator: AsyncIterator) -> Any:
        """Return the next item from an async iterator."""
        return await iterator.__anext__()


__all__ = [
    "ASYNC_DELAY",
    "create_source_event_stream",
    "default_field_resolver",
    "default_type_resolver",
    "execute",
    "execute_sync",
    "experimental_execute_incrementally",
    "experimental_subscribe_incrementally",
    "subscribe",
    "AsyncPayloadRecord",
    "DeferredFragmentRecord",
    "StreamRecord",
    "ExecutionResult",
    "ExecutionContext",
    "ExperimentalIncrementalExecutionResults",
    "FormattedExecutionResult",
    "FormattedIncrementalDeferResult",
    "FormattedIncrementalResult",
    "FormattedIncrementalStreamResult",
    "FormattedInitialIncrementalExecutionResult",
    "FormattedSubsequentIncrementalExecutionResult",
    "IncrementalDeferResult",
    "IncrementalResult",
    "IncrementalStreamResult",
    "InitialIncrementalExecutionResult",
    "Middleware",
    "SubsequentIncrementalExecutionResult",
]


# Terminology
#
# "Definitions" are the generic name for top-level statements in the document.
# Examples of this include:
# 1) Operations (such as a query)
# 2) Fragments
#
# "Operations" are a generic name for requests in the document.
# Examples of this include:
# 1) query,
# 2) mutation
#
# "Selections" are the definitions that can appear legally and at
# single level of the query. These include:
# 1) field references e.g "a"
# 2) fragment "spreads" e.g. "...c"
# 3) inline fragment "spreads" e.g. "...on Type { a }"


class FormattedExecutionResult(TypedDict, total=False):
    """Formatted execution result"""

    data: Optional[Dict[str, Any]]
    errors: List[GraphQLFormattedError]
    extensions: Dict[str, Any]


class ExecutionResult:
    """The result of GraphQL execution.

    - ``data`` is the result of a successful execution of the query.
    - ``errors`` is included when any errors occurred as a non-empty list.
    - ``extensions`` is reserved for adding non-standard properties.
    """

    __slots__ = "data", "errors", "extensions"

    data: Optional[Dict[str, Any]]
    errors: Optional[List[GraphQLError]]
    extensions: Optional[Dict[str, Any]]

    def __init__(
        self,
        data: Optional[Dict[str, Any]] = None,
        errors: Optional[List[GraphQLError]] = None,
        extensions: Optional[Dict[str, Any]] = None,
    ):
        self.data = data
        self.errors = errors
        self.extensions = extensions

    def __repr__(self) -> str:
        name = self.__class__.__name__
        ext = "" if self.extensions is None else f", extensions={self.extensions}"
        return f"{name}(data={self.data!r}, errors={self.errors!r}{ext})"

    def __iter__(self) -> Iterable[Any]:
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

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, dict):
            if "extensions" not in other:
                return other == dict(data=self.data, errors=self.errors)
            return other == dict(
                data=self.data, errors=self.errors, extensions=self.extensions
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

    def __ne__(self, other: Any) -> bool:
        return not self == other


class FormattedIncrementalDeferResult(TypedDict, total=False):
    """Formatted incremental deferred execution result"""

    data: Optional[Dict[str, Any]]
    errors: List[GraphQLFormattedError]
    path: List[Union[str, int]]
    label: str
    extensions: Dict[str, Any]


class IncrementalDeferResult:
    """Incremental deferred execution result"""

    data: Optional[Dict[str, Any]]
    errors: Optional[List[GraphQLError]]
    path: Optional[List[Union[str, int]]]
    label: Optional[str]
    extensions: Optional[Dict[str, Any]]

    __slots__ = "data", "errors", "path", "label", "extensions"

    def __init__(
        self,
        data: Optional[Dict[str, Any]] = None,
        errors: Optional[List[GraphQLError]] = None,
        path: Optional[List[Union[str, int]]] = None,
        label: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
    ):
        self.data = data
        self.errors = errors
        self.path = path
        self.label = label
        self.extensions = extensions

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: List[str] = [f"data={self.data!r}, errors={self.errors!r}"]
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

    def __eq__(self, other: Any) -> bool:
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

    def __ne__(self, other: Any) -> bool:
        return not self == other


class FormattedIncrementalStreamResult(TypedDict, total=False):
    """Formatted incremental stream execution result"""

    items: Optional[List[Any]]
    errors: List[GraphQLFormattedError]
    path: List[Union[str, int]]
    label: str
    extensions: Dict[str, Any]


class IncrementalStreamResult:
    """Incremental streamed execution result"""

    items: Optional[List[Any]]
    errors: Optional[List[GraphQLError]]
    path: Optional[List[Union[str, int]]]
    label: Optional[str]
    extensions: Optional[Dict[str, Any]]

    __slots__ = "items", "errors", "path", "label", "extensions"

    def __init__(
        self,
        items: Optional[List[Any]] = None,
        errors: Optional[List[GraphQLError]] = None,
        path: Optional[List[Union[str, int]]] = None,
        label: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
    ):
        self.items = items
        self.errors = errors
        self.path = path
        self.label = label
        self.extensions = extensions

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: List[str] = [f"items={self.items!r}, errors={self.errors!r}"]
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

    def __eq__(self, other: Any) -> bool:
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

    def __ne__(self, other: Any) -> bool:
        return not self == other


FormattedIncrementalResult = Union[
    FormattedIncrementalDeferResult, FormattedIncrementalStreamResult
]

IncrementalResult = Union[IncrementalDeferResult, IncrementalStreamResult]


class FormattedInitialIncrementalExecutionResult(TypedDict, total=False):
    """Formatted initial incremental execution result"""

    data: Optional[Dict[str, Any]]
    errors: List[GraphQLFormattedError]
    hasNext: bool
    incremental: List[FormattedIncrementalResult]
    extensions: Dict[str, Any]


class InitialIncrementalExecutionResult:
    """Initial incremental execution result.

    - ``has_next`` is True if a future payload is expected.
    - ``incremental`` is a list of the results from defer/stream directives.
    """

    data: Optional[Dict[str, Any]]
    errors: Optional[List[GraphQLError]]
    incremental: Optional[Sequence[IncrementalResult]]
    has_next: bool
    extensions: Optional[Dict[str, Any]]

    __slots__ = "data", "errors", "has_next", "incremental", "extensions"

    def __init__(
        self,
        data: Optional[Dict[str, Any]] = None,
        errors: Optional[List[GraphQLError]] = None,
        incremental: Optional[Sequence[IncrementalResult]] = None,
        has_next: bool = False,
        extensions: Optional[Dict[str, Any]] = None,
    ):
        self.data = data
        self.errors = errors
        self.incremental = incremental
        self.has_next = has_next
        self.extensions = extensions

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: List[str] = [f"data={self.data!r}, errors={self.errors!r}"]
        if self.incremental:
            args.append(f"incremental[{len(self.incremental)}]")
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
        if self.incremental:
            formatted["incremental"] = [result.formatted for result in self.incremental]
        formatted["hasNext"] = self.has_next
        if self.extensions is not None:
            formatted["extensions"] = self.extensions
        return formatted

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, dict):
            return (
                other.get("data") == self.data
                and other.get("errors") == self.errors
                and (
                    "incremental" not in other
                    or other["incremental"] == self.incremental
                )
                and ("hasNext" not in other or other["hasNext"] == self.has_next)
                and (
                    "extensions" not in other or other["extensions"] == self.extensions
                )
            )
        if isinstance(other, tuple):
            size = len(other)
            return (
                1 < size < 6
                and (
                    self.data,
                    self.errors,
                    self.incremental,
                    self.has_next,
                    self.extensions,
                )[:size]
                == other
            )
        return (
            isinstance(other, self.__class__)
            and other.data == self.data
            and other.errors == self.errors
            and other.incremental == self.incremental
            and other.has_next == self.has_next
            and other.extensions == self.extensions
        )

    def __ne__(self, other: Any) -> bool:
        return not self == other


class FormattedSubsequentIncrementalExecutionResult(TypedDict, total=False):
    """Formatted subsequent incremental execution result"""

    incremental: List[FormattedIncrementalResult]
    hasNext: bool
    extensions: Dict[str, Any]


class SubsequentIncrementalExecutionResult:
    """Subsequent incremental execution result.

    - ``has_next`` is True if a future payload is expected.
    - ``incremental`` is a list of the results from defer/stream directives.
    """

    __slots__ = "has_next", "incremental", "extensions"

    incremental: Optional[Sequence[IncrementalResult]]
    has_next: bool
    extensions: Optional[Dict[str, Any]]

    def __init__(
        self,
        incremental: Optional[Sequence[IncrementalResult]] = None,
        has_next: bool = False,
        extensions: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.incremental = incremental
        self.has_next = has_next
        self.extensions = extensions

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: List[str] = []
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

    def __eq__(self, other: Any) -> bool:
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

    def __ne__(self, other: Any) -> bool:
        return not self == other


class StreamArguments(NamedTuple):
    """Arguments of the stream directive"""

    initial_count: int
    label: Optional[str]


class ExperimentalIncrementalExecutionResults(NamedTuple):
    """Execution results when retrieved incrementally."""

    initial_result: InitialIncrementalExecutionResult
    subsequent_results: AsyncGenerator[SubsequentIncrementalExecutionResult, None]


Middleware: TypeAlias = Optional[Union[Tuple, List, MiddlewareManager]]


class ExecutionContext:
    """Data that must be available at all points during query execution.

    Namely, schema of the type system that is currently executing, and the fragments
    defined in the query document.
    """

    schema: GraphQLSchema
    fragments: Dict[str, FragmentDefinitionNode]
    root_value: Any
    context_value: Any
    operation: OperationDefinitionNode
    variable_values: Dict[str, Any]
    field_resolver: GraphQLFieldResolver
    type_resolver: GraphQLTypeResolver
    subscribe_field_resolver: GraphQLFieldResolver
    errors: List[GraphQLError]
    subsequent_payloads: Dict[AsyncPayloadRecord, None]  # used as ordered set
    middleware_manager: Optional[MiddlewareManager]

    is_awaitable: Callable[[Any], TypeGuard[Awaitable]] = staticmethod(
        default_is_awaitable  # type: ignore
    )

    def __init__(
        self,
        schema: GraphQLSchema,
        fragments: Dict[str, FragmentDefinitionNode],
        root_value: Any,
        context_value: Any,
        operation: OperationDefinitionNode,
        variable_values: Dict[str, Any],
        field_resolver: GraphQLFieldResolver,
        type_resolver: GraphQLTypeResolver,
        subscribe_field_resolver: GraphQLFieldResolver,
        subsequent_payloads: Dict[AsyncPayloadRecord, None],
        errors: List[GraphQLError],
        middleware_manager: Optional[MiddlewareManager],
        is_awaitable: Optional[Callable[[Any], bool]],
    ) -> None:
        self.schema = schema
        self.fragments = fragments
        self.root_value = root_value
        self.context_value = context_value
        self.operation = operation
        self.variable_values = variable_values
        self.field_resolver = field_resolver
        self.type_resolver = type_resolver
        self.subscribe_field_resolver = subscribe_field_resolver
        self.subsequent_payloads = subsequent_payloads
        self.errors = errors
        self.middleware_manager = middleware_manager
        if is_awaitable:
            self.is_awaitable = is_awaitable
        self._canceled_iterators: Set[AsyncIterator] = set()
        self._subfields_cache: Dict[Tuple, FieldsAndPatches] = {}

    @classmethod
    def build(
        cls,
        schema: GraphQLSchema,
        document: DocumentNode,
        root_value: Any = None,
        context_value: Any = None,
        raw_variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        field_resolver: Optional[GraphQLFieldResolver] = None,
        type_resolver: Optional[GraphQLTypeResolver] = None,
        subscribe_field_resolver: Optional[GraphQLFieldResolver] = None,
        middleware: Optional[Middleware] = None,
        is_awaitable: Optional[Callable[[Any], bool]] = None,
    ) -> Union[List[GraphQLError], ExecutionContext]:
        """Build an execution context

        Constructs a ExecutionContext object from the arguments passed to execute, which
        we will pass throughout the other execution methods.

        Throws a GraphQLError if a valid execution context cannot be created.

        For internal use only.
        """
        # If the schema used for execution is invalid, raise an error.
        assert_valid_schema(schema)

        operation: Optional[OperationDefinitionNode] = None
        fragments: Dict[str, FragmentDefinitionNode] = {}
        middleware_manager: Optional[MiddlewareManager] = None
        if middleware is not None:
            if isinstance(middleware, (list, tuple)):
                middleware_manager = MiddlewareManager(*middleware)
            elif isinstance(middleware, MiddlewareManager):
                middleware_manager = middleware
            else:
                raise TypeError(
                    "Middleware must be passed as a list or tuple of functions"
                    " or objects, or as a single MiddlewareManager object."
                    f" Got {inspect(middleware)} instead."
                )

        for definition in document.definitions:
            if isinstance(definition, OperationDefinitionNode):
                if operation_name is None:
                    if operation:
                        return [
                            GraphQLError(
                                "Must provide operation name"
                                " if query contains multiple operations."
                            )
                        ]
                    operation = definition
                elif definition.name and definition.name.value == operation_name:
                    operation = definition
            elif isinstance(definition, FragmentDefinitionNode):
                fragments[definition.name.value] = definition

        if not operation:
            if operation_name is not None:
                return [GraphQLError(f"Unknown operation named '{operation_name}'.")]
            return [GraphQLError("Must provide an operation.")]

        coerced_variable_values = get_variable_values(
            schema,
            operation.variable_definitions or (),
            raw_variable_values or {},
            max_errors=50,
        )

        if isinstance(coerced_variable_values, list):
            return coerced_variable_values  # errors

        return cls(
            schema,
            fragments,
            root_value,
            context_value,
            operation,
            coerced_variable_values,  # coerced values
            field_resolver or default_field_resolver,
            type_resolver or default_type_resolver,
            subscribe_field_resolver or default_field_resolver,
            {},
            [],
            middleware_manager,
            is_awaitable,
        )

    @staticmethod
    def build_response(
        data: Optional[Dict[str, Any]], errors: List[GraphQLError]
    ) -> ExecutionResult:
        """Build response.

        Given a completed execution context and data, build the (data, errors) response
        defined by the "Response" section of the GraphQL spec.
        """
        if not errors:
            return ExecutionResult(data, None)
        # Sort the error list in order to make it deterministic, since we might have
        # been using parallel execution.
        errors.sort(
            key=lambda error: (error.locations or [], error.path or [], error.message)
        )
        return ExecutionResult(data, errors)

    def build_per_event_execution_context(self, payload: Any) -> ExecutionContext:
        """Create a copy of the execution context for usage with subscribe events."""
        return self.__class__(
            self.schema,
            self.fragments,
            payload,
            self.context_value,
            self.operation,
            self.variable_values,
            self.field_resolver,
            self.type_resolver,
            self.subscribe_field_resolver,
            {},
            [],
            self.middleware_manager,
            self.is_awaitable,
        )

    def execute_operation(self) -> AwaitableOrValue[Dict[str, Any]]:
        """Execute an operation.

        Implements the "Executing operations" section of the spec.
        """
        schema = self.schema
        operation = self.operation
        root_type = schema.get_root_type(operation.operation)
        if root_type is None:
            raise GraphQLError(
                "Schema is not configured to execute"
                f" {operation.operation.value} operation.",
                operation,
            )

        root_fields, patches = collect_fields(
            schema,
            self.fragments,
            self.variable_values,
            root_type,
            operation.selection_set,
        )

        root_value = self.root_value
        # noinspection PyTypeChecker
        result = (
            self.execute_fields_serially
            if operation.operation == OperationType.MUTATION
            else self.execute_fields
        )(
            root_type, root_value, None, root_fields
        )  # type: ignore

        for patch in patches:
            label, patch_fields = patch
            self.execute_deferred_fragment(
                root_type, root_value, patch_fields, label, None
            )

        return result

    def execute_fields_serially(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Optional[Path],
        fields: Dict[str, List[FieldNode]],
    ) -> AwaitableOrValue[Dict[str, Any]]:
        """Execute the given fields serially.

        Implements the "Executing selection sets" section of the spec
        for fields that must be executed serially.
        """
        is_awaitable = self.is_awaitable

        def reducer(
            results: Dict[str, Any], field_item: Tuple[str, List[FieldNode]]
        ) -> AwaitableOrValue[Dict[str, Any]]:
            response_name, field_nodes = field_item
            field_path = Path(path, response_name, parent_type.name)
            result = self.execute_field(
                parent_type, source_value, field_nodes, field_path
            )
            if result is Undefined:
                return results
            if is_awaitable(result):
                # noinspection PyShadowingNames
                async def set_result(
                    response_name: str,
                    awaitable_result: Awaitable,
                ) -> Dict[str, Any]:
                    results[response_name] = await awaitable_result
                    return results

                return set_result(response_name, result)
            results[response_name] = result
            return results

        # noinspection PyTypeChecker
        return async_reduce(reducer, fields.items(), {})

    def execute_fields(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Optional[Path],
        fields: Dict[str, List[FieldNode]],
        async_payload_record: Optional[AsyncPayloadRecord] = None,
    ) -> AwaitableOrValue[Dict[str, Any]]:
        """Execute the given fields concurrently.

        Implements the "Executing selection sets" section of the spec
        for fields that may be executed in parallel.
        """
        results = {}
        is_awaitable = self.is_awaitable
        awaitable_fields: List[str] = []
        append_awaitable = awaitable_fields.append
        for response_name, field_nodes in fields.items():
            field_path = Path(path, response_name, parent_type.name)
            result = self.execute_field(
                parent_type, source_value, field_nodes, field_path, async_payload_record
            )
            if result is not Undefined:
                results[response_name] = result
                if is_awaitable(result):
                    append_awaitable(response_name)

        # If there are no coroutines, we can just return the object.
        if not awaitable_fields:
            return results

        # Otherwise, results is a map from field name to the result of resolving that
        # field, which is possibly a coroutine object. Return a coroutine object that
        # will yield this same map, but with any coroutines awaited in parallel and
        # replaced with the values they yielded.
        async def get_results() -> Dict[str, Any]:
            if len(awaitable_fields) == 1:
                # If there is only one field, avoid the overhead of parallelization.
                field = awaitable_fields[0]
                results[field] = await results[field]
            else:
                results.update(
                    zip(
                        awaitable_fields,
                        await gather(*(results[field] for field in awaitable_fields)),
                    )
                )
            return results

        return get_results()

    def execute_field(
        self,
        parent_type: GraphQLObjectType,
        source: Any,
        field_nodes: List[FieldNode],
        path: Path,
        async_payload_record: Optional[AsyncPayloadRecord] = None,
    ) -> AwaitableOrValue[Any]:
        """Resolve the field on the given source object.

        Implements the "Executing fields" section of the spec.

        In particular, this method figures out the value that the field returns by
        calling its resolve function, then calls complete_value to await coroutine
        objects, serialize scalars, or execute the sub-selection-set for objects.
        """
        errors = async_payload_record.errors if async_payload_record else self.errors
        field_name = field_nodes[0].name.value
        field_def = self.schema.get_field(parent_type, field_name)
        if not field_def:
            return Undefined

        return_type = field_def.type
        resolve_fn = field_def.resolve or self.field_resolver

        if self.middleware_manager:
            resolve_fn = self.middleware_manager.get_field_resolver(resolve_fn)

        info = self.build_resolve_info(field_def, field_nodes, parent_type, path)

        # Get the resolve function, regardless of if its result is normal or abrupt
        # (error).
        try:
            # Build a dictionary of arguments from the field.arguments AST, using the
            # variables scope to fulfill any variable references.
            args = get_argument_values(field_def, field_nodes[0], self.variable_values)

            # Note that contrary to the JavaScript implementation, we pass the context
            # value as part of the resolve info.
            result = resolve_fn(source, info, **args)

            if self.is_awaitable(result):
                # noinspection PyShadowingNames
                async def await_result() -> Any:
                    try:
                        completed = self.complete_value(
                            return_type,
                            field_nodes,
                            info,
                            path,
                            await result,
                            async_payload_record,
                        )
                        if self.is_awaitable(completed):
                            return await completed
                        return completed
                    except Exception as raw_error:
                        error = located_error(raw_error, field_nodes, path.as_list())
                        handle_field_error(error, return_type, errors)
                        return None

                return await_result()

            completed = self.complete_value(
                return_type, field_nodes, info, path, result, async_payload_record
            )
            if self.is_awaitable(completed):
                # noinspection PyShadowingNames
                async def await_completed() -> Any:
                    try:
                        return await completed
                    except Exception as raw_error:
                        error = located_error(raw_error, field_nodes, path.as_list())
                        handle_field_error(error, return_type, errors)
                        self.filter_subsequent_payloads(path)
                        return None

                return await_completed()

            return completed
        except Exception as raw_error:
            error = located_error(raw_error, field_nodes, path.as_list())
            handle_field_error(error, return_type, errors)
            self.filter_subsequent_payloads(path)
            return None

    def build_resolve_info(
        self,
        field_def: GraphQLField,
        field_nodes: List[FieldNode],
        parent_type: GraphQLObjectType,
        path: Path,
    ) -> GraphQLResolveInfo:
        """Build the GraphQLResolveInfo object.

        For internal use only."""
        # The resolve function's first argument is a collection of information about
        # the current execution state.
        return GraphQLResolveInfo(
            field_nodes[0].name.value,
            field_nodes,
            field_def.type,
            parent_type,
            path,
            self.schema,
            self.fragments,
            self.root_value,
            self.operation,
            self.variable_values,
            self.context_value,
            self.is_awaitable,
        )

    def complete_value(
        self,
        return_type: GraphQLOutputType,
        field_nodes: List[FieldNode],
        info: GraphQLResolveInfo,
        path: Path,
        result: Any,
        async_payload_record: Optional[AsyncPayloadRecord],
    ) -> AwaitableOrValue[Any]:
        """Complete a value.

        Implements the instructions for completeValue as defined in the
        "Value completion" section of the spec.

        If the field type is Non-Null, then this recursively completes the value
        for the inner type. It throws a field error if that completion returns null,
        as per the "Nullability" section of the spec.

        If the field type is a List, then this recursively completes the value
        for the inner type on each item in the list.

        If the field type is a Scalar or Enum, ensures the completed value is a legal
        value of the type by calling the ``serialize`` method of GraphQL type
        definition.

        If the field is an abstract type, determine the runtime type of the value and
        then complete based on that type.

        Otherwise, the field type expects a sub-selection set, and will complete the
        value by evaluating all sub-selections.
        """
        # If result is an Exception, throw a located error.
        if isinstance(result, Exception):
            raise result

        # If field type is NonNull, complete for inner type, and throw field error if
        # result is null.
        if is_non_null_type(return_type):
            completed = self.complete_value(
                return_type.of_type,
                field_nodes,
                info,
                path,
                result,
                async_payload_record,
            )
            if completed is None:
                raise TypeError(
                    "Cannot return null for non-nullable field"
                    f" {info.parent_type.name}.{info.field_name}."
                )
            return completed

        # If result value is null or undefined then return null.
        if result is None or result is Undefined:
            return None

        # If field type is List, complete each item in the list with inner type
        if is_list_type(return_type):
            return self.complete_list_value(
                return_type, field_nodes, info, path, result, async_payload_record
            )

        # If field type is a leaf type, Scalar or Enum, serialize to a valid value,
        # returning null if serialization is not possible.
        if is_leaf_type(return_type):
            return self.complete_leaf_value(return_type, result)

        # If field type is an abstract type, Interface or Union, determine the runtime
        # Object type and complete for that type.
        if is_abstract_type(return_type):
            return self.complete_abstract_value(
                return_type, field_nodes, info, path, result, async_payload_record
            )

        # If field type is Object, execute and complete all sub-selections.
        if is_object_type(return_type):
            return self.complete_object_value(
                return_type, field_nodes, info, path, result, async_payload_record
            )

        # Not reachable. All possible output types have been considered.
        raise TypeError(  # pragma: no cover
            "Cannot complete value of unexpected output type:"
            f" '{inspect(return_type)}'."
        )

    def get_stream_values(
        self, field_nodes: List[FieldNode], path: Path
    ) -> Optional[StreamArguments]:
        """Get stream values.

        Returns an object containing the `@stream` arguments if a field should be
        streamed based on the experimental flag, stream directive present and
        not disabled by the "if" argument.
        """
        # do not stream inner lists of multidimensional lists
        if isinstance(path.key, int):
            return None

        # validation only allows equivalent streams on multiple fields, so it is
        # safe to only check the first field_node for the stream directive
        stream = get_directive_values(
            GraphQLStreamDirective, field_nodes[0], self.variable_values
        )

        if not stream or stream.get("if") is False:
            return None

        initial_count = stream.get("initialCount")
        if initial_count is None or initial_count < 0:
            raise ValueError("initialCount must be a positive integer")

        label = stream.get("label")
        return StreamArguments(initial_count=initial_count, label=label)

    async def complete_async_iterator_value(
        self,
        item_type: GraphQLOutputType,
        field_nodes: List[FieldNode],
        info: GraphQLResolveInfo,
        path: Path,
        iterator: AsyncIterator[Any],
        async_payload_record: Optional[AsyncPayloadRecord],
    ) -> List[Any]:
        """Complete an async iterator.

        Complete a async iterator value by completing the result and calling
        recursively until all the results are completed.
        """
        errors = async_payload_record.errors if async_payload_record else self.errors
        stream = self.get_stream_values(field_nodes, path)
        is_awaitable = self.is_awaitable
        awaitable_indices: List[int] = []
        append_awaitable = awaitable_indices.append
        completed_results: List[Any] = []
        append_result = completed_results.append
        index = 0
        while True:
            if (
                stream
                and isinstance(stream.initial_count, int)
                and index >= stream.initial_count
            ):
                try:
                    await wait_for(
                        shield(
                            self.execute_stream_iterator(
                                index,
                                iterator,
                                field_nodes,
                                info,
                                item_type,
                                path,
                                stream.label,
                                async_payload_record,
                            )
                        ),
                        timeout=ASYNC_DELAY,
                    )
                except TimeoutError:
                    pass
                break

            field_path = path.add_key(index, None)
            try:
                try:
                    value = await anext(iterator)
                except StopAsyncIteration:
                    break
                try:
                    completed_item = self.complete_value(
                        item_type,
                        field_nodes,
                        info,
                        field_path,
                        value,
                        async_payload_record,
                    )
                    if is_awaitable(completed_item):
                        append_awaitable(index)
                    append_result(completed_item)
                except Exception as raw_error:
                    append_result(None)
                    error = located_error(raw_error, field_nodes, field_path.as_list())
                    handle_field_error(error, item_type, errors)
            except Exception as raw_error:
                append_result(None)
                error = located_error(raw_error, field_nodes, field_path.as_list())
                handle_field_error(error, item_type, errors)
                break
            index += 1

        if not awaitable_indices:
            return completed_results

        if len(awaitable_indices) == 1:
            # If there is only one index, avoid the overhead of parallelization.
            index = awaitable_indices[0]
            completed_results[index] = await completed_results[index]
        else:
            for index, result in zip(
                awaitable_indices,
                await gather(
                    *(completed_results[index] for index in awaitable_indices)
                ),
            ):
                completed_results[index] = result
        return completed_results

    def complete_list_value(
        self,
        return_type: GraphQLList[GraphQLOutputType],
        field_nodes: List[FieldNode],
        info: GraphQLResolveInfo,
        path: Path,
        result: Union[AsyncIterable[Any], Iterable[Any]],
        async_payload_record: Optional[AsyncPayloadRecord],
    ) -> AwaitableOrValue[List[Any]]:
        """Complete a list value.

        Complete a list value by completing each item in the list with the inner type.
        """
        item_type = return_type.of_type
        errors = async_payload_record.errors if async_payload_record else self.errors

        if isinstance(result, AsyncIterable):
            iterator = result.__aiter__()

            return self.complete_async_iterator_value(
                item_type, field_nodes, info, path, iterator, async_payload_record
            )

        if not is_iterable(result):
            raise GraphQLError(
                "Expected Iterable, but did not find one for field"
                f" '{info.parent_type.name}.{info.field_name}'."
            )

        stream = self.get_stream_values(field_nodes, path)

        # This is specified as a simple map, however we're optimizing the path where
        # the list contains no coroutine objects by avoiding creating another coroutine
        # object.
        is_awaitable = self.is_awaitable
        awaitable_indices: List[int] = []
        append_awaitable = awaitable_indices.append
        previous_async_payload_record = async_payload_record
        completed_results: List[Any] = []
        append_result = completed_results.append
        for index, item in enumerate(result):
            # No need to modify the info object containing the path, since from here on
            # it is not ever accessed by resolver functions.
            item_path = path.add_key(index, None)
            completed_item: AwaitableOrValue[Any]

            if (
                stream
                and isinstance(stream.initial_count, int)
                and index >= stream.initial_count
            ):
                previous_async_payload_record = self.execute_stream_field(
                    path,
                    item_path,
                    item,
                    field_nodes,
                    info,
                    item_type,
                    stream.label,
                    previous_async_payload_record,
                )
                continue
            if is_awaitable(item):
                # noinspection PyShadowingNames
                async def await_completed(item: Any, item_path: Path) -> Any:
                    try:
                        completed = self.complete_value(
                            item_type,
                            field_nodes,
                            info,
                            item_path,
                            await item,
                            async_payload_record,
                        )
                        if is_awaitable(completed):
                            return await completed
                        return completed
                    except Exception as raw_error:
                        error = located_error(
                            raw_error, field_nodes, item_path.as_list()
                        )
                        handle_field_error(error, item_type, errors)
                        self.filter_subsequent_payloads(item_path)
                        return None

                completed_item = await_completed(item, item_path)
            else:
                try:
                    completed_item = self.complete_value(
                        item_type,
                        field_nodes,
                        info,
                        item_path,
                        item,
                        async_payload_record,
                    )
                    if is_awaitable(completed_item):
                        # noinspection PyShadowingNames
                        async def await_completed(item: Any, item_path: Path) -> Any:
                            try:
                                return await item
                            except Exception as raw_error:
                                error = located_error(
                                    raw_error, field_nodes, item_path.as_list()
                                )
                                handle_field_error(error, item_type, errors)
                                self.filter_subsequent_payloads(item_path)
                                return None

                        completed_item = await_completed(completed_item, item_path)
                except Exception as raw_error:
                    error = located_error(raw_error, field_nodes, item_path.as_list())
                    handle_field_error(error, item_type, errors)
                    self.filter_subsequent_payloads(item_path)
                    completed_item = None

            if is_awaitable(completed_item):
                append_awaitable(index)
            append_result(completed_item)

        if not awaitable_indices:
            return completed_results

        # noinspection PyShadowingNames
        async def get_completed_results() -> List[Any]:
            if len(awaitable_indices) == 1:
                # If there is only one index, avoid the overhead of parallelization.
                index = awaitable_indices[0]
                completed_results[index] = await completed_results[index]
            else:
                for index, result in zip(
                    awaitable_indices,
                    await gather(
                        *(completed_results[index] for index in awaitable_indices)
                    ),
                ):
                    completed_results[index] = result
            return completed_results

        return get_completed_results()

    @staticmethod
    def complete_leaf_value(return_type: GraphQLLeafType, result: Any) -> Any:
        """Complete a leaf value.

        Complete a Scalar or Enum by serializing to a valid value, returning null if
        serialization is not possible.
        """
        serialized_result = return_type.serialize(result)
        if serialized_result is Undefined or serialized_result is None:
            raise TypeError(
                f"Expected `{inspect(return_type)}.serialize({inspect(result)})`"
                f" to return non-nullable value, returned: {inspect(serialized_result)}"
            )
        return serialized_result

    def complete_abstract_value(
        self,
        return_type: GraphQLAbstractType,
        field_nodes: List[FieldNode],
        info: GraphQLResolveInfo,
        path: Path,
        result: Any,
        async_payload_record: Optional[AsyncPayloadRecord],
    ) -> AwaitableOrValue[Any]:
        """Complete an abstract value.

        Complete a value of an abstract type by determining the runtime object type of
        that value, then complete the value for that type.
        """
        resolve_type_fn = return_type.resolve_type or self.type_resolver
        runtime_type = resolve_type_fn(result, info, return_type)

        if self.is_awaitable(runtime_type):
            runtime_type = cast(Awaitable, runtime_type)

            async def await_complete_object_value() -> Any:
                value = self.complete_object_value(
                    self.ensure_valid_runtime_type(
                        await runtime_type,  # type: ignore
                        return_type,
                        field_nodes,
                        info,
                        result,
                    ),
                    field_nodes,
                    info,
                    path,
                    result,
                    async_payload_record,
                )
                if self.is_awaitable(value):
                    return await value  # type: ignore
                return value  # pragma: no cover

            return await_complete_object_value()
        runtime_type = cast(Optional[str], runtime_type)

        return self.complete_object_value(
            self.ensure_valid_runtime_type(
                runtime_type, return_type, field_nodes, info, result
            ),
            field_nodes,
            info,
            path,
            result,
            async_payload_record,
        )

    def ensure_valid_runtime_type(
        self,
        runtime_type_name: Any,
        return_type: GraphQLAbstractType,
        field_nodes: List[FieldNode],
        info: GraphQLResolveInfo,
        result: Any,
    ) -> GraphQLObjectType:
        if runtime_type_name is None:
            raise GraphQLError(
                f"Abstract type '{return_type.name}' must resolve"
                " to an Object type at runtime"
                f" for field '{info.parent_type.name}.{info.field_name}'."
                f" Either the '{return_type.name}' type should provide"
                " a 'resolve_type' function or each possible type should provide"
                " an 'is_type_of' function.",
                field_nodes,
            )

        if is_object_type(runtime_type_name):  # pragma: no cover
            raise GraphQLError(
                "Support for returning GraphQLObjectType from resolve_type was"
                " removed in GraphQL-core 3.2, please return type name instead."
            )

        if not isinstance(runtime_type_name, str):
            raise GraphQLError(
                f"Abstract type '{return_type.name}' must resolve"
                " to an Object type at runtime"
                f" for field '{info.parent_type.name}.{info.field_name}' with value"
                f" {inspect(result)}, received '{inspect(runtime_type_name)}'.",
                field_nodes,
            )

        runtime_type = self.schema.get_type(runtime_type_name)

        if runtime_type is None:
            raise GraphQLError(
                f"Abstract type '{return_type.name}' was resolved to a type"
                f" '{runtime_type_name}' that does not exist inside the schema.",
                field_nodes,
            )

        if not is_object_type(runtime_type):
            raise GraphQLError(
                f"Abstract type '{return_type.name}' was resolved"
                f" to a non-object type '{runtime_type_name}'.",
                field_nodes,
            )

        if not self.schema.is_sub_type(return_type, runtime_type):
            raise GraphQLError(
                f"Runtime Object type '{runtime_type.name}' is not a possible"
                f" type for '{return_type.name}'.",
                field_nodes,
            )

        # noinspection PyTypeChecker
        return runtime_type

    def complete_object_value(
        self,
        return_type: GraphQLObjectType,
        field_nodes: List[FieldNode],
        info: GraphQLResolveInfo,
        path: Path,
        result: Any,
        async_payload_record: Optional[AsyncPayloadRecord],
    ) -> AwaitableOrValue[Dict[str, Any]]:
        """Complete an Object value by executing all sub-selections."""
        # If there is an `is_type_of()` predicate function, call it with the current
        # result. If `is_type_of()` returns False, then raise an error rather than
        # continuing execution.
        if return_type.is_type_of:
            is_type_of = return_type.is_type_of(result, info)

            if self.is_awaitable(is_type_of):

                async def execute_subfields_async() -> Dict[str, Any]:
                    if not await is_type_of:  # type: ignore
                        raise invalid_return_type_error(
                            return_type, result, field_nodes
                        )
                    return self.collect_and_execute_subfields(
                        return_type, field_nodes, path, result, async_payload_record
                    )  # type: ignore

                return execute_subfields_async()

            if not is_type_of:
                raise invalid_return_type_error(return_type, result, field_nodes)

        return self.collect_and_execute_subfields(
            return_type, field_nodes, path, result, async_payload_record
        )

    def collect_and_execute_subfields(
        self,
        return_type: GraphQLObjectType,
        field_nodes: List[FieldNode],
        path: Path,
        result: Any,
        async_payload_record: Optional[AsyncPayloadRecord],
    ) -> AwaitableOrValue[Dict[str, Any]]:
        # Collect sub-fields to execute to complete this value.
        sub_field_nodes, sub_patches = self.collect_subfields(return_type, field_nodes)

        sub_fields = self.execute_fields(
            return_type, result, path, sub_field_nodes, async_payload_record
        )

        for sub_patch in sub_patches:
            label, sub_patch_field_nodes = sub_patch
            self.execute_deferred_fragment(
                return_type,
                result,
                sub_patch_field_nodes,
                label,
                path,
                async_payload_record,
            )

        return sub_fields

    def collect_subfields(
        self, return_type: GraphQLObjectType, field_nodes: List[FieldNode]
    ) -> FieldsAndPatches:
        """Collect subfields.

        A cached collection of relevant subfields with regard to the return type is
        kept in the execution context as ``_subfields_cache``. This ensures the
        subfields are not repeatedly calculated, which saves overhead when resolving
        lists of values.
        """
        cache = self._subfields_cache
        # We cannot use the field_nodes themselves as key for the cache, since they
        # are not hashable as a list. We also do not want to use the field_nodes
        # themselves (converted to a tuple) as keys, since hashing them is slow.
        # Therefore, we use the ids of the field_nodes as keys. Note that we do not
        # use the id of the list, since we want to hit the cache for all lists of
        # the same nodes, not only for the same list of nodes. Also, the list id may
        # even be reused, in which case we would get wrong results from the cache.
        key = (
            (return_type, id(field_nodes[0]))
            if len(field_nodes) == 1  # optimize most frequent case
            else tuple((return_type, *map(id, field_nodes)))
        )
        sub_fields_and_patches = cache.get(key)
        if sub_fields_and_patches is None:
            sub_fields_and_patches = collect_subfields(
                self.schema,
                self.fragments,
                self.variable_values,
                return_type,
                field_nodes,
            )
            cache[key] = sub_fields_and_patches
        return sub_fields_and_patches

    def map_source_to_response(
        self, result_or_stream: Union[ExecutionResult, AsyncIterable[Any]]
    ) -> AwaitableOrValue[
        Union[
            AsyncGenerator[
                Union[
                    ExecutionResult,
                    InitialIncrementalExecutionResult,
                    SubsequentIncrementalExecutionResult,
                ],
                None,
            ],
            ExecutionResult,
        ]
    ]:
        """Map source result to response.

        For each payload yielded from a subscription,
        map it over the normal GraphQL :func:`~graphql.execution.execute` function,
        with ``payload`` as the ``root_value``.
        This implements the "MapSourceToResponseEvent" algorithm
        described in the GraphQL specification.
        The :func:`~graphql.execution.execute` function provides
        the "ExecuteSubscriptionEvent" algorithm,
        as it is nearly identical to the "ExecuteQuery" algorithm,
        for which :func:`~graphql.execution.execute` is also used.
        """

        if not isinstance(result_or_stream, AsyncIterable):
            return result_or_stream  # pragma: no cover

        async def callback(payload: Any) -> AsyncGenerator:
            result = execute_impl(self.build_per_event_execution_context(payload))
            return ensure_async_iterable(
                await result if self.is_awaitable(result) else result  # type: ignore
            )

        return flatten_async_iterable(map_async_iterable(result_or_stream, callback))

    def execute_deferred_fragment(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        fields: Dict[str, List[FieldNode]],
        label: Optional[str] = None,
        path: Optional[Path] = None,
        parent_context: Optional[AsyncPayloadRecord] = None,
    ) -> None:
        async_payload_record = DeferredFragmentRecord(label, path, parent_context, self)
        try:
            awaitable_or_data = self.execute_fields(
                parent_type, source_value, path, fields, async_payload_record
            )

            if self.is_awaitable(awaitable_or_data):

                async def await_data(
                    awaitable: Awaitable[Dict[str, Any]]
                ) -> Optional[Dict[str, Any]]:
                    # noinspection PyShadowingNames

                    try:
                        return await awaitable
                    except GraphQLError as error:
                        async_payload_record.errors.append(error)
                        return None

                awaitable_or_data = await_data(awaitable_or_data)  # type: ignore
        except GraphQLError as error:
            async_payload_record.errors.append(error)
            awaitable_or_data = None

        async_payload_record.add_data(awaitable_or_data)

    def execute_stream_field(
        self,
        path: Path,
        item_path: Path,
        item: AwaitableOrValue[Any],
        field_nodes: List[FieldNode],
        info: GraphQLResolveInfo,
        item_type: GraphQLOutputType,
        label: Optional[str] = None,
        parent_context: Optional[AsyncPayloadRecord] = None,
    ) -> AsyncPayloadRecord:
        async_payload_record = StreamRecord(
            label, item_path, None, parent_context, self
        )
        completed_item: Any
        try:
            try:
                if self.is_awaitable(item):

                    async def await_completed_item() -> Any:
                        completed = self.complete_value(
                            item_type,
                            field_nodes,
                            info,
                            item_path,
                            await item,
                            async_payload_record,
                        )
                        return (
                            await completed
                            if self.is_awaitable(completed)
                            else completed
                        )

                    completed_item = await_completed_item()

                else:
                    completed_item = self.complete_value(
                        item_type,
                        field_nodes,
                        info,
                        item_path,
                        item,
                        async_payload_record,
                    )

                if self.is_awaitable(completed_item):

                    async def await_completed_item() -> Any:
                        # noinspection PyShadowingNames
                        try:
                            return await completed_item
                        except Exception as raw_error:
                            # noinspection PyShadowingNames
                            error = located_error(
                                raw_error, field_nodes, item_path.as_list()
                            )
                            handle_field_error(
                                error, item_type, async_payload_record.errors
                            )
                            self.filter_subsequent_payloads(
                                item_path, async_payload_record
                            )
                            return None

                    complete_item = await_completed_item()

                else:
                    complete_item = completed_item
            except Exception as raw_error:
                error = located_error(raw_error, field_nodes, item_path.as_list())
                handle_field_error(error, item_type, async_payload_record.errors)
                self.filter_subsequent_payloads(  # pragma: no cover
                    item_path, async_payload_record
                )
                complete_item = None  # pragma: no cover

        except GraphQLError as error:
            async_payload_record.errors.append(error)
            self.filter_subsequent_payloads(item_path, async_payload_record)
            async_payload_record.add_items(None)
            return async_payload_record

        completed_items: AwaitableOrValue[Optional[List[Any]]]
        if self.is_awaitable(complete_item):

            async def await_completed_items() -> Optional[List[Any]]:
                # noinspection PyShadowingNames
                try:
                    return [await complete_item]  # type: ignore
                except GraphQLError as error:
                    async_payload_record.errors.append(error)
                    self.filter_subsequent_payloads(path, async_payload_record)
                    return None

            completed_items = await_completed_items()
        else:
            completed_items = [complete_item]

        async_payload_record.add_items(completed_items)
        return async_payload_record

    async def execute_stream_iterator_item(
        self,
        iterator: AsyncIterator[Any],
        field_nodes: List[FieldNode],
        info: GraphQLResolveInfo,
        item_type: GraphQLOutputType,
        async_payload_record: StreamRecord,
        field_path: Path,
    ) -> Any:
        if iterator in self._canceled_iterators:
            raise StopAsyncIteration
        try:
            item = await anext(iterator)
            completed_item = self.complete_value(
                item_type, field_nodes, info, field_path, item, async_payload_record
            )

            return (
                await completed_item
                if self.is_awaitable(completed_item)
                else completed_item
            )

        except StopAsyncIteration as raw_error:
            async_payload_record.set_is_completed_iterator()
            raise StopAsyncIteration from raw_error

        except Exception as raw_error:
            error = located_error(raw_error, field_nodes, field_path.as_list())
            handle_field_error(error, item_type, async_payload_record.errors)
            self.filter_subsequent_payloads(field_path, async_payload_record)

    async def execute_stream_iterator(
        self,
        initial_index: int,
        iterator: AsyncIterator[Any],
        field_modes: List[FieldNode],
        info: GraphQLResolveInfo,
        item_type: GraphQLOutputType,
        path: Optional[Path],
        label: Optional[str],
        parent_context: Optional[AsyncPayloadRecord],
    ) -> None:
        index = initial_index
        previous_async_payload_record = parent_context

        while True:
            field_path = Path(path, index, None)
            async_payload_record = StreamRecord(
                label, field_path, iterator, previous_async_payload_record, self
            )

            awaitable_data = self.execute_stream_iterator_item(
                iterator, field_modes, info, item_type, async_payload_record, field_path
            )

            try:
                data = await awaitable_data
            except StopAsyncIteration:
                if async_payload_record.errors:
                    async_payload_record.add_items(None)  # pragma: no cover
                else:
                    del self.subsequent_payloads[async_payload_record]
                break
            except GraphQLError as error:
                # entire stream has errored and bubbled upwards
                self.filter_subsequent_payloads(path, async_payload_record)
                if iterator:  # pragma: no cover else
                    with suppress(Exception):
                        await iterator.aclose()  # type: ignore
                    # running generators cannot be closed since Python 3.8,
                    # so we need to remember that this iterator is already canceled
                    self._canceled_iterators.add(iterator)
                async_payload_record.add_items(None)
                async_payload_record.errors.append(error)
                break

            async_payload_record.add_items([data])

            previous_async_payload_record = async_payload_record
            index += 1

    def filter_subsequent_payloads(
        self,
        null_path: Optional[Path] = None,
        current_async_record: Optional[AsyncPayloadRecord] = None,
    ) -> None:
        null_path_list = null_path.as_list() if null_path else []
        for async_record in list(self.subsequent_payloads):
            if async_record is current_async_record:
                # don't remove payload from where error originates
                continue
            if async_record.path[: len(null_path_list)] != null_path_list:
                # async_record points to a path unaffected by this payload
                continue
            # async_record path points to nulled error field
            if isinstance(async_record, StreamRecord) and async_record.iterator:
                self._canceled_iterators.add(async_record.iterator)
            del self.subsequent_payloads[async_record]

    def get_completed_incremental_results(self) -> List[IncrementalResult]:
        incremental_results: List[IncrementalResult] = []
        append_result = incremental_results.append
        subsequent_payloads = list(self.subsequent_payloads)
        for async_payload_record in subsequent_payloads:
            incremental_result: IncrementalResult
            if not async_payload_record.completed.is_set():
                continue
            del self.subsequent_payloads[async_payload_record]
            if isinstance(async_payload_record, StreamRecord):
                items = async_payload_record.items
                if async_payload_record.is_completed_iterator:
                    # async iterable resolver finished but there may be pending payload
                    continue  # pragma: no cover
                incremental_result = IncrementalStreamResult(
                    items,
                    async_payload_record.errors
                    if async_payload_record.errors
                    else None,
                    async_payload_record.path,
                    async_payload_record.label,
                )
            else:
                data = async_payload_record.data
                incremental_result = IncrementalDeferResult(
                    data,
                    async_payload_record.errors
                    if async_payload_record.errors
                    else None,
                    async_payload_record.path,
                    async_payload_record.label,
                )

            append_result(incremental_result)

        return incremental_results

    async def yield_subsequent_payloads(
        self,
    ) -> AsyncGenerator[SubsequentIncrementalExecutionResult, None]:
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


UNEXPECTED_MULTIPLE_PAYLOADS = (
    "Executing this GraphQL operation would unexpectedly produce multiple payloads"
    " (due to @defer or @stream directive)"
)


def execute(
    schema: GraphQLSchema,
    document: DocumentNode,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: Optional[Dict[str, Any]] = None,
    operation_name: Optional[str] = None,
    field_resolver: Optional[GraphQLFieldResolver] = None,
    type_resolver: Optional[GraphQLTypeResolver] = None,
    subscribe_field_resolver: Optional[GraphQLFieldResolver] = None,
    middleware: Optional[Middleware] = None,
    execution_context_class: Optional[Type[ExecutionContext]] = None,
    is_awaitable: Optional[Callable[[Any], bool]] = None,
) -> AwaitableOrValue[ExecutionResult]:
    """Execute a GraphQL operation.

    Implements the "Executing requests" section of the GraphQL specification.

    Returns an ExecutionResult (if all encountered resolvers are synchronous),
    or a coroutine object eventually yielding an ExecutionResult.

    If the arguments to this function do not result in a legal execution context,
    a GraphQLError will be thrown immediately explaining the invalid input.

    This function does not support incremental delivery (`@defer` and `@stream`).
    If an operation which would defer or stream data is executed with this
    function, it will throw or resolve to an object containing an error instead.
    Use `experimental_execute_incrementally` if you want to support incremental
    delivery.
    """
    result = experimental_execute_incrementally(
        schema,
        document,
        root_value,
        context_value,
        variable_values,
        operation_name,
        field_resolver,
        type_resolver,
        subscribe_field_resolver,
        middleware,
        execution_context_class,
        is_awaitable,
    )
    if isinstance(result, ExecutionResult):
        return result
    if isinstance(result, ExperimentalIncrementalExecutionResults):
        raise GraphQLError(UNEXPECTED_MULTIPLE_PAYLOADS)

    async def await_result() -> Any:
        awaited_result = await result  # type: ignore
        if isinstance(awaited_result, ExecutionResult):
            return awaited_result
        return ExecutionResult(
            None, errors=[GraphQLError(UNEXPECTED_MULTIPLE_PAYLOADS)]
        )

    return await_result()


def experimental_execute_incrementally(
    schema: GraphQLSchema,
    document: DocumentNode,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: Optional[Dict[str, Any]] = None,
    operation_name: Optional[str] = None,
    field_resolver: Optional[GraphQLFieldResolver] = None,
    type_resolver: Optional[GraphQLTypeResolver] = None,
    subscribe_field_resolver: Optional[GraphQLFieldResolver] = None,
    middleware: Optional[Middleware] = None,
    execution_context_class: Optional[Type[ExecutionContext]] = None,
    is_awaitable: Optional[Callable[[Any], bool]] = None,
) -> AwaitableOrValue[Union[ExecutionResult, ExperimentalIncrementalExecutionResults]]:
    """Execute GraphQL operation incrementally (internal implementation).

     Implements the "Executing requests" section of the GraphQL specification,
     including `@defer` and `@stream` as proposed in
     https://github.com/graphql/graphql-spec/pull/742

    This function returns an awaitable that is either a single ExecutionResult or
    an ExperimentalIncrementalExecutionResults object, containing an `initialResult`
    and a stream of `subsequent_results`.
    """
    if execution_context_class is None:
        execution_context_class = ExecutionContext

    # If a valid execution context cannot be created due to incorrect arguments,
    # a "Response" with only errors is returned.
    context = execution_context_class.build(
        schema,
        document,
        root_value,
        context_value,
        variable_values,
        operation_name,
        field_resolver,
        type_resolver,
        subscribe_field_resolver,
        middleware,
        is_awaitable,
    )

    # Return early errors if execution context failed.
    if isinstance(context, list):
        return ExecutionResult(None, errors=context)

    return execute_impl(context)


def execute_impl(
    context: ExecutionContext,
) -> AwaitableOrValue[Union[ExecutionResult, ExperimentalIncrementalExecutionResults]]:
    """Execute GraphQL operation (internal implementation)."""
    # Return a possible coroutine object that will eventually yield the data described
    # by the "Response" section of the GraphQL specification.
    #
    # If errors are encountered while executing a GraphQL field, only that field and
    # its descendants will be omitted, and sibling fields will still be executed. An
    # execution which encounters errors will still result in a coroutine object that
    # can be executed without errors.
    #
    # Errors from sub-fields of a NonNull type may propagate to the top level,
    # at which point we still log the error and null the parent field, which
    # in this case is the entire response.
    errors = context.errors
    build_response = context.build_response
    try:
        result = context.execute_operation()

        if context.is_awaitable(result):
            # noinspection PyShadowingNames
            async def await_result() -> Any:
                try:
                    initial_result = build_response(
                        await result, errors  # type: ignore
                    )
                    if context.subsequent_payloads:
                        return ExperimentalIncrementalExecutionResults(
                            initial_result=InitialIncrementalExecutionResult(
                                initial_result.data,
                                initial_result.errors,
                                has_next=True,
                            ),
                            subsequent_results=context.yield_subsequent_payloads(),
                        )
                    return initial_result
                except GraphQLError as error:
                    errors.append(error)
                    return build_response(None, errors)

            return await_result()

        initial_result = build_response(result, errors)  # type: ignore
        if context.subsequent_payloads:
            return ExperimentalIncrementalExecutionResults(
                initial_result=InitialIncrementalExecutionResult(
                    initial_result.data,
                    initial_result.errors,
                    has_next=True,
                ),
                subsequent_results=context.yield_subsequent_payloads(),
            )
        return initial_result
    except GraphQLError as error:
        errors.append(error)
        return build_response(None, errors)


def assume_not_awaitable(_value: Any) -> bool:
    """Replacement for is_awaitable if everything is assumed to be synchronous."""
    return False


def execute_sync(
    schema: GraphQLSchema,
    document: DocumentNode,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: Optional[Dict[str, Any]] = None,
    operation_name: Optional[str] = None,
    field_resolver: Optional[GraphQLFieldResolver] = None,
    type_resolver: Optional[GraphQLTypeResolver] = None,
    middleware: Optional[Middleware] = None,
    execution_context_class: Optional[Type[ExecutionContext]] = None,
    check_sync: bool = False,
) -> ExecutionResult:
    """Execute a GraphQL operation synchronously.

    Also implements the "Executing requests" section of the GraphQL specification.

    However, it guarantees to complete synchronously (or throw an error) assuming
    that all field resolvers are also synchronous.

    Set check_sync to True to still run checks that no awaitable values are returned.
    """
    is_awaitable = (
        check_sync
        if callable(check_sync)
        else (None if check_sync else assume_not_awaitable)
    )

    result = experimental_execute_incrementally(
        schema,
        document,
        root_value,
        context_value,
        variable_values,
        operation_name,
        field_resolver,
        type_resolver,
        None,
        middleware,
        execution_context_class,
        is_awaitable,
    )

    # Assert that the execution was synchronous.
    if default_is_awaitable(result) or isinstance(
        result, ExperimentalIncrementalExecutionResults
    ):
        if default_is_awaitable(result):
            ensure_future(cast(Awaitable[ExecutionResult], result)).cancel()
        raise RuntimeError("GraphQL execution failed to complete synchronously.")

    return cast(ExecutionResult, result)


def handle_field_error(
    error: GraphQLError, return_type: GraphQLOutputType, errors: List[GraphQLError]
) -> None:
    """Handle error properly according to the field type."""
    # If the field type is non-nullable, then it is resolved without any protection
    # from errors, however it still properly locates the error.
    if is_non_null_type(return_type):
        raise error
    # Otherwise, error protection is applied, logging the error and resolving a
    # null value for this field if one is encountered.
    errors.append(error)
    return None


def invalid_return_type_error(
    return_type: GraphQLObjectType, result: Any, field_nodes: List[FieldNode]
) -> GraphQLError:
    """Create a GraphQLError for an invalid return type."""
    return GraphQLError(
        f"Expected value of type '{return_type.name}' but got: {inspect(result)}.",
        field_nodes,
    )


def get_typename(value: Any) -> Optional[str]:
    """Get the ``__typename`` property of the given value."""
    if isinstance(value, Mapping):
        return value.get("__typename")
    # need to de-mangle the attribute assumed to be "private" in Python
    for cls in value.__class__.__mro__:
        __typename = getattr(value, f"_{cls.__name__}__typename", None)
        if __typename:
            return __typename
    return None


def default_type_resolver(
    value: Any, info: GraphQLResolveInfo, abstract_type: GraphQLAbstractType
) -> AwaitableOrValue[Optional[str]]:
    """Default type resolver function.

    If a resolve_type function is not given, then a default resolve behavior is used
    which attempts two strategies:

    First, See if the provided value has a ``__typename`` field defined, if so, use that
    value as name of the resolved type.

    Otherwise, test each possible type for the abstract type by calling
    :meth:`~graphql.type.GraphQLObjectType.is_type_of` for the object
    being coerced, returning the first type that matches.
    """
    # First, look for `__typename`.
    type_name = get_typename(value)
    if isinstance(type_name, str):
        return type_name

    # Otherwise, test each possible type.
    possible_types = info.schema.get_possible_types(abstract_type)
    is_awaitable = info.is_awaitable
    awaitable_is_type_of_results: List[Awaitable] = []
    append_awaitable_results = awaitable_is_type_of_results.append
    awaitable_types: List[GraphQLObjectType] = []
    append_awaitable_types = awaitable_types.append

    for type_ in possible_types:
        if type_.is_type_of:
            is_type_of_result = type_.is_type_of(value, info)

            if is_awaitable(is_type_of_result):
                append_awaitable_results(cast(Awaitable, is_type_of_result))
                append_awaitable_types(type_)
            elif is_type_of_result:
                return type_.name

    if awaitable_is_type_of_results:
        # noinspection PyShadowingNames
        async def get_type() -> Optional[str]:
            is_type_of_results = await gather(*awaitable_is_type_of_results)
            for is_type_of_result, type_ in zip(is_type_of_results, awaitable_types):
                if is_type_of_result:
                    return type_.name
            return None

        return get_type()

    return None


def default_field_resolver(source: Any, info: GraphQLResolveInfo, **args: Any) -> Any:
    """Default field resolver.

    If a resolve function is not given, then a default resolve behavior is used which
    takes the property of the source object of the same name as the field and returns
    it as the result, or if it's a function, returns the result of calling that function
    while passing along args and context.

    For dictionaries, the field names are used as keys, for all other objects they are
    used as attribute names.
    """
    # Ensure source is a value for which property access is acceptable.
    field_name = info.field_name
    value = (
        source.get(field_name)
        if isinstance(source, Mapping)
        else getattr(source, field_name, None)
    )
    if callable(value):
        return value(info, **args)
    return value


def subscribe(
    schema: GraphQLSchema,
    document: DocumentNode,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: Optional[Dict[str, Any]] = None,
    operation_name: Optional[str] = None,
    field_resolver: Optional[GraphQLFieldResolver] = None,
    type_resolver: Optional[GraphQLTypeResolver] = None,
    subscribe_field_resolver: Optional[GraphQLFieldResolver] = None,
    execution_context_class: Optional[Type[ExecutionContext]] = None,
) -> AwaitableOrValue[Union[AsyncIterator[ExecutionResult], ExecutionResult]]:
    """Create a GraphQL subscription.

    Implements the "Subscribe" algorithm described in the GraphQL spec.

    Returns a coroutine object which yields either an AsyncIterator (if successful) or
    an ExecutionResult (client error). The coroutine will raise an exception if a server
    error occurs.

    If the client-provided arguments to this function do not result in a compliant
    subscription, a GraphQL Response (ExecutionResult) with descriptive errors and no
    data will be returned.

    If the source stream could not be created due to faulty subscription resolver logic
    or underlying systems, the coroutine object will yield a single ExecutionResult
    containing ``errors`` and no ``data``.

    If the operation succeeded, the coroutine will yield an AsyncIterator, which yields
    a stream of ExecutionResults representing the response stream.

    This function does not support incremental delivery (`@defer` and `@stream`).
    If an operation which would defer or stream data is executed with this function,
    each :class:`InitialIncrementalExecutionResult` and
    :class:`SubsequentIncrementalExecutionResult`
    in the result stream will be replaced with an :class:`ExecutionResult`
    with a single error stating that defer/stream is not supported.
    Use :func:`experimental_subscribe_incrementally` if you want to support
    incremental delivery.
    """
    result = experimental_subscribe_incrementally(
        schema,
        document,
        root_value,
        context_value,
        variable_values,
        operation_name,
        field_resolver,
        type_resolver,
        subscribe_field_resolver,
        execution_context_class,
    )

    if isinstance(result, ExecutionResult):
        return result
    if isinstance(result, AsyncIterable):
        return map_async_iterable(result, ensure_single_execution_result)

    async def await_result() -> Union[AsyncIterator[ExecutionResult], ExecutionResult]:
        result_or_iterable = await result  # type: ignore
        if isinstance(result_or_iterable, AsyncIterable):
            return map_async_iterable(
                result_or_iterable, ensure_single_execution_result
            )
        return result_or_iterable

    return await_result()


async def ensure_single_execution_result(
    result: Union[
        ExecutionResult,
        InitialIncrementalExecutionResult,
        SubsequentIncrementalExecutionResult,
    ]
) -> ExecutionResult:
    """Ensure that the given result does not use incremental delivery."""
    if not isinstance(result, ExecutionResult):
        return ExecutionResult(
            None, errors=[GraphQLError(UNEXPECTED_MULTIPLE_PAYLOADS)]
        )
    return result


def experimental_subscribe_incrementally(
    schema: GraphQLSchema,
    document: DocumentNode,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: Optional[Dict[str, Any]] = None,
    operation_name: Optional[str] = None,
    field_resolver: Optional[GraphQLFieldResolver] = None,
    type_resolver: Optional[GraphQLTypeResolver] = None,
    subscribe_field_resolver: Optional[GraphQLFieldResolver] = None,
    execution_context_class: Optional[Type[ExecutionContext]] = None,
) -> AwaitableOrValue[
    Union[
        AsyncGenerator[
            Union[
                ExecutionResult,
                InitialIncrementalExecutionResult,
                SubsequentIncrementalExecutionResult,
            ],
            None,
        ],
        ExecutionResult,
    ]
]:
    """Create a GraphQL subscription.

    Implements the "Subscribe" algorithm described in the GraphQL spec.

    Returns a coroutine object which yields either an AsyncIterator (if successful) or
    an ExecutionResult (client error). The coroutine will raise an exception if a server
    error occurs.

    If the client-provided arguments to this function do not result in a compliant
    subscription, a GraphQL Response (ExecutionResult) with descriptive errors and no
    data will be returned.

    If the source stream could not be created due to faulty subscription resolver logic
    or underlying systems, the coroutine object will yield a single ExecutionResult
    containing ``errors`` and no ``data``.

    If the operation succeeded, the coroutine will yield an AsyncIterator, which yields
    a stream of ExecutionResults representing the response stream.

    Each result may be an ExecutionResult with no ``has_next`` attribute (if executing
    the event did not use `@defer` or `@stream`), or an
    :class:`InitialIncrementalExecutionResult` or
    :class:`SubsequentIncrementalExecutionResult`
    (if executing the event used `@defer` or `@stream`). In the case of
    incremental execution results, each event produces a single
    :class:`InitialIncrementalExecutionResult` followed by one or more
    :class:`SubsequentIncrementalExecutionResult`; all but the last have
    ``has_next == true``, and the last has ``has_next == False``.
    There is no interleaving between results generated from the same original event.
    """
    if execution_context_class is None:
        execution_context_class = ExecutionContext

    # If a valid context cannot be created due to incorrect arguments,
    # a "Response" with only errors is returned.
    context = execution_context_class.build(
        schema,
        document,
        root_value,
        context_value,
        variable_values,
        operation_name,
        field_resolver,
        type_resolver,
        subscribe_field_resolver,
    )

    # Return early errors if execution context failed.
    if isinstance(context, list):
        return ExecutionResult(None, errors=context)

    result_or_stream = create_source_event_stream_impl(context)

    if context.is_awaitable(result_or_stream):
        # noinspection PyShadowingNames
        async def await_result() -> Any:
            awaited_result_or_stream = await result_or_stream  # type: ignore
            if isinstance(awaited_result_or_stream, ExecutionResult):
                return awaited_result_or_stream
            return context.map_source_to_response(  # type: ignore
                awaited_result_or_stream
            )

        return await_result()

    if isinstance(result_or_stream, ExecutionResult):
        return result_or_stream

    return context.map_source_to_response(result_or_stream)  # type: ignore


async def ensure_async_iterable(
    some_execution_result: Union[
        ExecutionResult, ExperimentalIncrementalExecutionResults
    ],
) -> AsyncGenerator[
    Union[
        ExecutionResult,
        InitialIncrementalExecutionResult,
        SubsequentIncrementalExecutionResult,
    ],
    None,
]:
    if isinstance(some_execution_result, ExecutionResult):
        yield some_execution_result
    else:
        yield some_execution_result.initial_result
        async for result in some_execution_result.subsequent_results:
            yield result


def create_source_event_stream(
    schema: GraphQLSchema,
    document: DocumentNode,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: Optional[Dict[str, Any]] = None,
    operation_name: Optional[str] = None,
    field_resolver: Optional[GraphQLFieldResolver] = None,
    type_resolver: Optional[GraphQLTypeResolver] = None,
    subscribe_field_resolver: Optional[GraphQLFieldResolver] = None,
    execution_context_class: Optional[Type[ExecutionContext]] = None,
) -> AwaitableOrValue[Union[AsyncIterable[Any], ExecutionResult]]:
    """Create source event stream

    Implements the "CreateSourceEventStream" algorithm described in the GraphQL
    specification, resolving the subscription source event stream.

    Returns a coroutine that yields an AsyncIterable.

    If the client-provided arguments to this function do not result in a compliant
    subscription, a GraphQL Response (ExecutionResult) with descriptive errors and no
    data will be returned.

    If the source stream could not be created due to faulty subscription resolver logic
    or underlying systems, the coroutine object will yield a single ExecutionResult
    containing ``errors`` and no ``data``.

    A source event stream represents a sequence of events, each of which triggers a
    GraphQL execution for that event.

    This may be useful when hosting the stateful subscription service in a different
    process or machine than the stateless GraphQL execution engine, or otherwise
    separating these two steps. For more on this, see the "Supporting Subscriptions
    at Scale" information in the GraphQL spec.
    """
    # If a valid context cannot be created due to incorrect arguments,
    # a "Response" with only errors is returned.
    context = (execution_context_class or ExecutionContext).build(
        schema,
        document,
        root_value,
        context_value,
        variable_values,
        operation_name,
        field_resolver,
        type_resolver,
        subscribe_field_resolver,
    )

    # Return early errors if execution context failed.
    if isinstance(context, list):
        return ExecutionResult(None, errors=context)

    return create_source_event_stream_impl(context)


def create_source_event_stream_impl(
    context: ExecutionContext,
) -> AwaitableOrValue[Union[AsyncIterable[Any], ExecutionResult]]:
    """Create source event stream (internal implementation)."""
    try:
        event_stream = execute_subscription(context)
    except GraphQLError as error:
        return ExecutionResult(None, errors=[error])

    if context.is_awaitable(event_stream):
        awaitable_event_stream = cast(Awaitable, event_stream)

        # noinspection PyShadowingNames
        async def await_event_stream() -> Union[AsyncIterable[Any], ExecutionResult]:
            try:
                return await awaitable_event_stream
            except GraphQLError as error:
                return ExecutionResult(None, errors=[error])

        return await_event_stream()

    return event_stream


def execute_subscription(
    context: ExecutionContext,
) -> AwaitableOrValue[AsyncIterable[Any]]:
    schema = context.schema

    root_type = schema.subscription_type
    if root_type is None:
        raise GraphQLError(
            "Schema is not configured to execute subscription operation.",
            context.operation,
        )

    root_fields = collect_fields(
        schema,
        context.fragments,
        context.variable_values,
        root_type,
        context.operation.selection_set,
    ).fields
    first_root_field = next(iter(root_fields.items()))
    response_name, field_nodes = first_root_field
    field_name = field_nodes[0].name.value
    field_def = schema.get_field(root_type, field_name)

    if not field_def:
        raise GraphQLError(
            f"The subscription field '{field_name}' is not defined.", field_nodes
        )

    path = Path(None, response_name, root_type.name)
    info = context.build_resolve_info(field_def, field_nodes, root_type, path)

    # Implements the "ResolveFieldEventStream" algorithm from GraphQL specification.
    # It differs from "ResolveFieldValue" due to providing a different `resolveFn`.

    try:
        # Build a dictionary of arguments from the field.arguments AST, using the
        # variables scope to fulfill any variable references.
        args = get_argument_values(field_def, field_nodes[0], context.variable_values)

        # Call the `subscribe()` resolver or the default resolver to produce an
        # AsyncIterable yielding raw payloads.
        resolve_fn = field_def.subscribe or context.subscribe_field_resolver

        result = resolve_fn(context.root_value, info, **args)
        if context.is_awaitable(result):
            # noinspection PyShadowingNames
            async def await_result() -> AsyncIterable[Any]:
                try:
                    return assert_event_stream(await result)
                except Exception as error:
                    raise located_error(error, field_nodes, path.as_list())

            return await_result()

        return assert_event_stream(result)

    except Exception as error:
        raise located_error(error, field_nodes, path.as_list())


def assert_event_stream(result: Any) -> AsyncIterable:
    if isinstance(result, Exception):
        raise result

    # Assert field returned an event stream, otherwise yield an error.
    if not isinstance(result, AsyncIterable):
        raise GraphQLError(
            "Subscription field must return AsyncIterable."
            f" Received: {inspect(result)}."
        )

    return result


class DeferredFragmentRecord:
    """A record collecting data marked with the defer directive"""

    errors: List[GraphQLError]
    label: Optional[str]
    path: List[Union[str, int]]
    data: Optional[Dict[str, Any]]
    parent_context: Optional[AsyncPayloadRecord]
    completed: Event
    _context: ExecutionContext
    _data: AwaitableOrValue[Optional[Dict[str, Any]]]
    _data_added: Event

    def __init__(
        self,
        label: Optional[str],
        path: Optional[Path],
        parent_context: Optional[AsyncPayloadRecord],
        context: ExecutionContext,
    ) -> None:
        self.label = label
        self.path = path.as_list() if path else []
        self.parent_context = parent_context
        self.errors = []
        self._context = context
        context.subsequent_payloads[self] = None
        self.data = self._data = None
        self.completed = Event()
        self._data_added = Event()

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: List[str] = [f"path={self.path!r}"]
        if self.label:
            args.append(f"label={self.label!r}")
        if self.parent_context:
            args.append("parent_context")
        if self.data is not None:
            args.append("data")
        return f"{name}({', '.join(args)})"

    def __await__(self) -> Generator[Any, None, Optional[Dict[str, Any]]]:
        return self.wait().__await__()

    async def wait(self) -> Optional[Dict[str, Any]]:
        if self.parent_context:
            await self.parent_context.completed.wait()
        _data = self._data
        try:
            data = (
                await _data  # type: ignore
                if self._context.is_awaitable(_data)
                else _data
            )
        finally:
            await sleep(ASYNC_DELAY)  # always defer completion a little bit
            self.data = data
            self.completed.set()
        return data

    def add_data(self, data: AwaitableOrValue[Optional[Dict[str, Any]]]) -> None:
        self._data = data
        self._data_added.set()


class StreamRecord:
    """A record collecting items marked with the stream directive"""

    errors: List[GraphQLError]
    label: Optional[str]
    path: List[Union[str, int]]
    items: Optional[List[str]]
    parent_context: Optional[AsyncPayloadRecord]
    iterator: Optional[AsyncIterator[Any]]
    is_completed_iterator: bool
    completed: Event
    _context: ExecutionContext
    _items: AwaitableOrValue[Optional[List[Any]]]
    _items_added: Event

    def __init__(
        self,
        label: Optional[str],
        path: Optional[Path],
        iterator: Optional[AsyncIterator[Any]],
        parent_context: Optional[AsyncPayloadRecord],
        context: ExecutionContext,
    ) -> None:
        self.label = label
        self.path = path.as_list() if path else []
        self.parent_context = parent_context
        self.iterator = iterator
        self.errors = []
        self._context = context
        context.subsequent_payloads[self] = None
        self.items = self._items = None
        self.completed = Event()
        self._items_added = Event()
        self.is_completed_iterator = False

    def __repr__(self) -> str:
        name = self.__class__.__name__
        args: List[str] = [f"path={self.path!r}"]
        if self.label:
            args.append(f"label={self.label!r}")
        if self.parent_context:
            args.append("parent_context")
        if self.items is not None:
            args.append("items")
        return f"{name}({', '.join(args)})"

    def __await__(self) -> Generator[Any, None, Optional[List[str]]]:
        return self.wait().__await__()

    async def wait(self) -> Optional[List[str]]:
        await self._items_added.wait()
        if self.parent_context:
            await self.parent_context.completed.wait()
        _items = self._items
        try:
            items = (
                await _items  # type: ignore
                if self._context.is_awaitable(_items)
                else _items
            )
        finally:
            await sleep(ASYNC_DELAY)  # always defer completion a little bit
            self.items = items
            self.completed.set()
        return items

    def add_items(self, items: AwaitableOrValue[Optional[List[Any]]]) -> None:
        self._items = items
        self._items_added.set()

    def set_is_completed_iterator(self) -> None:
        self.is_completed_iterator = True
        self._items_added.set()


AsyncPayloadRecord = Union[DeferredFragmentRecord, StreamRecord]
