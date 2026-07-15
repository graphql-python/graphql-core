"""GraphQL execution"""

from __future__ import annotations

from asyncio import ensure_future
from collections.abc import Callable
from typing import (
    TYPE_CHECKING,
    Any,
    cast,
)

from ..error import GraphQLError, located_error
from ..language import is_subscription_operation_definition_node
from ..pyutils import (
    Path,
    inspect,
)
from ..pyutils.is_awaitable import (
    is_async_iterable as default_is_async_iterable,
)
from ..pyutils.is_awaitable import (
    is_awaitable as default_is_awaitable,
)
from .async_iterables import map_async_iterable
from .collect_fields import collect_fields
from .executor import (
    UNEXPECTED_MULTIPLE_PAYLOADS,
    AsyncWorkFinishedInfo,
    ExecutionHooks,
    Executor,
    Middleware,
    default_field_resolver,
    default_type_resolver,
)
from .executor_throwing_on_incremental import ExecutorThrowingOnIncremental
from .incremental.incremental_executor import IncrementalExecutor
from .types import ExecutionResult, ExperimentalIncrementalExecutionResults
from .values import get_argument_values

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterable, AsyncIterator, Awaitable
    from typing import TypeAlias, TypeGuard

    from ..language import DocumentNode
    from ..pyutils import AbortSignal, AwaitableOrValue
    from ..type import (
        GraphQLFieldResolver,
        GraphQLSchema,
        GraphQLTypeResolver,
    )
    from .middleware import MiddlewareManager

__all__ = [
    "AsyncWorkFinishedInfo",
    "ExecutionHooks",
    "Executor",
    "Middleware",
    "RootSelectionSetExecutor",
    "create_source_event_stream",
    "default_field_resolver",
    "default_type_resolver",
    "execute",
    "execute_root_selection_set",
    "execute_subscription_event",
    "execute_sync",
    "experimental_execute_incrementally",
    "map_source_to_response_event",
    "subscribe",
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


UNEXPECTED_EXPERIMENTAL_DIRECTIVES = (
    "The provided schema unexpectedly contains experimental directives"
    " (@defer or @stream). These directives may only be utilized"
    " if experimental execution features are explicitly enabled."
)


def execute(  # noqa: PLR0913
    schema: GraphQLSchema,
    document: DocumentNode,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: dict[str, Any] | None = None,
    operation_name: str | None = None,
    field_resolver: GraphQLFieldResolver | None = None,
    type_resolver: GraphQLTypeResolver | None = None,
    subscribe_field_resolver: GraphQLFieldResolver | None = None,
    max_coercion_errors: int = 50,
    enable_early_execution: bool = False,
    middleware: Middleware | None = None,
    executor_class: type[Executor] | None = None,
    is_awaitable: Callable[[Any], TypeGuard[Awaitable]] | None = None,
    is_async_iterable: Callable[[Any], TypeGuard[AsyncIterable]] | None = None,
    hide_suggestions: bool = False,
    abort_signal: AbortSignal | None = None,
    hooks: ExecutionHooks | None = None,
    **custom_context_args: Any,
) -> AwaitableOrValue[ExecutionResult]:
    """Execute a GraphQL operation.

    Implements the "Executing requests" section of the GraphQL specification.

    Returns an ExecutionResult (if all encountered resolvers are synchronous),
    or a coroutine object eventually yielding an ExecutionResult.

    If the arguments to this function do not result in a legal executor,
    a GraphQLError will be thrown immediately explaining the invalid input.

    This function does not support incremental delivery (`@defer` and `@stream`).
    If an operation that defers or streams data is executed with this function,
    it will throw an error instead. Use `experimental_execute_incrementally` if
    you want to support incremental delivery.
    """
    if schema.get_directive("defer") or schema.get_directive("stream"):
        raise GraphQLError(UNEXPECTED_EXPERIMENTAL_DIRECTIVES)

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
        max_coercion_errors,
        enable_early_execution,
        middleware,
        executor_class,
        is_awaitable,
        is_async_iterable,
        hide_suggestions=hide_suggestions,
        abort_signal=abort_signal,
        hooks=hooks,
        **custom_context_args,
    )
    if isinstance(result, ExecutionResult):
        return result
    if isinstance(result, ExperimentalIncrementalExecutionResults):
        raise GraphQLError(UNEXPECTED_MULTIPLE_PAYLOADS)

    async def await_result() -> Any:
        awaited_result = await result
        if isinstance(awaited_result, ExecutionResult):
            return awaited_result
        raise GraphQLError(UNEXPECTED_MULTIPLE_PAYLOADS)

    return await_result()


def experimental_execute_incrementally(  # noqa: PLR0913
    schema: GraphQLSchema,
    document: DocumentNode,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: dict[str, Any] | None = None,
    operation_name: str | None = None,
    field_resolver: GraphQLFieldResolver | None = None,
    type_resolver: GraphQLTypeResolver | None = None,
    subscribe_field_resolver: GraphQLFieldResolver | None = None,
    max_coercion_errors: int = 50,
    enable_early_execution: bool = False,
    middleware: Middleware | None = None,
    executor_class: type[Executor] | None = None,
    is_awaitable: Callable[[Any], TypeGuard[Awaitable]] | None = None,
    is_async_iterable: Callable[[Any], TypeGuard[AsyncIterable]] | None = None,
    hide_suggestions: bool = False,
    abort_signal: AbortSignal | None = None,
    hooks: ExecutionHooks | None = None,
    **custom_context_args: Any,
) -> AwaitableOrValue[ExecutionResult | ExperimentalIncrementalExecutionResults]:
    """Execute GraphQL operation incrementally (internal implementation).

    Implements the "Executing requests" section of the GraphQL specification,
    including `@defer` and `@stream` as proposed in
    https://github.com/graphql/graphql-spec/pull/742

    This function returns an awaitable that is either a single ExecutionResult or
    an ExperimentalIncrementalExecutionResults object, containing an `initial_result`
    and a stream of `subsequent_results`.
    """
    if executor_class is None:
        executor_class = IncrementalExecutor

    # If a valid executor cannot be created due to incorrect arguments,
    # a "Response" with only errors is returned.
    executor = executor_class.build(
        schema,
        document,
        root_value,
        context_value,
        variable_values,
        operation_name,
        field_resolver,
        type_resolver,
        subscribe_field_resolver,
        max_coercion_errors,
        enable_early_execution,
        middleware,
        is_awaitable,
        is_async_iterable,
        hide_suggestions=hide_suggestions,
        abort_signal=abort_signal,
        hooks=hooks,
        **custom_context_args,
    )

    # Return early errors if executor failed.
    if isinstance(executor, list):
        return ExecutionResult(None, errors=executor)

    return executor.execute_operation()


def assume_not_awaitable(_value: Any) -> TypeGuard[Awaitable]:
    """Replacement for is_awaitable if everything is assumed to be synchronous."""
    return False


def execute_sync(
    schema: GraphQLSchema,
    document: DocumentNode,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: dict[str, Any] | None = None,
    operation_name: str | None = None,
    field_resolver: GraphQLFieldResolver | None = None,
    type_resolver: GraphQLTypeResolver | None = None,
    max_coercion_errors: int = 50,
    middleware: Middleware | None = None,
    executor_class: type[Executor] | None = None,
    check_sync: bool = False,
    hide_suggestions: bool = False,
    abort_signal: AbortSignal | None = None,
    hooks: ExecutionHooks | None = None,
) -> ExecutionResult:
    """Execute a GraphQL operation synchronously.

    Also implements the "Executing requests" section of the GraphQL specification.

    However, it guarantees to complete synchronously (or throw an error) assuming
    that all field resolvers are also synchronous.

    Set check_sync to True to still run checks that no awaitable values are returned.
    """
    is_awaitable = (
        cast("Callable[[Any], TypeGuard[Awaitable]]", check_sync)
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
        max_coercion_errors,
        False,
        middleware,
        executor_class,
        is_awaitable,
        hide_suggestions=hide_suggestions,
        abort_signal=abort_signal,
        hooks=hooks,
    )

    # Assert that the execution was synchronous.
    if default_is_awaitable(result) or isinstance(
        result, ExperimentalIncrementalExecutionResults
    ):
        if default_is_awaitable(result):
            ensure_future(cast("Awaitable[ExecutionResult]", result)).cancel()
        msg = "GraphQL execution failed to complete synchronously."
        raise RuntimeError(msg)

    return cast("ExecutionResult", result)


def subscribe(
    schema: GraphQLSchema,
    document: DocumentNode,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: dict[str, Any] | None = None,
    operation_name: str | None = None,
    field_resolver: GraphQLFieldResolver | None = None,
    type_resolver: GraphQLTypeResolver | None = None,
    subscribe_field_resolver: GraphQLFieldResolver | None = None,
    max_coercion_errors: int = 50,
    enable_early_execution: bool = False,
    executor_class: type[Executor] | None = None,
    middleware: MiddlewareManager | None = None,
    hide_suggestions: bool = False,
    **custom_context_args: Any,
) -> AwaitableOrValue[AsyncIterator[ExecutionResult] | ExecutionResult]:
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
    If an operation that defers or streams data is executed with this function,
    a field error will be raised at the location of the `@defer` or `@stream` directive.

    To customize how each subscription event is executed, compose the subscription
    pipeline directly instead of calling this function: build an executor with
    :meth:`Executor.build`, resolve the source event stream with
    :func:`~graphql.execution.create_source_event_stream`, and map it to the response
    stream with :func:`~graphql.execution.map_source_to_response_event`, passing a
    custom ``root_selection_set_executor``.
    """
    if executor_class is None:
        executor_class = ExecutorThrowingOnIncremental

    # If a valid executor cannot be created due to incorrect arguments,
    # a "Response" with only errors is returned.
    executor = executor_class.build(
        schema,
        document,
        root_value,
        context_value,
        variable_values,
        operation_name,
        field_resolver,
        type_resolver,
        subscribe_field_resolver,
        max_coercion_errors,
        enable_early_execution,
        middleware=middleware,
        hide_suggestions=hide_suggestions,
        **custom_context_args,
    )

    # Return early errors if executor failed.
    if isinstance(executor, list):
        return ExecutionResult(None, errors=executor)

    if not is_subscription_operation_definition_node(executor.operation):
        msg = "Expected subscription operation."
        raise GraphQLError(msg)

    result_or_stream = create_source_event_stream(executor)

    if executor.is_awaitable(result_or_stream):

        async def await_result() -> Any:
            awaited_result_or_stream = await result_or_stream
            return (
                map_source_to_response_event(executor, awaited_result_or_stream)
                if executor.is_async_iterable(awaited_result_or_stream)
                else awaited_result_or_stream
            )

        return await_result()

    return (
        map_source_to_response_event(executor, result_or_stream)  # type: ignore
        if executor.is_async_iterable(result_or_stream)
        else result_or_stream
    )


def execute_root_selection_set(
    executor: Executor,
) -> AwaitableOrValue[ExecutionResult]:
    """Execute the root selection set.

    Implements the "Executing operations" section of the GraphQL specification,
    running the given executor to completion. This does not support
    incremental delivery (``@defer`` and ``@stream``).
    """
    return cast("AwaitableOrValue[ExecutionResult]", executor.execute_operation())


def execute_subscription_event(
    executor: Executor,
) -> AwaitableOrValue[ExecutionResult]:
    """Execute a single subscription event.

    This is the default ``root_selection_set_executor`` used by
    :func:`map_source_to_response_event`. It provides the "ExecuteSubscriptionEvent"
    algorithm described in the GraphQL specification, which is nearly identical to the
    "ExecuteQuery" algorithm. A custom executor may wrap this function to set up and
    tear down a per-event executor.

    The passed executor should be a per-event executor as created by
    :meth:`Executor.build_per_event_executor`.
    """
    return cast("AwaitableOrValue[ExecutionResult]", executor.execute_operation(False))


RootSelectionSetExecutor: TypeAlias = Callable[
    ["Executor"], "AwaitableOrValue[ExecutionResult]"
]


def map_source_to_response_event(
    executor: Executor,
    source_event_stream: AsyncIterable[Any],
    root_selection_set_executor: RootSelectionSetExecutor = execute_subscription_event,
) -> AsyncGenerator[ExecutionResult, None]:
    """Map a subscription source event stream to a response event stream.

    Implements the "MapSourceToResponseEvent" algorithm described in the GraphQL
    specification, mapping each event from a subscription source event stream to an
    ExecutionResult in the response stream.

    For each payload yielded from the source event stream, it is mapped over the normal
    GraphQL :func:`~graphql.execution.execute` function, with ``payload`` as the
    ``root_value``. Each event is executed with the given
    ``root_selection_set_executor``, which defaults to
    :func:`~graphql.execution.execute_subscription_event` (providing the
    "ExecuteSubscriptionEvent" algorithm) but can be overridden to set up and tear
    down a custom executor around the execution of each event.
    """
    build_executor = executor.build_per_event_executor

    async def callback(payload: Any) -> ExecutionResult:
        result = root_selection_set_executor(build_executor(payload))
        # typecast to ExecutionResult, not possible to return
        # ExperimentalIncrementalExecutionResults when operation is 'subscription'.
        return (
            await cast("Awaitable[ExecutionResult]", result)
            if executor.is_awaitable(result)
            else cast("ExecutionResult", result)
        )

    return map_async_iterable(
        executor.cancellable_iterable(source_event_stream), callback
    )


def create_source_event_stream(
    executor: Executor,
) -> AwaitableOrValue[AsyncIterable[Any] | ExecutionResult]:
    """Create source event stream

    Implements the "CreateSourceEventStream" algorithm described in the GraphQL
    specification, resolving the subscription source event stream for a
    previously built executor.

    Returns a coroutine that yields an AsyncIterable.

    If the built executor is invalid, or if the resolved event stream is not an
    async iterable, a GraphQL Response (ExecutionResult) with descriptive errors
    and no data will be returned.

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
    if not isinstance(executor, Executor):
        msg = (
            "Passing execution arguments to create_source_event_stream()"
            " was removed in graphql-core version 3.3;"
            " call Executor.build() first and pass the result instead,"
            " or use subscribe() for the full subscription pipeline."
        )
        raise GraphQLError(msg)

    try:
        event_stream = execute_subscription(executor)
    except GraphQLError as error:
        return ExecutionResult(None, errors=[error])

    if executor.is_awaitable(event_stream):

        async def await_event_stream() -> AsyncIterable[Any] | ExecutionResult:
            try:
                return await event_stream
            except GraphQLError as error:
                return ExecutionResult(None, errors=[error])

        return await_event_stream()

    return event_stream


def execute_subscription(
    executor: Executor,
) -> AwaitableOrValue[AsyncIterable[Any]]:
    schema = executor.schema

    root_type = schema.subscription_type
    if root_type is None:
        msg = "Schema is not configured to execute subscription operation."
        raise GraphQLError(msg, executor.operation)

    grouped_field_set = collect_fields(
        schema,
        executor.fragments,
        executor.variable_values,
        root_type,
        executor.operation,
        executor.hide_suggestions,
    ).grouped_field_set

    first_root_field = next(iter(grouped_field_set.items()))
    response_name, field_details_list = first_root_field
    field_name = field_details_list[0].node.name.value
    field_def = schema.get_field(root_type, field_name)

    field_nodes = [field_details.node for field_details in field_details_list]
    if not field_def:
        msg = f"The subscription field '{field_name}' is not defined."
        raise GraphQLError(msg, field_nodes)

    path = Path(None, response_name, root_type.name)
    info = executor.build_resolve_info(field_def, field_nodes, root_type, path)

    # Implements the "ResolveFieldEventStream" algorithm from GraphQL specification.
    # It differs from "ResolveFieldValue" due to providing a different `resolveFn`.

    try:
        # Build a dictionary of arguments from the field.arguments AST, using the
        # variables scope to fulfill any variable references.
        args = get_argument_values(
            field_def,
            field_nodes[0],
            executor.variable_values,
            field_details_list[0].fragment_variable_values,
            executor.hide_suggestions,
        )

        # Call the `subscribe()` resolver or the default resolver to produce an
        # AsyncIterable yielding raw payloads.
        resolve_fn = field_def.subscribe or executor.subscribe_field_resolver

        result = resolve_fn(executor.root_value, info, **args)
        if executor.is_awaitable(result):

            async def await_result() -> AsyncIterable[Any]:
                try:
                    return assert_event_stream(await executor.with_abort_signal(result))
                except Exception as error:
                    raise located_error(error, field_nodes, path.as_list()) from error

            return await_result()

        return assert_event_stream(result)

    except Exception as error:
        raise located_error(error, field_nodes, path.as_list()) from error


def assert_event_stream(result: Any) -> AsyncIterable:
    if isinstance(result, Exception):
        raise result

    # Assert field returned an event stream, otherwise yield an error.
    if not default_is_async_iterable(result):
        msg = (
            "Subscription field must return AsyncIterable."
            f" Received: {inspect(result)}."
        )
        raise GraphQLError(msg)

    return result
