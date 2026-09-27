"""Execute a GraphQL operation"""

from __future__ import annotations

from inspect import iscoroutine
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


async def graphql(  # noqa: PLR0913, PLR0917
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

    Parses, validates, and executes a GraphQL document against a schema.

    This is the primary entry point for fulfilling GraphQL operations. Use this
    when you want a single-call request lifecycle that always needs to be awaited.

    More sophisticated GraphQL servers, such as those which persist queries, may
    wish to separate the validation and execution phases to a static-time tooling
    step and a server runtime step.

    This function does not support incremental delivery (``@defer`` and
    ``@stream``); use :func:`~graphql.execution.experimental_execute_incrementally`
    after parsing and validating when incremental delivery is required.

    :param schema: The schema used for validation or execution.
    :param source: A GraphQL language-formatted string or source object representing
        the requested operation.
    :param root_value: Initial root value passed to the operation.
    :param context_value: Application context value passed to every resolver.
        It is made available as the ``context`` attribute of the resolve info.
    :param variable_values: Runtime variable values keyed by variable name.
    :param operation_name: Name of the operation to execute when the document
        contains multiple operations.
    :param field_resolver: Resolver used when a field does not define its own
        resolver.
    :param type_resolver: Resolver used when an abstract type does not define its own
        resolver.
    :param middleware: The middleware to wrap the resolvers with.
    :param executor_class: The executor class to use to build the executor.
    :param is_awaitable: The predicate to be used for checking whether values are
        awaitable.
    :param is_async_iterable: The predicate to be used for checking whether values
        are async iterables.
    :param hide_suggestions: Whether suggestion text should be omitted from request
        errors.
    :param abort_signal: AbortSignal used to cancel execution, e.g. the signal of an
        :class:`~graphql.AbortController`.
    :param no_location: By default, the parser creates AST nodes that know the
        location in the source that they correspond to. Setting this parameter to
        ``True`` disables that behavior for performance or testing.
    :param max_tokens: The maximum number of tokens allowed within the document,
        to limit the CPU time and memory the parser can burn.
    :param experimental_fragment_arguments: Allows fragment variable definitions
        and arguments on fragment spreads to be parsed (experimental).
    :param rules: Validation rules to use instead of the specified rules.
    :param max_errors: Maximum number of validation errors before validation stops.
    :param harness: Custom parse, validate, execute, and subscribe functions for this
        request pipeline. Defaults to ``default_harness``.
    :returns: An execution result or validation errors.

    Execute a complete asynchronous request with variables:

    >>> import asyncio
    >>> from graphql import graphql, build_schema
    >>> schema = build_schema('''
    ...   type Query {
    ...     greeting(name: String!): String
    ...   }
    ... ''')
    >>> result = asyncio.run(graphql(
    ...     schema,
    ...     'query SayHello($name: String!) { greeting(name: $name) }',
    ...     root_value={'greeting': lambda _info, name: f'Hello, {name}!'},
    ...     variable_values={'name': 'Ada'},
    ...     operation_name='SayHello',
    ... ))
    >>> result
    ExecutionResult(data={'greeting': 'Hello, Ada!'}, errors=None)

    This variant supplies context plus custom field and type resolvers:

    >>> schema = build_schema('''
    ...   interface Named {
    ...     name: String!
    ...   }
    ...
    ...   type User implements Named {
    ...     name: String!
    ...   }
    ...
    ...   type Query {
    ...     viewer: Named
    ...   }
    ... ''')
    >>> def field_resolver(source, info, **_args):
    ...     assert info.context['locale'] == 'en'
    ...     return source[info.field_name]
    >>> def type_resolver(value, _info, _abstract_type):
    ...     return 'User' if value['kind'] == 'user' else None
    >>> result = asyncio.run(graphql(
    ...     schema,
    ...     '{ viewer { __typename name } }',
    ...     root_value={'viewer': {'kind': 'user', 'name': 'Ada'}},
    ...     context_value={'locale': 'en'},
    ...     field_resolver=field_resolver,
    ...     type_resolver=type_resolver,
    ... ))
    >>> result
    ExecutionResult(data={'viewer': {'__typename': 'User', 'name': 'Ada'}}, errors=None)

    This variant customizes the request pipeline with a harness:

    >>> from graphql import AbortController
    >>> from graphql.harness import default_harness
    >>> schema = build_schema('''
    ...   type Query {
    ...     greeting: String
    ...   }
    ... ''')
    >>> stages = []
    >>> def record_stage(stage):
    ...     def stage_fn(*args, **kwargs):
    ...         stages.append(stage)
    ...         return getattr(default_harness, stage)(*args, **kwargs)
    ...     return stage_fn
    >>> harness = default_harness._replace(
    ...     parse=record_stage('parse'),
    ...     validate=record_stage('validate'),
    ...     execute=record_stage('execute'),
    ...     subscribe=record_stage('subscribe'),
    ... )
    >>> result = asyncio.run(graphql(
    ...     schema,
    ...     '{ greeting }',
    ...     root_value={'greeting': 'Hello'},
    ...     rules=[],
    ...     max_errors=25,
    ...     hide_suggestions=True,
    ...     no_location=True,
    ...     abort_signal=AbortController().signal,
    ...     harness=harness,
    ... ))
    >>> result
    ExecutionResult(data={'greeting': 'Hello'}, errors=None)
    >>> stages
    ['parse', 'validate', 'execute']
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
    """Replacement for isawaitable if everything is assumed to be synchronous.

    :meta private:
    """
    return False


def assume_not_async_iterable(_value: Any) -> TypeGuard[AsyncIterable]:
    """Replacement for is_async_iterable if everything is assumed to be synchronous.

    :meta private:
    """
    return False


def graphql_sync(  # noqa: PLR0913, PLR0917
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

    Parses, validates, and executes a GraphQL document synchronously.

    This function guarantees that execution completes synchronously, or raises an
    error, assuming that all field resolvers are also synchronous. It raises a
    :exc:`RuntimeError` when execution does not complete synchronously.

    :param schema: The schema used for validation or execution.
    :param source: A GraphQL language-formatted string or source object representing
        the requested operation.
    :param root_value: Initial root value passed to the operation.
    :param context_value: Application context value passed to every resolver.
        It is made available as the ``context`` attribute of the resolve info.
    :param variable_values: Runtime variable values keyed by variable name.
    :param operation_name: Name of the operation to execute when the document
        contains multiple operations.
    :param field_resolver: Resolver used when a field does not define its own
        resolver.
    :param type_resolver: Resolver used when an abstract type does not define its own
        resolver.
    :param middleware: The middleware to wrap the resolvers with.
    :param executor_class: The executor class to use to build the executor.
    :param check_sync: Set this to ``True`` to still run checks that no awaitable
        values are returned by resolvers. You can also pass a custom predicate for
        checking whether values are awaitable.
    :param hide_suggestions: Whether suggestion text should be omitted from request
        errors.
    :param abort_signal: AbortSignal used to cancel execution, e.g. the signal of an
        :class:`~graphql.AbortController`.
    :param no_location: By default, the parser creates AST nodes that know the
        location in the source that they correspond to. Setting this parameter to
        ``True`` disables that behavior for performance or testing.
    :param max_tokens: The maximum number of tokens allowed within the document,
        to limit the CPU time and memory the parser can burn.
    :param experimental_fragment_arguments: Allows fragment variable definitions
        and arguments on fragment spreads to be parsed (experimental).
    :param rules: Validation rules to use instead of the specified rules.
    :param max_errors: Maximum number of validation errors before validation stops.
    :param harness: Custom parse, validate, execute, and subscribe functions for this
        request pipeline. Defaults to ``default_harness``.
    :returns: Completed execution output, or request errors if parsing or
        validation fails.

    Execute a complete synchronous request with variables:

    >>> from graphql import graphql_sync, build_schema
    >>> schema = build_schema('''
    ...   type Query {
    ...     greeting(name: String!): String
    ...   }
    ... ''')
    >>> result = graphql_sync(
    ...     schema,
    ...     'query SayHello($name: String!) { greeting(name: $name) }',
    ...     root_value={'greeting': lambda _info, name: f'Hello, {name}!'},
    ...     variable_values={'name': 'Ada'},
    ...     operation_name='SayHello',
    ... )
    >>> result
    ExecutionResult(data={'greeting': 'Hello, Ada!'}, errors=None)

    This variant uses a synchronous custom field resolver and context:

    >>> schema = build_schema('''
    ...   type Query {
    ...     greeting: String
    ...   }
    ... ''')
    >>> result = graphql_sync(
    ...     schema,
    ...     '{ greeting }',
    ...     field_resolver=lambda _source, info, **_args: (
    ...         info.context['default_greeting']
    ...     ),
    ...     context_value={'default_greeting': 'Hello'},
    ... )
    >>> result
    ExecutionResult(data={'greeting': 'Hello'}, errors=None)
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
        if iscoroutine(result):  # pragma: no branch
            # close the coroutine to avoid a "was never awaited" warning
            result.close()
        msg = "GraphQL execution failed to complete synchronously."
        raise RuntimeError(msg)

    return cast("ExecutionResult", result)


def graphql_impl(  # noqa: PLR0913, PLR0917
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
    """Execute a query, return asynchronously only if necessary.

    :meta private:
    """
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
