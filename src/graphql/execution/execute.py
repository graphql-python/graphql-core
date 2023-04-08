from __future__ import annotations  # Python < 3.10

from asyncio import ensure_future, gather
from collections.abc import Mapping
from inspect import isawaitable
from typing import (
    Any,
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
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

from ..error import GraphQLError, GraphQLFormattedError, located_error
from ..language import (
    DocumentNode,
    FieldNode,
    FragmentDefinitionNode,
    OperationDefinitionNode,
    OperationType,
)
from ..pyutils import AwaitableOrValue, Path, Undefined, inspect
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
    GraphQLTypeResolver,
    assert_valid_schema,
    is_abstract_type,
    is_leaf_type,
    is_list_type,
    is_non_null_type,
    is_object_type,
)
from .collect_fields import collect_fields, collect_subfields
from .map_async_iterable import MapAsyncIterable
from .middleware import MiddlewareManager
from .values import get_argument_values, get_variable_values


try:  # pragma: no cover
    anext
except NameError:  # pragma: no cover (Python < 3.10)
    # noinspection PyShadowingBuiltins
    async def anext(iterator: AsyncIterator) -> Any:
        """Return the next item from an async iterator."""
        return await iterator.__anext__()


__all__ = [
    "create_source_event_stream",
    "default_field_resolver",
    "default_type_resolver",
    "execute",
    "execute_sync",
    "subscribe",
    "ExecutionResult",
    "ExecutionContext",
    "FormattedExecutionResult",
    "Middleware",
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

    errors: List[GraphQLFormattedError]
    data: Optional[Dict[str, Any]]
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
        self.errors = errors
        self.middleware_manager = middleware_manager
        if is_awaitable:
            self.is_awaitable = is_awaitable
        self._subfields_cache: Dict[Tuple, Dict[str, List[FieldNode]]] = {}

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
            [],
            self.middleware_manager,
            self.is_awaitable,
        )

    def execute_operation(self) -> AwaitableOrValue[Any]:
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

        root_fields = collect_fields(
            schema,
            self.fragments,
            self.variable_values,
            root_type,
            operation.selection_set,
        )

        return (
            self.execute_fields_serially
            if operation.operation == OperationType.MUTATION
            else self.execute_fields
        )(root_type, self.root_value, None, root_fields)

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
        results: AwaitableOrValue[Dict[str, Any]] = {}
        is_awaitable = self.is_awaitable
        for response_name, field_nodes in fields.items():
            field_path = Path(path, response_name, parent_type.name)
            result = self.execute_field(
                parent_type, source_value, field_nodes, field_path
            )
            if result is Undefined:
                continue
            if is_awaitable(results):
                # noinspection PyShadowingNames
                async def await_and_set_result(
                    results: Awaitable[Dict[str, Any]],
                    response_name: str,
                    result: AwaitableOrValue[Any],
                ) -> Dict[str, Any]:
                    awaited_results = await results
                    awaited_results[response_name] = (
                        await result if is_awaitable(result) else result
                    )
                    return awaited_results

                results = await_and_set_result(
                    cast(Awaitable, results), response_name, result
                )
            elif is_awaitable(result):
                # noinspection PyShadowingNames
                async def set_result(
                    results: Dict[str, Any],
                    response_name: str,
                    result: Awaitable,
                ) -> Dict[str, Any]:
                    results[response_name] = await result
                    return results

                results = set_result(
                    cast(Dict[str, Any], results), response_name, result
                )
            else:
                cast(Dict[str, Any], results)[response_name] = result
        return results

    def execute_fields(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Optional[Path],
        fields: Dict[str, List[FieldNode]],
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
                parent_type, source_value, field_nodes, field_path
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

    def execute_field(
        self,
        parent_type: GraphQLObjectType,
        source: Any,
        field_nodes: List[FieldNode],
        path: Path,
    ) -> AwaitableOrValue[Any]:
        """Resolve the field on the given source object.

        Implements the "Executing fields" section of the spec.

        In particular, this method figures out the value that the field returns by
        calling its resolve function, then calls complete_value to await coroutine
        objects, serialize scalars, or execute the sub-selection-set for objects.
        """
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
                            return_type, field_nodes, info, path, await result
                        )
                        if self.is_awaitable(completed):
                            return await completed
                        return completed
                    except Exception as raw_error:
                        error = located_error(raw_error, field_nodes, path.as_list())
                        self.handle_field_error(error, return_type)
                        return None

                return await_result()

            completed = self.complete_value(
                return_type, field_nodes, info, path, result
            )
            if self.is_awaitable(completed):
                # noinspection PyShadowingNames
                async def await_completed() -> Any:
                    try:
                        return await completed
                    except Exception as raw_error:
                        error = located_error(raw_error, field_nodes, path.as_list())
                        self.handle_field_error(error, return_type)
                        return None

                return await_completed()

            return completed
        except Exception as raw_error:
            error = located_error(raw_error, field_nodes, path.as_list())
            self.handle_field_error(error, return_type)
            return None

    def handle_field_error(
        self,
        error: GraphQLError,
        return_type: GraphQLOutputType,
    ) -> None:
        # If the field type is non-nullable, then it is resolved without any protection
        # from errors, however it still properly locates the error.
        if is_non_null_type(return_type):
            raise error
        # Otherwise, error protection is applied, logging the error and resolving a
        # null value for this field if one is encountered.
        self.errors.append(error)
        return None

    def complete_value(
        self,
        return_type: GraphQLOutputType,
        field_nodes: List[FieldNode],
        info: GraphQLResolveInfo,
        path: Path,
        result: Any,
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
                return_type, field_nodes, info, path, result
            )

        # If field type is a leaf type, Scalar or Enum, serialize to a valid value,
        # returning null if serialization is not possible.
        if is_leaf_type(return_type):
            return self.complete_leaf_value(return_type, result)

        # If field type is an abstract type, Interface or Union, determine the runtime
        # Object type and complete for that type.
        if is_abstract_type(return_type):
            return self.complete_abstract_value(
                return_type, field_nodes, info, path, result
            )

        # If field type is Object, execute and complete all sub-selections.
        if is_object_type(return_type):
            return self.complete_object_value(
                return_type, field_nodes, info, path, result
            )

        # Not reachable. All possible output types have been considered.
        raise TypeError(  # pragma: no cover
            "Cannot complete value of unexpected output type:"
            f" '{inspect(return_type)}'."
        )

    async def complete_async_iterator_value(
        self,
        item_type: GraphQLOutputType,
        field_nodes: List[FieldNode],
        info: GraphQLResolveInfo,
        path: Path,
        iterator: AsyncIterator[Any],
    ) -> List[Any]:
        """Complete an async iterator.

        Complete a async iterator value by completing the result and calling
        recursively until all the results are completed.
        """
        is_awaitable = self.is_awaitable
        awaitable_indices: List[int] = []
        append_awaitable = awaitable_indices.append
        completed_results: List[Any] = []
        append_result = completed_results.append
        index = 0
        while True:
            field_path = path.add_key(index, None)
            try:
                try:
                    value = await anext(iterator)
                except StopAsyncIteration:
                    break
                try:
                    completed_item = self.complete_value(
                        item_type, field_nodes, info, field_path, value
                    )
                    if is_awaitable(completed_item):
                        append_awaitable(index)
                    append_result(completed_item)
                except Exception as raw_error:
                    append_result(None)
                    error = located_error(raw_error, field_nodes, field_path.as_list())
                    self.handle_field_error(error, item_type)
            except Exception as raw_error:
                append_result(None)
                error = located_error(raw_error, field_nodes, field_path.as_list())
                self.handle_field_error(error, item_type)
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
    ) -> AwaitableOrValue[List[Any]]:
        """Complete a list value.

        Complete a list value by completing each item in the list with the inner type.
        """
        item_type = return_type.of_type

        if isinstance(result, AsyncIterable):
            iterator = result.__aiter__()

            return self.complete_async_iterator_value(
                item_type, field_nodes, info, path, iterator
            )

        if not is_iterable(result):
            raise GraphQLError(
                "Expected Iterable, but did not find one for field"
                f" '{info.parent_type.name}.{info.field_name}'."
            )

        # This is specified as a simple map, however we're optimizing the path where
        # the list contains no coroutine objects by avoiding creating another coroutine
        # object.
        is_awaitable = self.is_awaitable
        awaitable_indices: List[int] = []
        append_awaitable = awaitable_indices.append
        completed_results: List[Any] = []
        append_result = completed_results.append
        for index, item in enumerate(result):
            # No need to modify the info object containing the path, since from here on
            # it is not ever accessed by resolver functions.
            item_path = path.add_key(index, None)
            completed_item: AwaitableOrValue[Any]
            if is_awaitable(item):
                # noinspection PyShadowingNames
                async def await_completed(item: Any, item_path: Path) -> Any:
                    try:
                        completed = self.complete_value(
                            item_type, field_nodes, info, item_path, await item
                        )
                        if is_awaitable(completed):
                            return await completed
                        return completed
                    except Exception as raw_error:
                        error = located_error(
                            raw_error, field_nodes, item_path.as_list()
                        )
                        self.handle_field_error(error, item_type)  # noqa: B023
                        return None

                completed_item = await_completed(item, item_path)
            else:
                try:
                    completed_item = self.complete_value(
                        item_type, field_nodes, info, item_path, item
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
                                self.handle_field_error(error, item_type)  # noqa: B023
                                return None

                        completed_item = await_completed(completed_item, item_path)
                except Exception as raw_error:
                    error = located_error(raw_error, field_nodes, item_path.as_list())
                    self.handle_field_error(error, item_type)
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

        return runtime_type

    def complete_object_value(
        self,
        return_type: GraphQLObjectType,
        field_nodes: List[FieldNode],
        info: GraphQLResolveInfo,
        path: Path,
        result: Any,
    ) -> AwaitableOrValue[Dict[str, Any]]:
        """Complete an Object value by executing all sub-selections."""
        # Collect sub-fields to execute to complete this value.
        sub_field_nodes = self.collect_subfields(return_type, field_nodes)

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
                    return self.execute_fields(
                        return_type, result, path, sub_field_nodes
                    )  # type: ignore

                return execute_subfields_async()

            if not is_type_of:
                raise invalid_return_type_error(return_type, result, field_nodes)

        return self.execute_fields(return_type, result, path, sub_field_nodes)

    def collect_subfields(
        self, return_type: GraphQLObjectType, field_nodes: List[FieldNode]
    ) -> Dict[str, List[FieldNode]]:
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
        sub_field_nodes = cache.get(key)
        if sub_field_nodes is None:
            sub_field_nodes = collect_subfields(
                self.schema,
                self.fragments,
                self.variable_values,
                return_type,
                field_nodes,
            )
            cache[key] = sub_field_nodes
        return sub_field_nodes


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
        return ExecutionResult(data=None, errors=context)

    return execute_impl(context)


def execute_impl(context: ExecutionContext) -> AwaitableOrValue[ExecutionResult]:
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
                    return build_response(await result, errors)
                except GraphQLError as error:
                    errors.append(error)
                    return build_response(None, errors)

            return await_result()
    except GraphQLError as error:
        errors.append(error)
        return build_response(None, errors)
    else:
        return build_response(result, errors)  # type: ignore


def assume_not_awaitable(_value: Any) -> bool:
    """Replacement for isawaitable if everything is assumed to be synchronous."""
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

    result = execute(
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
    if isawaitable(result):
        ensure_future(cast(Awaitable[ExecutionResult], result)).cancel()
        raise RuntimeError("GraphQL execution failed to complete synchronously.")

    return cast(ExecutionResult, result)


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
        return ExecutionResult(data=None, errors=context)

    result_or_stream = create_source_event_stream_impl(context)

    build_context = context.build_per_event_execution_context

    async def map_source_to_response(payload: Any) -> ExecutionResult:
        """Map source to response.

        For each payload yielded from a subscription, map it over the normal GraphQL
        :func:`~graphql.execute` function, with ``payload`` as the ``root_value``.
        This implements the "MapSourceToResponseEvent" algorithm described in the
        GraphQL specification. The :func:`~graphql.execute` function provides the
        "ExecuteSubscriptionEvent" algorithm, as it is nearly identical to the
        "ExecuteQuery" algorithm, for which :func:`~graphql.execute` is also used.
        """
        result = execute_impl(build_context(payload))
        return await result if isawaitable(result) else result

    if execution_context_class.is_awaitable(result_or_stream):
        awaitable_result_or_stream = cast(Awaitable, result_or_stream)

        # noinspection PyShadowingNames
        async def await_result() -> Any:
            result_or_stream = await awaitable_result_or_stream
            if isinstance(result_or_stream, ExecutionResult):
                return result_or_stream
            return MapAsyncIterable(result_or_stream, map_source_to_response)

        return await_result()

    if isinstance(result_or_stream, ExecutionResult):
        return result_or_stream

    # Map every source value to a ExecutionResult value as described above.
    return MapAsyncIterable(
        cast(AsyncIterable[Any], result_or_stream), map_source_to_response
    )


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
        return ExecutionResult(data=None, errors=context)

    return create_source_event_stream_impl(context)


def create_source_event_stream_impl(
    context: ExecutionContext,
) -> AwaitableOrValue[Union[AsyncIterable[Any], ExecutionResult]]:
    """Create source event stream (internal implementation)."""
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
