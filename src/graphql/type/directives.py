"""GraphQL directives"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict, TypeGuard, cast

from ..language import DirectiveLocation, ast
from ..pyutils import inspect
from .assert_name import assert_name
from .definition import (
    GraphQLArgument,
    GraphQLDefaultInput,
    GraphQLInputType,
    GraphQLNonNull,
)
from .scalars import GraphQLBoolean, GraphQLInt, GraphQLString

if TYPE_CHECKING:
    from collections.abc import Collection

__all__ = [
    "DEFAULT_DEPRECATION_REASON",
    "DirectiveLocation",
    "GraphQLDeferDirective",
    "GraphQLDeprecatedDirective",
    "GraphQLDirective",
    "GraphQLDirectiveKwargs",
    "GraphQLIncludeDirective",
    "GraphQLOneOfDirective",
    "GraphQLSkipDirective",
    "GraphQLSpecifiedByDirective",
    "GraphQLStreamDirective",
    "assert_directive",
    "is_directive",
    "is_specified_directive",
    "specified_directives",
]


class GraphQLDirectiveKwargs(TypedDict, total=False):
    """Arguments for GraphQL directives"""

    name: str
    """The GraphQL name for this schema element."""
    locations: tuple[DirectiveLocation, ...]
    """Locations where this directive may be applied."""
    args: dict[str, GraphQLArgument]
    """Arguments accepted by this directive."""
    is_repeatable: bool
    """Whether this directive may appear more than once at the same location."""
    deprecation_reason: str | None
    """Reason this element is deprecated, if one was provided."""
    description: str | None
    """Human-readable description for this schema element, if provided."""
    extensions: dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: ast.DirectiveDefinitionNode | None
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: tuple[ast.DirectiveExtensionNode, ...]
    """AST extension nodes applied to this schema element."""


class GraphQLDirective:  # noqa: PLW1641
    """GraphQL Directive

    Directives are used by the GraphQL runtime as a way of modifying execution behavior.
    Type system creators will usually not create these directly.

    :param name: the GraphQL name for this directive
    :param locations: the locations where this directive may be applied, given as
        :class:`~graphql.language.DirectiveLocation` values or their names
    :param args: the arguments accepted by this directive, given as a dictionary
        mapping argument names to :class:`GraphQLArgument` instances or input types
    :param is_repeatable: whether this directive may appear more than once at the
        same location
    :param deprecation_reason: the reason this directive is deprecated, if any
    :param description: a human-readable description for this directive, if any
    :param extensions: custom extension fields reserved for users
    :param ast_node: the AST node from which this directive was built, if available
    :param extension_ast_nodes: the AST extension nodes applied to this directive

    >>> from graphql import (
    ...     DirectiveLocation,
    ...     GraphQLArgument,
    ...     GraphQLBoolean,
    ...     GraphQLDefaultInput,
    ...     GraphQLDirective,
    ...     GraphQLInt,
    ...     GraphQLNonNull,
    ...     parse,
    ... )
    >>> document = parse(
    ...     '''
    ...     directive @cacheControl(maxAge: Int) repeatable on FIELD_DEFINITION
    ...     extend directive @cacheControl @tag
    ...     ''',
    ... )
    >>> definition = document.definitions[0]
    >>> cache_control = GraphQLDirective(
    ...     name='cacheControl',
    ...     description='Controls HTTP cache hints for a field.',
    ...     locations=[DirectiveLocation.FIELD_DEFINITION],
    ...     args={
    ...         'inheritMaxAge': GraphQLArgument(
    ...             GraphQLNonNull(GraphQLBoolean),
    ...             description='Inherit the parent cache hint.',
    ...             default=GraphQLDefaultInput(False),
    ...             deprecation_reason='Use maxAge instead.',
    ...             extensions={'scope': 'cache'},
    ...         ),
    ...         'maxAge': GraphQLArgument(
    ...             GraphQLInt, ast_node=definition.arguments[0]
    ...         ),
    ...     },
    ...     is_repeatable=True,
    ...     deprecation_reason='Use @cache instead.',
    ...     extensions={'scope': 'cache'},
    ...     ast_node=definition,
    ...     extension_ast_nodes=[document.definitions[1]],
    ... )
    >>> cache_control.name
    'cacheControl'
    >>> cache_control.description
    'Controls HTTP cache hints for a field.'
    >>> list(cache_control.args)
    ['inheritMaxAge', 'maxAge']
    >>> cache_control.args['inheritMaxAge'].default.value
    False
    >>> cache_control.is_repeatable
    True
    >>> cache_control.extensions
    {'scope': 'cache'}
    """

    name: str
    """The GraphQL name for this schema element."""
    locations: tuple[DirectiveLocation, ...]
    """Locations where this directive may be applied."""
    is_repeatable: bool
    """Whether this directive may appear more than once at the same location."""
    args: dict[str, GraphQLArgument]
    """Arguments accepted by this directive."""
    deprecation_reason: str | None
    """Reason this element is deprecated, if one was provided."""
    description: str | None
    """Human-readable description for this schema element, if provided."""
    extensions: dict[str, Any]
    """Custom extension fields reserved for users."""
    ast_node: ast.DirectiveDefinitionNode | None
    """AST node from which this schema element was built, if available."""
    extension_ast_nodes: tuple[ast.DirectiveExtensionNode, ...]
    """AST extension nodes applied to this schema element."""

    def __init__(
        self,
        name: str,
        locations: Collection[DirectiveLocation],
        args: dict[str, GraphQLArgument] | None = None,
        is_repeatable: bool = False,
        deprecation_reason: str | None = None,
        description: str | None = None,
        extensions: dict[str, Any] | None = None,
        ast_node: ast.DirectiveDefinitionNode | None = None,
        extension_ast_nodes: Collection[ast.DirectiveExtensionNode] | None = None,
    ) -> None:
        assert_name(name)
        try:
            locations = tuple(
                value
                if isinstance(value, DirectiveLocation)
                else DirectiveLocation[cast("str", value)]
                for value in locations
            )
        except (KeyError, TypeError) as error:
            msg = (
                f"{name} locations must be specified"
                " as a collection of DirectiveLocation enum values."
            )
            raise TypeError(msg) from error
        if args:
            args = {
                assert_name(name): value
                if isinstance(value, GraphQLArgument)
                else GraphQLArgument(cast("GraphQLInputType", value))
                for name, value in args.items()
            }
        else:
            args = {}
        self.name = name
        self.locations = locations
        self.args = args
        self.is_repeatable = is_repeatable
        self.deprecation_reason = deprecation_reason
        self.description = description
        self.extensions = extensions or {}
        self.ast_node = ast_node
        self.extension_ast_nodes = (
            tuple(extension_ast_nodes) if extension_ast_nodes else ()
        )

    def __str__(self) -> str:
        """Get the schema coordinate identifying this directive.

        >>> from graphql import DirectiveLocation, GraphQLDirective
        >>> tag = GraphQLDirective('tag', [DirectiveLocation.FIELD_DEFINITION])
        >>> str(tag)
        '@tag'
        """
        return f"@{self.name}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}({self})>"

    def __eq__(self, other: object) -> bool:
        return self is other or (
            isinstance(other, GraphQLDirective)
            and self.name == other.name
            and self.locations == other.locations
            and self.args == other.args
            and self.is_repeatable == other.is_repeatable
            and self.deprecation_reason == other.deprecation_reason
            and self.description == other.description
            and self.extensions == other.extensions
        )

    def to_kwargs(self) -> GraphQLDirectiveKwargs:
        """Get a normalized dictionary of keyword arguments for this directive.

        :returns: keyword arguments that can be used to recreate this directive

        >>> from graphql import DirectiveLocation, GraphQLDirective, GraphQLString
        >>> tag = GraphQLDirective(
        ...     'tag', [DirectiveLocation.FIELD_DEFINITION], {'name': GraphQLString}
        ... )
        >>> kwargs = tag.to_kwargs()
        >>> tag_copy = GraphQLDirective(**kwargs)
        >>> kwargs['args']['name'].type is GraphQLString
        True
        >>> list(tag_copy.args)
        ['name']
        """
        return GraphQLDirectiveKwargs(
            name=self.name,
            locations=self.locations,
            args=self.args,
            is_repeatable=self.is_repeatable,
            deprecation_reason=self.deprecation_reason,
            description=self.description,
            extensions=self.extensions,
            ast_node=self.ast_node,
            extension_ast_nodes=self.extension_ast_nodes,
        )

    def __copy__(self) -> GraphQLDirective:  # pragma: no cover
        return self.__class__(**self.to_kwargs())


def is_directive(directive: Any) -> TypeGuard[GraphQLDirective]:
    """Test if the given value is a GraphQL directive.

    :param directive: the value to inspect
    :returns: whether the value is a :class:`GraphQLDirective`

    >>> from graphql import DirectiveLocation, GraphQLDirective, GraphQLString
    >>> from graphql import is_directive
    >>> upper = GraphQLDirective('upper', [DirectiveLocation.FIELD_DEFINITION])
    >>> is_directive(upper)
    True
    >>> is_directive(GraphQLString)
    False
    """
    return isinstance(directive, GraphQLDirective)


def assert_directive(directive: Any) -> GraphQLDirective:
    """Return the value as a GraphQL directive, or raise if it is not a directive.

    :param directive: the value to inspect
    :returns: the value typed as a :class:`GraphQLDirective`

    >>> from graphql import DirectiveLocation, GraphQLDirective, GraphQLString
    >>> from graphql import assert_directive
    >>> upper = GraphQLDirective('upper', [DirectiveLocation.FIELD_DEFINITION])
    >>> assert_directive(upper) is upper
    True
    >>> assert_directive(GraphQLString)
    Traceback (most recent call last):
    ...
    TypeError: Expected String to be a GraphQL directive.
    """
    if not is_directive(directive):
        msg = f"Expected {inspect(directive)} to be a GraphQL directive."
        raise TypeError(msg)
    return directive


GraphQLIncludeDirective = GraphQLDirective(
    name="include",
    locations=[
        DirectiveLocation.FIELD,
        DirectiveLocation.FRAGMENT_SPREAD,
        DirectiveLocation.INLINE_FRAGMENT,
    ],
    args={
        "if": GraphQLArgument(
            GraphQLNonNull(GraphQLBoolean), description="Included when true."
        )
    },
    description="Directs the executor to include this field or fragment"
    " only when the `if` argument is true.",
)
"""Used to conditionally include fields or fragments."""

GraphQLSkipDirective = GraphQLDirective(
    name="skip",
    locations=[
        DirectiveLocation.FIELD,
        DirectiveLocation.FRAGMENT_SPREAD,
        DirectiveLocation.INLINE_FRAGMENT,
    ],
    args={
        "if": GraphQLArgument(
            GraphQLNonNull(GraphQLBoolean), description="Skipped when true."
        )
    },
    description="Directs the executor to skip this field or fragment"
    " when the `if` argument is true.",
)
"""Used to conditionally skip (exclude) fields or fragments."""

GraphQLDeferDirective = GraphQLDirective(
    name="defer",
    description="Directs the executor to defer this fragment"
    " when the `if` argument is true or undefined.",
    locations=[DirectiveLocation.FRAGMENT_SPREAD, DirectiveLocation.INLINE_FRAGMENT],
    args={
        "if": GraphQLArgument(
            GraphQLNonNull(GraphQLBoolean),
            description="Deferred when true or undefined.",
            default_value=True,
        ),
        "label": GraphQLArgument(GraphQLString, description="Unique name"),
    },
)
"""Experimental directive used to conditionally defer fragments.

This directive is exported for schemas that explicitly opt in to incremental
delivery. It is not included in ``specified_directives``.
"""

GraphQLStreamDirective = GraphQLDirective(
    name="stream",
    description="Directs the executor to stream plural fields"
    " when the `if` argument is true or undefined.",
    locations=[DirectiveLocation.FIELD],
    args={
        "if": GraphQLArgument(
            GraphQLNonNull(GraphQLBoolean),
            description="Stream when true or undefined.",
            default_value=True,
        ),
        "label": GraphQLArgument(GraphQLString, description="Unique name"),
        "initialCount": GraphQLArgument(
            GraphQLInt,
            description="Number of items to return immediately",
            default_value=0,
        ),
    },
)
"""Experimental directive used to conditionally stream list fields.

This directive is exported for schemas that explicitly opt in to incremental
delivery. It is not included in ``specified_directives``.
"""

DEFAULT_DEPRECATION_REASON = "No longer supported"
"""Constant string used for default reason for a deprecation."""

GraphQLDeprecatedDirective = GraphQLDirective(
    name="deprecated",
    locations=[
        DirectiveLocation.FIELD_DEFINITION,
        DirectiveLocation.ARGUMENT_DEFINITION,
        DirectiveLocation.INPUT_FIELD_DEFINITION,
        DirectiveLocation.ENUM_VALUE,
        DirectiveLocation.DIRECTIVE_DEFINITION,
    ],
    args={
        "reason": GraphQLArgument(
            GraphQLNonNull(GraphQLString),
            description="Explains why this element was deprecated,"
            " usually also including a suggestion for how to access"
            " supported similar data."
            " Formatted using the Markdown syntax, as specified by"
            " [CommonMark](https://commonmark.org/).",
            default=GraphQLDefaultInput(value=DEFAULT_DEPRECATION_REASON),
        )
    },
    description="Marks an element of a GraphQL schema as no longer supported.",
)
"""Used to declare element of a GraphQL schema as deprecated.

The ``reason`` argument is non-null and defaults to ``DEFAULT_DEPRECATION_REASON``.
"""

GraphQLSpecifiedByDirective = GraphQLDirective(
    name="specifiedBy",
    locations=[DirectiveLocation.SCALAR],
    args={
        "url": GraphQLArgument(
            GraphQLNonNull(GraphQLString),
            description="The URL that specifies the behavior of this scalar.",
        )
    },
    description="Exposes a URL that specifies the behavior of this scalar.",
)
"""Used to provide a URL for specifying the behavior of custom scalar definitions."""

GraphQLOneOfDirective = GraphQLDirective(
    name="oneOf",
    locations=[DirectiveLocation.INPUT_OBJECT],
    args={},
    description="Indicates exactly one field must be supplied"
    " and this field must not be `null`.",
)
"""Used to indicate an Input Object is a OneOf Input Object."""

GraphQLDisableErrorPropagationDirective = GraphQLDirective(
    name="experimental_disableErrorPropagation",
    locations=[
        DirectiveLocation.QUERY,
        DirectiveLocation.MUTATION,
        DirectiveLocation.SUBSCRIPTION,
    ],
    description="Disables error propagation.",
)
"""Disables error propagation (experimental).

:meta private:
"""

specified_directives: tuple[GraphQLDirective, ...] = (
    GraphQLIncludeDirective,
    GraphQLSkipDirective,
    GraphQLDeprecatedDirective,
    GraphQLSpecifiedByDirective,
    GraphQLOneOfDirective,
)
"""A tuple with all directives from the GraphQL specification

Experimental ``@defer`` and ``@stream`` are exported separately and are not
included in this tuple.
"""


def is_specified_directive(directive: GraphQLDirective) -> bool:
    """Check whether the given directive is one of the specified directives.

    :param directive: the directive to inspect
    :returns: whether the directive is specified by GraphQL

    >>> from graphql import DirectiveLocation, GraphQLDirective
    >>> from graphql import GraphQLIncludeDirective, is_specified_directive
    >>> custom_directive = GraphQLDirective(
    ...     'auth', [DirectiveLocation.FIELD_DEFINITION]
    ... )
    >>> is_specified_directive(GraphQLIncludeDirective)
    True
    >>> is_specified_directive(custom_directive)
    False
    """
    return any(
        specified_directive.name == directive.name
        for specified_directive in specified_directives
    )
