"""GraphQL execution"""

from __future__ import annotations

from asyncio import (
    TimeoutError,  # only needed for Python < 3.11  # noqa: A004
    ensure_future,
    sleep,
)
from collections.abc import (
    AsyncGenerator,
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Callable,
    Iterable,
    Mapping,
    Sequence,
)
from contextlib import suppress
from copy import copy
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    NamedTuple,
    TypeVar,
    cast,
)

from ..error import GraphQLError, located_error
from ..language import (
    DocumentNode,
    FieldNode,
    FragmentDefinitionNode,
    OperationDefinitionNode,
    OperationType,
)
from ..pyutils import (
    AwaitableOrValue,
    BoxedAwaitableOrValue,
    Path,
    RefMap,
    Undefined,
    async_reduce,
    gather_with_cancel,
    inspect,
    is_iterable,
)
from ..pyutils.is_awaitable import is_awaitable as default_is_awaitable
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
from .async_iterables import map_async_iterable
from .build_field_plan import (
    DeferUsageSet,
    FieldGroup,
    FieldPlan,
    GroupedFieldSet,
    build_field_plan,
)
from .collect_fields import (
    CollectedFields,
    DeferUsage,
    FieldDetails,
    collect_fields,
    collect_subfields,
)
from .incremental_publisher import (
    IncrementalPublisherContext,
    build_incremental_response,
)
from .middleware import MiddlewareManager
from .types import (
    BareDeferredGroupedFieldSetResult,
    CancellableStreamRecord,
    DeferredFragmentRecord,
    DeferredGroupedFieldSetRecord,
    DeferredGroupedFieldSetResult,
    ExecutionResult,
    ExperimentalIncrementalExecutionResults,
    IncrementalDataRecord,
    NonReconcilableDeferredGroupedFieldSetResult,
    ReconcilableDeferredGroupedFieldSetResult,
    StreamItemRecord,
    StreamItemResult,
    StreamRecord,
)
from .values import get_argument_values, get_directive_values, get_variable_values

if TYPE_CHECKING:
    from typing import TypeAlias, TypeGuard

    from ..pyutils import UndefinedType

__all__ = [
    "ExecutionContext",
    "GraphQLWrappedResult",
    "Middleware",
    "create_source_event_stream",
    "default_field_resolver",
    "default_type_resolver",
    "execute",
    "execute_sync",
    "experimental_execute_incrementally",
    "subscribe",
]

suppress_exceptions = suppress(Exception)
suppress_timeout_error = suppress(TimeoutError)


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


Middleware: TypeAlias = tuple | list | MiddlewareManager | None


class StreamUsage(NamedTuple):
    """Stream directive usage information"""

    label: str | None
    initial_count: int
    field_group: FieldGroup


class SubFieldPlan(NamedTuple):
    """A plan for executing fields with defer usages."""

    grouped_field_set: GroupedFieldSet
    new_grouped_field_sets: RefMap[DeferUsageSet, GroupedFieldSet]
    new_defer_usages: list[DeferUsage]


class IncrementalContext:
    """A context for incremental execution."""

    errors: list[GraphQLError] | None
    defer_usage_set: DeferUsageSet | None

    __slots__ = "defer_usage_set", "errors"

    def __init__(self, defer_usage_set: DeferUsageSet | None = None) -> None:
        self.errors = None
        self.defer_usage_set = defer_usage_set


class ExecutionContext(IncrementalPublisherContext):
    """Data that must be available at all points during query execution.

    Namely, schema of the type system that is currently executing, and the fragments
    defined in the query document.
    """

    schema: GraphQLSchema
    fragments: dict[str, FragmentDefinitionNode]
    root_value: Any
    context_value: Any
    operation: OperationDefinitionNode
    variable_values: dict[str, Any]
    field_resolver: GraphQLFieldResolver
    type_resolver: GraphQLTypeResolver
    subscribe_field_resolver: GraphQLFieldResolver
    enable_early_execution: bool
    errors: list[GraphQLError] | None
    cancellable_streams: set[CancellableStreamRecord] | None
    middleware_manager: MiddlewareManager | None

    is_awaitable: Callable[[Any], TypeGuard[Awaitable]] = staticmethod(
        default_is_awaitable  # type: ignore
    )

    def __init__(
        self,
        schema: GraphQLSchema,
        fragments: dict[str, FragmentDefinitionNode],
        root_value: Any,
        context_value: Any,
        operation: OperationDefinitionNode,
        variable_values: dict[str, Any],
        field_resolver: GraphQLFieldResolver,
        type_resolver: GraphQLTypeResolver,
        subscribe_field_resolver: GraphQLFieldResolver,
        enable_early_execution: bool = False,
        middleware_manager: MiddlewareManager | None = None,
        is_awaitable: Callable[[Any], TypeGuard[Awaitable]] | None = None,
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
        self.enable_early_execution = enable_early_execution
        self.middleware_manager = middleware_manager
        self.is_awaitable = is_awaitable or default_is_awaitable
        self.errors = None
        self.cancellable_streams = None
        self._canceled_iterators: set[AsyncIterator] = set()
        self._relevant_sub_fields: dict[tuple, CollectedFields] = {}
        self._stream_usages: RefMap[FieldGroup, StreamUsage] = RefMap()
        self._field_plans: RefMap[GroupedFieldSet, FieldPlan] = RefMap()

    @classmethod
    def build(
        cls,
        schema: GraphQLSchema,
        document: DocumentNode,
        root_value: Any = None,
        context_value: Any = None,
        raw_variable_values: dict[str, Any] | None = None,
        operation_name: str | None = None,
        field_resolver: GraphQLFieldResolver | None = None,
        type_resolver: GraphQLTypeResolver | None = None,
        subscribe_field_resolver: GraphQLFieldResolver | None = None,
        enable_early_execution: bool = False,
        middleware: Middleware | None = None,
        is_awaitable: Callable[[Any], TypeGuard[Awaitable]] | None = None,
        **custom_args: Any,
    ) -> list[GraphQLError] | ExecutionContext:
        """Build an execution context

        Constructs a ExecutionContext object from the arguments passed to execute, which
        we will pass throughout the other execution methods.

        Throws a GraphQLError if a valid execution context cannot be created.

        For internal use only.
        """
        # If the schema used for execution is invalid, raise an error.
        assert_valid_schema(schema)

        operation: OperationDefinitionNode | None = None
        fragments: dict[str, FragmentDefinitionNode] = {}
        middleware_manager: MiddlewareManager | None = None
        if middleware is not None:
            if isinstance(middleware, (list, tuple)):
                middleware_manager = MiddlewareManager(*middleware)
            elif isinstance(middleware, MiddlewareManager):
                middleware_manager = middleware
            else:
                msg = (
                    "Middleware must be passed as a list or tuple of functions"
                    " or objects, or as a single MiddlewareManager object."
                    f" Got {inspect(middleware)} instead."
                )
                raise TypeError(msg)

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
            enable_early_execution,
            middleware_manager,
            is_awaitable,
            **custom_args,
        )

    def build_per_event_execution_context(self, payload: Any) -> ExecutionContext:
        """Create a copy of the execution context for usage with subscribe events."""
        context = copy(self)
        context.root_value = payload
        context.errors = None
        return context

    def execute_operation(
        self,
    ) -> AwaitableOrValue[ExecutionResult | ExperimentalIncrementalExecutionResults]:
        """Execute an operation.

        Implements the "Executing operations" section of the spec.

        Return a possible coroutine object that will eventually yield the data described
        by the "Response" section of the GraphQL specification.

        If errors are encountered while executing a GraphQL field, only that field and
        its descendants will be omitted, and sibling fields will still be executed. An
        execution which encounters errors will still result in a coroutine object that
        can be executed without errors.

        Errors from sub-fields of a NonNull type may propagate to the top level,
        at which point we still log the error and null the parent field, which
        in this case is the entire response.
        """
        try:
            operation = self.operation
            schema = self.schema
            root_type = schema.get_root_type(operation.operation)
            if root_type is None:
                msg = (
                    "Schema is not configured to execute"
                    f" {operation.operation.value} operation."
                )
                raise GraphQLError(msg, operation)  # noqa: TRY301
            root_value = self.root_value

            collected_fields = collect_fields(
                schema, self.fragments, self.variable_values, root_type, operation
            )
            grouped_field_set, new_defer_usages = collected_fields

            if new_defer_usages:
                field_plan = build_field_plan(grouped_field_set)
                grouped_field_set = field_plan.grouped_field_set
                new_grouped_field_sets = field_plan.new_grouped_field_sets
                new_defer_map = add_new_deferred_fragments(new_defer_usages, RefMap())
                graphql_wrapped_result = self.execute_root_grouped_field_set(
                    operation.operation,
                    root_type,
                    root_value,
                    grouped_field_set,
                    new_defer_map,
                )
                if new_grouped_field_sets:
                    new_deferred_grouped_field_set_records = (
                        self.execute_deferred_grouped_field_sets(
                            root_type,
                            root_value,
                            None,
                            None,
                            new_grouped_field_sets,
                            new_defer_map,
                        )
                    )
                    graphql_wrapped_result = self.with_new_deferred_grouped_field_sets(
                        graphql_wrapped_result, new_deferred_grouped_field_set_records
                    )

            else:
                graphql_wrapped_result = self.execute_root_grouped_field_set(
                    operation.operation, root_type, root_value, grouped_field_set, None
                )

            if self.is_awaitable(graphql_wrapped_result):

                async def await_result() -> (
                    ExecutionResult | ExperimentalIncrementalExecutionResults
                ):
                    try:
                        resolved = await graphql_wrapped_result
                    except GraphQLError as error:
                        return ExecutionResult(None, with_error(self.errors, error))
                    return self.build_data_response(
                        resolved.result, resolved.increments
                    )

                return await_result()

            resolved = cast("GraphQLWrappedResult", graphql_wrapped_result)

        except GraphQLError as error:
            return ExecutionResult(None, with_error(self.errors, error))

        return self.build_data_response(resolved.result, resolved.increments)

    def execute_root_grouped_field_set(
        self,
        operation: OperationType,
        root_type: GraphQLObjectType,
        root_value: Any,
        grouped_field_set: GroupedFieldSet,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord] | None,
    ) -> AwaitableOrValue[GraphQLWrappedResult[dict[str, Any]]]:
        """Execute the root grouped field set."""
        return (
            self.execute_fields_serially
            if operation == OperationType.MUTATION
            else self.execute_fields
        )(
            root_type,
            root_value,
            None,
            grouped_field_set,
            None,
            defer_map,
        )

    def execute_fields_serially(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Path | None,
        grouped_field_set: GroupedFieldSet,
        incremental_context: IncrementalContext | None,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord] | None,
    ) -> AwaitableOrValue[GraphQLWrappedResult[dict[str, Any]]]:
        """Execute the given fields serially.

        Implements the "Executing selection sets" section of the spec
        for fields that must be executed serially.
        """
        is_awaitable = self.is_awaitable

        def reducer(
            graphql_wrapped_result: GraphQLWrappedResult[dict[str, Any]],
            field_item: tuple[str, FieldGroup],
        ) -> AwaitableOrValue[GraphQLWrappedResult[dict[str, Any]]]:
            response_name, field_group = field_item
            field_path = Path(path, response_name, parent_type.name)
            result = self.execute_field(
                parent_type,
                source_value,
                field_group,
                field_path,
                incremental_context,
                defer_map,
            )
            if result is Undefined:
                return graphql_wrapped_result
            if is_awaitable(result):

                async def set_result() -> GraphQLWrappedResult[dict[str, Any]]:
                    resolved = await result
                    graphql_wrapped_result.result[response_name] = resolved.result
                    graphql_wrapped_result.add_increments(resolved.increments)
                    return graphql_wrapped_result

                return set_result()

            resolved = cast("GraphQLWrappedResult[dict[str, Any]]", result)
            graphql_wrapped_result.result[response_name] = resolved.result
            graphql_wrapped_result.add_increments(resolved.increments)
            return graphql_wrapped_result

        return async_reduce(
            reducer, grouped_field_set.items(), GraphQLWrappedResult({})
        )

    def execute_fields(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Path | None,
        grouped_field_set: GroupedFieldSet,
        incremental_context: IncrementalContext | None,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord] | None,
    ) -> AwaitableOrValue[GraphQLWrappedResult[dict[str, Any]]]:
        """Execute the given fields concurrently.

        Implements the "Executing selection sets" section of the spec
        for fields that may be executed in parallel.
        """
        results: dict[str, Any] = {}
        graphql_wrapped_result = GraphQLWrappedResult(results)
        add_increments = graphql_wrapped_result.add_increments
        is_awaitable = self.is_awaitable
        awaitable_fields: list[str] = []
        append_awaitable = awaitable_fields.append
        for response_name, field_group in grouped_field_set.items():
            field_path = Path(path, response_name, parent_type.name)
            result = self.execute_field(
                parent_type,
                source_value,
                field_group,
                field_path,
                incremental_context,
                defer_map,
            )
            if result is not Undefined:
                if is_awaitable(result):

                    async def resolve(
                        result: Awaitable[GraphQLWrappedResult[dict[str, Any]]],
                    ) -> dict[str, Any]:
                        resolved = await result
                        add_increments(resolved.increments)
                        return resolved.result

                    results[response_name] = resolve(result)
                    append_awaitable(response_name)
                else:
                    result = cast("GraphQLWrappedResult[dict[str, Any]]", result)
                    results[response_name] = result.result
                    add_increments(result.increments)

        # If there are no coroutines, we can just return the object.
        if not awaitable_fields:
            return graphql_wrapped_result

        # Otherwise, results is a map from field name to the result of resolving that
        # field, which is possibly a coroutine object. Return a coroutine object that
        # will yield this same map, but with any coroutines awaited in parallel and
        # replaced with the values they yielded.
        async def get_results() -> GraphQLWrappedResult[dict[str, Any]]:
            if len(awaitable_fields) == 1:
                # If there is only one field, avoid the overhead of parallelization.
                field = awaitable_fields[0]
                results[field] = await results[field]
            else:
                awaited_results = await gather_with_cancel(
                    *(results[field] for field in awaitable_fields)
                )
                results.update(zip(awaitable_fields, awaited_results, strict=True))

            return GraphQLWrappedResult(results, graphql_wrapped_result.increments)

        return get_results()

    def execute_field(
        self,
        parent_type: GraphQLObjectType,
        source: Any,
        field_group: FieldGroup,
        path: Path,
        incremental_context: IncrementalContext | None,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord] | None,
    ) -> AwaitableOrValue[GraphQLWrappedResult[Any]] | UndefinedType:
        """Resolve the field on the given source object.

        Implements the "Executing fields" section of the spec.

        In particular, this method figures out the value that the field returns by
        calling its resolve function, then calls complete_value to await coroutine
        objects, serialize scalars, or execute the sub-selection-set for objects.
        """
        field_name = field_group[0].node.name.value
        field_def = self.schema.get_field(parent_type, field_name)
        if not field_def:
            return Undefined

        return_type = field_def.type
        resolve_fn = field_def.resolve or self.field_resolver

        if self.middleware_manager:
            resolve_fn = self.middleware_manager.get_field_resolver(resolve_fn)

        info = self.build_resolve_info(
            field_def, to_nodes(field_group), parent_type, path
        )

        # Get the resolve function, regardless of if its result is normal or abrupt
        # (error).
        try:
            # Build a dictionary of arguments from the field.arguments AST, using the
            # variables scope to fulfill any variable references.
            args = get_argument_values(
                field_def, field_group[0].node, self.variable_values
            )

            # Note that contrary to the JavaScript implementation, we pass the context
            # value as part of the resolve info.
            result = resolve_fn(source, info, **args)

            if self.is_awaitable(result):
                return self.complete_awaitable_value(
                    return_type,
                    field_group,
                    info,
                    path,
                    result,
                    incremental_context,
                    defer_map,
                )

            completed = self.complete_value(
                return_type,
                field_group,
                info,
                path,
                result,
                incremental_context,
                defer_map,
            )
            if self.is_awaitable(completed):

                async def await_completed() -> Any:
                    try:
                        return await completed
                    except Exception as raw_error:
                        self.handle_field_error(
                            raw_error,
                            return_type,
                            field_group,
                            path,
                            incremental_context,
                        )
                        return GraphQLWrappedResult(None)

                return await_completed()

        except Exception as raw_error:
            self.handle_field_error(
                raw_error,
                return_type,
                field_group,
                path,
                incremental_context,
            )
            return GraphQLWrappedResult(None)

        return completed

    def build_resolve_info(
        self,
        field_def: GraphQLField,
        field_nodes: list[FieldNode],
        parent_type: GraphQLObjectType,
        path: Path,
    ) -> GraphQLResolveInfo:
        """Build the GraphQLResolveInfo object.

        For internal use only.
        """
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

    def handle_field_error(
        self,
        raw_error: Exception,
        return_type: GraphQLOutputType,
        field_group: FieldGroup,
        path: Path,
        incremental_context: IncrementalContext | None = None,
    ) -> None:
        """Handle error properly according to the field type."""
        error = located_error(raw_error, to_nodes(field_group), path.as_list())

        # If the field type is non-nullable, then it is resolved without any protection
        # from errors, however it still properly locates the error.
        if is_non_null_type(return_type):
            raise error

        # Otherwise, error protection is applied, logging the error and resolving a
        # null value for this field if one is encountered.
        context = incremental_context or self
        errors = context.errors
        if errors is None:
            context.errors = errors = []
        errors.append(error)

    def complete_value(
        self,
        return_type: GraphQLOutputType,
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        path: Path,
        result: Any,
        incremental_context: IncrementalContext | None,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord] | None,
    ) -> AwaitableOrValue[GraphQLWrappedResult[Any]]:
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
                field_group,
                info,
                path,
                result,
                incremental_context,
                defer_map,
            )
            if isinstance(completed, GraphQLWrappedResult) and completed.result is None:
                msg = (
                    "Cannot return null for non-nullable field"
                    f" {info.parent_type.name}.{info.field_name}."
                )
                raise TypeError(msg)
            return completed

        # If result value is null or undefined then return null.
        if result is None or result is Undefined:
            return GraphQLWrappedResult(None)

        # If field type is List, complete each item in the list with inner type
        if is_list_type(return_type):
            return self.complete_list_value(
                return_type,
                field_group,
                info,
                path,
                result,
                incremental_context,
                defer_map,
            )

        # If field type is a leaf type, Scalar or Enum, serialize to a valid value,
        # returning null if serialization is not possible.
        if is_leaf_type(return_type):
            return GraphQLWrappedResult(self.complete_leaf_value(return_type, result))

        # If field type is an abstract type, Interface or Union, determine the runtime
        # Object type and complete for that type.
        if is_abstract_type(return_type):
            return self.complete_abstract_value(
                return_type,
                field_group,
                info,
                path,
                result,
                incremental_context,
                defer_map,
            )

        # If field type is Object, execute and complete all sub-selections.
        if is_object_type(return_type):
            return self.complete_object_value(
                return_type,
                field_group,
                info,
                path,
                result,
                incremental_context,
                defer_map,
            )

        # Not reachable. All possible output types have been considered.
        msg = (
            "Cannot complete value of unexpected output type:"
            f" '{inspect(return_type)}'."
        )  # pragma: no cover
        raise TypeError(msg)  # pragma: no cover

    async def complete_awaitable_value(
        self,
        return_type: GraphQLOutputType,
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        path: Path,
        result: Any,
        incremental_context: IncrementalContext | None,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord] | None,
    ) -> GraphQLWrappedResult[Any]:
        """Complete an awaitable value."""
        try:
            resolved = await result
            completed = self.complete_value(
                return_type,
                field_group,
                info,
                path,
                resolved,
                incremental_context,
                defer_map,
            )
            if self.is_awaitable(completed):
                completed = await completed
        except Exception as raw_error:
            self.handle_field_error(
                raw_error, return_type, field_group, path, incremental_context
            )
            completed = GraphQLWrappedResult(None)
        return completed  # type: ignore

    def get_stream_usage(
        self, field_group: FieldGroup, path: Path
    ) -> StreamUsage | None:
        """Get stream usage.

        Returns an object containing info for streaming if a field should be
        streamed based on the experimental flag, stream directive present and
        not disabled by the "if" argument.
        """
        # do not stream inner lists of multidimensional lists
        if isinstance(path.key, int):
            return None

        stream_usage = self._stream_usages.get(field_group)
        if stream_usage is not None:
            return stream_usage  # pragma: no cover

        # validation only allows equivalent streams on multiple fields, so it is
        # safe to only check the first field_node for the stream directive
        stream = get_directive_values(
            GraphQLStreamDirective, field_group[0].node, self.variable_values
        )

        if not stream or stream.get("if") is False:
            return None

        initial_count = stream.get("initialCount")
        if initial_count is None or initial_count < 0:
            msg = "initialCount must be a positive integer"
            raise ValueError(msg)

        if self.operation.operation == OperationType.SUBSCRIPTION:
            msg = (
                "`@stream` directive not supported on subscription operations."
                " Disable `@stream` by setting the `if` argument to `false`."
            )
            raise TypeError(msg)

        streamed_field_group: FieldGroup = [
            FieldDetails(field_details.node, None) for field_details in field_group
        ]

        stream_usage = StreamUsage(
            stream.get("label"), stream["initialCount"], streamed_field_group
        )

        self._stream_usages[field_group] = stream_usage

        return stream_usage

    async def complete_async_iterator_value(
        self,
        item_type: GraphQLOutputType,
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        path: Path,
        async_iterator: AsyncIterator[Any],
        incremental_context: IncrementalContext | None,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord] | None,
    ) -> GraphQLWrappedResult[list[Any]]:
        """Complete an async iterator.

        Complete an async iterator value by completing the result and calling
        recursively until all the results are completed.
        """
        is_awaitable = self.is_awaitable
        complete_list_item_value = self.complete_list_item_value
        complete_awaitable_list_item_value = self.complete_awaitable_list_item_value
        completed_results: list[Any] = []
        append_completed = completed_results.append
        graphql_wrapped_result = GraphQLWrappedResult(completed_results)
        add_increment = graphql_wrapped_result.add_increment
        awaitable_indices: list[int] = []
        append_awaitable = awaitable_indices.append
        stream_usage = self.get_stream_usage(field_group, path)
        index = 0
        while True:
            if stream_usage and index >= stream_usage.initial_count:
                stream_item_queue = self.build_async_stream_item_queue(
                    index,
                    path,
                    async_iterator,
                    stream_usage.field_group,
                    info,
                    item_type,
                )

                try:
                    early_return = async_iterator.aclose()  # type: ignore
                except AttributeError:
                    early_return = None
                stream_record: StreamRecord

                if early_return is None:
                    stream_record = StreamRecord(
                        stream_item_queue, path, stream_usage.label
                    )
                else:
                    stream_record = CancellableStreamRecord(
                        early_return,
                        stream_item_queue,
                        path,
                        stream_usage.label,
                    )
                    if self.cancellable_streams is None:  # pragma: no branch
                        self.cancellable_streams = set()
                    self.cancellable_streams.add(stream_record)
                    self._canceled_iterators.add(async_iterator)

                add_increment(stream_record)
                break

            item_path = path.add_key(index, None)
            try:
                item = await anext(async_iterator)
            except StopAsyncIteration:
                break
            except Exception as raw_error:
                raise located_error(
                    raw_error, to_nodes(field_group), path.as_list()
                ) from raw_error

            if is_awaitable(item):
                append_completed(
                    complete_awaitable_list_item_value(
                        item,
                        graphql_wrapped_result,
                        item_type,
                        field_group,
                        info,
                        item_path,
                        incremental_context,
                        defer_map,
                    )
                )
                append_awaitable(index)

            elif complete_list_item_value(
                item,
                completed_results,
                graphql_wrapped_result,
                item_type,
                field_group,
                info,
                item_path,
                incremental_context,
                defer_map,
            ):
                append_awaitable(index)

            index += 1

        if not awaitable_indices:
            return graphql_wrapped_result

        if len(awaitable_indices) == 1:
            # If there is only one index, avoid the overhead of parallelization.
            index = awaitable_indices[0]
            completed_results[index] = await completed_results[index]
        else:
            awaited_results = await gather_with_cancel(
                *(completed_results[index] for index in awaitable_indices)
            )
            for index, sub_result in zip(
                awaitable_indices, awaited_results, strict=True
            ):
                completed_results[index] = sub_result
        return GraphQLWrappedResult(
            completed_results, graphql_wrapped_result.increments
        )

    def complete_list_value(
        self,
        return_type: GraphQLList[GraphQLOutputType],
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        path: Path,
        result: AsyncIterable[Any] | Iterable[Any],
        incremental_context: IncrementalContext | None,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord] | None,
    ) -> AwaitableOrValue[GraphQLWrappedResult[list[Any]]]:
        """Complete a list value.

        Complete a list value by completing each item in the list with the inner type.
        """
        item_type = return_type.of_type

        if isinstance(result, AsyncIterable):
            async_iterator = result.__aiter__()

            return self.complete_async_iterator_value(
                item_type,
                field_group,
                info,
                path,
                async_iterator,
                incremental_context,
                defer_map,
            )

        if not is_iterable(result):
            msg = (
                "Expected Iterable, but did not find one for field"
                f" '{info.parent_type.name}.{info.field_name}'."
            )
            raise GraphQLError(msg)

        return self.complete_iterable_value(
            item_type,
            field_group,
            info,
            path,
            result,
            incremental_context,
            defer_map,
        )

    def complete_iterable_value(
        self,
        item_type: GraphQLOutputType,
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        path: Path,
        items: Iterable[Any],
        incremental_context: IncrementalContext | None,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord] | None,
    ) -> AwaitableOrValue[GraphQLWrappedResult[list[Any]]]:
        """Complete an iterable value."""
        # This is specified as a simple map, however we're optimizing the path
        # where the list contains no awaitable routine objects by avoiding creating
        # another awaitable object.
        is_awaitable = self.is_awaitable
        complete_list_item_value = self.complete_list_item_value
        complete_awaitable_list_item_value = self.complete_awaitable_list_item_value
        completed_results: list[Any] = []
        graphql_wrapped_result = GraphQLWrappedResult(completed_results)
        add_increment = graphql_wrapped_result.add_increment
        append_completed = completed_results.append
        awaitable_indices: list[int] = []
        append_awaitable = awaitable_indices.append
        stream_usage = self.get_stream_usage(field_group, path)
        iterator = iter(items)
        index = 0
        while True:
            try:
                item = next(iterator)
            except StopIteration:
                break
            if stream_usage and index >= stream_usage.initial_count:
                sync_stream_item_queue = self.build_sync_stream_item_queue(
                    item,
                    index,
                    path,
                    iterator,
                    stream_usage.field_group,
                    info,
                    item_type,
                )
                sync_stream_record = StreamRecord(
                    sync_stream_item_queue, path, stream_usage.label
                )

                add_increment(sync_stream_record)
                break

            # No need to modify the info object containing the path,
            # since from here on it is not ever accessed by resolver functions.
            item_path = path.add_key(index, None)

            if is_awaitable(item):
                append_completed(
                    complete_awaitable_list_item_value(
                        item,
                        graphql_wrapped_result,
                        item_type,
                        field_group,
                        info,
                        item_path,
                        incremental_context,
                        defer_map,
                    )
                )
                append_awaitable(index)

            elif complete_list_item_value(
                item,
                completed_results,
                graphql_wrapped_result,
                item_type,
                field_group,
                info,
                item_path,
                incremental_context,
                defer_map,
            ):
                append_awaitable(index)

            index += 1

        if not awaitable_indices:
            return graphql_wrapped_result

        async def get_completed_results() -> GraphQLWrappedResult[list[Any]]:
            if len(awaitable_indices) == 1:
                # If there is only one index, avoid the overhead of parallelization.
                index = awaitable_indices[0]
                completed_results[index] = await completed_results[index]
            else:
                awaited_results = await gather_with_cancel(
                    *(completed_results[index] for index in awaitable_indices)
                )
                for index, sub_result in zip(
                    awaitable_indices, awaited_results, strict=True
                ):
                    completed_results[index] = sub_result
            return GraphQLWrappedResult(
                completed_results, graphql_wrapped_result.increments
            )

        return get_completed_results()

    def complete_list_item_value(
        self,
        item: Any,
        complete_results: list[Any],
        parent: GraphQLWrappedResult[list[Any]],
        item_type: GraphQLOutputType,
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        item_path: Path,
        incremental_context: IncrementalContext | None,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord] | None,
    ) -> bool:
        """Complete a list item value by adding it to the completed results.

        Returns True if the value is awaitable.
        """
        is_awaitable = self.is_awaitable

        try:
            completed_item = self.complete_value(
                item_type,
                field_group,
                info,
                item_path,
                item,
                incremental_context,
                defer_map,
            )

            if is_awaitable(completed_item):

                async def await_completed() -> Any:
                    try:
                        resolved = await completed_item  # type: ignore
                    except Exception as raw_error:
                        self.handle_field_error(
                            raw_error,
                            item_type,
                            field_group,
                            item_path,
                            incremental_context,
                        )
                        return None
                    parent.add_increments(resolved.increments)
                    return resolved.result

                complete_results.append(await_completed())
                return True

            completed_item = cast("GraphQLWrappedResult[Any]", completed_item)
            complete_results.append(completed_item.result)
            parent.add_increments(completed_item.increments)

        except Exception as raw_error:
            self.handle_field_error(
                raw_error,
                item_type,
                field_group,
                item_path,
                incremental_context,
            )
            complete_results.append(None)

        return False

    async def complete_awaitable_list_item_value(
        self,
        item: Any,
        parent: GraphQLWrappedResult[list[Any]],
        item_type: GraphQLOutputType,
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        item_path: Path,
        incremental_context: IncrementalContext | None,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord] | None,
    ) -> Any:
        """Complete an awaitable list item value."""
        try:
            resolved = await item
            completed = self.complete_value(
                item_type,
                field_group,
                info,
                item_path,
                resolved,
                incremental_context,
                defer_map,
            )
            if self.is_awaitable(completed):
                completed = await completed
            completed = cast("GraphQLWrappedResult[list[Any]]", completed)
            parent.add_increments(completed.increments)
        except Exception as raw_error:
            self.handle_field_error(
                raw_error,
                item_type,
                field_group,
                item_path,
                incremental_context,
            )
            return None
        else:
            return completed.result

    @staticmethod
    def complete_leaf_value(return_type: GraphQLLeafType, result: Any) -> Any:
        """Complete a leaf value.

        Complete a Scalar or Enum by serializing to a valid value, returning null if
        serialization is not possible.
        """
        serialized_result = return_type.serialize(result)
        if serialized_result is Undefined or serialized_result is None:
            msg = (
                f"Expected `{inspect(return_type)}.serialize({inspect(result)})`"
                " to return non-nullable value, returned:"
                f" {inspect(serialized_result)}"
            )
            raise TypeError(msg)
        return serialized_result

    def complete_abstract_value(
        self,
        return_type: GraphQLAbstractType,
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        path: Path,
        result: Any,
        incremental_context: IncrementalContext | None,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord] | None,
    ) -> AwaitableOrValue[GraphQLWrappedResult[dict[str, Any]]]:
        """Complete an abstract value.

        Complete a value of an abstract type by determining the runtime object type of
        that value, then complete the value for that type.
        """
        resolve_type_fn = return_type.resolve_type or self.type_resolver
        runtime_type = resolve_type_fn(result, info, return_type)

        if self.is_awaitable(runtime_type):

            async def await_complete_object_value() -> Any:
                value = self.complete_object_value(
                    self.ensure_valid_runtime_type(
                        await runtime_type,  # type: ignore
                        return_type,
                        field_group,
                        info,
                        result,
                    ),
                    field_group,
                    info,
                    path,
                    result,
                    incremental_context,
                    defer_map,
                )
                if self.is_awaitable(value):
                    return await value
                return value  # pragma: no cover

            return await_complete_object_value()
        runtime_type = cast("str | None", runtime_type)

        return self.complete_object_value(
            self.ensure_valid_runtime_type(
                runtime_type, return_type, field_group, info, result
            ),
            field_group,
            info,
            path,
            result,
            incremental_context,
            defer_map,
        )

    def ensure_valid_runtime_type(
        self,
        runtime_type_name: Any,
        return_type: GraphQLAbstractType,
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        result: Any,
    ) -> GraphQLObjectType:
        """Ensure that the given type is valid at runtime."""
        if runtime_type_name is None:
            msg = (
                f"Abstract type '{return_type.name}' must resolve"
                " to an Object type at runtime"
                f" for field '{info.parent_type.name}.{info.field_name}'."
                f" Either the '{return_type.name}' type should provide"
                " a 'resolve_type' function or each possible type should provide"
                " an 'is_type_of' function."
            )
            raise GraphQLError(msg, to_nodes(field_group))

        if is_object_type(runtime_type_name):  # pragma: no cover
            msg = (
                "Support for returning GraphQLObjectType from resolve_type was"
                " removed in GraphQL-core 3.2, please return type name instead."
            )
            raise GraphQLError(msg)

        if not isinstance(runtime_type_name, str):
            msg = (
                f"Abstract type '{return_type.name}' must resolve"
                " to an Object type at runtime"
                f" for field '{info.parent_type.name}.{info.field_name}' with value"
                f" {inspect(result)}, received '{inspect(runtime_type_name)}'."
            )
            raise GraphQLError(msg, to_nodes(field_group))

        runtime_type = self.schema.get_type(runtime_type_name)

        if runtime_type is None:
            msg = (
                f"Abstract type '{return_type.name}' was resolved to a type"
                f" '{runtime_type_name}' that does not exist inside the schema."
            )
            raise GraphQLError(msg, to_nodes(field_group))

        if not is_object_type(runtime_type):
            msg = (
                f"Abstract type '{return_type.name}' was resolved"
                f" to a non-object type '{runtime_type_name}'."
            )
            raise GraphQLError(msg, to_nodes(field_group))

        if not self.schema.is_sub_type(return_type, runtime_type):
            msg = (
                f"Runtime Object type '{runtime_type.name}' is not a possible"
                f" type for '{return_type.name}'."
            )
            raise GraphQLError(msg, to_nodes(field_group))

        return runtime_type

    def complete_object_value(
        self,
        return_type: GraphQLObjectType,
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        path: Path,
        result: Any,
        incremental_context: IncrementalContext | None,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord] | None,
    ) -> AwaitableOrValue[GraphQLWrappedResult[dict[str, Any]]]:
        """Complete an Object value by executing all sub-selections."""
        # If there is an `is_type_of()` predicate function, call it with the current
        # result. If `is_type_of()` returns False, then raise an error rather than
        # continuing execution.
        if return_type.is_type_of:
            is_type_of = return_type.is_type_of(result, info)

            if self.is_awaitable(is_type_of):

                async def execute_subfields_async() -> GraphQLWrappedResult[
                    dict[str, Any]
                ]:
                    if not await is_type_of:
                        raise invalid_return_type_error(
                            return_type, result, field_group
                        )
                    graphql_wrapped_result = self.collect_and_execute_subfields(
                        return_type,
                        field_group,
                        path,
                        result,
                        incremental_context,
                        defer_map,
                    )
                    if self.is_awaitable(graphql_wrapped_result):  # pragma: no cover
                        return await graphql_wrapped_result
                    return cast(
                        "GraphQLWrappedResult[dict[str, Any]]", graphql_wrapped_result
                    )

                return execute_subfields_async()

            if not is_type_of:
                raise invalid_return_type_error(return_type, result, field_group)

        return self.collect_and_execute_subfields(
            return_type, field_group, path, result, incremental_context, defer_map
        )

    def collect_and_execute_subfields(
        self,
        return_type: GraphQLObjectType,
        field_group: FieldGroup,
        path: Path,
        result: Any,
        incremental_context: IncrementalContext | None,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord] | None,
    ) -> AwaitableOrValue[GraphQLWrappedResult[dict[str, Any]]]:
        """Collect sub-fields to execute to complete this value."""
        collected_subfields = self.collect_subfields(return_type, field_group)
        grouped_field_set, new_defer_usages = collected_subfields
        if defer_map is None and not new_defer_usages:
            return self.execute_fields(
                return_type, result, path, grouped_field_set, incremental_context, None
            )
        sub_field_plan = self.build_sub_field_plan(
            grouped_field_set,
            incremental_context.defer_usage_set if incremental_context else None,
        )

        grouped_field_set, new_grouped_field_sets = sub_field_plan

        new_defer_map = add_new_deferred_fragments(
            new_defer_usages,
            RefMap(defer_map.items()) if defer_map else RefMap(),
            path,
        )

        sub_fields = self.execute_fields(
            return_type,
            result,
            path,
            grouped_field_set,
            incremental_context,
            new_defer_map,
        )

        if new_grouped_field_sets:
            new_deferred_grouped_field_set_records = (
                self.execute_deferred_grouped_field_sets(
                    return_type,
                    result,
                    path,
                    incremental_context.defer_usage_set
                    if incremental_context
                    else None,
                    new_grouped_field_sets,
                    new_defer_map,
                )
            )
            return self.with_new_deferred_grouped_field_sets(
                sub_fields, new_deferred_grouped_field_set_records
            )

        return sub_fields

    def collect_subfields(
        self, return_type: GraphQLObjectType, field_group: FieldGroup
    ) -> CollectedFields:
        """Collect subfields.

        A memoized function collecting relevant subfields regarding the return type.
        Memoizing ensures the subfields are not repeatedly calculated, which saves
        overhead when resolving lists of values.
        """
        relevant_sub_fields = self._relevant_sub_fields
        # We cannot use the field_group itself as key for the cache, since it
        # is not hashable as a list. We also do not want to use the field_group
        # itself (converted to a tuple) as keys, since hashing them is slow.
        # Therefore, we use the ids of the field_group items as keys. Note that we do
        # not use the id of the list, since we want to hit the cache for all lists of
        # the same nodes, not only for the same list of nodes. Also, the list id may
        # even be reused, in which case we would get wrong results from the cache.
        key = (
            (return_type, id(field_group[0]))
            if len(field_group) == 1  # optimize most frequent case
            else (return_type, *map(id, field_group))
        )
        collected_fields: CollectedFields | None = relevant_sub_fields.get(key)
        if collected_fields is None:
            collected_fields = collect_subfields(
                self.schema,
                self.fragments,
                self.variable_values,
                self.operation,
                return_type,
                field_group,
            )
            relevant_sub_fields[key] = collected_fields
        return collected_fields

    def build_sub_field_plan(
        self,
        original_grouped_field_set: GroupedFieldSet,
        defer_usage_set: DeferUsageSet | None,
    ) -> FieldPlan:
        """Build a cached sub-field plan."""
        field_plans = self._field_plans
        field_plan = field_plans.get(original_grouped_field_set)
        if field_plan is not None:
            return field_plan
        field_plan = build_field_plan(original_grouped_field_set, defer_usage_set)
        field_plans[original_grouped_field_set] = field_plan
        return field_plan

    def map_source_to_response(
        self, result_or_stream: ExecutionResult | AsyncIterable[Any]
    ) -> AsyncGenerator[ExecutionResult, None] | ExecutionResult:
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

        build_context = self.build_per_event_execution_context

        async def callback(payload: Any) -> ExecutionResult:
            result = build_context(payload).execute_operation()
            # typecast to ExecutionResult, not possible to return
            # ExperimentalIncrementalExecutionResults when operation is 'subscription'.
            return (
                await cast("Awaitable[ExecutionResult]", result)
                if self.is_awaitable(result)
                else cast("ExecutionResult", result)
            )

        return map_async_iterable(result_or_stream, callback)

    def execute_deferred_grouped_field_sets(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Path | None,
        parent_defer_usages: DeferUsageSet | None,
        new_grouped_field_sets: RefMap[DeferUsageSet, GroupedFieldSet],
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
    ) -> list[DeferredGroupedFieldSetRecord]:
        """Execute deferred grouped field sets."""
        is_awaitable = self.is_awaitable
        new_deferred_grouped_field_set_records: list[DeferredGroupedFieldSetRecord] = []
        append_record = new_deferred_grouped_field_set_records.append
        for defer_usage_set, grouped_field_set in new_grouped_field_sets.items():
            deferred_fragment_records = get_deferred_fragment_records(
                defer_usage_set, defer_map
            )

            deferred_record = DeferredGroupedFieldSetRecord(
                deferred_fragment_records,
                cast("BoxedAwaitableOrValue[DeferredGroupedFieldSetResult]", None),
            )

            def executor(
                deferred_record: DeferredGroupedFieldSetRecord = deferred_record,
                grouped_field_set: GroupedFieldSet = grouped_field_set,
                defer_usage_set: DeferUsageSet = defer_usage_set,
            ) -> AwaitableOrValue[DeferredGroupedFieldSetResult]:
                return self.execute_deferred_grouped_field_set(
                    deferred_record,
                    parent_type,
                    source_value,
                    path,
                    grouped_field_set,
                    IncrementalContext(defer_usage_set),
                    defer_map,
                )

            should_defer_this_defer_usage_set = should_defer(
                parent_defer_usages, defer_usage_set
            )

            if should_defer_this_defer_usage_set:
                if self.enable_early_execution:

                    async def execute_async(
                        executor: Callable[
                            [], AwaitableOrValue[DeferredGroupedFieldSetResult]
                        ] = executor,
                    ) -> DeferredGroupedFieldSetResult:
                        result = executor()
                        if is_awaitable(result):
                            return await result
                        return result  # type: ignore

                    deferred_record.result = BoxedAwaitableOrValue(execute_async())
                else:

                    def execute_sync(
                        executor: Callable[
                            [], AwaitableOrValue[DeferredGroupedFieldSetResult]
                        ] = executor,
                    ) -> BoxedAwaitableOrValue[DeferredGroupedFieldSetResult]:
                        return BoxedAwaitableOrValue(executor())

                    deferred_record.result = execute_sync

            else:
                deferred_record.result = BoxedAwaitableOrValue(executor())

            append_record(deferred_record)

        return new_deferred_grouped_field_set_records

    def execute_deferred_grouped_field_set(
        self,
        deferred_grouped_field_set_record: DeferredGroupedFieldSetRecord,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Path | None,
        grouped_field_set: GroupedFieldSet,
        incremental_context: IncrementalContext,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
    ) -> AwaitableOrValue[DeferredGroupedFieldSetResult]:
        """Execute deferred grouped field set."""
        try:
            result = self.execute_fields(
                parent_type,
                source_value,
                path,
                grouped_field_set,
                incremental_context,
                defer_map,
            )
        except GraphQLError as error:
            return NonReconcilableDeferredGroupedFieldSetResult(
                deferred_grouped_field_set_record,
                path.as_list() if path else [],
                with_error(incremental_context.errors, error),
            )

        if self.is_awaitable(result):

            async def await_result() -> DeferredGroupedFieldSetResult:
                try:
                    awaited_result = await result
                except GraphQLError as error:
                    return NonReconcilableDeferredGroupedFieldSetResult(
                        deferred_grouped_field_set_record,
                        path.as_list() if path else [],
                        with_error(incremental_context.errors, error),
                    )
                return build_deferred_grouped_field_set_result(
                    incremental_context.errors,
                    deferred_grouped_field_set_record,
                    path,
                    awaited_result,
                )

            return await_result()

        return build_deferred_grouped_field_set_result(
            incremental_context.errors,
            deferred_grouped_field_set_record,
            path,
            result,  # type: ignore
        )

    def build_sync_stream_item_queue(
        self,
        initial_item: AwaitableOrValue[Any],
        initial_index: int,
        stream_path: Path,
        iterator: Iterable[Any],
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        item_type: GraphQLOutputType,
    ) -> list[StreamItemRecord]:
        """Build sync stream item queue."""
        is_awaitable = self.is_awaitable
        enable_early_execution = self.enable_early_execution
        complete_stream_item = self.complete_stream_item

        stream_item_queue: list[StreamItemRecord] = []
        append_stream_item = stream_item_queue.append

        def first_executor() -> StreamItemResult:
            initial_path = stream_path.add_key(initial_index)

            first_stream_item: BoxedAwaitableOrValue[StreamItemResult] = (
                BoxedAwaitableOrValue(
                    complete_stream_item(
                        initial_path,
                        initial_item,
                        IncrementalContext(),
                        field_group,
                        info,
                        item_type,
                    )
                )
            )

            current_index = initial_index + 1
            current_stream_item: (
                BoxedAwaitableOrValue[StreamItemResult]
                | Callable[[], BoxedAwaitableOrValue[StreamItemResult]]
            ) = first_stream_item
            for item in iterator:
                if isinstance(current_stream_item, BoxedAwaitableOrValue):
                    result = current_stream_item.value
                    if not is_awaitable(result) and result.errors:
                        break

                item_path = stream_path.add_key(current_index)

                def current_executor(
                    item: Any = item, item_path: Path = item_path
                ) -> AwaitableOrValue[StreamItemResult]:
                    return complete_stream_item(
                        item_path,
                        item,
                        IncrementalContext(),
                        field_group,
                        info,
                        item_type,
                    )

                current_stream_item = (
                    BoxedAwaitableOrValue(current_executor())
                    if enable_early_execution
                    else lambda executor=current_executor:  # type: ignore
                    BoxedAwaitableOrValue(executor())
                )

                append_stream_item(current_stream_item)

                current_index = initial_index + 1

            append_stream_item(BoxedAwaitableOrValue(StreamItemResult()))

            return first_stream_item.value

        if enable_early_execution:

            async def await_first_stream_item() -> StreamItemResult:
                return first_executor()

            append_stream_item(BoxedAwaitableOrValue(await_first_stream_item()))
        else:
            append_stream_item(lambda: BoxedAwaitableOrValue(first_executor()))

        return stream_item_queue

    def build_async_stream_item_queue(
        self,
        initial_index: int,
        stream_path: Path,
        async_iterator: AsyncIterator[Any],
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        item_type: GraphQLOutputType,
    ) -> list[StreamItemRecord]:
        """Build async stream item queue."""

        def executor() -> AwaitableOrValue[StreamItemResult]:
            return self.get_next_async_stream_item_result(
                stream_item_queue,
                stream_path,
                initial_index,
                async_iterator,
                field_group,
                info,
                item_type,
            )

        stream_item_queue: list[StreamItemRecord] = []
        stream_item_queue.append(
            BoxedAwaitableOrValue(executor())
            if self.enable_early_execution
            else lambda: BoxedAwaitableOrValue(executor())
        )

        return stream_item_queue

    async def get_next_async_stream_item_result(
        self,
        stream_item_queue: list[StreamItemRecord],
        stream_path: Path,
        index: int,
        async_iterator: AsyncIterator[Any],
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        item_type: GraphQLOutputType,
    ) -> StreamItemResult:
        """Get the next async stream items result."""
        try:
            item = await anext(async_iterator)
        except StopAsyncIteration:
            return StreamItemResult()
        except Exception as error:
            return StreamItemResult(
                errors=[
                    located_error(error, to_nodes(field_group), stream_path.as_list())
                ],
            )

        item_path = stream_path.add_key(index)

        result = self.complete_stream_item(
            item_path,
            item,
            IncrementalContext(),
            field_group,
            info,
            item_type,
        )

        def executor() -> AwaitableOrValue[StreamItemResult]:
            return self.get_next_async_stream_item_result(
                stream_item_queue,
                stream_path,
                index,
                async_iterator,
                field_group,
                info,
                item_type,
            )

        stream_item_queue.append(
            BoxedAwaitableOrValue(executor())
            if self.enable_early_execution
            else lambda: BoxedAwaitableOrValue(executor())
        )

        if self.is_awaitable(result):
            await sleep(0)  # allow other tasks to run
            return await result
        return cast("StreamItemResult", result)

    def complete_stream_item(
        self,
        item_path: Path,
        item: Any,
        incremental_context: IncrementalContext,
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        item_type: GraphQLOutputType,
    ) -> AwaitableOrValue[StreamItemResult]:
        """Complete the stream items."""
        is_awaitable = self.is_awaitable
        if is_awaitable(item):

            async def await_stream_item_result() -> StreamItemResult:
                try:
                    awaited_item = await self.complete_awaitable_value(
                        item_type,
                        field_group,
                        info,
                        item_path,
                        item,
                        incremental_context,
                        RefMap(),
                    )
                except GraphQLError as error:
                    return StreamItemResult(
                        errors=with_error(incremental_context.errors, error)
                    )
                return build_stream_item_result(
                    awaited_item, incremental_context.errors
                )

            return await_stream_item_result()

        try:
            try:
                result = self.complete_value(
                    item_type,
                    field_group,
                    info,
                    item_path,
                    item,
                    incremental_context,
                    RefMap(),
                )
            except Exception as raw_error:
                self.handle_field_error(
                    raw_error,
                    item_type,
                    field_group,
                    item_path,
                    incremental_context,
                )
                result = GraphQLWrappedResult(None)
        except GraphQLError as error:
            return StreamItemResult(
                errors=with_error(incremental_context.errors, error)
            )

        if is_awaitable(result):

            async def await_stream_item_result() -> StreamItemResult:
                try:
                    try:
                        awaited_item = await result
                    except Exception as raw_error:
                        self.handle_field_error(
                            raw_error,
                            item_type,
                            field_group,
                            item_path,
                            incremental_context,
                        )
                        awaited_item = GraphQLWrappedResult(None)
                except GraphQLError as error:
                    return StreamItemResult(
                        errors=with_error(incremental_context.errors, error)
                    )
                return build_stream_item_result(
                    awaited_item, incremental_context.errors
                )

            return await_stream_item_result()

        return build_stream_item_result(
            result,  # type: ignore
            incremental_context.errors,
        )

    def with_new_deferred_grouped_field_sets(
        self,
        result: AwaitableOrValue[GraphQLWrappedResult[dict[str, Any]]],
        new_deferred_grouped_field_set_records: list[DeferredGroupedFieldSetRecord],
    ) -> AwaitableOrValue[GraphQLWrappedResult[dict[str, Any]]]:
        """Add new deferred grouped field sets to result."""
        if self.is_awaitable(result):

            async def await_result() -> GraphQLWrappedResult[dict[str, Any]]:
                resolved = await result
                resolved.add_increments(new_deferred_grouped_field_set_records)
                return resolved

            return await_result()

        resolved = cast("GraphQLWrappedResult[dict[str, Any]]", result)
        resolved.add_increments(new_deferred_grouped_field_set_records)
        return resolved

    def build_data_response(
        self,
        data: dict[str, Any],
        incremental_data_records: Sequence[IncrementalDataRecord] | None,
    ) -> ExecutionResult | ExperimentalIncrementalExecutionResults:
        """Build the data response."""
        if not incremental_data_records:
            return ExecutionResult(data, self.errors or None)
        return build_incremental_response(
            self,
            data,
            self.errors,
            incremental_data_records,
        )


def with_error(
    errors: Sequence[GraphQLError] | None, error: GraphQLError
) -> list[GraphQLError]:
    """Return a new list of errors with the given error appended."""
    return [error] if errors is None else [*errors, error]


def to_nodes(field_group: FieldGroup) -> list[FieldNode]:
    """Convert a field group to a list of field nodes."""
    return [field_details.node for field_details in field_group]


T = TypeVar("T")


class GraphQLWrappedResult(Generic[T]):
    """Wrapper class for GraphQL results with increments."""

    __slots__ = "increments", "result"

    result: T
    increments: list[IncrementalDataRecord] | None

    def __init__(
        self,
        result: T,
        increments: list[IncrementalDataRecord] | None = None,
    ) -> None:
        self.result = result
        self.increments = increments

    def add_increment(
        self,
        increment: IncrementalDataRecord,
    ) -> None:
        """Add a single given increment to the wrapped result."""
        if self.increments is None:
            self.increments = [increment]
        else:
            self.increments.append(increment)

    def add_increments(
        self,
        increments: Sequence[IncrementalDataRecord] | None,
    ) -> None:
        """Add the given increments to the wrapped result."""
        if increments is None:
            return
        if self.increments is None:
            self.increments = list(increments)
        else:
            self.increments.extend(increments)


UNEXPECTED_EXPERIMENTAL_DIRECTIVES = (
    "The provided schema unexpectedly contains experimental directives"
    " (@defer or @stream). These directives may only be utilized"
    " if experimental execution features are explicitly enabled."
)


UNEXPECTED_MULTIPLE_PAYLOADS = (
    "Executing this GraphQL operation would unexpectedly produce multiple payloads"
    " (due to @defer or @stream directive)"
)


def execute(
    schema: GraphQLSchema,
    document: DocumentNode,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: dict[str, Any] | None = None,
    operation_name: str | None = None,
    field_resolver: GraphQLFieldResolver | None = None,
    type_resolver: GraphQLTypeResolver | None = None,
    subscribe_field_resolver: GraphQLFieldResolver | None = None,
    enable_early_execution: bool = False,
    middleware: Middleware | None = None,
    execution_context_class: type[ExecutionContext] | None = None,
    is_awaitable: Callable[[Any], TypeGuard[Awaitable]] | None = None,
    **custom_context_args: Any,
) -> AwaitableOrValue[ExecutionResult]:
    """Execute a GraphQL operation.

    Implements the "Executing requests" section of the GraphQL specification.

    Returns an ExecutionResult (if all encountered resolvers are synchronous),
    or a coroutine object eventually yielding an ExecutionResult.

    If the arguments to this function do not result in a legal execution context,
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
        enable_early_execution,
        middleware,
        execution_context_class,
        is_awaitable,
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


def experimental_execute_incrementally(
    schema: GraphQLSchema,
    document: DocumentNode,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: dict[str, Any] | None = None,
    operation_name: str | None = None,
    field_resolver: GraphQLFieldResolver | None = None,
    type_resolver: GraphQLTypeResolver | None = None,
    subscribe_field_resolver: GraphQLFieldResolver | None = None,
    enable_early_execution: bool = False,
    middleware: Middleware | None = None,
    execution_context_class: type[ExecutionContext] | None = None,
    is_awaitable: Callable[[Any], TypeGuard[Awaitable]] | None = None,
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
        enable_early_execution,
        middleware,
        is_awaitable,
        **custom_context_args,
    )

    # Return early errors if execution context failed.
    if isinstance(context, list):
        return ExecutionResult(None, errors=context)

    return context.execute_operation()


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
    middleware: Middleware | None = None,
    execution_context_class: type[ExecutionContext] | None = None,
    check_sync: bool = False,
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
        False,
        middleware,
        execution_context_class,
        is_awaitable,
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


def invalid_return_type_error(
    return_type: GraphQLObjectType, result: Any, field_group: FieldGroup
) -> GraphQLError:
    """Create a GraphQLError for an invalid return type."""
    return GraphQLError(
        f"Expected value of type '{return_type.name}' but got: {inspect(result)}.",
        to_nodes(field_group),
    )


def deferred_fragment_record_from_defer_usage(
    defer_usage: DeferUsage, defer_map: RefMap[DeferUsage, DeferredFragmentRecord]
) -> DeferredFragmentRecord:
    """Get the deferred fragment record mapped to the given defer usage."""
    return defer_map[defer_usage]


def add_new_deferred_fragments(
    new_defer_usages: Sequence[DeferUsage],
    new_defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
    path: Path | None = None,
) -> RefMap[DeferUsage, DeferredFragmentRecord]:
    """Add new deferred fragments to the defer map.

    Instantiates new DeferredFragmentRecords for the given path within an
    incremental data record, returning an updated map of DeferUsage
    objects to DeferredFragmentRecords.

    Note: As defer directives may be used with operations returning lists,
          a DeferUsage object may correspond to many DeferredFragmentRecords.

    DeferredFragmentRecord creation includes the following steps:
    1. The new DeferredFragmentRecord is instantiated at the given path.
    2. The parent result record is calculated from the given incremental data record.
    3. The IncrementalPublisher is notified that a new DeferredFragmentRecord
       with the calculated parent has been added; the record will be released only
       after the parent has completed.
    """
    # For each new DeferUsage object:
    for new_defer_usage in new_defer_usages:
        parent_defer_usage = new_defer_usage.parent_defer_usage

        parent = (
            None
            if parent_defer_usage is None
            else deferred_fragment_record_from_defer_usage(
                parent_defer_usage, new_defer_map
            )
        )

        # Instantiate the new record.
        deferred_fragment_record = DeferredFragmentRecord(
            parent, path, new_defer_usage.label
        )

        # Update the map.
        new_defer_map[new_defer_usage] = deferred_fragment_record

    return new_defer_map


def should_defer(
    parent_defer_usages: DeferUsageSet | None, defer_usage_set: DeferUsageSet
) -> bool:
    """Decide whether to defer the given defer usage set.

    If we have a new child defer usage, defer.
    Otherwise, this defer usage was already deferred when it was initially
    encountered, and is now in the midst of executing early, so the new
    deferred grouped fields set can be executed immediately.
    """
    return parent_defer_usages is None or not any(
        defer_usage in parent_defer_usages for defer_usage in defer_usage_set
    )


def build_deferred_grouped_field_set_result(
    errors: list[GraphQLError] | None,
    deferred_grouped_field_set_record: DeferredGroupedFieldSetRecord,
    path: Path | None,
    result: GraphQLWrappedResult[dict[str, Any]],
) -> DeferredGroupedFieldSetResult:
    """Build a deferred grouped fieldset result."""
    return ReconcilableDeferredGroupedFieldSetResult(
        deferred_grouped_field_set_record=deferred_grouped_field_set_record,
        path=path.as_list() if path else [],
        result=BareDeferredGroupedFieldSetResult(result.result, errors or None),
        incremental_data_records=result.increments,
    )


def get_deferred_fragment_records(
    defer_usages: DeferUsageSet, defer_map: RefMap[DeferUsage, DeferredFragmentRecord]
) -> list[DeferredFragmentRecord]:
    """Get the deferred fragment records for the given defer usages."""
    return [
        deferred_fragment_record_from_defer_usage(defer_usage, defer_map)
        for defer_usage in defer_usages
    ]


def build_stream_item_result(
    result: GraphQLWrappedResult[Any], errors: list[GraphQLError] | None = None
) -> StreamItemResult:
    """Build a stream item result."""
    return StreamItemResult(result.result, result.increments, errors)


def get_typename(value: Any) -> str | None:
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
) -> AwaitableOrValue[str | None]:
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
    awaitable_is_type_of_results: list[Awaitable[bool]] = []
    append_awaitable_result = awaitable_is_type_of_results.append
    awaitable_types: list[GraphQLObjectType] = []
    append_awaitable_type = awaitable_types.append

    for type_ in possible_types:
        if type_.is_type_of:
            is_type_of_result = type_.is_type_of(value, info)

            if is_awaitable(is_type_of_result):
                append_awaitable_result(cast("Awaitable[bool]", is_type_of_result))
                append_awaitable_type(type_)
            elif is_type_of_result:
                return type_.name

    if awaitable_is_type_of_results:

        async def get_type() -> str | None:
            is_type_of_results = await gather_with_cancel(*awaitable_is_type_of_results)
            for is_type_of_result, type_ in zip(
                is_type_of_results, awaitable_types, strict=True
            ):
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
    variable_values: dict[str, Any] | None = None,
    operation_name: str | None = None,
    field_resolver: GraphQLFieldResolver | None = None,
    type_resolver: GraphQLTypeResolver | None = None,
    subscribe_field_resolver: GraphQLFieldResolver | None = None,
    enable_early_execution: bool = False,
    execution_context_class: type[ExecutionContext] | None = None,
    middleware: MiddlewareManager | None = None,
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
        enable_early_execution,
        middleware=middleware,
        **custom_context_args,
    )

    # Return early errors if execution context failed.
    if isinstance(context, list):
        return ExecutionResult(None, errors=context)

    result_or_stream = create_source_event_stream_impl(context)

    if context.is_awaitable(result_or_stream):

        async def await_result() -> Any:
            awaited_result_or_stream = await result_or_stream
            if isinstance(awaited_result_or_stream, ExecutionResult):
                return awaited_result_or_stream
            return context.map_source_to_response(awaited_result_or_stream)

        return await_result()

    if isinstance(result_or_stream, ExecutionResult):
        return result_or_stream

    return context.map_source_to_response(result_or_stream)  # type: ignore


def create_source_event_stream(
    schema: GraphQLSchema,
    document: DocumentNode,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: dict[str, Any] | None = None,
    operation_name: str | None = None,
    field_resolver: GraphQLFieldResolver | None = None,
    type_resolver: GraphQLTypeResolver | None = None,
    subscribe_field_resolver: GraphQLFieldResolver | None = None,
    enable_early_execution: bool = False,
    execution_context_class: type[ExecutionContext] | None = None,
    **custom_context_args: Any,
) -> AwaitableOrValue[AsyncIterable[Any] | ExecutionResult]:
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
        enable_early_execution,
        **custom_context_args,
    )

    # Return early errors if execution context failed.
    if isinstance(context, list):
        return ExecutionResult(None, errors=context)

    return create_source_event_stream_impl(context)


def create_source_event_stream_impl(
    context: ExecutionContext,
) -> AwaitableOrValue[AsyncIterable[Any] | ExecutionResult]:
    """Create source event stream (internal implementation)."""
    try:
        event_stream = execute_subscription(context)
    except GraphQLError as error:
        return ExecutionResult(None, errors=[error])

    if context.is_awaitable(event_stream):

        async def await_event_stream() -> AsyncIterable[Any] | ExecutionResult:
            try:
                return await event_stream
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
        msg = "Schema is not configured to execute subscription operation."
        raise GraphQLError(msg, context.operation)

    grouped_field_set = collect_fields(
        schema,
        context.fragments,
        context.variable_values,
        root_type,
        context.operation,
    ).grouped_field_set

    first_root_field = next(iter(grouped_field_set.items()))
    response_name, field_group = first_root_field
    field_name = field_group[0].node.name.value
    field_def = schema.get_field(root_type, field_name)

    field_nodes = [field_details.node for field_details in field_group]
    if not field_def:
        msg = f"The subscription field '{field_name}' is not defined."
        raise GraphQLError(msg, field_nodes)

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

            async def await_result() -> AsyncIterable[Any]:
                try:
                    return assert_event_stream(await result)
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
    if not isinstance(result, AsyncIterable):
        msg = (
            "Subscription field must return AsyncIterable."
            f" Received: {inspect(result)}."
        )
        raise GraphQLError(msg)

    return result
