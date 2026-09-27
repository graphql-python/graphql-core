"""Helpers for handling values"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple, TypeAlias

from ..error import GraphQLError
from ..language import (
    DirectiveDefinitionNode,
    DirectiveExtensionNode,
    DirectiveNode,
    EnumValueDefinitionNode,
    ExecutableDefinitionNode,
    FieldDefinitionNode,
    FieldNode,
    FragmentSpreadNode,
    InputValueDefinitionNode,
    SchemaDefinitionNode,
    SelectionNode,
    TypeDefinitionNode,
    TypeExtensionNode,
    VariableDefinitionNode,
    VariableNode,
)
from ..pyutils import Undefined, print_path_list
from ..type import (
    GraphQLDirective,
    GraphQLField,
    GraphQLSchema,
    is_non_null_type,
    is_required_argument,
)
from ..type.validate import validate_default_input
from ..utilities.coerce_input_value import (
    coerce_default_value,
    coerce_input_literal,
    coerce_input_value,
)
from ..utilities.validate_input_value import (
    validate_input_literal,
    validate_input_value,
)
from .get_variable_signature import GraphQLVariableSignature, get_variable_signature

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping

    from ..language import ArgumentNode, FragmentArgumentNode
    from ..type import GraphQLArgument

__all__ = [
    "FragmentVariableValueSource",
    "FragmentVariableValues",
    "VariableValueSource",
    "VariableValues",
    "get_argument_values",
    "get_directive_values",
    "get_fragment_variable_values",
    "get_variable_values",
]


class VariableValueSource(NamedTuple):
    """The signature of a variable and its original input value."""

    signature: GraphQLVariableSignature
    value: Any = Undefined


class VariableValues(NamedTuple):
    """The coerced values of the variables and their original sources.

    Coerced variable values prepared for execution.

    The ``coerced`` dict contains runtime values keyed by variable name. The
    ``sources`` dict records whether each value came from request input, an
    operation default, or a fragment-variable default so utilities can preserve
    defaults when replacing variables in literals.
    """

    sources: dict[str, VariableValueSource]
    """Source metadata for each variable value keyed by variable name."""

    coerced: dict[str, Any]
    """Coerced runtime variable values keyed by variable name."""


class FragmentVariableValueSource(NamedTuple):
    """A fragment variable signature with the source value from its spread."""

    signature: GraphQLVariableSignature
    value: Any = Undefined
    fragment_variable_values: FragmentVariableValues | None = None


class FragmentVariableValues(NamedTuple):
    """The coerced values of fragment variables and their original sources."""

    sources: dict[str, FragmentVariableValueSource]
    coerced: dict[str, Any]


VariableValuesOrErrors: TypeAlias = list[GraphQLError] | VariableValues


def get_variable_values(
    schema: GraphQLSchema,
    var_def_nodes: Collection[VariableDefinitionNode],
    inputs: dict[str, Any],
    max_errors: int | None = None,
    hide_suggestions: bool = False,
) -> VariableValuesOrErrors:
    """Get coerced variable values based on provided definitions.

    Prepares a dict of variable values of the correct type based on the provided
    variable definitions and arbitrary input. If the input cannot be parsed to match
    the variable definitions, a list of GraphQLErrors will be returned instead.

    :param schema: GraphQL schema to use.
    :param var_def_nodes: The variable definition AST nodes to coerce.
    :param inputs: The runtime variable values keyed by variable name.
    :param max_errors: Maximum number of coercion errors to report (unlimited by
        default). When the limit is exceeded, an additional error is added and
        coercion is aborted.
    :param hide_suggestions: Whether suggestion text should be omitted from errors.
    :returns: Coerced variable values with source metadata, or request errors.

    Coerce provided variables and apply operation defaults:

    >>> from graphql import build_schema, get_variable_values, parse
    >>> schema = build_schema('''
    ...     type Query {
    ...       reviews(stars: Int!, limit: Int = 10): [String]
    ...     }
    ... ''')
    >>> document = parse('''
    ...     query ($stars: Int!, $limit: Int = 10) {
    ...       reviews(stars: $stars, limit: $limit)
    ...     }
    ... ''')
    >>> operation = document.definitions[0]
    >>> result = get_variable_values(
    ...     schema, operation.variable_definitions, {'stars': 5}
    ... )
    >>> result.coerced
    {'stars': 5, 'limit': 10}

    This variant uses ``max_errors`` to cap reported coercion errors:

    >>> schema = build_schema('''
    ...     input ReviewInput {
    ...       stars: Int!
    ...     }
    ...
    ...     type Query {
    ...       review(input: ReviewInput!): String
    ...     }
    ... ''')
    >>> document = parse('''
    ...     query ($first: ReviewInput!, $second: ReviewInput!) {
    ...       first: review(input: $first)
    ...       second: review(input: $second)
    ...     }
    ... ''')
    >>> operation = document.definitions[0]
    >>> errors = get_variable_values(
    ...     schema,
    ...     operation.variable_definitions,
    ...     {'first': {'stars': 'bad'}, 'second': {'stars': 'also bad'}},
    ...     max_errors=1,
    ... )
    >>> len(errors)
    2
    >>> errors[1].message
    'Too many errors processing variables, error limit reached. Execution aborted.'
    """
    errors: list[GraphQLError] = []

    def on_error(error: GraphQLError) -> None:
        if max_errors is not None and len(errors) >= max_errors:
            msg = (
                "Too many errors processing variables,"
                " error limit reached. Execution aborted."
            )
            raise GraphQLError(msg)
        errors.append(error)

    try:
        variable_values = coerce_variable_values(
            schema, var_def_nodes, inputs, on_error, hide_suggestions
        )
        if not errors:
            return variable_values
    except GraphQLError as e:
        errors.append(e)

    return errors


def coerce_variable_values(
    schema: GraphQLSchema,
    var_def_nodes: Collection[VariableDefinitionNode],
    inputs: dict[str, Any],
    on_error: Callable[[GraphQLError], None],
    hide_suggestions: bool = False,
) -> VariableValues:
    """Coerce the variable values, reporting errors via the given callback.

    :meta private:
    """
    sources: dict[str, VariableValueSource] = {}
    coerced: dict[str, Any] = {}
    for var_def_node in var_def_nodes:
        var_signature = get_variable_signature(schema, var_def_node)
        if isinstance(var_signature, GraphQLError):
            on_error(var_signature)
            continue

        var_name = var_signature.name
        var_type = var_signature.type
        value = inputs.get(var_name, Undefined)
        if value is Undefined:
            sources[var_name] = VariableValueSource(var_signature)
            if var_def_node.default_value:

                def on_default_value_error(
                    error: GraphQLError,
                    path: list[str | int],
                    var_name: str = var_name,
                    var_def_node: VariableDefinitionNode = var_def_node,
                ) -> None:
                    on_error(
                        GraphQLError(
                            f"Variable '${var_name}' has invalid default value"
                            f"{print_path_list(path)}: {error.message}",
                            var_def_node,
                        )
                    )

                maybe_use_default_value(
                    coerced,
                    var_name,
                    var_signature,
                    on_default_value_error,
                    hide_suggestions,
                )
                continue
            if not is_non_null_type(var_type):
                # Non-provided values for nullable variables are omitted.
                continue
        else:
            sources[var_name] = VariableValueSource(var_signature, value)

        coerced_value = coerce_input_value(value, var_type)
        if coerced_value is not Undefined:
            coerced[var_name] = coerced_value
        else:

            def on_input_value_error(
                error: GraphQLError,
                path: list[str | int],
                var_name: str = var_name,
                var_def_node: VariableDefinitionNode = var_def_node,
            ) -> None:
                on_error(
                    GraphQLError(
                        f"Variable '${var_name}' has invalid value"
                        f"{print_path_list(path)}: {error.message}",
                        var_def_node,
                        original_error=error,
                    )
                )

            validate_input_value(
                value, var_type, on_input_value_error, hide_suggestions
            )

    return VariableValues(sources, coerced)


def maybe_use_default_value(
    coerced_values: dict[str, Any],
    name: str,
    input_value: GraphQLArgument | GraphQLVariableSignature,
    on_error: Callable[[GraphQLError, list[str | int]], None],
    hide_suggestions: bool = False,
) -> None:
    """Use the default value of the given input value definition, if it exists."""
    try:
        # coerce_default_value() assumes validation has already rejected invalid
        # defaults. If validation was skipped, invalid defaults or nested input
        # field defaults can raise here; recover with validation-style errors below.
        coerced_default_value = coerce_default_value(input_value)
        if coerced_default_value is not Undefined:
            coerced_values[name] = coerced_default_value
    except TypeError as error:
        default_input = input_value.default
        # Defensive: coerce_default_value() should only raise
        # while coercing a default.
        if default_input is None:  # pragma: no cover
            raise

        # Prefer validation's user-facing errors for invalid defaults.
        reported_validation_error = False

        def on_default_input_error(
            default_error: GraphQLError, path: list[str | int]
        ) -> None:
            nonlocal reported_validation_error
            reported_validation_error = True
            on_error(default_error, path)

        validate_default_input(
            default_input, input_value.type, on_default_input_error, hide_suggestions
        )

        if not reported_validation_error:
            # The default itself validated, so coercion failed while applying
            # a nested input field default. Surface the original coercion error.
            on_error(GraphQLError(str(error), original_error=error), [])


def get_fragment_variable_values(
    fragment_spread_node: FragmentSpreadNode,
    fragment_signatures: Mapping[str, GraphQLVariableSignature],
    variable_values: VariableValues,
    fragment_variable_values: FragmentVariableValues | None = None,
    hide_suggestions: bool = False,
) -> FragmentVariableValues:
    """Get coerced variable values for a fragment spread.

    Prepares the variable values for a fragment spread, preserving the original
    sources of the variable values alongside the coerced values.

    :meta private:
    """
    arg_node_map = {arg.name.value: arg for arg in fragment_spread_node.arguments or []}
    sources: dict[str, FragmentVariableValueSource] = {}
    coerced: dict[str, Any] = {}
    for var_name, var_signature in fragment_signatures.items():
        argument_node = arg_node_map.get(var_name)
        if argument_node is None:
            sources[var_name] = FragmentVariableValueSource(var_signature)
        else:
            sources[var_name] = FragmentVariableValueSource(
                var_signature, argument_node.value, fragment_variable_values
            )

        coerce_argument(
            coerced,
            fragment_spread_node,
            var_name,
            var_signature,
            argument_node,
            variable_values,
            fragment_variable_values,
            hide_suggestions,
        )

    return FragmentVariableValues(sources, coerced)


def get_argument_values(
    type_def: GraphQLField | GraphQLDirective,
    node: FieldNode | DirectiveNode,
    variable_values: VariableValues | None = None,
    fragment_variable_values: FragmentVariableValues | None = None,
    hide_suggestions: bool = False,
) -> dict[str, Any]:
    """Get coerced argument values based on provided definitions and nodes.

    Prepares a dict of argument values given a list of argument definitions and list
    of argument AST nodes.

    :param type_def: Field or directive definition that declares the arguments.
    :param node: Field or directive AST node supplying argument literals.
    :param variable_values: Operation variable values returned by
        :func:`get_variable_values`.
    :param fragment_variable_values: Fragment variable values for the current
        fragment scope.
    :param hide_suggestions: Whether suggestion text should be omitted from errors.
    :returns: A dict of coerced argument values.

    Read literal argument values and defaults:

    >>> from graphql import build_schema, get_argument_values, parse
    >>> schema = build_schema('''
    ...     type Query {
    ...       reviews(stars: Int!, limit: Int = 10): [String]
    ...     }
    ... ''')
    >>> field_def = schema.query_type.fields['reviews']
    >>> document = parse('{ reviews(stars: 5) }')
    >>> field_node = document.definitions[0].selection_set.selections[0]
    >>> get_argument_values(field_def, field_node)
    {'stars': 5, 'limit': 10}

    This variant resolves argument values from operation variables:

    >>> from graphql import get_variable_values
    >>> schema = build_schema('''
    ...     type Query {
    ...       reviews(stars: Int!): [String]
    ...     }
    ... ''')
    >>> field_def = schema.query_type.fields['reviews']
    >>> document = parse('query ($stars: Int!) { reviews(stars: $stars) }')
    >>> operation = document.definitions[0]
    >>> field_node = operation.selection_set.selections[0]
    >>> variables = get_variable_values(
    ...     schema, operation.variable_definitions, {'stars': 5}
    ... )
    >>> get_argument_values(field_def, field_node, variables)
    {'stars': 5}
    >>> get_argument_values(field_def, field_node)
    Traceback (most recent call last):
    ...
    graphql.error.graphql_error.GraphQLError: Invalid argument
    ...
    """
    coerced_values: dict[str, Any] = {}
    arg_node_map = {arg.name.value: arg for arg in node.arguments or []}

    for name, arg_def in type_def.args.items():
        coerce_argument(
            coerced_values,
            node,
            name,
            arg_def,
            arg_node_map.get(name),
            variable_values,
            fragment_variable_values,
            hide_suggestions,
        )
    return coerced_values


def coerce_argument(
    coerced_values: dict[str, Any],
    node: FieldNode | DirectiveNode | FragmentSpreadNode,
    arg_name: str,
    arg_def: GraphQLArgument | GraphQLVariableSignature,
    argument_node: ArgumentNode | FragmentArgumentNode | None,
    variable_values: VariableValues | None,
    fragment_variable_values: FragmentVariableValues | None,
    hide_suggestions: bool = False,
) -> None:
    """Coerce a single argument value into the given coerced values mapping."""
    arg_type = arg_def.type
    out_name = getattr(arg_def, "out_name", None) or arg_name

    def on_arg_default_value_error(error: GraphQLError, path: list[str | int]) -> None:
        msg = (
            f"{print_argument_or_fragment_variable(arg_def, arg_name, node)}"
            f" has invalid default value{print_path_list(path)}: {error.message}"
        )
        raise GraphQLError(msg, node)

    if argument_node is None:
        if is_required_argument(arg_def):
            # Note: ProvidedRequiredArgumentsRule validation should catch this
            # before execution. This is a runtime check to ensure execution does
            # not continue with an invalid argument value.
            msg = (
                f"{print_argument_or_fragment_variable(arg_def, arg_name, node)}"
                f" of required type '{arg_type}' was not provided."
            )
            raise GraphQLError(msg, node)
        maybe_use_default_value(
            coerced_values,
            out_name,
            arg_def,
            on_arg_default_value_error,
            hide_suggestions,
        )
        return

    value_node = argument_node.value

    # Variables without a value are treated as if no argument was provided if
    # the argument is not required.
    if isinstance(value_node, VariableNode):
        variable_name = value_node.name.value
        scoped_variable_values = (
            fragment_variable_values
            if fragment_variable_values
            and variable_name in fragment_variable_values.sources
            else variable_values
        )
        if (
            scoped_variable_values is None
            or variable_name not in scoped_variable_values.coerced
        ) and not is_required_argument(arg_def):
            maybe_use_default_value(
                coerced_values,
                out_name,
                arg_def,
                on_arg_default_value_error,
                hide_suggestions,
            )
            return

    coerced_value = coerce_input_literal(
        value_node,
        arg_type,
        variable_values,
        fragment_variable_values,
    )
    if coerced_value is Undefined:
        # Note: `values_of_correct_type` validation should catch this before
        # execution. This is a runtime check to ensure execution does not
        # continue with an invalid argument value.
        def on_argument_value_error(
            error: GraphQLError,
            path: list[str | int],
        ) -> None:
            error.message = (
                f"{print_argument_or_fragment_variable(arg_def, arg_name, node)}"
                f" has invalid value{print_path_list(path)}: {error.message}"
            )
            raise error

        validate_input_literal(
            value_node,
            arg_type,
            on_argument_value_error,
            variable_values,
            fragment_variable_values,
            hide_suggestions,
        )
        # Unreachable: validate_input_literal always reports an error here.
        msg = "Invalid argument"  # pragma: no cover
        raise GraphQLError(msg, value_node)  # pragma: no cover
    coerced_values[out_name] = coerced_value


# TODO: clean up the naming of is_required_argument() and arg_def
# if/when experimental fragment variables are merged
def print_argument_or_fragment_variable(
    arg_def: GraphQLArgument | GraphQLVariableSignature,
    arg_name: str,
    node: FieldNode | DirectiveNode | FragmentSpreadNode,
) -> str:
    """Describe an argument or fragment variable for use in error messages."""
    if isinstance(arg_def, GraphQLVariableSignature):
        return f"Variable '${arg_def.name}' defined by fragment '{node.name.value}'"
    return f"Argument '{arg_name}'"


NodeWithDirective: TypeAlias = (
    DirectiveDefinitionNode
    | DirectiveExtensionNode
    | EnumValueDefinitionNode
    | ExecutableDefinitionNode
    | FieldDefinitionNode
    | InputValueDefinitionNode
    | SelectionNode
    | SchemaDefinitionNode
    | TypeDefinitionNode
    | TypeExtensionNode
)


def get_directive_values(
    directive_def: GraphQLDirective,
    node: NodeWithDirective,
    variable_values: VariableValues | None = None,
    fragment_variable_values: FragmentVariableValues | None = None,
    hide_suggestions: bool = False,
) -> dict[str, Any] | None:
    """Get coerced argument values based on provided nodes.

    Prepares a dict of argument values given a directive definition and an AST node
    which may contain directives. Optionally also accepts the variable values.

    If the directive does not exist on the node, returns None.

    :param directive_def: Directive definition to read argument definitions from.
    :param node: AST node that may contain directives.
    :param variable_values: Operation variable values returned by
        :func:`get_variable_values`.
    :param fragment_variable_values: Fragment variable values for the current
        fragment scope.
    :param hide_suggestions: Whether suggestion text should be omitted from errors.
    :returns: A dict of coerced directive argument values, or None when absent.

    Read literal directive arguments from a node:

    >>> from graphql import GraphQLSkipDirective, get_directive_values, parse
    >>> document = parse('{ name @skip(if: true) }')
    >>> field_node = document.definitions[0].selection_set.selections[0]
    >>> get_directive_values(GraphQLSkipDirective, field_node)
    {'if': True}

    This variant resolves directive arguments from variables and handles absent
    directives:

    >>> from graphql import GraphQLIncludeDirective, build_schema, get_variable_values
    >>> schema = build_schema('type Query { name: String }')
    >>> document = parse(
    ...     'query ($includeName: Boolean!) { name @include(if: $includeName) }'
    ... )
    >>> operation = document.definitions[0]
    >>> field_node = operation.selection_set.selections[0]
    >>> variables = get_variable_values(
    ...     schema, operation.variable_definitions, {'includeName': False}
    ... )
    >>> get_directive_values(GraphQLIncludeDirective, field_node, variables)
    {'if': False}
    >>> field_node = parse('{ name }').definitions[0].selection_set.selections[0]
    >>> get_directive_values(GraphQLIncludeDirective, field_node) is None
    True
    """
    directives = node.directives
    if directives:
        directive_name = directive_def.name
        for directive in directives:
            if directive.name.value == directive_name:
                return get_argument_values(
                    directive_def,
                    directive,
                    variable_values,
                    fragment_variable_values,
                    hide_suggestions,
                )
    return None
