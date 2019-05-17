from asyncio import ensure_future
from inspect import isawaitable
from typing import Any, Awaitable, Dict, Union, Type, cast

from .error import GraphQLError
from .execution import execute, ExecutionResult, ExecutionContext, Middleware
from .language import parse, Source
from .pyutils import AwaitableOrValue
from .type import (
    GraphQLFieldResolver,
    GraphQLSchema,
    GraphQLTypeResolver,
    validate_schema,
)

__all__ = ["graphql", "graphql_sync"]


async def graphql(
    schema: GraphQLSchema,
    source: Union[str, Source],
    root_value: Any = None,
    context_value: Any = None,
    variable_values: Dict[str, Any] = None,
    operation_name: str = None,
    field_resolver: GraphQLFieldResolver = None,
    type_resolver: GraphQLTypeResolver = None,
    middleware: Middleware = None,
    execution_context_class: Type[ExecutionContext] = ExecutionContext,
) -> ExecutionResult:
    """Execute a GraphQL operation asynchronously.

    This is the primary entry point function for fulfilling GraphQL operations by
    parsing, validating, and executing a GraphQL document along side a GraphQL schema.

    More sophisticated GraphQL servers, such as those which persist queries, may wish
    to separate the validation and execution phases to a static time tooling step,
    and a server runtime step.

    Accepts the following arguments:

    :arg schema:
      The GraphQL type system to use when validating and executing a query.
    :arg source:
      A GraphQL language formatted string representing the requested operation.
    :arg root_value:
      The value provided as the first argument to resolver functions on the top level
      type (e.g. the query object type).
    :arg context_value:
      The context value is provided as an attribute of the second argument
      (the resolve info) to resolver functions. It is used to pass shared information
      useful at any point during query execution, for example the currently logged in
      user and connections to databases or other services.
    :arg variable_values:
      A mapping of variable name to runtime value to use for all variables defined
      in the request string.
    :arg operation_name:
      The name of the operation to use if request string contains multiple possible
      operations. Can be omitted if request string contains only one operation.
    :arg field_resolver:
      A resolver function to use when one is not provided by the schema.
      If not provided, the default field resolver is used (which looks for a value
      or method on the source value with the field's name).
    :arg type_resolver:
      A type resolver function to use when none is provided by the schema.
      If not provided, the default type resolver is used (which looks for a
      `__typename` field or alternatively calls the `is_type_of` method).
    :arg middleware:
      The middleware to wrap the resolvers with
    :arg execution_context_class:
      The execution context class to use to build the context
    """
    # Always return asynchronously for a consistent API.
    result = graphql_impl(
        schema,
        source,
        root_value,
        context_value,
        variable_values,
        operation_name,
        field_resolver,
        type_resolver,
        middleware,
        execution_context_class,
    )

    if isawaitable(result):
        return await cast(Awaitable[ExecutionResult], result)

    return cast(ExecutionResult, result)


def graphql_sync(
    schema: GraphQLSchema,
    source: Union[str, Source],
    root_value: Any = None,
    context_value: Any = None,
    variable_values: Dict[str, Any] = None,
    operation_name: str = None,
    field_resolver: GraphQLFieldResolver = None,
    type_resolver: GraphQLTypeResolver = None,
    middleware: Middleware = None,
    execution_context_class: Type[ExecutionContext] = ExecutionContext,
) -> ExecutionResult:
    """Execute a GraphQL operation synchronously.

    The graphql_sync function also fulfills GraphQL operations by parsing, validating,
    and executing a GraphQL document along side a GraphQL schema. However, it guarantees
    to complete synchronously (or throw an error) assuming that all field resolvers
    are also synchronous.
    """
    result = graphql_impl(
        schema,
        source,
        root_value,
        context_value,
        variable_values,
        operation_name,
        field_resolver,
        type_resolver,
        middleware,
        execution_context_class,
    )

    # Assert that the execution was synchronous.
    if isawaitable(result):
        ensure_future(cast(Awaitable[ExecutionResult], result)).cancel()
        raise RuntimeError("GraphQL execution failed to complete synchronously.")

    return cast(ExecutionResult, result)


def graphql_impl(
    schema,
    source,
    root_value,
    context_value,
    variable_values,
    operation_name,
    field_resolver,
    type_resolver,
    middleware,
    execution_context_class,
) -> AwaitableOrValue[ExecutionResult]:
    """Execute a query, return asynchronously only if necessary."""
    # Validate Schema
    schema_validation_errors = validate_schema(schema)
    if schema_validation_errors:
        return ExecutionResult(data=None, errors=schema_validation_errors)

    # Parse
    try:
        document = parse(source)
    except GraphQLError as error:
        return ExecutionResult(data=None, errors=[error])
    except Exception as error:
        error = GraphQLError(str(error), original_error=error)
        return ExecutionResult(data=None, errors=[error])

    # Validate
    from .validation import validate

    validation_errors = validate(schema, document)
    if validation_errors:
        return ExecutionResult(data=None, errors=validation_errors)

    # Execute
    return execute(
        schema,
        document,
        root_value,
        context_value,
        variable_values,
        operation_name,
        field_resolver,
        type_resolver,
        middleware,
        execution_context_class,
    )
