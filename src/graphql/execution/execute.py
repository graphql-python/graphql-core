from asyncio import gather
from inspect import isawaitable
from typing import (
    Any,
    Awaitable,
    Dict,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Set,
    Union,
    Tuple,
    Type,
    cast,
)

from ..error import GraphQLError, INVALID, located_error
from ..language import (
    DocumentNode,
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    InlineFragmentNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
)
from ..pyutils import inspect, is_invalid, is_nullish, AwaitableOrValue
from ..utilities import get_operation_root_type, type_from_ast
from ..type import (
    GraphQLAbstractType,
    GraphQLField,
    GraphQLIncludeDirective,
    GraphQLLeafType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLOutputType,
    GraphQLSchema,
    GraphQLSkipDirective,
    GraphQLFieldResolver,
    GraphQLTypeResolver,
    GraphQLResolveInfo,
    ResponsePath,
    SchemaMetaFieldDef,
    TypeMetaFieldDef,
    TypeNameMetaFieldDef,
    assert_valid_schema,
    is_abstract_type,
    is_leaf_type,
    is_list_type,
    is_non_null_type,
    is_object_type,
)
from .middleware import MiddlewareManager
from .values import get_argument_values, get_directive_values, get_variable_values

__all__ = [
    "add_path",
    "assert_valid_execution_arguments",
    "default_field_resolver",
    "default_type_resolver",
    "execute",
    "get_field_def",
    "response_path_as_list",
    "ExecutionResult",
    "ExecutionContext",
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


class ExecutionResult(NamedTuple):
    """The result of GraphQL execution.

    - `data` is the result of a successful execution of the query.
    - `errors` is included when any errors occurred as a non-empty list.
    """

    data: Optional[Dict[str, Any]]
    errors: Optional[List[GraphQLError]]


ExecutionResult.__new__.__defaults__ = (None, None)  # type: ignore

Middleware = Optional[Union[Tuple, List, MiddlewareManager]]


def execute(
    schema: GraphQLSchema,
    document: DocumentNode,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: Dict[str, Any] = None,
    operation_name: str = None,
    field_resolver: GraphQLFieldResolver = None,
    type_resolver: GraphQLTypeResolver = None,
    middleware: Middleware = None,
    execution_context_class: Type["ExecutionContext"] = None,
) -> AwaitableOrValue[ExecutionResult]:
    """Execute a GraphQL operation.

    Implements the "Evaluating requests" section of the GraphQL specification.

    Returns an ExecutionResult (if all encountered resolvers are synchronous),
    or a coroutine object eventually yielding an ExecutionResult.

    If the arguments to this function do not result in a legal execution context,
    a GraphQLError will be thrown immediately explaining the invalid input.
    """
    # If arguments are missing or incorrect, throw an error.
    assert_valid_execution_arguments(schema, document, variable_values)

    if execution_context_class is None:
        execution_context_class = ExecutionContext

    # If a valid execution context cannot be created due to incorrect arguments,
    # a "Response" with only errors is returned.
    exe_context = execution_context_class.build(
        schema,
        document,
        root_value,
        context_value,
        variable_values,
        operation_name,
        field_resolver,
        type_resolver,
        middleware,
    )

    # Return early errors if execution context failed.
    if isinstance(exe_context, list):
        return ExecutionResult(data=None, errors=exe_context)

    # Return a possible coroutine object that will eventually yield the data described
    # by the "Response" section of the GraphQL specification.
    #
    # If errors are encountered while executing a GraphQL field, only that field and
    # its descendants will be omitted, and sibling fields will still be executed. An
    # execution which encounters errors will still result in a coroutine object that
    # can be executed without errors.

    data = exe_context.execute_operation(exe_context.operation, root_value)
    return exe_context.build_response(data)


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
    middleware_manager: Optional[MiddlewareManager]
    errors: List[GraphQLError]

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
        middleware_manager: Optional[MiddlewareManager],
        errors: List[GraphQLError],
    ) -> None:
        self.schema = schema
        self.fragments = fragments
        self.root_value = root_value
        self.context_value = context_value
        self.operation = operation
        self.variable_values = variable_values
        self.field_resolver = field_resolver  # type: ignore
        self.type_resolver = type_resolver  # type: ignore
        self.middleware_manager = middleware_manager
        self.errors = errors
        self._subfields_cache: Dict[
            Tuple[GraphQLObjectType, Tuple[FieldNode, ...]], Dict[str, List[FieldNode]]
        ] = {}

    @classmethod
    def build(
        cls,
        schema: GraphQLSchema,
        document: DocumentNode,
        root_value: Any = None,
        context_value: Any = None,
        raw_variable_values: Dict[str, Any] = None,
        operation_name: str = None,
        field_resolver: GraphQLFieldResolver = None,
        type_resolver: GraphQLTypeResolver = None,
        middleware: Middleware = None,
    ) -> Union[List[GraphQLError], "ExecutionContext"]:
        """Build an execution context

        Constructs a ExecutionContext object from the arguments passed to execute, which
        we will pass throughout the other execution methods.

        Throws a GraphQLError if a valid execution context cannot be created.
        """
        errors: List[GraphQLError] = []
        operation: Optional[OperationDefinitionNode] = None
        has_multiple_assumed_operations = False
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
                if not operation_name and operation:
                    has_multiple_assumed_operations = True
                elif not operation_name or (
                    definition.name and definition.name.value == operation_name
                ):
                    operation = definition
            elif isinstance(definition, FragmentDefinitionNode):
                fragments[definition.name.value] = definition

        if not operation:
            if operation_name:
                errors.append(
                    GraphQLError(f"Unknown operation named '{operation_name}'.")
                )
            else:
                errors.append(GraphQLError("Must provide an operation."))
        elif has_multiple_assumed_operations:
            errors.append(
                GraphQLError(
                    "Must provide operation name"
                    " if query contains multiple operations."
                )
            )

        variable_values = None
        if operation:
            coerced_variable_values = get_variable_values(
                schema, operation.variable_definitions or [], raw_variable_values or {}
            )

            if coerced_variable_values.errors:
                errors.extend(coerced_variable_values.errors)
            else:
                variable_values = coerced_variable_values.coerced

        if errors:
            return errors

        if operation is None:
            raise TypeError("Has operation if no errors.")
        if variable_values is None:
            raise TypeError("Has variables if no errors.")

        return cls(
            schema,
            fragments,
            root_value,
            context_value,
            operation,
            variable_values,
            field_resolver or default_field_resolver,
            type_resolver or default_type_resolver,
            middleware_manager,
            errors,
        )

    def build_response(
        self, data: AwaitableOrValue[Optional[Dict[str, Any]]]
    ) -> AwaitableOrValue[ExecutionResult]:
        """Build response.

        Given a completed execution context and data, build the (data, errors) response
        defined by the "Response" section of the GraphQL spec.
        """
        if isawaitable(data):

            async def build_response_async():
                return self.build_response(await data)

            return build_response_async()
        data = cast(Optional[Dict[str, Any]], data)
        errors = self.errors
        if not errors:
            return ExecutionResult(data, None)
        # Sort the error list in order to make it deterministic, since we might have
        # been using parallel execution.
        errors.sort(key=lambda error: (error.locations, error.path, error.message))
        return ExecutionResult(data, errors)

    def execute_operation(
        self, operation: OperationDefinitionNode, root_value: Any
    ) -> Optional[AwaitableOrValue[Any]]:
        """Execute an operation.

        Implements the "Evaluating operations" section of the spec.
        """
        type_ = get_operation_root_type(self.schema, operation)
        fields = self.collect_fields(type_, operation.selection_set, {}, set())

        path = None

        # Errors from sub-fields of a NonNull type may propagate to the top level, at
        # which point we still log the error and null the parent field, which in this
        # case is the entire response.
        #
        # Similar to complete_value_catching_error.
        try:
            result = (
                self.execute_fields_serially
                if operation.operation == OperationType.MUTATION
                else self.execute_fields
            )(type_, root_value, path, fields)
        except GraphQLError as error:
            self.errors.append(error)
            return None
        except Exception as error:
            error = GraphQLError(str(error), original_error=error)
            self.errors.append(error)
            return None
        else:
            if isawaitable(result):
                # noinspection PyShadowingNames
                async def await_result():
                    try:
                        return await result
                    except GraphQLError as error:
                        self.errors.append(error)
                    except Exception as error:
                        error = GraphQLError(str(error), original_error=error)
                        self.errors.append(error)

                return await_result()
            return result

    def execute_fields_serially(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Optional[ResponsePath],
        fields: Dict[str, List[FieldNode]],
    ) -> AwaitableOrValue[Dict[str, Any]]:
        """Execute the given fields serially.

        Implements the "Evaluating selection sets" section of the spec for "write" mode.
        """
        results: Dict[str, Any] = {}
        for response_name, field_nodes in fields.items():
            field_path = add_path(path, response_name)
            result = self.resolve_field(
                parent_type, source_value, field_nodes, field_path
            )
            if result is INVALID:
                continue
            if isawaitable(results):
                # noinspection PyShadowingNames
                async def await_and_set_result(results, response_name, result):
                    awaited_results = await results
                    awaited_results[response_name] = (
                        await result if isawaitable(result) else result
                    )
                    return awaited_results

                # noinspection PyTypeChecker
                results = await_and_set_result(
                    cast(Awaitable, results), response_name, result
                )
            elif isawaitable(result):
                # noinspection PyShadowingNames
                async def set_result(results, response_name, result):
                    results[response_name] = await result
                    return results

                # noinspection PyTypeChecker
                results = set_result(results, response_name, result)
            else:
                results[response_name] = result
        if isawaitable(results):
            # noinspection PyShadowingNames
            async def get_results():
                return await cast(Awaitable, results)

            return get_results()
        return results

    def execute_fields(
        self,
        parent_type: GraphQLObjectType,
        source_value: Any,
        path: Optional[ResponsePath],
        fields: Dict[str, List[FieldNode]],
    ) -> AwaitableOrValue[Dict[str, Any]]:
        """Execute the given fields concurrently.

        Implements the "Evaluating selection sets" section of the spec for "read" mode.
        """
        results = {}
        awaitable_fields: List[str] = []
        append_awaitable = awaitable_fields.append
        for response_name, field_nodes in fields.items():
            field_path = add_path(path, response_name)
            result = self.resolve_field(
                parent_type, source_value, field_nodes, field_path
            )
            if result is not INVALID:
                results[response_name] = result
                if isawaitable(result):
                    append_awaitable(response_name)

        #  If there are no coroutines, we can just return the object
        if not awaitable_fields:
            return results

        # Otherwise, results is a map from field name to the result of resolving that
        # field, which is possibly a coroutine object. Return a coroutine object that
        # will yield this same map, but with any coroutines awaited in parallel and
        # replaced with the values they yielded.
        async def get_results():
            results.update(
                zip(
                    awaitable_fields,
                    await gather(*(results[field] for field in awaitable_fields)),
                )
            )
            return results

        return get_results()

    def collect_fields(
        self,
        runtime_type: GraphQLObjectType,
        selection_set: SelectionSetNode,
        fields: Dict[str, List[FieldNode]],
        visited_fragment_names: Set[str],
    ) -> Dict[str, List[FieldNode]]:
        """Collect fields.

        Given a selection_set, adds all of the fields in that selection to the passed in
        map of fields, and returns it at the end.

        collect_fields requires the "runtime type" of an object. For a field which
        returns an Interface or Union type, the "runtime type" will be the actual
        Object type returned by that field.
        """
        for selection in selection_set.selections:
            if isinstance(selection, FieldNode):
                if not self.should_include_node(selection):
                    continue
                name = get_field_entry_key(selection)
                fields.setdefault(name, []).append(selection)
            elif isinstance(selection, InlineFragmentNode):
                if not self.should_include_node(
                    selection
                ) or not self.does_fragment_condition_match(selection, runtime_type):
                    continue
                self.collect_fields(
                    runtime_type,
                    selection.selection_set,
                    fields,
                    visited_fragment_names,
                )
            elif isinstance(selection, FragmentSpreadNode):
                frag_name = selection.name.value
                if frag_name in visited_fragment_names or not self.should_include_node(
                    selection
                ):
                    continue
                visited_fragment_names.add(frag_name)
                fragment = self.fragments.get(frag_name)
                if not fragment or not self.does_fragment_condition_match(
                    fragment, runtime_type
                ):
                    continue
                self.collect_fields(
                    runtime_type, fragment.selection_set, fields, visited_fragment_names
                )
        return fields

    def should_include_node(
        self, node: Union[FragmentSpreadNode, FieldNode, InlineFragmentNode]
    ) -> bool:
        """Check if node should be included

        Determines if a field should be included based on the @include and @skip
        directives, where @skip has higher precedence than @include.
        """
        skip = get_directive_values(GraphQLSkipDirective, node, self.variable_values)
        if skip and skip["if"]:
            return False

        include = get_directive_values(
            GraphQLIncludeDirective, node, self.variable_values
        )
        if include and not include["if"]:
            return False

        return True

    def does_fragment_condition_match(
        self,
        fragment: Union[FragmentDefinitionNode, InlineFragmentNode],
        type_: GraphQLObjectType,
    ) -> bool:
        """Determine if a fragment is applicable to the given type."""
        type_condition_node = fragment.type_condition
        if not type_condition_node:
            return True
        conditional_type = type_from_ast(self.schema, type_condition_node)
        if conditional_type is type_:
            return True
        if is_abstract_type(conditional_type):
            return self.schema.is_possible_type(
                cast(GraphQLAbstractType, conditional_type), type_
            )
        return False

    def build_resolve_info(
        self,
        field_def: GraphQLField,
        field_nodes: List[FieldNode],
        parent_type: GraphQLObjectType,
        path: ResponsePath,
    ) -> GraphQLResolveInfo:
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
        )

    def resolve_field(
        self,
        parent_type: GraphQLObjectType,
        source: Any,
        field_nodes: List[FieldNode],
        path: ResponsePath,
    ) -> AwaitableOrValue[Any]:
        """Resolve the field on the given source object.

        In particular, this figures out the value that the field returns by calling its
        resolve function, then calls complete_value to await coroutine objects,
        serialize scalars, or execute the sub-selection-set for objects.
        """
        field_node = field_nodes[0]
        field_name = field_node.name.value

        field_def = get_field_def(self.schema, parent_type, field_name)
        if not field_def:
            return INVALID

        resolve_fn = field_def.resolve or self.field_resolver

        if self.middleware_manager:
            resolve_fn = self.middleware_manager.get_field_resolver(resolve_fn)

        info = self.build_resolve_info(field_def, field_nodes, parent_type, path)

        # Get the resolve function, regardless of if its result is normal or abrupt
        # (error).
        result = self.resolve_field_value_or_error(
            field_def, field_nodes, resolve_fn, source, info
        )

        return self.complete_value_catching_error(
            field_def.type, field_nodes, info, path, result
        )

    def resolve_field_value_or_error(
        self,
        field_def: GraphQLField,
        field_nodes: List[FieldNode],
        resolve_fn: GraphQLFieldResolver,
        source: Any,
        info: GraphQLResolveInfo,
    ) -> Union[Exception, Any]:
        try:
            # Build a dictionary of arguments from the field.arguments AST, using the
            # variables scope to fulfill any variable references.
            args = get_argument_values(field_def, field_nodes[0], self.variable_values)

            # Note that contrary to the JavaScript implementation, we pass the context
            # value as part of the resolve info.
            result = resolve_fn(source, info, **args)
            if isawaitable(result):
                # noinspection PyShadowingNames
                async def await_result():
                    try:
                        return await result
                    except GraphQLError as error:
                        return error
                    except Exception as error:
                        return GraphQLError(str(error), original_error=error)

                return await_result()
            return result
        except GraphQLError as error:
            return error
        except Exception as error:
            return GraphQLError(str(error), original_error=error)

    def complete_value_catching_error(
        self,
        return_type: GraphQLOutputType,
        field_nodes: List[FieldNode],
        info: GraphQLResolveInfo,
        path: ResponsePath,
        result: Any,
    ) -> AwaitableOrValue[Any]:
        """Complete a value while catching an error.

        This is a small wrapper around completeValue which detects and logs errors in
        the execution context.
        """
        try:
            if isawaitable(result):

                async def await_result():
                    value = self.complete_value(
                        return_type, field_nodes, info, path, await result
                    )
                    if isawaitable(value):
                        return await value
                    return value

                completed = await_result()
            else:
                completed = self.complete_value(
                    return_type, field_nodes, info, path, result
                )
            if isawaitable(completed):
                # noinspection PyShadowingNames
                async def await_completed():
                    try:
                        return await completed
                    except Exception as error:
                        self.handle_field_error(error, field_nodes, path, return_type)

                return await_completed()
            return completed
        except Exception as error:
            self.handle_field_error(error, field_nodes, path, return_type)
            return None

    def handle_field_error(
        self,
        raw_error: Exception,
        field_nodes: List[FieldNode],
        path: ResponsePath,
        return_type: GraphQLOutputType,
    ) -> None:
        error = located_error(raw_error, field_nodes, response_path_as_list(path))

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
        path: ResponsePath,
        result: Any,
    ) -> AwaitableOrValue[Any]:
        """Complete a value.

        Implements the instructions for completeValue as defined in the "Field entries"
        section of the spec.

        If the field type is Non-Null, then this recursively completes the value for the
        inner type. It throws a field error if that completion returns null, as per the
        "Nullability" section of the spec.

        If the field type is a List, then this recursively completes the value for the
        inner type on each item in the list.

        If the field type is a Scalar or Enum, ensures the completed value is a legal
        value of the type by calling the `serialize` method of GraphQL type definition.

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
                cast(GraphQLNonNull, return_type).of_type,
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

        # If result value is null-ish (null, INVALID, or NaN) then return null.
        if is_nullish(result):
            return None

        # If field type is List, complete each item in the list with inner type
        if is_list_type(return_type):
            return self.complete_list_value(
                cast(GraphQLList, return_type), field_nodes, info, path, result
            )

        # If field type is a leaf type, Scalar or Enum, serialize to a valid value,
        # returning null if serialization is not possible.
        if is_leaf_type(return_type):
            return self.complete_leaf_value(cast(GraphQLLeafType, return_type), result)

        # If field type is an abstract type, Interface or Union, determine the runtime
        # Object type and complete for that type.
        if is_abstract_type(return_type):
            return self.complete_abstract_value(
                cast(GraphQLAbstractType, return_type), field_nodes, info, path, result
            )

        # If field type is Object, execute and complete all sub-selections.
        if is_object_type(return_type):
            return self.complete_object_value(
                cast(GraphQLObjectType, return_type), field_nodes, info, path, result
            )

        # Not reachable. All possible output types have been considered.
        raise TypeError(  # pragma: no cover
            "Cannot complete value of unexpected output type:"
            f" '{inspect(return_type)}'."
        )

    def complete_list_value(
        self,
        return_type: GraphQLList[GraphQLOutputType],
        field_nodes: List[FieldNode],
        info: GraphQLResolveInfo,
        path: ResponsePath,
        result: Iterable[Any],
    ) -> AwaitableOrValue[Any]:
        """Complete a list value.

        Complete a list value by completing each item in the list with the inner type.
        """
        if not isinstance(result, Iterable) or isinstance(result, str):
            raise TypeError(
                "Expected Iterable, but did not find one for field"
                f" {info.parent_type.name}.{info.field_name}."
            )

        # This is specified as a simple map, however we're optimizing the path where
        # the list contains no coroutine objects by avoiding creating another coroutine
        # object.
        item_type = return_type.of_type
        awaitable_indices: List[int] = []
        append_awaitable = awaitable_indices.append
        completed_results: List[Any] = []
        append_result = completed_results.append
        for index, item in enumerate(result):
            # No need to modify the info object containing the path, since from here on
            # it is not ever accessed by resolver functions.
            field_path = add_path(path, index)
            completed_item = self.complete_value_catching_error(
                item_type, field_nodes, info, field_path, item
            )

            if isawaitable(completed_item):
                append_awaitable(index)
            append_result(completed_item)

        if not awaitable_indices:
            return completed_results

        # noinspection PyShadowingNames
        async def get_completed_results():
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
        if is_invalid(serialized_result):
            raise TypeError(
                f"Expected a value of type '{inspect(return_type)}'"
                f" but received: {inspect(result)}"
            )
        return serialized_result

    def complete_abstract_value(
        self,
        return_type: GraphQLAbstractType,
        field_nodes: List[FieldNode],
        info: GraphQLResolveInfo,
        path: ResponsePath,
        result: Any,
    ) -> AwaitableOrValue[Any]:
        """Complete an abstract value.

        Complete a value of an abstract type by determining the runtime object type of
        that value, then complete the value for that type.
        """
        resolve_type_fn = return_type.resolve_type or self.type_resolver
        runtime_type = resolve_type_fn(result, info, return_type)  # type: ignore

        if isawaitable(runtime_type):

            async def await_complete_object_value():
                value = self.complete_object_value(
                    self.ensure_valid_runtime_type(
                        await runtime_type, return_type, field_nodes, info, result
                    ),
                    field_nodes,
                    info,
                    path,
                    result,
                )
                if isawaitable(value):
                    return await value
                return value

            return await_complete_object_value()
        runtime_type = cast(Optional[Union[GraphQLObjectType, str]], runtime_type)

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
        runtime_type_or_name: Optional[Union[GraphQLObjectType, str]],
        return_type: GraphQLAbstractType,
        field_nodes: List[FieldNode],
        info: GraphQLResolveInfo,
        result: Any,
    ) -> GraphQLObjectType:
        runtime_type = (
            self.schema.get_type(runtime_type_or_name)
            if isinstance(runtime_type_or_name, str)
            else runtime_type_or_name
        )

        if not is_object_type(runtime_type):
            raise GraphQLError(
                f"Abstract type {return_type.name} must resolve"
                " to an Object type at runtime"
                f" for field {info.parent_type.name}.{info.field_name}"
                f" with value {inspect(result)}, received '{inspect(runtime_type)}'."
                f" Either the {return_type.name} type should provide"
                ' a "resolve_type" function or each possible type should'
                ' provide an "is_type_of" function.',
                field_nodes,
            )
        runtime_type = cast(GraphQLObjectType, runtime_type)

        if not self.schema.is_possible_type(return_type, runtime_type):
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
        path: ResponsePath,
        result: Any,
    ) -> AwaitableOrValue[Dict[str, Any]]:
        """Complete an Object value by executing all sub-selections."""
        # If there is an `is_type_of()` predicate function, call it with the current
        # result. If `is_type_of()` returns False, then raise an error rather than
        #  continuing execution.
        if return_type.is_type_of:
            is_type_of = return_type.is_type_of(result, info)

            if isawaitable(is_type_of):

                async def collect_and_execute_subfields_async():
                    if not await is_type_of:
                        raise invalid_return_type_error(
                            return_type, result, field_nodes
                        )
                    return self.collect_and_execute_subfields(
                        return_type, field_nodes, path, result
                    )

                return collect_and_execute_subfields_async()

            if not is_type_of:
                raise invalid_return_type_error(return_type, result, field_nodes)

        return self.collect_and_execute_subfields(
            return_type, field_nodes, path, result
        )

    def collect_and_execute_subfields(
        self,
        return_type: GraphQLObjectType,
        field_nodes: List[FieldNode],
        path: ResponsePath,
        result: Any,
    ) -> AwaitableOrValue[Dict[str, Any]]:
        """Collect sub-fields to execute to complete this value."""
        sub_field_nodes = self.collect_subfields(return_type, field_nodes)
        return self.execute_fields(return_type, result, path, sub_field_nodes)

    def collect_subfields(
        self, return_type: GraphQLObjectType, field_nodes: List[FieldNode]
    ) -> Dict[str, List[FieldNode]]:
        """Collect subfields.

        A cached collection of relevant subfields with regard to the return type is
        kept in the execution context as `_subfields_cache`. This ensures the
        subfields are not repeatedly calculated, which saves overhead when resolving
        lists of values.
        """
        cache_key = return_type, tuple(field_nodes)
        sub_field_nodes = self._subfields_cache.get(cache_key)
        if sub_field_nodes is None:
            sub_field_nodes = {}
            visited_fragment_names: Set[str] = set()
            for field_node in field_nodes:
                selection_set = field_node.selection_set
                if selection_set:
                    sub_field_nodes = self.collect_fields(
                        return_type,
                        selection_set,
                        sub_field_nodes,
                        visited_fragment_names,
                    )
            self._subfields_cache[cache_key] = sub_field_nodes
        return sub_field_nodes


def assert_valid_execution_arguments(
    schema: GraphQLSchema,
    document: DocumentNode,
    raw_variable_values: Dict[str, Any] = None,
) -> None:
    """Check that the arguments are acceptable.

    Essential assertions before executing to provide developer feedback for improper use
    of the GraphQL library.
    """
    if not document:
        raise TypeError("Must provide document")

    # If the schema used for execution is invalid, throw an error.
    assert_valid_schema(schema)

    # Variables, if provided, must be a dictionary.
    if not (raw_variable_values is None or isinstance(raw_variable_values, dict)):
        raise TypeError(
            "Variables must be provided as a dictionary where each property is a"
            " variable value. Perhaps look to see if an unparsed JSON string was"
            " provided."
        )


def response_path_as_list(path: ResponsePath) -> List[Union[str, int]]:
    """Get response path as a list.

    Given a ResponsePath (found in the `path` entry in the information provided as the
    last argument to a field resolver), return a list of the path keys.
    """
    flattened: List[Union[str, int]] = []
    append = flattened.append
    curr: Optional[ResponsePath] = path
    while curr:
        append(curr.key)
        curr = curr.prev
    return flattened[::-1]


def add_path(prev: Optional[ResponsePath], key: Union[str, int]) -> ResponsePath:
    """Add a key to a response path.

    Given a ResponsePath and a key, return a new ResponsePath containing the new key.
    """
    return ResponsePath(prev, key)


def get_field_def(
    schema: GraphQLSchema, parent_type: GraphQLObjectType, field_name: str
) -> GraphQLField:
    """Get field definition.

    This method looks up the field on the given type definition. It has special casing
    for the two introspection fields, `__schema` and `__typename`. `__typename` is
    special because it can always be queried as a field, even in situations where no
    other fields are allowed, like on a Union. `__schema` could get automatically
    added to the query type, but that would require mutating type definitions, which
    would cause issues.
    """
    if field_name == "__schema" and schema.query_type == parent_type:
        return SchemaMetaFieldDef
    elif field_name == "__type" and schema.query_type == parent_type:
        return TypeMetaFieldDef
    elif field_name == "__typename":
        return TypeNameMetaFieldDef
    return parent_type.fields.get(field_name)


def get_field_entry_key(node: FieldNode) -> str:
    """Implements the logic to compute the key of a given field's entry"""
    return node.alias.value if node.alias else node.name.value


def invalid_return_type_error(
    return_type: GraphQLObjectType, result: Any, field_nodes: List[FieldNode]
) -> GraphQLError:
    """Create a GraphQLError for an invalid return type."""
    return GraphQLError(
        f"Expected value of type '{return_type.name}' but got: {inspect(result)}.",
        field_nodes,
    )


def default_type_resolver(
    value: Any, info: GraphQLResolveInfo, abstract_type: GraphQLAbstractType
) -> AwaitableOrValue[Optional[Union[GraphQLObjectType, str]]]:
    """Default type resolver function.

    If a resolve_type function is not given, then a default resolve behavior is used
    which attempts two strategies:

    First, See if the provided value has a `__typename` field defined, if so, use that
    value as name of the resolved type.

    Otherwise, test each possible type for the abstract type by calling `is_type_of`
    for the object being coerced, returning the first type that matches.
    """
    # First, look for `__typename`.
    type_name = (
        value.get("__typename")
        if isinstance(value, dict)
        # need to de-mangle the attribute assumed to be "private" in Python
        else getattr(value, f"_{value.__class__.__name__}__typename", None)
    )
    if isinstance(type_name, str):
        return type_name

    # Otherwise, test each possible type.
    possible_types = info.schema.get_possible_types(abstract_type)
    awaitable_is_type_of_results: List[Awaitable] = []
    append_awaitable_results = awaitable_is_type_of_results.append
    awaitable_types: List[GraphQLObjectType] = []
    append_awaitable_types = awaitable_types.append

    for type_ in possible_types:
        if type_.is_type_of:
            is_type_of_result = type_.is_type_of(value, info)

            if isawaitable(is_type_of_result):
                append_awaitable_results(cast(Awaitable, is_type_of_result))
                append_awaitable_types(type_)
            elif is_type_of_result:
                return type_

    if awaitable_is_type_of_results:
        # noinspection PyShadowingNames
        async def get_type():
            is_type_of_results = await gather(*awaitable_is_type_of_results)
            for is_type_of_result, type_ in zip(is_type_of_results, awaitable_types):
                if is_type_of_result:
                    return type_

        return get_type()

    return None


def default_field_resolver(source, info, **args):
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
        if isinstance(source, dict)
        else getattr(source, field_name, None)
    )
    if callable(value):
        return value(info, **args)
    return value
