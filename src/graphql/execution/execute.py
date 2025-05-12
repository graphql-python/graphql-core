"""GraphQL execution"""

from __future__ import annotations

from asyncio import (
    CancelledError,
    create_task,
    ensure_future,
    gather,
    shield,
    wait_for,
)
from contextlib import suppress
from copy import copy
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Callable,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)

try:
    from typing import TypeAlias, TypeGuard  # noqa: F401
except ImportError:  # Python < 3.10
    from typing_extensions import TypeAlias
try:  # only needed for Python < 3.11
    from asyncio.exceptions import TimeoutError  # noqa: A004
except ImportError:  # Python < 3.7
    from concurrent.futures import TimeoutError  # noqa: A004

from ..error import GraphQLError, located_error
from ..language import (
    DocumentNode,
    FragmentDefinitionNode,
    OperationDefinitionNode,
    OperationType,
)
from ..pyutils import (
    AwaitableOrValue,
    Path,
    RefMap,
    Undefined,
    async_reduce,
    inspect,
    is_iterable,
)
from ..pyutils import is_awaitable as default_is_awaitable
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
from .collect_fields import (
    NON_DEFERRED_TARGET_SET,
    CollectFieldsResult,
    DeferUsage,
    DeferUsageSet,
    FieldDetails,
    FieldGroup,
    GroupedFieldSet,
    GroupedFieldSetDetails,
    collect_fields,
    collect_subfields,
)
from .incremental_publisher import (
    ASYNC_DELAY,
    DeferredFragmentRecord,
    DeferredGroupedFieldSetRecord,
    ExecutionResult,
    ExperimentalIncrementalExecutionResults,
    IncrementalDataRecord,
    IncrementalPublisher,
    InitialResultRecord,
    StreamItemsRecord,
    StreamRecord,
)
from .middleware import MiddlewareManager
from .values import get_argument_values, get_directive_values, get_variable_values

try:  # pragma: no cover
    anext  # noqa: B018  # pyright: ignore
except NameError:  # pragma: no cover (Python < 3.10)
    # noinspection PyShadowingBuiltins
    async def anext(iterator: AsyncIterator) -> Any:
        """Return the next item from an async iterator."""
        return await iterator.__anext__()


__all__ = [
    "ASYNC_DELAY",
    "ExecutionContext",
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


Middleware: TypeAlias = Optional[Union[Tuple, List, MiddlewareManager]]


class StreamUsage(NamedTuple):
    """Stream directive usage information"""

    label: str | None
    initial_count: int
    field_group: FieldGroup


class ExecutionContext:
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
    incremental_publisher: IncrementalPublisher
    middleware_manager: MiddlewareManager | None

    is_awaitable: Callable[[Any], bool] = staticmethod(default_is_awaitable)

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
        incremental_publisher: IncrementalPublisher,
        middleware_manager: MiddlewareManager | None,
        is_awaitable: Callable[[Any], bool] | None,
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
        self.incremental_publisher = incremental_publisher
        self.middleware_manager = middleware_manager
        if is_awaitable:
            self.is_awaitable = is_awaitable
        self._canceled_iterators: set[AsyncIterator] = set()
        self._subfields_cache: dict[tuple, CollectFieldsResult] = {}
        self._tasks: set[Awaitable] = set()
        self._stream_usages: RefMap[FieldGroup, StreamUsage] = RefMap()

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
        middleware: Middleware | None = None,
        is_awaitable: Callable[[Any], bool] | None = None,
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
            IncrementalPublisher(),
            middleware_manager,
            is_awaitable,
            **custom_args,
        )

    def build_per_event_execution_context(self, payload: Any) -> ExecutionContext:
        """Create a copy of the execution context for usage with subscribe events."""
        context = copy(self)
        context.root_value = payload
        return context

    def execute_operation(
        self, initial_result_record: InitialResultRecord
    ) -> AwaitableOrValue[dict[str, Any]]:
        """Execute an operation.

        Implements the "Executing operations" section of the spec.
        """
        operation = self.operation
        schema = self.schema
        root_type = schema.get_root_type(operation.operation)
        if root_type is None:
            msg = (
                "Schema is not configured to execute"
                f" {operation.operation.value} operation."
            )
            raise GraphQLError(msg, operation)

        grouped_field_set, new_grouped_field_set_details, new_defer_usages = (
            collect_fields(
                schema, self.fragments, self.variable_values, root_type, operation
            )
        )

        incremental_publisher = self.incremental_publisher
        new_defer_map = add_new_deferred_fragments(
            incremental_publisher, new_defer_usages, initial_result_record
        )

        path: Path | None = None

        new_deferred_grouped_field_set_records = add_new_deferred_grouped_field_sets(
            incremental_publisher,
            new_grouped_field_set_details,
            new_defer_map,
            path,
        )

        root_value = self.root_value
        # noinspection PyTypeChecker
        result = (
            self.execute_fields_serially
            if operation.operation == OperationType.MUTATION
            else self.execute_fields
        )(
            root_type,
            root_value,
            path,
            grouped_field_set,
            initial_result_record,
            new_defer_map,
        )

        self.execute_deferred_grouped_field_sets(
            root_type,
            root_value,
            path,
            new_deferred_grouped_field_set_records,
            new_defer_map,
        )

        return result

    def execute_fields_serially(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Path | None,
        grouped_field_set: GroupedFieldSet,
        incremental_data_record: IncrementalDataRecord,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
    ) -> AwaitableOrValue[dict[str, Any]]:
        """Execute the given fields serially.

        Implements the "Executing selection sets" section of the spec
        for fields that must be executed serially.
        """
        is_awaitable = self.is_awaitable

        def reducer(
            results: dict[str, Any], field_item: tuple[str, FieldGroup]
        ) -> AwaitableOrValue[dict[str, Any]]:
            response_name, field_group = field_item
            field_path = Path(path, response_name, parent_type.name)
            result = self.execute_field(
                parent_type,
                source_value,
                field_group,
                field_path,
                incremental_data_record,
                defer_map,
            )
            if result is Undefined:
                return results
            if is_awaitable(result):
                # noinspection PyShadowingNames
                async def set_result(
                    response_name: str,
                    awaitable_result: Awaitable,
                ) -> dict[str, Any]:
                    results[response_name] = await awaitable_result
                    return results

                return set_result(response_name, result)
            results[response_name] = result
            return results

        # noinspection PyTypeChecker
        return async_reduce(reducer, grouped_field_set.items(), {})

    def execute_fields(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Path | None,
        grouped_field_set: GroupedFieldSet,
        incremental_data_record: IncrementalDataRecord,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
    ) -> AwaitableOrValue[dict[str, Any]]:
        """Execute the given fields concurrently.

        Implements the "Executing selection sets" section of the spec
        for fields that may be executed in parallel.
        """
        results = {}
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
                incremental_data_record,
                defer_map,
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
        async def get_results() -> dict[str, Any]:
            if len(awaitable_fields) == 1:
                # If there is only one field, avoid the overhead of parallelization.
                field = awaitable_fields[0]
                results[field] = await results[field]
            else:
                tasks = {
                    create_task(results[field]): field  # type: ignore[arg-type]
                    for field in awaitable_fields
                }

                try:
                    awaited_results = await gather(*tasks)
                except Exception:
                    # Cancel unfinished tasks before raising the exception
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await gather(*tasks, return_exceptions=True)
                    raise

                results.update(zip(awaitable_fields, awaited_results))

            return results

        return get_results()

    def execute_field(
        self,
        parent_type: GraphQLObjectType,
        source: Any,
        field_group: FieldGroup,
        path: Path,
        incremental_data_record: IncrementalDataRecord,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
    ) -> AwaitableOrValue[Any]:
        """Resolve the field on the given source object.

        Implements the "Executing fields" section of the spec.

        In particular, this method figures out the value that the field returns by
        calling its resolve function, then calls complete_value to await coroutine
        objects, serialize scalars, or execute the sub-selection-set for objects.
        """
        field_name = field_group.fields[0].node.name.value
        field_def = self.schema.get_field(parent_type, field_name)
        if not field_def:
            return Undefined

        return_type = field_def.type
        resolve_fn = field_def.resolve or self.field_resolver

        if self.middleware_manager:
            resolve_fn = self.middleware_manager.get_field_resolver(resolve_fn)

        info = self.build_resolve_info(field_def, field_group, parent_type, path)

        # Get the resolve function, regardless of if its result is normal or abrupt
        # (error).
        try:
            # Build a dictionary of arguments from the field.arguments AST, using the
            # variables scope to fulfill any variable references.
            args = get_argument_values(
                field_def, field_group.fields[0].node, self.variable_values
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
                    incremental_data_record,
                    defer_map,
                )

            completed = self.complete_value(
                return_type,
                field_group,
                info,
                path,
                result,
                incremental_data_record,
                defer_map,
            )
            if self.is_awaitable(completed):
                # noinspection PyShadowingNames
                async def await_completed() -> Any:
                    try:
                        return await completed
                    except Exception as raw_error:
                        # Before Python 3.8 CancelledError inherits Exception and
                        # so gets caught here.
                        if isinstance(raw_error, CancelledError):
                            raise  # pragma: no cover
                        self.handle_field_error(
                            raw_error,
                            return_type,
                            field_group,
                            path,
                            incremental_data_record,
                        )
                        self.incremental_publisher.filter(path, incremental_data_record)
                        return None

                return await_completed()

        except Exception as raw_error:
            self.handle_field_error(
                raw_error,
                return_type,
                field_group,
                path,
                incremental_data_record,
            )
            self.incremental_publisher.filter(path, incremental_data_record)
            return None

        return completed

    def build_resolve_info(
        self,
        field_def: GraphQLField,
        field_group: FieldGroup,
        parent_type: GraphQLObjectType,
        path: Path,
    ) -> GraphQLResolveInfo:
        """Build the GraphQLResolveInfo object.

        For internal use only.
        """
        # The resolve function's first argument is a collection of information about
        # the current execution state.
        return GraphQLResolveInfo(
            field_group.fields[0].node.name.value,
            field_group.to_nodes(),
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
        incremental_data_record: IncrementalDataRecord,
    ) -> None:
        """Handle error properly according to the field type."""
        error = located_error(raw_error, field_group.to_nodes(), path.as_list())

        # If the field type is non-nullable, then it is resolved without any protection
        # from errors, however it still properly locates the error.
        if is_non_null_type(return_type):
            raise error

        # Otherwise, error protection is applied, logging the error and resolving a
        # null value for this field if one is encountered.
        self.incremental_publisher.add_field_error(incremental_data_record, error)

    def complete_value(
        self,
        return_type: GraphQLOutputType,
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        path: Path,
        result: Any,
        incremental_data_record: IncrementalDataRecord,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
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
                field_group,
                info,
                path,
                result,
                incremental_data_record,
                defer_map,
            )
            if completed is None:
                msg = (
                    "Cannot return null for non-nullable field"
                    f" {info.parent_type.name}.{info.field_name}."
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
                field_group,
                info,
                path,
                result,
                incremental_data_record,
                defer_map,
            )

        # If field type is a leaf type, Scalar or Enum, serialize to a valid value,
        # returning null if serialization is not possible.
        if is_leaf_type(return_type):
            return self.complete_leaf_value(return_type, result)

        # If field type is an abstract type, Interface or Union, determine the runtime
        # Object type and complete for that type.
        if is_abstract_type(return_type):
            return self.complete_abstract_value(
                return_type,
                field_group,
                info,
                path,
                result,
                incremental_data_record,
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
                incremental_data_record,
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
        incremental_data_record: IncrementalDataRecord,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
    ) -> Any:
        """Complete an awaitable value."""
        try:
            resolved = await result
            completed = self.complete_value(
                return_type,
                field_group,
                info,
                path,
                resolved,
                incremental_data_record,
                defer_map,
            )
            if self.is_awaitable(completed):
                completed = await completed
        except Exception as raw_error:
            # Before Python 3.8 CancelledError inherits Exception and
            # so gets caught here.
            if isinstance(raw_error, CancelledError):
                raise  # pragma: no cover
            self.handle_field_error(
                raw_error, return_type, field_group, path, incremental_data_record
            )
            self.incremental_publisher.filter(path, incremental_data_record)
            completed = None
        return completed

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
            GraphQLStreamDirective, field_group.fields[0].node, self.variable_values
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

        streamed_field_group = FieldGroup(
            [
                FieldDetails(field_details.node, None)
                for field_details in field_group.fields
            ],
            NON_DEFERRED_TARGET_SET,
        )

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
        incremental_data_record: IncrementalDataRecord,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
    ) -> list[Any]:
        """Complete an async iterator.

        Complete an async iterator value by completing the result and calling
        recursively until all the results are completed.
        """
        stream_usage = self.get_stream_usage(field_group, path)
        complete_list_item_value = self.complete_list_item_value
        awaitable_indices: list[int] = []
        append_awaitable = awaitable_indices.append
        completed_results: list[Any] = []
        index = 0
        while True:
            if stream_usage and index >= stream_usage.initial_count:
                try:
                    early_return = async_iterator.aclose  # type: ignore
                except AttributeError:
                    early_return = None
                stream_record = StreamRecord(path, stream_usage.label, early_return)

                with suppress_timeout_error:
                    await wait_for(
                        shield(
                            self.execute_stream_async_iterator(
                                index,
                                async_iterator,
                                stream_usage.field_group,
                                info,
                                item_type,
                                path,
                                incremental_data_record,
                                stream_record,
                            )
                        ),
                        timeout=ASYNC_DELAY,
                    )
                break

            item_path = path.add_key(index, None)
            try:
                try:
                    value = await anext(async_iterator)
                except StopAsyncIteration:
                    break
            except Exception as raw_error:
                raise located_error(
                    raw_error, field_group.to_nodes(), path.as_list()
                ) from raw_error
            if complete_list_item_value(
                value,
                completed_results,
                item_type,
                field_group,
                info,
                item_path,
                incremental_data_record,
                defer_map,
            ):
                append_awaitable(index)

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
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        path: Path,
        result: AsyncIterable[Any] | Iterable[Any],
        incremental_data_record: IncrementalDataRecord,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
    ) -> AwaitableOrValue[list[Any]]:
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
                incremental_data_record,
                defer_map,
            )

        if not is_iterable(result):
            msg = (
                "Expected Iterable, but did not find one for field"
                f" '{info.parent_type.name}.{info.field_name}'."
            )
            raise GraphQLError(msg)

        stream_usage = self.get_stream_usage(field_group, path)

        # This is specified as a simple map, however we're optimizing the path where
        # the list contains no coroutine objects by avoiding creating another coroutine
        # object.
        complete_list_item_value = self.complete_list_item_value
        current_parents = incremental_data_record
        awaitable_indices: list[int] = []
        append_awaitable = awaitable_indices.append
        completed_results: list[Any] = []
        stream_record: StreamRecord | None = None
        for index, item in enumerate(result):
            # No need to modify the info object containing the path, since from here on
            # it is not ever accessed by resolver functions.
            item_path = path.add_key(index, None)

            if stream_usage and index >= stream_usage.initial_count:
                if stream_record is None:
                    stream_record = StreamRecord(path, stream_usage.label)
                current_parents = self.execute_stream_field(
                    path,
                    item_path,
                    item,
                    stream_usage.field_group,
                    info,
                    item_type,
                    current_parents,
                    stream_record,
                )
                continue

            if complete_list_item_value(
                item,
                completed_results,
                item_type,
                field_group,
                info,
                item_path,
                incremental_data_record,
                defer_map,
            ):
                append_awaitable(index)

        if stream_record is not None:
            self.incremental_publisher.set_is_final_record(
                cast("StreamItemsRecord", current_parents)
            )

        if not awaitable_indices:
            return completed_results

        # noinspection PyShadowingNames
        async def get_completed_results() -> list[Any]:
            if len(awaitable_indices) == 1:
                # If there is only one index, avoid the overhead of parallelization.
                index = awaitable_indices[0]
                completed_results[index] = await completed_results[index]
            else:
                for index, sub_result in zip(
                    awaitable_indices,
                    await gather(
                        *(completed_results[index] for index in awaitable_indices)
                    ),
                ):
                    completed_results[index] = sub_result
            return completed_results

        return get_completed_results()

    def complete_list_item_value(
        self,
        item: Any,
        complete_results: list[Any],
        item_type: GraphQLOutputType,
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        item_path: Path,
        incremental_data_record: IncrementalDataRecord,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
    ) -> bool:
        """Complete a list item value by adding it to the completed results.

        Returns True if the value is awaitable.
        """
        is_awaitable = self.is_awaitable

        if is_awaitable(item):
            complete_results.append(
                self.complete_awaitable_value(
                    item_type,
                    field_group,
                    info,
                    item_path,
                    item,
                    incremental_data_record,
                    defer_map,
                )
            )
            return True

        try:
            completed_item = self.complete_value(
                item_type,
                field_group,
                info,
                item_path,
                item,
                incremental_data_record,
                defer_map,
            )

            if is_awaitable(completed_item):
                # noinspection PyShadowingNames
                async def await_completed() -> Any:
                    try:
                        return await completed_item
                    except Exception as raw_error:
                        self.handle_field_error(
                            raw_error,
                            item_type,
                            field_group,
                            item_path,
                            incremental_data_record,
                        )
                        self.incremental_publisher.filter(
                            item_path, incremental_data_record
                        )
                        return None

                complete_results.append(await_completed())
                return True

            complete_results.append(completed_item)

        except Exception as raw_error:
            self.handle_field_error(
                raw_error,
                item_type,
                field_group,
                item_path,
                incremental_data_record,
            )
            self.incremental_publisher.filter(item_path, incremental_data_record)
            complete_results.append(None)

        return False

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
        incremental_data_record: IncrementalDataRecord,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
    ) -> AwaitableOrValue[Any]:
        """Complete an abstract value.

        Complete a value of an abstract type by determining the runtime object type of
        that value, then complete the value for that type.
        """
        resolve_type_fn = return_type.resolve_type or self.type_resolver
        runtime_type = resolve_type_fn(result, info, return_type)

        if self.is_awaitable(runtime_type):
            runtime_type = cast("Awaitable", runtime_type)

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
                    incremental_data_record,
                    defer_map,
                )
                if self.is_awaitable(value):
                    return await value  # type: ignore
                return value  # pragma: no cover

            return await_complete_object_value()
        runtime_type = cast("Optional[str]", runtime_type)

        return self.complete_object_value(
            self.ensure_valid_runtime_type(
                runtime_type, return_type, field_group, info, result
            ),
            field_group,
            info,
            path,
            result,
            incremental_data_record,
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
            raise GraphQLError(msg, field_group.to_nodes())

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
            raise GraphQLError(msg, field_group.to_nodes())

        runtime_type = self.schema.get_type(runtime_type_name)

        if runtime_type is None:
            msg = (
                f"Abstract type '{return_type.name}' was resolved to a type"
                f" '{runtime_type_name}' that does not exist inside the schema."
            )
            raise GraphQLError(msg, field_group.to_nodes())

        if not is_object_type(runtime_type):
            msg = (
                f"Abstract type '{return_type.name}' was resolved"
                f" to a non-object type '{runtime_type_name}'."
            )
            raise GraphQLError(msg, field_group.to_nodes())

        if not self.schema.is_sub_type(return_type, runtime_type):
            msg = (
                f"Runtime Object type '{runtime_type.name}' is not a possible"
                f" type for '{return_type.name}'."
            )
            raise GraphQLError(msg, field_group.to_nodes())

        # noinspection PyTypeChecker
        return runtime_type

    def complete_object_value(
        self,
        return_type: GraphQLObjectType,
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        path: Path,
        result: Any,
        incremental_data_record: IncrementalDataRecord,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
    ) -> AwaitableOrValue[dict[str, Any]]:
        """Complete an Object value by executing all sub-selections."""
        # If there is an `is_type_of()` predicate function, call it with the current
        # result. If `is_type_of()` returns False, then raise an error rather than
        # continuing execution.
        if return_type.is_type_of:
            is_type_of = return_type.is_type_of(result, info)

            if self.is_awaitable(is_type_of):

                async def execute_subfields_async() -> dict[str, Any]:
                    if not await is_type_of:  # type: ignore
                        raise invalid_return_type_error(
                            return_type, result, field_group
                        )
                    return self.collect_and_execute_subfields(
                        return_type,
                        field_group,
                        path,
                        result,
                        incremental_data_record,
                        defer_map,
                    )  # type: ignore

                return execute_subfields_async()

            if not is_type_of:
                raise invalid_return_type_error(return_type, result, field_group)

        return self.collect_and_execute_subfields(
            return_type, field_group, path, result, incremental_data_record, defer_map
        )

    def collect_and_execute_subfields(
        self,
        return_type: GraphQLObjectType,
        field_group: FieldGroup,
        path: Path,
        result: Any,
        incremental_data_record: IncrementalDataRecord,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
    ) -> AwaitableOrValue[dict[str, Any]]:
        """Collect sub-fields to execute to complete this value."""
        grouped_field_set, new_grouped_field_set_details, new_defer_usages = (
            self.collect_subfields(return_type, field_group)
        )

        incremental_publisher = self.incremental_publisher
        new_defer_map = add_new_deferred_fragments(
            incremental_publisher,
            new_defer_usages,
            incremental_data_record,
            defer_map,
            path,
        )
        new_deferred_grouped_field_set_records = add_new_deferred_grouped_field_sets(
            incremental_publisher, new_grouped_field_set_details, new_defer_map, path
        )

        sub_fields = self.execute_fields(
            return_type,
            result,
            path,
            grouped_field_set,
            incremental_data_record,
            new_defer_map,
        )

        self.execute_deferred_grouped_field_sets(
            return_type,
            result,
            path,
            new_deferred_grouped_field_set_records,
            new_defer_map,
        )

        return sub_fields

    def collect_subfields(
        self, return_type: GraphQLObjectType, field_group: FieldGroup
    ) -> CollectFieldsResult:
        """Collect subfields.

        A cached collection of relevant subfields with regard to the return type is
        kept in the execution context as ``_subfields_cache``. This ensures the
        subfields are not repeatedly calculated, which saves overhead when resolving
        lists of values.
        """
        cache = self._subfields_cache
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
        sub_fields_and_patches = cache.get(key)
        if sub_fields_and_patches is None:
            sub_fields_and_patches = collect_subfields(
                self.schema,
                self.fragments,
                self.variable_values,
                self.operation,
                return_type,
                field_group,
            )
            cache[key] = sub_fields_and_patches
        return sub_fields_and_patches

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

        async def callback(payload: Any) -> ExecutionResult:
            result = execute_impl(self.build_per_event_execution_context(payload))
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
        new_deferred_grouped_field_set_records: Sequence[DeferredGroupedFieldSetRecord],
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
    ) -> None:
        """Execute deferred grouped field sets."""
        for deferred_grouped_field_set_record in new_deferred_grouped_field_set_records:
            if deferred_grouped_field_set_record.should_initiate_defer:

                async def execute_deferred_grouped_field_set(
                    deferred_grouped_field_set_record: DeferredGroupedFieldSetRecord,
                ) -> None:
                    self.execute_deferred_grouped_field_set(
                        parent_type,
                        source_value,
                        path,
                        deferred_grouped_field_set_record,
                        defer_map,
                    )

                self.add_task(
                    execute_deferred_grouped_field_set(
                        deferred_grouped_field_set_record
                    )
                )

            else:
                self.execute_deferred_grouped_field_set(
                    parent_type,
                    source_value,
                    path,
                    deferred_grouped_field_set_record,
                    defer_map,
                )

    def execute_deferred_grouped_field_set(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Path | None,
        deferred_grouped_field_set_record: DeferredGroupedFieldSetRecord,
        defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
    ) -> None:
        """Execute deferred grouped field set."""
        incremental_publisher = self.incremental_publisher
        try:
            incremental_result = self.execute_fields(
                parent_type,
                source_value,
                path,
                deferred_grouped_field_set_record.grouped_field_set,
                deferred_grouped_field_set_record,
                defer_map,
            )

            if self.is_awaitable(incremental_result):
                incremental_result = cast("Awaitable", incremental_result)

                async def await_incremental_result() -> None:
                    try:
                        result = await incremental_result
                    except GraphQLError as error:
                        incremental_publisher.mark_errored_deferred_grouped_field_set(
                            deferred_grouped_field_set_record, error
                        )
                    else:
                        incremental_publisher.complete_deferred_grouped_field_set(
                            deferred_grouped_field_set_record, result
                        )

                self.add_task(await_incremental_result())

            else:
                incremental_publisher.complete_deferred_grouped_field_set(
                    deferred_grouped_field_set_record,
                    incremental_result,  # type: ignore
                )

        except GraphQLError as error:
            incremental_publisher.mark_errored_deferred_grouped_field_set(
                deferred_grouped_field_set_record, error
            )

    def execute_stream_field(
        self,
        path: Path,
        item_path: Path,
        item: AwaitableOrValue[Any],
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        item_type: GraphQLOutputType,
        incremental_data_record: IncrementalDataRecord,
        stream_record: StreamRecord,
    ) -> StreamItemsRecord:
        """Execute stream field."""
        is_awaitable = self.is_awaitable
        incremental_publisher = self.incremental_publisher
        stream_items_record = StreamItemsRecord(stream_record, item_path)
        incremental_publisher.report_new_stream_items_record(
            stream_items_record, incremental_data_record
        )
        completed_item: Any

        if is_awaitable(item):

            async def await_completed_awaitable_item() -> None:
                try:
                    value = await self.complete_awaitable_value(
                        item_type,
                        field_group,
                        info,
                        item_path,
                        item,
                        stream_items_record,
                        RefMap(),
                    )
                except GraphQLError as error:
                    incremental_publisher.filter(path, stream_items_record)
                    incremental_publisher.mark_errored_stream_items_record(
                        stream_items_record, error
                    )
                else:
                    incremental_publisher.complete_stream_items_record(
                        stream_items_record, [value]
                    )

            self.add_task(await_completed_awaitable_item())
            return stream_items_record

        try:
            try:
                completed_item = self.complete_value(
                    item_type,
                    field_group,
                    info,
                    item_path,
                    item,
                    stream_items_record,
                    RefMap(),
                )
            except Exception as raw_error:
                self.handle_field_error(
                    raw_error,
                    item_type,
                    field_group,
                    item_path,
                    stream_items_record,
                )
                completed_item = None
                incremental_publisher.filter(item_path, stream_items_record)
        except GraphQLError as error:
            incremental_publisher.filter(path, stream_items_record)
            incremental_publisher.mark_errored_stream_items_record(
                stream_items_record, error
            )
            return stream_items_record

        if is_awaitable(completed_item):

            async def await_completed_item() -> None:
                try:
                    try:
                        value = await completed_item
                    except Exception as raw_error:  # pragma: no cover
                        self.handle_field_error(
                            raw_error,
                            item_type,
                            field_group,
                            item_path,
                            stream_items_record,
                        )
                        incremental_publisher.filter(item_path, stream_items_record)
                        value = None
                except GraphQLError as error:  # pragma: no cover
                    incremental_publisher.filter(path, stream_items_record)
                    incremental_publisher.mark_errored_stream_items_record(
                        stream_items_record, error
                    )
                else:
                    incremental_publisher.complete_stream_items_record(
                        stream_items_record, [value]
                    )

            self.add_task(await_completed_item())
            return stream_items_record

        incremental_publisher.complete_stream_items_record(
            stream_items_record, [completed_item]
        )
        return stream_items_record

    async def execute_stream_async_iterator_item(
        self,
        async_iterator: AsyncIterator[Any],
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        item_type: GraphQLOutputType,
        stream_items_record: StreamItemsRecord,
        item_path: Path,
    ) -> Any:
        """Execute stream iterator item."""
        if async_iterator in self._canceled_iterators:
            raise StopAsyncIteration  # pragma: no cover
        try:
            item = await anext(async_iterator)
        except StopAsyncIteration as raw_error:
            self.incremental_publisher.set_is_completed_async_iterator(
                stream_items_record
            )
            raise StopAsyncIteration from raw_error
        except Exception as raw_error:
            raise located_error(
                raw_error,
                field_group.to_nodes(),
                stream_items_record.stream_record.path,
            ) from raw_error
        else:
            if stream_items_record.stream_record.errors:
                raise StopAsyncIteration  # pragma: no cover
        try:
            completed_item = self.complete_value(
                item_type,
                field_group,
                info,
                item_path,
                item,
                stream_items_record,
                RefMap(),
            )
            return (
                await completed_item
                if self.is_awaitable(completed_item)
                else completed_item
            )
        except Exception as raw_error:
            self.handle_field_error(
                raw_error, item_type, field_group, item_path, stream_items_record
            )
            self.incremental_publisher.filter(item_path, stream_items_record)

    async def execute_stream_async_iterator(
        self,
        initial_index: int,
        async_iterator: AsyncIterator[Any],
        field_group: FieldGroup,
        info: GraphQLResolveInfo,
        item_type: GraphQLOutputType,
        path: Path,
        incremental_data_record: IncrementalDataRecord,
        stream_record: StreamRecord,
    ) -> None:
        """Execute stream iterator."""
        incremental_publisher = self.incremental_publisher
        index = initial_index
        current_incremental_data_record = incremental_data_record

        while True:
            item_path = Path(path, index, None)
            stream_items_record = StreamItemsRecord(stream_record, item_path)
            incremental_publisher.report_new_stream_items_record(
                stream_items_record, current_incremental_data_record
            )

            try:
                completed_item = await self.execute_stream_async_iterator_item(
                    async_iterator,
                    field_group,
                    info,
                    item_type,
                    stream_items_record,
                    item_path,
                )
            except GraphQLError as error:
                incremental_publisher.filter(path, stream_items_record)
                incremental_publisher.mark_errored_stream_items_record(
                    stream_items_record, error
                )
                if async_iterator:  # pragma: no cover else
                    with suppress_exceptions:
                        await async_iterator.aclose()  # type: ignore
                    # running generators cannot be closed since Python 3.8,
                    # so we need to remember that this iterator is already canceled
                    self._canceled_iterators.add(async_iterator)
                return
            except StopAsyncIteration:
                done = True
                completed_item = None
            else:
                done = False

            incremental_publisher.complete_stream_items_record(
                stream_items_record, [completed_item]
            )

            if done:
                break
            current_incremental_data_record = stream_items_record
            index += 1

    def add_task(self, awaitable: Awaitable[Any]) -> None:
        """Add the given task to the tasks set for later execution."""
        tasks = self._tasks
        task = ensure_future(awaitable)
        tasks.add(task)
        task.add_done_callback(tasks.discard)


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
    middleware: Middleware | None = None,
    execution_context_class: type[ExecutionContext] | None = None,
    is_awaitable: Callable[[Any], bool] | None = None,
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
    middleware: Middleware | None = None,
    execution_context_class: type[ExecutionContext] | None = None,
    is_awaitable: Callable[[Any], bool] | None = None,
    **custom_context_args: Any,
) -> AwaitableOrValue[ExecutionResult | ExperimentalIncrementalExecutionResults]:
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
        **custom_context_args,
    )

    # Return early errors if execution context failed.
    if isinstance(context, list):
        return ExecutionResult(None, errors=context)

    return execute_impl(context)


def execute_impl(
    context: ExecutionContext,
) -> AwaitableOrValue[ExecutionResult | ExperimentalIncrementalExecutionResults]:
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
    incremental_publisher = context.incremental_publisher
    initial_result_record = InitialResultRecord()
    try:
        data = context.execute_operation(initial_result_record)
        if context.is_awaitable(data):

            async def await_response() -> (
                ExecutionResult | ExperimentalIncrementalExecutionResults
            ):
                try:
                    return incremental_publisher.build_data_response(
                        initial_result_record,
                        await data,  # type: ignore
                    )
                except GraphQLError as error:
                    return incremental_publisher.build_error_response(
                        initial_result_record, error
                    )

            return await_response()

        return incremental_publisher.build_data_response(initial_result_record, data)  # type: ignore

    except GraphQLError as error:
        return incremental_publisher.build_error_response(initial_result_record, error)


def assume_not_awaitable(_value: Any) -> bool:
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
        field_group.to_nodes(),
    )


def add_new_deferred_fragments(
    incremental_publisher: IncrementalPublisher,
    new_defer_usages: Sequence[DeferUsage],
    incremental_data_record: IncrementalDataRecord,
    defer_map: RefMap[DeferUsage, DeferredFragmentRecord] | None = None,
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
    if not new_defer_usages:
        # Given no DeferUsages, return the existing map, creating one if necessary.
        return RefMap() if defer_map is None else defer_map

    # Create a copy of the old map.
    new_defer_map = RefMap() if defer_map is None else RefMap(defer_map.items())

    # For each new DeferUsage object:
    for defer_usage in new_defer_usages:
        ancestors = defer_usage.ancestors
        parent_defer_usage = ancestors[0] if ancestors else None

        # If the parent target is defined, the parent target is a DeferUsage object
        # and the parent result record is the DeferredFragmentRecord corresponding
        # to that DeferUsage.
        # If the parent target is not defined, the parent result record is either:
        #  - the InitialResultRecord, or
        #  - a StreamItemsRecord, as `@defer` may be nested under `@stream`.
        parent = (
            cast(
                "Union[InitialResultRecord, StreamItemsRecord]", incremental_data_record
            )
            if parent_defer_usage is None
            else deferred_fragment_record_from_defer_usage(
                parent_defer_usage, new_defer_map
            )
        )

        # Instantiate the new record.
        deferred_fragment_record = DeferredFragmentRecord(path, defer_usage.label)

        # Report the new record to the Incremental Publisher.
        incremental_publisher.report_new_defer_fragment_record(
            deferred_fragment_record, parent
        )

        # Update the map.
        new_defer_map[defer_usage] = deferred_fragment_record

    return new_defer_map


def deferred_fragment_record_from_defer_usage(
    defer_usage: DeferUsage, defer_map: RefMap[DeferUsage, DeferredFragmentRecord]
) -> DeferredFragmentRecord:
    """Get the deferred fragment record mapped to the given defer usage."""
    return defer_map[defer_usage]


def add_new_deferred_grouped_field_sets(
    incremental_publisher: IncrementalPublisher,
    new_grouped_field_set_details: Mapping[DeferUsageSet, GroupedFieldSetDetails],
    defer_map: RefMap[DeferUsage, DeferredFragmentRecord],
    path: Path | None = None,
) -> list[DeferredGroupedFieldSetRecord]:
    """Add new deferred grouped field sets to the defer map."""
    new_deferred_grouped_field_set_records: list[DeferredGroupedFieldSetRecord] = []

    for (
        new_grouped_field_set_defer_usages,
        grouped_field_set_details,
    ) in new_grouped_field_set_details.items():
        deferred_fragment_records = get_deferred_fragment_records(
            new_grouped_field_set_defer_usages, defer_map
        )
        deferred_grouped_field_set_record = DeferredGroupedFieldSetRecord(
            deferred_fragment_records,
            grouped_field_set_details.grouped_field_set,
            grouped_field_set_details.should_initiate_defer,
            path,
        )
        incremental_publisher.report_new_deferred_grouped_filed_set_record(
            deferred_grouped_field_set_record
        )
        new_deferred_grouped_field_set_records.append(deferred_grouped_field_set_record)

    return new_deferred_grouped_field_set_records


def get_deferred_fragment_records(
    defer_usages: DeferUsageSet, defer_map: RefMap[DeferUsage, DeferredFragmentRecord]
) -> list[DeferredFragmentRecord]:
    """Get the deferred fragment records for the given defer usages."""
    return [
        deferred_fragment_record_from_defer_usage(defer_usage, defer_map)
        for defer_usage in defer_usages
    ]


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
    awaitable_is_type_of_results: list[Awaitable] = []
    append_awaitable_results = awaitable_is_type_of_results.append
    awaitable_types: list[GraphQLObjectType] = []
    append_awaitable_types = awaitable_types.append

    for type_ in possible_types:
        if type_.is_type_of:
            is_type_of_result = type_.is_type_of(value, info)

            if is_awaitable(is_type_of_result):
                append_awaitable_results(cast("Awaitable", is_type_of_result))
                append_awaitable_types(type_)
            elif is_type_of_result:
                return type_.name

    if awaitable_is_type_of_results:
        # noinspection PyShadowingNames
        async def get_type() -> str | None:
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
    variable_values: dict[str, Any] | None = None,
    operation_name: str | None = None,
    field_resolver: GraphQLFieldResolver | None = None,
    type_resolver: GraphQLTypeResolver | None = None,
    subscribe_field_resolver: GraphQLFieldResolver | None = None,
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
        middleware=middleware,
        **custom_context_args,
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
        awaitable_event_stream = cast("Awaitable", event_stream)

        # noinspection PyShadowingNames
        async def await_event_stream() -> AsyncIterable[Any] | ExecutionResult:
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
    field_name = field_group.fields[0].node.name.value
    field_def = schema.get_field(root_type, field_name)

    if not field_def:
        msg = f"The subscription field '{field_name}' is not defined."
        raise GraphQLError(msg, field_group.to_nodes())

    path = Path(None, response_name, root_type.name)
    info = context.build_resolve_info(field_def, field_group, root_type, path)

    # Implements the "ResolveFieldEventStream" algorithm from GraphQL specification.
    # It differs from "ResolveFieldValue" due to providing a different `resolveFn`.

    try:
        # Build a dictionary of arguments from the field.arguments AST, using the
        # variables scope to fulfill any variable references.
        args = get_argument_values(
            field_def, field_group.fields[0].node, context.variable_values
        )

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
                    raise located_error(
                        error, field_group.to_nodes(), path.as_list()
                    ) from error

            return await_result()

        return assert_event_stream(result)

    except Exception as error:
        raise located_error(error, field_group.to_nodes(), path.as_list()) from error


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
