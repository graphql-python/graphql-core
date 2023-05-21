from __future__ import annotations  # Python < 3.10

from typing import Any, Collection, Dict, Optional, Tuple, cast

from ..language import DirectiveLocation, ast
from ..pyutils import inspect
from .assert_name import assert_name
from .definition import GraphQLArgument, GraphQLInputType, GraphQLNonNull
from .scalars import GraphQLBoolean, GraphQLInt, GraphQLString


try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict
try:
    from typing import TypeGuard
except ImportError:  # Python < 3.10
    from typing_extensions import TypeGuard

__all__ = [
    "is_directive",
    "assert_directive",
    "is_specified_directive",
    "specified_directives",
    "GraphQLDeferDirective",
    "GraphQLDirective",
    "GraphQLDirectiveKwargs",
    "GraphQLIncludeDirective",
    "GraphQLSkipDirective",
    "GraphQLStreamDirective",
    "GraphQLDeprecatedDirective",
    "GraphQLSpecifiedByDirective",
    "DirectiveLocation",
    "DEFAULT_DEPRECATION_REASON",
]


class GraphQLDirectiveKwargs(TypedDict, total=False):
    name: str
    locations: Tuple[DirectiveLocation, ...]
    args: Dict[str, GraphQLArgument]
    is_repeatable: bool
    description: Optional[str]
    extensions: Dict[str, Any]
    ast_node: Optional[ast.DirectiveDefinitionNode]


class GraphQLDirective:
    """GraphQL Directive

    Directives are used by the GraphQL runtime as a way of modifying execution behavior.
    Type system creators will usually not create these directly.
    """

    name: str
    locations: Tuple[DirectiveLocation, ...]
    is_repeatable: bool
    args: Dict[str, GraphQLArgument]
    description: Optional[str]
    extensions: Dict[str, Any]
    ast_node: Optional[ast.DirectiveDefinitionNode]

    def __init__(
        self,
        name: str,
        locations: Collection[DirectiveLocation],
        args: Optional[Dict[str, GraphQLArgument]] = None,
        is_repeatable: bool = False,
        description: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
        ast_node: Optional[ast.DirectiveDefinitionNode] = None,
    ) -> None:
        assert_name(name)
        try:
            locations = tuple(
                value
                if isinstance(value, DirectiveLocation)
                else DirectiveLocation[cast(str, value)]
                for value in locations
            )
        except (KeyError, TypeError):
            raise TypeError(
                f"{name} locations must be specified"
                " as a collection of DirectiveLocation enum values."
            )
        if args:
            args = {
                assert_name(name): value
                if isinstance(value, GraphQLArgument)
                else GraphQLArgument(cast(GraphQLInputType, value))
                for name, value in args.items()
            }
        else:
            args = {}
        self.name = name
        self.locations = locations
        self.args = args
        self.is_repeatable = is_repeatable
        self.description = description
        self.extensions = extensions or {}
        self.ast_node = ast_node

    def __str__(self) -> str:
        return f"@{self.name}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}({self})>"

    def __eq__(self, other: Any) -> bool:
        return self is other or (
            isinstance(other, GraphQLDirective)
            and self.name == other.name
            and self.locations == other.locations
            and self.args == other.args
            and self.is_repeatable == other.is_repeatable
            and self.description == other.description
            and self.extensions == other.extensions
        )

    def to_kwargs(self) -> GraphQLDirectiveKwargs:
        return GraphQLDirectiveKwargs(
            name=self.name,
            locations=self.locations,
            args=self.args,
            is_repeatable=self.is_repeatable,
            description=self.description,
            extensions=self.extensions,
            ast_node=self.ast_node,
        )

    def __copy__(self) -> GraphQLDirective:  # pragma: no cover
        return self.__class__(**self.to_kwargs())


def is_directive(directive: Any) -> TypeGuard[GraphQLDirective]:
    """Test if the given value is a GraphQL directive."""
    return isinstance(directive, GraphQLDirective)


def assert_directive(directive: Any) -> GraphQLDirective:
    if not is_directive(directive):
        raise TypeError(f"Expected {inspect(directive)} to be a GraphQL directive.")
    return directive


# Used to conditionally include fields or fragments.
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


# Used to conditionally skip (exclude) fields or fragments:
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

# Used to conditionally defer fragments:
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

# Used to conditionally stream list fields:
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


# Constant string used for default reason for a deprecation:
DEFAULT_DEPRECATION_REASON = "No longer supported"

# Used to declare element of a GraphQL schema as deprecated:
GraphQLDeprecatedDirective = GraphQLDirective(
    name="deprecated",
    locations=[
        DirectiveLocation.FIELD_DEFINITION,
        DirectiveLocation.ARGUMENT_DEFINITION,
        DirectiveLocation.INPUT_FIELD_DEFINITION,
        DirectiveLocation.ENUM_VALUE,
    ],
    args={
        "reason": GraphQLArgument(
            GraphQLString,
            description="Explains why this element was deprecated,"
            " usually also including a suggestion for how to access"
            " supported similar data."
            " Formatted using the Markdown syntax, as specified by"
            " [CommonMark](https://commonmark.org/).",
            default_value=DEFAULT_DEPRECATION_REASON,
        )
    },
    description="Marks an element of a GraphQL schema as no longer supported.",
)

# Used to provide a URL for specifying the behaviour of custom scalar definitions:
GraphQLSpecifiedByDirective = GraphQLDirective(
    name="specifiedBy",
    locations=[DirectiveLocation.SCALAR],
    args={
        "url": GraphQLArgument(
            GraphQLNonNull(GraphQLString),
            description="The URL that specifies the behaviour of this scalar.",
        )
    },
    description="Exposes a URL that specifies the behaviour of this scalar.",
)


specified_directives: Tuple[GraphQLDirective, ...] = (
    GraphQLIncludeDirective,
    GraphQLSkipDirective,
    GraphQLDeprecatedDirective,
    GraphQLSpecifiedByDirective,
)
"""A tuple with all directives from the GraphQL specification"""


def is_specified_directive(directive: GraphQLDirective) -> bool:
    """Check whether the given directive is one of the specified directives."""
    return any(
        specified_directive.name == directive.name
        for specified_directive in specified_directives
    )
