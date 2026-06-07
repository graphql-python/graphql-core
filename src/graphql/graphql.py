"""Execute a GraphQL operation"""

from __future__ import annotations

from asyncio import ensure_future
from typing import TYPE_CHECKING, Any, cast

from .error import GraphQLError
from .execution import ExecutionResult, Executor, Middleware
from .harness import GraphQLHarness, default_harness
from .pyutils.is_awaitable import is_awaitable as default_is_awaitable
from .type import (
    GraphQLFieldResolver,
    GraphQLSchema,
    GraphQLTypeResolver,
    validate_schema,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable, Callable, Collection
    from typing import TypeGuard

    from .language import DocumentNode, Source
    from .pyutils import AbortSignal, AwaitableOrValue
    from .validation import ASTValidationRule

__all__ = ["graphql", "graphql_sync"]


async def graphql(  # noqa: PLR0913
    schema: GraphQLSchema,
    source: str | Source,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: dict[str, Any] | None = None,
    operation_name: str | None = None,
    field_resolver: GraphQLFieldResolver | None = None,
    type_resolver: GraphQLTypeResolver | None = None,
    middleware: Middleware | None = None,
    executor_class: type[Executor] | None = None,
    is_awaitable: Callable[[Any], TypeGuard[Awaitable]] | None = None,
    is_async_iterable: Callable[[Any], TypeGuard[AsyncIterable]] | None = None,
    hide_suggestions: bool = False,
    abort_signal: AbortSignal | None = None,
    no_location: bool = False,
    max_tokens: int | None = None,
    experimental_fragment_arguments: bool = False,
    rules: Collection[type[ASTValidationRule]] | None = None,
    max_errors: int | None = None,
    harness: GraphQLHarness = default_harness,
) -> ExecutionResult:
    """Execute a GraphQL operation asynchronously.

    This is the primary entry point function for fulfilling GraphQL operations by
    parsing, validating, and executing a GraphQL document along side a GraphQL schema.

    More sophisticated GraphQL servers, such as those which persist queries, may wish
    to separate the validation and execution phases to a static time tooling step,
    and a server runtime step.

    This function does not support incremental delivery (`@defer` and `@stream`).

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
      ``__typename`` field or alternatively calls the
      :meth:`~graphql.type.GraphQLObjectType.is_type_of` method).
    :arg middleware:
      The middleware to wrap the resolvers with
    :arg executor_class:
      The executor class to use to build the executor
    :arg is_awaitable:
      The predicate to be used for checking whether values are awaitable
    :arg is_async_iterable:
      The predicate to be used for checking whether values are async iterables
    :arg abort_signal:
      A signal object that can be used to cancel execution, e.g. the signal of an
      :class:`~graphql.AbortController`
    :arg no_location:
      Parse option: do not include location information in the parsed document.
    :arg max_tokens:
      Parse option: the maximum number of tokens the document may contain.
    :arg experimental_fragment_arguments:
      Parse option: enable experimental support for fragment arguments.
    :arg rules:
      The validation rules to use when validating the query.
      If not provided, the specified rules are used.
    :arg max_errors:
      The maximum number of validation errors to report before stopping.
    :arg harness:
      A custom set of parse/validate/execute/subscribe functions to use when
      fulfilling the operation. Defaults to ``default_harness``.
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
        executor_class,
        is_awaitable,
        is_async_iterable,
        hide_suggestions,
        abort_signal,
        no_location,
        max_tokens,
        experimental_fragment_arguments,
        rules,
        max_errors,
        harness,
    )

    if default_is_awaitable(result):
        return await cast("Awaitable[ExecutionResult]", result)

    return cast("ExecutionResult", result)


def assume_not_awaitable(_value: Any) -> TypeGuard[Awaitable]:
    """Replacement for is_awaitable if everything is assumed to be synchronous."""
    return False


def assume_not_async_iterable(_value: Any) -> TypeGuard[AsyncIterable]:
    """Replacement for is_async_iterable if everything is assumed to be synchronous."""
    return False


def graphql_sync(  # noqa: PLR0913
    schema: GraphQLSchema,
    source: str | Source,
    root_value: Any = None,
    context_value: Any = None,
    variable_values: dict[str, Any] | None = None,
    operation_name: str | None = None,
    field_resolver: GraphQLFieldResolver | None = None,
    type_resolver: GraphQLTypeResolver | None = None,
    middleware: Middleware | None = None,
    executor_class: type[Executor] | None = None,
    check_sync: bool = False,
    hide_suggestions: bool = False,
    abort_signal: AbortSignal | None = None,
    no_location: bool = False,
    max_tokens: int | None = None,
    experimental_fragment_arguments: bool = False,
    rules: Collection[type[ASTValidationRule]] | None = None,
    max_errors: int | None = None,
    harness: GraphQLHarness = default_harness,
) -> ExecutionResult:
    """Execute a GraphQL operation synchronously.

    The graphql_sync function also fulfills GraphQL operations by parsing, validating,
    and executing a GraphQL document along side a GraphQL schema. However, it guarantees
    to complete synchronously (or throw an error) assuming that all field resolvers
    are also synchronous.

    Set check_sync to True to still run checks that no awaitable values are returned.
    """
    is_awaitable = (
        cast("Callable[[Any], TypeGuard[Awaitable]]", check_sync)
        if callable(check_sync)
        else (None if check_sync else assume_not_awaitable)
    )
    is_async_iterable = assume_not_async_iterable if not check_sync else None
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
        executor_class,
        is_awaitable,
        is_async_iterable,
        hide_suggestions,
        abort_signal,
        no_location,
        max_tokens,
        experimental_fragment_arguments,
        rules,
        max_errors,
        harness,
    )

    # Assert that the execution was synchronous.
    if default_is_awaitable(result):
        ensure_future(result).cancel()
        msg = "GraphQL execution failed to complete synchronously."
        raise RuntimeError(msg)

    return cast("ExecutionResult", result)


def graphql_impl(  # noqa: PLR0913
    schema: GraphQLSchema,
    source: str | Source,
    root_value: Any,
    context_value: Any,
    variable_values: dict[str, Any] | None,
    operation_name: str | None,
    field_resolver: GraphQLFieldResolver | None,
    type_resolver: GraphQLTypeResolver | None,
    middleware: Middleware | None,
    executor_class: type[Executor] | None,
    is_awaitable: Callable[[Any], TypeGuard[Awaitable]] | None,
    is_async_iterable: Callable[[Any], TypeGuard[AsyncIterable]] | None = None,
    hide_suggestions: bool = False,
    abort_signal: AbortSignal | None = None,
    no_location: bool = False,
    max_tokens: int | None = None,
    experimental_fragment_arguments: bool = False,
    rules: Collection[type[ASTValidationRule]] | None = None,
    max_errors: int | None = None,
    harness: GraphQLHarness = default_harness,
) -> AwaitableOrValue[ExecutionResult]:
    """Execute a query, return asynchronously only if necessary."""
    # Validate Schema
    if schema_validation_errors := validate_schema(schema):
        return ExecutionResult(data=None, errors=schema_validation_errors)

    def check_validation_and_execute(
        validation_errors: list[GraphQLError], document: DocumentNode
    ) -> AwaitableOrValue[ExecutionResult]:
        if validation_errors:
            return ExecutionResult(data=None, errors=validation_errors)

        # Execute
        return harness.execute(
            schema,
            document,
            root_value,
            context_value,
            variable_values,
            operation_name,
            field_resolver,
            type_resolver,
            None,
            50,
            False,
            middleware,
            executor_class,
            is_awaitable,
            is_async_iterable,
            hide_suggestions=hide_suggestions,
            abort_signal=abort_signal,
        )

    def validate_and_execute(
        document: DocumentNode,
    ) -> AwaitableOrValue[ExecutionResult]:
        # Validate
        validation_result = harness.validate(
            schema, document, rules, max_errors, hide_suggestions=hide_suggestions
        )

        if default_is_awaitable(validation_result):

            async def await_validation() -> ExecutionResult:
                validation_errors = await cast(
                    "Awaitable[list[GraphQLError]]", validation_result
                )
                result = check_validation_and_execute(validation_errors, document)
                if default_is_awaitable(result):
                    return await cast("Awaitable[ExecutionResult]", result)
                return cast("ExecutionResult", result)

            return await_validation()

        return check_validation_and_execute(
            cast("list[GraphQLError]", validation_result), document
        )

    # Parse
    try:
        document = harness.parse(
            source,
            no_location=no_location,
            max_tokens=max_tokens,
            experimental_fragment_arguments=experimental_fragment_arguments,
        )
    except GraphQLError as error:
        return ExecutionResult(data=None, errors=[error])

    if default_is_awaitable(document):

        async def await_document() -> ExecutionResult:
            try:
                resolved_document = await cast("Awaitable[DocumentNode]", document)
            except GraphQLError as error:
                return ExecutionResult(data=None, errors=[error])
            result = validate_and_execute(resolved_document)
            if default_is_awaitable(result):
                return await cast("Awaitable[ExecutionResult]", result)
            return cast("ExecutionResult", result)

        return await_document()

    return validate_and_execute(cast("DocumentNode", document))
