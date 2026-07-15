"""GraphQL executor"""

from __future__ import annotations

from asyncio import (
    FIRST_COMPLETED,
    ensure_future,
    gather,
    get_running_loop,
    iscoroutine,
    wait,
)
from collections.abc import (
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Callable,
    Iterable,
    Iterator,
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
    AbortSignal,
    AwaitableOrValue,
    Path,
    RefMap,
    Undefined,
    async_reduce,
    gather_with_cancel,
    inspect,
    is_iterable,
)
from ..pyutils.is_awaitable import (
    is_async_iterable as default_is_async_iterable,
)
from ..pyutils.is_awaitable import (
    is_awaitable as default_is_awaitable,
)
from ..type import (
    GraphQLAbstractType,
    GraphQLField,
    GraphQLFieldResolver,
    GraphQLLeafType,
    GraphQLList,
    GraphQLObjectType,
    GraphQLOutputType,
    GraphQLResolveInfo,
    GraphQLResolveInfoHelpers,
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
from ..type.directives import GraphQLDisableErrorPropagationDirective
from .aborted_graphql_execution_error import AbortedGraphQLExecutionError
from .collect_fields import (
    CollectedFields,
    DeferUsage,
    FieldDetails,
    FieldDetailsList,
    FragmentDetails,
    GroupedFieldSet,
    collect_fields,
    collect_subfields,
)
from .get_variable_signature import get_variable_signature
from .middleware import MiddlewareManager
from .types import ExecutionResult, ExperimentalIncrementalExecutionResults
from .values import (
    VariableValues,
    get_argument_values,
    get_directive_values,
    get_variable_values,
)

if TYPE_CHECKING:
    from asyncio import Future
    from typing import TypeAlias, TypeGuard

    from ..pyutils import UndefinedType
    from .get_variable_signature import GraphQLVariableSignature

__all__ = [
    "AsyncWorkFinishedInfo",
    "CollectedErrors",
    "ExecutionHooks",
    "Executor",
    "Middleware",
    "StreamUsage",
    "default_field_resolver",
    "default_type_resolver",
]

T = TypeVar("T")
TContext = TypeVar("TContext")

suppress_exceptions = suppress(Exception)

UNEXPECTED_MULTIPLE_PAYLOADS = (
    "Executing this GraphQL operation would unexpectedly produce multiple payloads"
    " (due to @defer or @stream directive)"
)

DEFER_NOT_SUPPORTED_ON_SUBSCRIPTIONS = (
    "`@defer` directive not supported on subscription operations."
    " Disable `@defer` by setting the `if` argument to `false`."
)

Middleware: TypeAlias = tuple | list | MiddlewareManager | None


class StreamUsage(NamedTuple):
    """Stream directive usage information"""

    label: str | None
    initial_count: int
    field_details_list: FieldDetailsList


class AsyncWorkFinishedInfo(NamedTuple):
    """Information passed to the ``async_work_finished`` execution hook."""

    executor: Executor


class ExecutionHooks(NamedTuple):
    """Hooks for observing the execution of a GraphQL operation.

    The ``async_work_finished`` hook is run when all asynchronous work tracked
    by the execution has finished. Cancelled asynchronous work may still be
    running even after the result has been delivered; this hook allows
    interested execution harnesses to track when this asynchronous work
    completes. Errors raised by the hook are ignored.
    """

    async_work_finished: Callable[[AsyncWorkFinishedInfo], None] | None = None


class CollectedErrors:
    """Field errors collected during execution, tracking nulled positions.

    For internal use only.
    """

    __slots__ = "_error_positions", "_errors"

    _error_positions: set[Path | None]
    _errors: list[GraphQLError]

    def __init__(self) -> None:
        self._error_positions = set()
        self._errors = []

    @property
    def errors(self) -> list[GraphQLError]:
        """Get the collected errors."""
        return self._errors

    def add(self, error: GraphQLError, path: Path | None) -> None:
        """Add an error raised at the given execution position.

        Does not modify the errors list if the execution position for this
        error or any of its ancestors has already been nulled via error
        propagation. This check should be unnecessary for implementations
        able to implement actual cancellation.
        """
        if self.has_nulled_position(path):
            return
        self._error_positions.add(path)
        self._errors.append(error)

    def has_nulled_position(self, start_path: Path | None) -> bool:
        """Check whether the given position or one of its ancestors is nulled."""
        error_positions = self._error_positions
        path = start_path
        while path is not None:
            if path in error_positions:
                return True
            path = path.prev
        return None in error_positions


class Executor(Generic[TContext]):
    """Executor for a validated GraphQL operation.

    Carries the data that must be available at all points during query
    execution - namely, the schema of the type system that is currently
    executing and the fragments defined in the query document - together
    with the state of the current execution.

    This base executor implements plain execution without incremental
    delivery: any ``@defer`` and ``@stream`` directives in the operation
    are ignored.
    """

    schema: GraphQLSchema
    # TODO: consider deprecating/removing fragment_definitions if/when fragment
    # arguments are officially supported and/or the full fragment details are
    # exposed within GraphQLResolveInfo.
    fragment_definitions: dict[str, FragmentDefinitionNode]
    fragments: dict[str, FragmentDetails]
    root_value: Any
    context_value: Any
    operation: OperationDefinitionNode
    variable_values: VariableValues
    field_resolver: GraphQLFieldResolver
    type_resolver: GraphQLTypeResolver
    subscribe_field_resolver: GraphQLFieldResolver
    enable_early_execution: bool
    hide_suggestions: bool
    abort_signal: AbortSignal | None
    hooks: ExecutionHooks | None
    async_helpers: GraphQLResolveInfoHelpers
    collected_errors: CollectedErrors
    pending_incremental_futures: set[Future[Any]]
    background_futures: set[Future[Any]]
    async_work_finished_hook_task: Future[None] | None
    middleware_manager: MiddlewareManager | None
    error_propagation: bool

    is_awaitable: Callable[[Any], TypeGuard[Awaitable]] = staticmethod(
        default_is_awaitable  # type: ignore
    )
    is_async_iterable: Callable[[Any], TypeGuard[AsyncIterable]] = staticmethod(
        default_is_async_iterable  # type: ignore
    )

    def __init__(  # noqa: PLR0913
        self,
        schema: GraphQLSchema,
        fragment_definitions: dict[str, FragmentDefinitionNode],
        fragments: dict[str, FragmentDetails],
        root_value: Any,
        context_value: Any,
        operation: OperationDefinitionNode,
        variable_values: VariableValues,
        field_resolver: GraphQLFieldResolver,
        type_resolver: GraphQLTypeResolver,
        subscribe_field_resolver: GraphQLFieldResolver,
        enable_early_execution: bool = False,
        middleware_manager: MiddlewareManager | None = None,
        is_awaitable: Callable[[Any], TypeGuard[Awaitable]] | None = None,
        is_async_iterable: Callable[[Any], TypeGuard[AsyncIterable]] | None = None,
        hide_suggestions: bool = False,
        abort_signal: AbortSignal | None = None,
        hooks: ExecutionHooks | None = None,
    ) -> None:
        self.schema = schema
        self.fragment_definitions = fragment_definitions
        self.fragments = fragments
        self.root_value = root_value
        self.context_value = context_value
        self.operation = operation
        self.variable_values = variable_values
        self.field_resolver = field_resolver
        self.type_resolver = type_resolver
        self.subscribe_field_resolver = subscribe_field_resolver
        self.enable_early_execution = enable_early_execution
        self.hide_suggestions = hide_suggestions
        self.abort_signal = abort_signal
        self.hooks = hooks
        self.async_helpers = GraphQLResolveInfoHelpers(
            gather=self.gather_async_work, track=self.track_async_work
        )
        self.middleware_manager = middleware_manager
        self.error_propagation = not any(
            directive.name.value == GraphQLDisableErrorPropagationDirective.name
            for directive in operation.directives or ()
        )
        self.is_awaitable = is_awaitable or default_is_awaitable
        self.is_async_iterable = is_async_iterable or default_is_async_iterable
        self.collected_errors = CollectedErrors()
        # Attributes holding shared execution state: these are shared between
        # this executor and all its sub-executors, since sub-executors are
        # created as shallow copies that replace only the per-execution state.
        self.pending_incremental_futures = set()
        self.background_futures = set()
        self.async_work_finished_hook_task = None
        self._relevant_sub_fields: dict[tuple, CollectedFields] = {}
        self._stream_usages: RefMap[FieldDetailsList, StreamUsage] = RefMap()

    @classmethod
    def build(  # noqa: PLR0913
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
        max_coercion_errors: int = 50,
        enable_early_execution: bool = False,
        middleware: Middleware | None = None,
        is_awaitable: Callable[[Any], TypeGuard[Awaitable]] | None = None,
        is_async_iterable: Callable[[Any], TypeGuard[AsyncIterable]] | None = None,
        hide_suggestions: bool = False,
        abort_signal: AbortSignal | None = None,
        hooks: ExecutionHooks | None = None,
        **custom_args: Any,
    ) -> list[GraphQLError] | Executor:
        """Build an executor

        Constructs an Executor object from the arguments passed to execute, which
        we will pass throughout the other execution methods.

        Throws a GraphQLError if a valid executor cannot be created.

        For internal use only.
        """
        # If the schema used for execution is invalid, raise an error.
        assert_valid_schema(schema)

        operation: OperationDefinitionNode | None = None
        fragment_definitions: dict[str, FragmentDefinitionNode] = {}
        fragments: dict[str, FragmentDetails] = {}
        fragment_variable_signature_errors: list[GraphQLError] = []
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
                fragment_definitions[definition.name.value] = definition
                variable_signatures: dict[str, GraphQLVariableSignature] | None = None
                if definition.variable_definitions:
                    variable_signatures = {}
                    for var_def in definition.variable_definitions:
                        signature = get_variable_signature(schema, var_def)
                        if isinstance(signature, GraphQLError):
                            fragment_variable_signature_errors.append(signature)
                            continue
                        variable_signatures[signature.name] = signature
                fragments[definition.name.value] = FragmentDetails(
                    definition, variable_signatures
                )

        if not operation:
            if operation_name is not None:
                return [GraphQLError(f"Unknown operation named '{operation_name}'.")]
            return [GraphQLError("Must provide an operation.")]

        if fragment_variable_signature_errors:
            return fragment_variable_signature_errors

        variable_values = get_variable_values(
            schema,
            operation.variable_definitions or (),
            raw_variable_values or {},
            max_errors=max_coercion_errors,
            hide_suggestions=hide_suggestions,
        )

        if isinstance(variable_values, list):
            return variable_values  # errors

        return cls(
            schema,
            fragment_definitions,
            fragments,
            root_value,
            context_value,
            operation,
            variable_values,
            field_resolver or default_field_resolver,
            type_resolver or default_type_resolver,
            subscribe_field_resolver or default_field_resolver,
            enable_early_execution,
            middleware_manager,
            is_awaitable,
            is_async_iterable,
            hide_suggestions=hide_suggestions,
            abort_signal=abort_signal,
            hooks=hooks,
            **custom_args,
        )

    def build_per_event_executor(self, payload: Any) -> Executor:
        """Create a copy of the executor for usage with subscribe events."""
        executor = copy(self)
        executor.root_value = payload
        executor.collected_errors = CollectedErrors()
        return executor

    def execute_operation(
        self,
        serially: bool | None = None,
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

        If the operation is aborted, the whole operation is rejected with an
        aborted execution error rather than resolving to a partial response with
        located errors; the partial result that the unwinding execution can still
        produce is exposed on that error.
        """
        abort_signal = self.abort_signal
        if abort_signal is not None and abort_signal.aborted:
            self.run_async_work_finished_hook()
            raise self.abort_error()
        try:
            operation = self.operation
            schema = self.schema
            operation_type = operation.operation
            root_type = schema.get_root_type(operation_type)
            if root_type is None:
                msg = (
                    "Schema is not configured to execute"
                    f" {operation_type.value} operation."
                )
                raise GraphQLError(msg, operation)  # noqa: TRY301
            root_value = self.root_value

            collected_fields = collect_fields(
                schema,
                self.fragments,
                self.variable_values,
                root_type,
                operation,
                self.hide_suggestions,
            )

            grouped_field_set, new_defer_usages, _forbidden = collected_fields

            result = self.execute_collected_root_fields(
                root_type,
                root_value,
                grouped_field_set,
                operation_type == OperationType.MUTATION
                if serially is None
                else serially,
                new_defer_usages,
            )

            if self.is_awaitable(result):

                async def await_result() -> (
                    ExecutionResult | ExperimentalIncrementalExecutionResults
                ):
                    try:
                        data = await result
                    except GraphQLError as error:
                        self.collected_errors.add(error, None)
                        return self.build_response(None)
                    except Exception:
                        # cancel incremental work started early and close the
                        # stream sources before re-raising, e.g. the abort reason
                        await self.cancel_incremental_work()
                        self.run_async_work_finished_hook()
                        raise
                    return self.build_response(data)

                if abort_signal is None:
                    return await_result()
                return self.with_aborted_execution_error(await_result())

            data = cast("dict[str, Any]", result)

        except GraphQLError as error:
            self.collected_errors.add(error, None)
            return self.finish(self.build_response(None))

        return self.finish(self.build_response(data))

    def execute_collected_root_fields(
        self,
        root_type: GraphQLObjectType,
        root_value: Any,
        grouped_field_set: GroupedFieldSet,
        serially: bool,
        new_defer_usages: Sequence[DeferUsage],
    ) -> AwaitableOrValue[dict[str, Any]]:
        """Execute the collected root fields, ignoring incremental delivery."""
        return self.execute_root_grouped_field_set(
            root_type,
            root_value,
            grouped_field_set,
            serially,
            None,
        )

    def execute_root_grouped_field_set(
        self,
        root_type: GraphQLObjectType,
        root_value: Any,
        grouped_field_set: GroupedFieldSet,
        serially: bool,
        position_context: TContext | None,
    ) -> AwaitableOrValue[dict[str, Any]]:
        """Execute the root grouped field set."""
        return (self.execute_fields_serially if serially else self.execute_fields)(
            root_type,
            root_value,
            None,
            grouped_field_set,
            position_context,
        )

    def build_response(
        self, data: dict[str, Any] | None
    ) -> ExecutionResult | ExperimentalIncrementalExecutionResults:
        """Build the response for the given completed data.

        Given completed execution data, build the ``(data, errors)`` response
        defined by the "Response" section of the GraphQL specification.
        """
        self.run_async_work_finished_hook()
        errors = self.collected_errors.errors
        return ExecutionResult(data, errors or None)

    def execute_fields_serially(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Path | None,
        grouped_field_set: GroupedFieldSet,
        position_context: TContext | None,
    ) -> AwaitableOrValue[dict[str, Any]]:
        """Execute the given fields serially.

        Implements the "Executing selection sets" section of the spec
        for fields that must be executed serially.
        """
        is_awaitable = self.is_awaitable
        abort_signal = self.abort_signal

        def reducer(
            results: dict[str, Any],
            field_item: tuple[str, FieldDetailsList],
        ) -> AwaitableOrValue[dict[str, Any]]:
            response_name, field_details_list = field_item
            field_path = Path(path, response_name, parent_type.name)
            if abort_signal is not None and abort_signal.aborted:
                # Reject the whole operation rather than serially completing the
                # remaining fields with located abort errors.
                raise self.abort_error()
            result = self.execute_field(
                parent_type,
                source_value,
                field_details_list,
                field_path,
                position_context,
            )
            if result is Undefined:
                return results
            if is_awaitable(result):

                async def set_result() -> dict[str, Any]:
                    results[response_name] = await result
                    return results

                return set_result()

            results[response_name] = result
            return results

        return async_reduce(reducer, grouped_field_set.items(), {})

    def execute_fields(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Path | None,
        grouped_field_set: GroupedFieldSet,
        position_context: TContext | None,
    ) -> AwaitableOrValue[dict[str, Any]]:
        """Execute the given fields concurrently.

        Implements the "Executing selection sets" section of the spec
        for fields that may be executed in parallel.
        """
        results: dict[str, Any] = {}
        is_awaitable = self.is_awaitable
        awaitable_fields: list[str] = []
        append_awaitable = awaitable_fields.append
        try:
            for response_name, field_details_list in grouped_field_set.items():
                field_path = Path(path, response_name, parent_type.name)
                result = self.execute_field(
                    parent_type,
                    source_value,
                    field_details_list,
                    field_path,
                    position_context,
                )
                if result is not Undefined:
                    results[response_name] = result
                    if is_awaitable(result):
                        append_awaitable(response_name)
        except Exception:
            if awaitable_fields:
                # Ensure that awaitables created by other fields are settled,
                # as they may also fail.
                self.settle_in_background(
                    [results[field] for field in awaitable_fields]
                )
            raise

        # If there are no coroutines, we can just return the object.
        if not awaitable_fields:
            return results

        # Otherwise, results is a map from field name to the result of resolving that
        # field, which is possibly a coroutine object. Return a coroutine object that
        # will yield this same map, but with any coroutines awaited in parallel and
        # replaced with the values they yielded.
        async def get_results() -> dict[str, Any]:
            if len(awaitable_fields) == 1:
                # If there is only one field, avoid the overhead of parallelization.
                field = awaitable_fields[0]
                results[field] = await results[field]
            else:
                awaited_results = await gather_with_cancel(
                    *(results[field] for field in awaitable_fields)
                )
                results.update(zip(awaitable_fields, awaited_results, strict=True))

            return results

        return get_results()

    def execute_field(
        self,
        parent_type: GraphQLObjectType,
        source: Any,
        field_details_list: FieldDetailsList,
        path: Path,
        position_context: TContext | None,
    ) -> AwaitableOrValue[Any] | UndefinedType:
        """Resolve the field on the given source object.

        Implements the "Executing fields" section of the spec.

        In particular, this method figures out the value that the field returns by
        calling its resolve function, then calls complete_value to await coroutine
        objects, coercing scalars, or execute the sub-selection-set for objects.
        """
        first_field_details = field_details_list[0]
        first_field_node = first_field_details.node
        field_name = first_field_node.name.value
        field_def = self.schema.get_field(parent_type, field_name)
        if not field_def:
            return Undefined

        return_type = field_def.type
        resolve_fn = field_def.resolve or self.field_resolver

        if self.middleware_manager:
            resolve_fn = self.middleware_manager.get_field_resolver(resolve_fn)

        info = self.build_resolve_info(
            field_def, to_nodes(field_details_list), parent_type, path
        )

        # Get the resolve function, regardless of if its result is normal or abrupt
        # (error).
        try:
            # Build a dictionary of arguments from the field.arguments AST, using the
            # variables scope to fulfill any variable references.
            args = get_argument_values(
                field_def,
                first_field_node,
                self.variable_values,
                first_field_details.fragment_variable_values,
                self.hide_suggestions,
            )

            # Note that contrary to the JavaScript implementation, we pass the context
            # value as part of the resolve info.
            result = resolve_fn(source, info, **args)

            if self.is_awaitable(result):
                return self.complete_awaitable_value(
                    return_type,
                    field_details_list,
                    info,
                    path,
                    result,
                    position_context,
                )

            completed = self.complete_value(
                return_type,
                field_details_list,
                info,
                path,
                result,
                position_context,
            )
            if self.is_awaitable(completed):

                async def await_completed() -> Any:
                    try:
                        return await completed
                    except Exception as raw_error:
                        self.handle_field_error(
                            raw_error,
                            return_type,
                            field_details_list,
                            path,
                        )
                        return None

                return await_completed()

        except Exception as raw_error:
            self.handle_field_error(
                raw_error,
                return_type,
                field_details_list,
                path,
            )
            return None

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
            self.fragment_definitions,
            self.root_value,
            self.operation,
            self.variable_values,
            self.context_value,
            self.is_awaitable,
            self.abort_signal,
            self.async_helpers,
        )

    def handle_field_error(
        self,
        raw_error: Exception,
        return_type: GraphQLOutputType,
        field_details_list: FieldDetailsList,
        path: Path,
    ) -> None:
        """Handle error properly according to the field type."""
        error = located_error(raw_error, to_nodes(field_details_list), path.as_list())

        # If the field type is non-nullable, then it is resolved without any protection
        # from errors, however it still properly locates the error.
        if self.error_propagation and is_non_null_type(return_type):
            raise error

        # Otherwise, error protection is applied, logging the error and resolving a
        # null value for this field if one is encountered.
        self.collected_errors.add(error, path)

    def complete_value(
        self,
        return_type: GraphQLOutputType,
        field_details_list: FieldDetailsList,
        info: GraphQLResolveInfo,
        path: Path,
        result: Any,
        position_context: TContext | None,
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
        value of the type by calling the ``coerce_output_value`` method of GraphQL type
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
                field_details_list,
                info,
                path,
                result,
                position_context,
            )
            if completed is None:
                msg = (
                    "Cannot return null for non-nullable field"
                    f" {info.parent_type}.{info.field_name}."
                )
                raise TypeError(msg)
            return completed

        # If result value is null or undefined then return null.
        if result is None or result is Undefined:
            return None

        # If field type is List, complete each item in the list with inner type
        if is_list_type(return_type):
            return self.complete_list_value(
                return_type,
                field_details_list,
                info,
                path,
                result,
                position_context,
            )

        # If field type is a leaf type, Scalar or Enum, coerce to a valid value,
        # returning null if coercion is not possible.
        if is_leaf_type(return_type):
            return self.complete_leaf_value(return_type, result)

        # If field type is an abstract type, Interface or Union, determine the runtime
        # Object type and complete for that type.
        if is_abstract_type(return_type):
            return self.complete_abstract_value(
                return_type,
                field_details_list,
                info,
                path,
                result,
                position_context,
            )

        # If field type is Object, execute and complete all sub-selections.
        if is_object_type(return_type):
            return self.complete_object_value(
                return_type,
                field_details_list,
                info,
                path,
                result,
                position_context,
            )

        # Not reachable. All possible output types have been considered.
        msg = (
            "Cannot complete value of unexpected output type:"
            f" '{inspect(return_type)}'."
        )  # pragma: no cover
        raise TypeError(msg)  # pragma: no cover

    async def with_abort_signal(self, awaitable: Awaitable[T]) -> T:
        """Await a value, but cancel immediately if the abort signal is triggered.

        This wraps awaitables returned by resolvers (and awaitable list items) so
        that a triggered abort signal interrupts execution *immediately* instead of
        only at the next field boundary. Without this, a hanging asynchronous
        resolver would prevent the operation from ever being cancelled.

        If the abort signal fires before the awaitable settles, the underlying
        awaitable is cancelled and the abort reason is raised (an exception reason
        is raised as is, any other value is reported as an unexpected error value).
        """
        abort_signal = self.abort_signal
        if abort_signal is None:
            return await awaitable
        task = ensure_future(awaitable)
        if not abort_signal.aborted:
            abort = ensure_future(abort_signal.wait())
            try:
                await wait({task, abort}, return_when=FIRST_COMPLETED)
            finally:
                if not abort.done():
                    abort.cancel()
            if not abort_signal.aborted:
                return task.result()
        # The abort signal fired (possibly in the same tick the task settled);
        # discard any task result and reject with the abort reason.
        task.cancel()
        with suppress(BaseException):
            await task
        raise self.abort_error()

    def abort_error(self) -> Exception:
        """Return the exception to raise when execution has been aborted.

        An abort reason that is itself an exception is raised as is; any other value
        is reported as an unexpected error value.
        """
        reason = self.abort_signal.reason  # type: ignore[union-attr]
        if isinstance(reason, Exception):
            return reason
        msg = f"Unexpected error value: {inspect(reason)}"
        return TypeError(msg)

    async def with_aborted_execution_error(self, awaitable: Awaitable[T]) -> T:
        """Await a result, but raise an aborted execution error when aborted.

        Unlike :meth:`with_abort_signal`, the awaited work is not cancelled as a
        whole when the abort signal is triggered: only its in-flight resolvers are
        cancelled individually, so that it still settles into a partial result,
        which is exposed via the raised aborted execution error.
        """
        abort_signal = self.abort_signal
        task = ensure_future(awaitable)
        if not abort_signal.aborted:  # type: ignore[union-attr]
            abort = ensure_future(abort_signal.wait())  # type: ignore[union-attr]
            try:
                await wait({task, abort}, return_when=FIRST_COMPLETED)
            finally:
                if not abort.done():
                    abort.cancel()
            if not abort_signal.aborted:  # type: ignore[union-attr]
                return task.result()
        # The abort signal fired (possibly in the same tick the task settled);
        # let the partial result settle in the background and expose it on the
        # aborted execution error that the operation is rejected with.
        self.settle_in_background([task])
        raise self.create_aborted_execution_error(task)

    def finish(self, result: T) -> T:
        """Check that execution has not been aborted before returning its result.

        If the operation has been aborted during otherwise synchronous execution,
        raise an aborted execution error exposing the already completed result.
        """
        abort_signal = self.abort_signal
        if abort_signal is not None and abort_signal.aborted:
            raise self.create_aborted_execution_error(result)
        return result

    def create_aborted_execution_error(
        self, result: AwaitableOrValue[Any]
    ) -> AbortedGraphQLExecutionError:
        """Create an aborted execution error exposing the given result."""
        reason = self.abort_signal.reason  # type: ignore[union-attr]
        return AbortedGraphQLExecutionError(reason, result)

    def abort(self, reason: BaseException | None = None) -> AwaitableOrValue[None]:
        """Abort the incremental work produced by this executor.

        The base executor produces no incremental work, so this is a no-op.
        """

    def track_incremental_future(self, future: Future[Any]) -> None:
        """Register a pending future belonging to incremental work.

        The registered futures can be cancelled via
        :meth:`cancel_incremental_work` when the incremental execution is
        stopped before they have settled.
        """
        futures = self.pending_incremental_futures
        futures.add(future)
        future.add_done_callback(futures.discard)

    async def cancel_incremental_work(
        self, reason: BaseException | None = None
    ) -> None:
        """Cancel all pending incremental work and close the stream sources.

        Aborts the incremental work produced by this executor, which cancels
        the still pending incremental execution tasks and triggers the early
        return of the stream sources, and cancels any remaining pending
        incremental futures, waiting until all cancellation has settled.
        """
        abort_result = self.abort(reason)
        if default_is_awaitable(abort_result):
            await abort_result
        futures = self.pending_incremental_futures
        if futures:
            pending = list(futures)
            for future in pending:
                future.cancel()
            await gather(*pending, return_exceptions=True)

    def settle_in_background(self, awaitables: list[Awaitable[Any]]) -> None:
        """Settle the given pending awaitables in the background.

        A bubbling synchronous error must not wait for pending sibling awaitables,
        but they must still be settled so that their errors can be observed before
        they would be orphaned (the Python analog of silencing JS unhandled
        rejections). Without a running event loop the awaitables can never run;
        pending coroutines are then closed instead to dispose of them.
        """
        try:
            get_running_loop()
        except RuntimeError:  # no running event loop
            for awaitable in awaitables:
                if iscoroutine(awaitable):  # pragma: no branch
                    awaitable.close()
            return
        future = gather(*awaitables, return_exceptions=True)
        background_futures = self.background_futures
        background_futures.add(future)
        future.add_done_callback(background_futures.discard)

    def track_async_work(self, values: Sequence[Any]) -> None:
        """Track possibly awaitable values as pending asynchronous work.

        Awaitables among the given values are settled in the background, so that
        they are still settled and their errors observed when they would otherwise
        be abandoned. Non-awaitable values are ignored.
        """
        is_awaitable = self.is_awaitable
        awaitables: list[Awaitable[Any]] = [
            value for value in values if is_awaitable(value)
        ]
        if awaitables:
            self.settle_in_background(awaitables)

    def gather_async_work(
        self, values: Sequence[Awaitable[Any]]
    ) -> Awaitable[list[Any]]:
        """Concurrently await the given values as one unit of asynchronous work.

        This allows resolvers to await multiple concurrent operations together.
        When one of the values fails, the others are cancelled and settled before
        the error is propagated, so that no asynchronous work is orphaned.
        """
        return gather_with_cancel(*values)

    def run_async_work_finished_hook(self) -> None:
        """Run the hook signaling that all asynchronous work has finished.

        If an ``async_work_finished`` execution hook is provided, run it as soon as
        all tracked pending asynchronous work has been settled - synchronously when
        there is no pending asynchronous work, which allows synchronous execution
        paths to remain synchronous. Errors raised by the hook are ignored.
        """
        hooks = self.hooks
        hook = hooks.async_work_finished if hooks is not None else None
        if hook is None:
            return
        info = AsyncWorkFinishedInfo(self)
        background_futures = self.background_futures
        if not background_futures:
            with suppress_exceptions:
                hook(info)
            return

        async def wait_and_run_hook() -> None:
            while background_futures:
                await wait(list(background_futures))
            with suppress_exceptions:
                hook(info)

        # keep a reference to the task so that it is not garbage collected
        self.async_work_finished_hook_task = ensure_future(wait_and_run_hook())

    def cancellable_iterable(self, iterable: AsyncIterable[T]) -> AsyncIterable[T]:
        """Wrap an async iterable so pending iteration is cancelled on abort.

        When the abort signal is triggered, any pending ``__anext__`` call returns
        immediately by raising the abort reason. This mirrors the JavaScript
        ``cancellableIterable``; GraphQL-core needs no ``AbortSignalListener``
        class since :meth:`with_abort_signal` already provides the cancellation
        mechanism.
        """
        if self.abort_signal is None:
            return iterable
        with_abort_signal = self.with_abort_signal
        iterator = iterable.__aiter__()

        class CancellableAsyncIterator:
            def __aiter__(self) -> AsyncIterator[T]:
                return self

            def __anext__(self) -> Awaitable[T]:
                return with_abort_signal(iterator.__anext__())

            async def aclose(self) -> None:
                aclose = getattr(iterator, "aclose", None)
                if aclose is not None:
                    await aclose()

        return CancellableAsyncIterator()

    async def complete_awaitable_value(
        self,
        return_type: GraphQLOutputType,
        field_details_list: FieldDetailsList,
        info: GraphQLResolveInfo,
        path: Path,
        result: Any,
        position_context: TContext | None,
    ) -> Any:
        """Complete an awaitable value."""
        try:
            resolved = await self.with_abort_signal(result)
            completed = self.complete_value(
                return_type,
                field_details_list,
                info,
                path,
                resolved,
                position_context,
            )
            if self.is_awaitable(completed):
                completed = await completed
        except Exception as raw_error:
            self.handle_field_error(raw_error, return_type, field_details_list, path)
            completed = None
        return completed

    def get_stream_usage(
        self, field_details_list: FieldDetailsList, path: Path
    ) -> StreamUsage | None:
        """Get stream usage.

        Returns an object containing info for streaming if a field should be
        streamed based on the experimental flag, stream directive present and
        not disabled by the "if" argument.
        """
        # do not stream inner lists of multidimensional lists
        if isinstance(path.key, int):
            return None

        stream_usage = self._stream_usages.get(field_details_list)
        if stream_usage is not None:
            return stream_usage  # pragma: no cover

        # validation only allows equivalent streams on multiple fields, so it is
        # safe to only check the first field_node for the stream directive
        stream = get_directive_values(
            GraphQLStreamDirective, field_details_list[0].node, self.variable_values
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

        streamed_field_details_list: FieldDetailsList = [
            FieldDetails(field_details.node, None)
            for field_details in field_details_list
        ]

        stream_usage = StreamUsage(
            stream.get("label"), stream["initialCount"], streamed_field_details_list
        )

        self._stream_usages[field_details_list] = stream_usage

        return stream_usage

    def handle_stream(
        self,
        index: int,
        path: Path,
        iterator: Iterator[Any] | AsyncIterator[Any],
        is_async: bool,
        stream_usage: StreamUsage,
        info: GraphQLResolveInfo,
        item_type: GraphQLOutputType,
    ) -> bool:
        """Handle streaming of the remaining list items, if supported.

        The base executor does not support streaming, so this is a no-op
        returning False, which means that the list is completed normally.
        """
        return False

    async def complete_async_iterator_value(
        self,
        item_type: GraphQLOutputType,
        field_details_list: FieldDetailsList,
        info: GraphQLResolveInfo,
        path: Path,
        async_iterator: AsyncIterator[Any],
        position_context: TContext | None,
    ) -> list[Any]:
        """Complete an async iterator.

        Complete an async iterator value by completing the result and calling
        recursively until all the results are completed.
        """
        is_awaitable = self.is_awaitable
        complete_list_item_value = self.complete_list_item_value
        complete_awaitable_list_item_value = self.complete_awaitable_list_item_value
        completed_results: list[Any] = []
        append_completed = completed_results.append
        awaitable_indices: list[int] = []
        append_awaitable = awaitable_indices.append
        stream_usage = self.get_stream_usage(field_details_list, path)
        try:
            early_return = async_iterator.aclose  # type: ignore[attr-defined]
        except AttributeError:
            early_return = None
        index = 0
        try:
            while True:
                if (
                    stream_usage
                    and index == stream_usage.initial_count
                    and self.handle_stream(
                        index,
                        path,
                        async_iterator,
                        True,
                        stream_usage,
                        info,
                        item_type,
                    )
                ):
                    break

                item_path = path.add_key(index, None)
                try:
                    item = await anext(async_iterator)
                except StopAsyncIteration:
                    break
                except Exception as raw_error:
                    raise located_error(
                        raw_error, to_nodes(field_details_list), path.as_list()
                    ) from raw_error

                if is_awaitable(item):
                    append_completed(
                        complete_awaitable_list_item_value(
                            item,
                            item_type,
                            field_details_list,
                            info,
                            item_path,
                            position_context,
                        )
                    )
                    append_awaitable(index)

                elif complete_list_item_value(
                    item,
                    completed_results,
                    item_type,
                    field_details_list,
                    info,
                    item_path,
                    position_context,
                ):
                    append_awaitable(index)

                index += 1
        except Exception:
            if early_return is not None:  # pragma: no branch
                with suppress_exceptions:
                    await early_return()
            if awaitable_indices:
                # Settle any awaitable items already collected in the background,
                # so that the current error is not delayed.
                self.settle_in_background(
                    [completed_results[index] for index in awaitable_indices]
                )
            raise

        if not awaitable_indices:
            return completed_results

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
        return completed_results

    def complete_list_value(
        self,
        return_type: GraphQLList[GraphQLOutputType],
        field_details_list: FieldDetailsList,
        info: GraphQLResolveInfo,
        path: Path,
        result: AsyncIterable[Any] | Iterable[Any],
        position_context: TContext | None,
    ) -> AwaitableOrValue[list[Any]]:
        """Complete a list value.

        Complete a list value by completing each item in the list with the inner type.
        """
        item_type = return_type.of_type

        if self.is_async_iterable(result):
            async_iterator = self.cancellable_iterable(result).__aiter__()

            return self.complete_async_iterator_value(
                item_type,
                field_details_list,
                info,
                path,
                async_iterator,
                position_context,
            )

        if not is_iterable(result):
            msg = (
                "Expected Iterable, but did not find one for field"
                f" '{info.parent_type}.{info.field_name}'."
            )
            raise GraphQLError(msg)

        return self.complete_iterable_value(
            item_type,
            field_details_list,
            info,
            path,
            result,
            position_context,
        )

    def complete_iterable_value(
        self,
        item_type: GraphQLOutputType,
        field_details_list: FieldDetailsList,
        info: GraphQLResolveInfo,
        path: Path,
        items: Iterable[Any],
        position_context: TContext | None,
    ) -> AwaitableOrValue[list[Any]]:
        """Complete an iterable value."""
        # This is specified as a simple map, however we're optimizing the path
        # where the list contains no awaitable routine objects by avoiding creating
        # another awaitable object.
        is_awaitable = self.is_awaitable
        complete_list_item_value = self.complete_list_item_value
        complete_awaitable_list_item_value = self.complete_awaitable_list_item_value
        completed_results: list[Any] = []
        append_completed = completed_results.append
        awaitable_indices: list[int] = []
        append_awaitable = awaitable_indices.append
        stream_usage = self.get_stream_usage(field_details_list, path)
        iterator = iter(items)
        index = 0
        try:
            while True:
                if (
                    stream_usage
                    and index == stream_usage.initial_count
                    and self.handle_stream(
                        index,
                        path,
                        iterator,
                        False,
                        stream_usage,
                        info,
                        item_type,
                    )
                ):
                    break

                try:
                    item = next(iterator)
                except StopIteration:
                    break

                # No need to modify the info object containing the path,
                # since from here on it is not ever accessed by resolver functions.
                item_path = path.add_key(index, None)

                if is_awaitable(item):
                    append_completed(
                        complete_awaitable_list_item_value(
                            item,
                            item_type,
                            field_details_list,
                            info,
                            item_path,
                            position_context,
                        )
                    )
                    append_awaitable(index)

                elif complete_list_item_value(
                    item,
                    completed_results,
                    item_type,
                    field_details_list,
                    info,
                    item_path,
                    position_context,
                ):
                    append_awaitable(index)

                index += 1
        except Exception:
            # Do not close the iterator. Instead, drain it so that any awaitable
            # items it still holds can be settled in the background before they
            # would be orphaned.
            maybe_awaitables = [completed_results[index] for index in awaitable_indices]
            maybe_awaitables.extend(collect_iterator_awaitables(iterator, is_awaitable))
            if maybe_awaitables:
                self.settle_in_background(maybe_awaitables)
            raise

        if not awaitable_indices:
            return completed_results

        async def get_completed_results() -> list[Any]:
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
            return completed_results

        return get_completed_results()

    def complete_list_item_value(
        self,
        item: Any,
        complete_results: list[Any],
        item_type: GraphQLOutputType,
        field_details_list: FieldDetailsList,
        info: GraphQLResolveInfo,
        item_path: Path,
        position_context: TContext | None,
    ) -> bool:
        """Complete a list item value by adding it to the completed results.

        Returns True if the value is awaitable.
        """
        is_awaitable = self.is_awaitable

        try:
            completed_item = self.complete_value(
                item_type,
                field_details_list,
                info,
                item_path,
                item,
                position_context,
            )

            if is_awaitable(completed_item):

                async def await_completed() -> Any:
                    try:
                        return await completed_item
                    except Exception as raw_error:
                        self.handle_field_error(
                            raw_error,
                            item_type,
                            field_details_list,
                            item_path,
                        )
                        return None

                complete_results.append(await_completed())
                return True

            complete_results.append(completed_item)

        except Exception as raw_error:
            self.handle_field_error(
                raw_error,
                item_type,
                field_details_list,
                item_path,
            )
            complete_results.append(None)

        return False

    async def complete_awaitable_list_item_value(
        self,
        item: Any,
        item_type: GraphQLOutputType,
        field_details_list: FieldDetailsList,
        info: GraphQLResolveInfo,
        item_path: Path,
        position_context: TContext | None,
    ) -> Any:
        """Complete an awaitable list item value."""
        try:
            resolved = await self.with_abort_signal(item)
            completed = self.complete_value(
                item_type,
                field_details_list,
                info,
                item_path,
                resolved,
                position_context,
            )
            if self.is_awaitable(completed):
                completed = await completed
        except Exception as raw_error:
            self.handle_field_error(
                raw_error,
                item_type,
                field_details_list,
                item_path,
            )
            return None
        return completed

    @staticmethod
    def complete_leaf_value(return_type: GraphQLLeafType, result: Any) -> Any:
        """Complete a leaf value.

        Complete a Scalar or Enum by coercing to a valid value, returning null if
        coercion is not possible.
        """
        coerced = return_type.coerce_output_value(result)
        if coerced is Undefined or coerced is None:
            msg = (
                f"Expected `{inspect(return_type)}.coerce_output_value("
                f"{inspect(result)})` to return non-nullable value, returned:"
                f" {inspect(coerced)}"
            )
            raise TypeError(msg)
        return coerced

    def complete_abstract_value(
        self,
        return_type: GraphQLAbstractType,
        field_details_list: FieldDetailsList,
        info: GraphQLResolveInfo,
        path: Path,
        result: Any,
        position_context: TContext | None,
    ) -> AwaitableOrValue[dict[str, Any]]:
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
                        await self.with_abort_signal(runtime_type),  # type: ignore
                        return_type,
                        field_details_list,
                        info,
                        result,
                    ),
                    field_details_list,
                    info,
                    path,
                    result,
                    position_context,
                )
                if self.is_awaitable(value):
                    return await value
                return value  # pragma: no cover

            return await_complete_object_value()
        runtime_type = cast("str | None", runtime_type)

        return self.complete_object_value(
            self.ensure_valid_runtime_type(
                runtime_type, return_type, field_details_list, info, result
            ),
            field_details_list,
            info,
            path,
            result,
            position_context,
        )

    def ensure_valid_runtime_type(
        self,
        runtime_type_name: Any,
        return_type: GraphQLAbstractType,
        field_details_list: FieldDetailsList,
        info: GraphQLResolveInfo,
        result: Any,
    ) -> GraphQLObjectType:
        """Ensure that the given type is valid at runtime."""
        if runtime_type_name is None:
            msg = (
                f"Abstract type '{return_type}' must resolve"
                " to an Object type at runtime"
                f" for field '{info.parent_type}.{info.field_name}'."
                f" Either the '{return_type}' type should provide"
                " a 'resolve_type' function or each possible type should provide"
                " an 'is_type_of' function."
            )
            raise GraphQLError(msg, to_nodes(field_details_list))

        if not isinstance(runtime_type_name, str):
            msg = (
                f"Abstract type '{return_type}' must resolve"
                " to an Object type at runtime"
                f" for field '{info.parent_type}.{info.field_name}' with value"
                f" {inspect(result)}, received '{inspect(runtime_type_name)}',"
                " which is not a valid Object type name."
            )
            raise GraphQLError(msg, to_nodes(field_details_list))

        runtime_type = self.schema.get_type(runtime_type_name)

        if runtime_type is None:
            msg = (
                f"Abstract type '{return_type}' was resolved to a type"
                f" '{runtime_type_name}' that does not exist inside the schema."
            )
            raise GraphQLError(msg, to_nodes(field_details_list))

        if not is_object_type(runtime_type):
            msg = (
                f"Abstract type '{return_type}' was resolved"
                f" to a non-object type '{runtime_type_name}'."
            )
            raise GraphQLError(msg, to_nodes(field_details_list))

        if not self.schema.is_sub_type(return_type, runtime_type):
            msg = (
                f"Runtime Object type '{runtime_type}' is not a possible"
                f" type for '{return_type}'."
            )
            raise GraphQLError(msg, to_nodes(field_details_list))

        return runtime_type

    def complete_object_value(
        self,
        return_type: GraphQLObjectType,
        field_details_list: FieldDetailsList,
        info: GraphQLResolveInfo,
        path: Path,
        result: Any,
        position_context: TContext | None,
    ) -> AwaitableOrValue[dict[str, Any]]:
        """Complete an Object value by executing all sub-selections."""
        # If there is an `is_type_of()` predicate function, call it with the current
        # result. If `is_type_of()` returns False, then raise an error rather than
        # continuing execution.
        if return_type.is_type_of:
            is_type_of = return_type.is_type_of(result, info)

            if self.is_awaitable(is_type_of):

                async def execute_subfields_async() -> dict[str, Any]:
                    if not await self.with_abort_signal(is_type_of):
                        raise invalid_return_type_error(
                            return_type, result, field_details_list
                        )
                    sub_fields = self.collect_and_execute_subfields(
                        return_type,
                        field_details_list,
                        path,
                        result,
                        position_context,
                    )
                    if self.is_awaitable(sub_fields):
                        return await sub_fields
                    return cast("dict[str, Any]", sub_fields)  # pragma: no cover

                return execute_subfields_async()

            if not is_type_of:
                raise invalid_return_type_error(return_type, result, field_details_list)

        return self.collect_and_execute_subfields(
            return_type,
            field_details_list,
            path,
            result,
            position_context,
        )

    def collect_and_execute_subfields(
        self,
        return_type: GraphQLObjectType,
        field_details_list: FieldDetailsList,
        path: Path,
        result: Any,
        position_context: TContext | None,
    ) -> AwaitableOrValue[dict[str, Any]]:
        """Collect sub-fields to execute to complete this value."""
        collected_subfields = self.collect_subfields(return_type, field_details_list)
        grouped_field_set, new_defer_usages, _forbidden = collected_subfields

        return self.execute_collected_subfields(
            return_type,
            result,
            path,
            grouped_field_set,
            new_defer_usages,
            position_context,
        )

    def execute_collected_subfields(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Path,
        grouped_field_set: GroupedFieldSet,
        new_defer_usages: Sequence[DeferUsage],
        position_context: TContext | None,
    ) -> AwaitableOrValue[dict[str, Any]]:
        """Execute the collected subfields, ignoring incremental delivery."""
        return self.execute_fields(
            parent_type,
            source_value,
            path,
            grouped_field_set,
            None,
        )

    def collect_subfields(
        self, return_type: GraphQLObjectType, field_details_list: FieldDetailsList
    ) -> CollectedFields:
        """Collect subfields.

        A memoized function collecting relevant subfields regarding the return type.
        Memoizing ensures the subfields are not repeatedly calculated, which saves
        overhead when resolving lists of values.
        """
        relevant_sub_fields = self._relevant_sub_fields
        # We cannot use the field_details_list itself as key for the cache, since it
        # is not hashable as a list. We also do not want to use the field_details_list
        # itself (converted to a tuple) as keys, since hashing them is slow.
        # Therefore, we use the ids of the field_details_list items as keys. Note that
        # we do not use the id of the list, since we want to hit the cache for all
        # lists of the same nodes, not only for the same list of nodes. Also, the list
        # id may even be reused, in which case we would get wrong results from cache.
        key = (
            (return_type, id(field_details_list[0]))
            if len(field_details_list) == 1  # optimize most frequent case
            else (return_type, *map(id, field_details_list))
        )
        collected_fields: CollectedFields | None = relevant_sub_fields.get(key)
        if collected_fields is None:
            collected_fields = collect_subfields(
                self.schema,
                self.fragments,
                self.variable_values,
                self.operation,
                return_type,
                field_details_list,
                self.hide_suggestions,
            )
            relevant_sub_fields[key] = collected_fields
        return collected_fields


def to_nodes(field_details_list: FieldDetailsList) -> list[FieldNode]:
    """Convert a field group to a list of field nodes."""
    return [field_details.node for field_details in field_details_list]


def invalid_return_type_error(
    return_type: GraphQLObjectType, result: Any, field_details_list: FieldDetailsList
) -> GraphQLError:
    """Create a GraphQLError for an invalid return type."""
    return GraphQLError(
        f"Expected value of type '{return_type}' but got: {inspect(result)}.",
        to_nodes(field_details_list),
    )


def collect_iterator_awaitables(
    iterator: Iterator[Any], is_awaitable: Callable[[Any], bool]
) -> list[Awaitable[Any]]:
    """Drain a synchronous iterator after an abrupt completion.

    Collects any awaitable values the iterator still holds so that their errors
    can be observed before they would otherwise be left orphaned.
    """
    awaitables: list[Awaitable[Any]] = []
    with suppress_exceptions:
        awaitables.extend(item for item in iterator if is_awaitable(item))
    return awaitables


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

    try:
        for type_ in possible_types:
            if type_.is_type_of:
                is_type_of_result = type_.is_type_of(value, info)

                if is_awaitable(is_type_of_result):
                    append_awaitable_result(cast("Awaitable[bool]", is_type_of_result))
                    append_awaitable_type(type_)
                elif is_type_of_result:
                    if awaitable_is_type_of_results:
                        info.async_helpers.track(awaitable_is_type_of_results)
                    return type_.name
    except Exception:
        if awaitable_is_type_of_results:
            # Settle the pending isTypeOf results in the background so that
            # their errors can be observed before they would be orphaned.
            info.async_helpers.track(awaitable_is_type_of_results)
        raise

    if awaitable_is_type_of_results:

        async def get_type() -> str | None:
            is_type_of_results = await info.async_helpers.gather(
                awaitable_is_type_of_results
            )
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
