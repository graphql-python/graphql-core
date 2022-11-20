from inspect import isawaitable
from typing import (
    Any,
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Dict,
    Optional,
    Type,
    Union,
    cast,
)

from ..error import GraphQLError, located_error
from ..execution.collect_fields import collect_fields
from ..execution.execute import (
    ExecutionContext,
    ExecutionResult,
    assert_valid_execution_arguments,
    execute,
)
from ..execution.values import get_argument_values
from ..language import DocumentNode
from ..pyutils import AwaitableOrValue, Path, inspect
from ..type import GraphQLFieldResolver, GraphQLSchema
from .map_async_iterator import MapAsyncIterator


__all__ = ["subscribe", "create_source_event_stream"]


def subscribe(
    schema: GraphQLSchema,
    document: DocumentNode,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: Optional[Dict[str, Any]] = None,
    operation_name: Optional[str] = None,
    field_resolver: Optional[GraphQLFieldResolver] = None,
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
    """
    result_or_stream = create_source_event_stream(
        schema,
        document,
        root_value,
        context_value,
        variable_values,
        operation_name,
        subscribe_field_resolver,
        execution_context_class,
    )

    async def map_source_to_response(payload: Any) -> ExecutionResult:
        """Map source to response.

        For each payload yielded from a subscription, map it over the normal GraphQL
        :func:`~graphql.execute` function, with ``payload`` as the ``root_value``.
        This implements the "MapSourceToResponseEvent" algorithm described in the
        GraphQL specification. The :func:`~graphql.execute` function provides the
        "ExecuteSubscriptionEvent" algorithm, as it is nearly identical to the
        "ExecuteQuery" algorithm, for which :func:`~graphql.execute` is also used.
        """
        result = execute(
            schema,
            document,
            payload,
            context_value,
            variable_values,
            operation_name,
            field_resolver,
            execution_context_class=execution_context_class,
        )
        return await result if isawaitable(result) else result

    if (execution_context_class or ExecutionContext).is_awaitable(result_or_stream):
        awaitable_result_or_stream = cast(Awaitable, result_or_stream)

        # noinspection PyShadowingNames
        async def await_result() -> Any:
            result_or_stream = await awaitable_result_or_stream
            if isinstance(result_or_stream, ExecutionResult):
                return result_or_stream
            return MapAsyncIterator(result_or_stream, map_source_to_response)

        return await_result()

    if isinstance(result_or_stream, ExecutionResult):
        return result_or_stream

    # Map every source value to a ExecutionResult value as described above.
    return MapAsyncIterator(
        cast(AsyncIterable[Any], result_or_stream), map_source_to_response
    )


def create_source_event_stream(
    schema: GraphQLSchema,
    document: DocumentNode,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: Optional[Dict[str, Any]] = None,
    operation_name: Optional[str] = None,
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
    # If arguments are missing or incorrectly typed, this is an internal developer
    # mistake which should throw an early error.
    assert_valid_execution_arguments(schema, document, variable_values)

    if not execution_context_class:
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
        subscribe_field_resolver=subscribe_field_resolver,
    )

    # Return early errors if execution context failed.
    if isinstance(context, list):
        return ExecutionResult(data=None, errors=context)

    try:
        event_stream = execute_subscription(context)
    except GraphQLError as error:
        return ExecutionResult(data=None, errors=[error])

    if context.is_awaitable(event_stream):
        awaitable_event_stream = cast(Awaitable, event_stream)

        # noinspection PyShadowingNames
        async def await_event_stream() -> Union[AsyncIterable[Any], ExecutionResult]:
            try:
                return await awaitable_event_stream
            except GraphQLError as error:
                return ExecutionResult(data=None, errors=[error])

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
    )
    response_name, field_nodes = next(iter(root_fields.items()))
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
