from typing import Any, Dict, List, Optional, Sequence, cast

from ..language import ast, DirectiveLocation
from ..pyutils import inspect, FrozenList
from .definition import GraphQLArgument, GraphQLInputType, GraphQLNonNull, is_input_type
from .scalars import GraphQLBoolean, GraphQLString

__all__ = [
    "is_directive",
    "assert_directive",
    "is_specified_directive",
    "specified_directives",
    "GraphQLDirective",
    "GraphQLIncludeDirective",
    "GraphQLSkipDirective",
    "GraphQLDeprecatedDirective",
    "DirectiveLocation",
    "DEFAULT_DEPRECATION_REASON",
]


class GraphQLDirective:
    """GraphQL Directive

    Directives are used by the GraphQL runtime as a way of modifying execution behavior.
    Type system creators will usually not create these directly.
    """

    name: str
    locations: List[DirectiveLocation]
    is_repeatable: bool
    args: Dict[str, GraphQLArgument]
    description: Optional[str]
    ast_node: Optional[ast.DirectiveDefinitionNode]

    def __init__(
        self,
        name: str,
        locations: Sequence[DirectiveLocation],
        args: Dict[str, GraphQLArgument] = None,
        is_repeatable: bool = False,
        description: str = None,
        ast_node: ast.DirectiveDefinitionNode = None,
    ) -> None:
        if not name:
            raise TypeError("Directive must be named.")
        elif not isinstance(name, str):
            raise TypeError("The directive name must be a string.")
        if not isinstance(is_repeatable, bool):
            raise TypeError(f"{name} is_repeatable flag must be True or False.")
        try:
            locations = [
                value
                if isinstance(value, DirectiveLocation)
                else DirectiveLocation[cast(str, value)]
                for value in locations
            ]
        except (KeyError, TypeError):
            raise TypeError(
                f"{name} locations must be specified"
                " as a sequence of DirectiveLocation enum values."
            )
        if args is None:
            args = {}
        elif not isinstance(args, dict) or not all(
            isinstance(key, str) for key in args
        ):
            raise TypeError(f"{name} args must be a dict with argument names as keys.")
        elif not all(
            isinstance(value, GraphQLArgument) or is_input_type(value)
            for value in args.values()
        ):
            raise TypeError(
                f"{name} args must be GraphQLArgument or input type objects."
            )
        else:
            args = {
                name: value
                if isinstance(value, GraphQLArgument)
                else GraphQLArgument(cast(GraphQLInputType, value))
                for name, value in args.items()
            }
        if description is not None and not isinstance(description, str):
            raise TypeError(f"{name} description must be a string.")
        if ast_node and not isinstance(ast_node, ast.DirectiveDefinitionNode):
            raise TypeError(f"{name} AST node must be a DirectiveDefinitionNode.")
        self.name = name
        self.locations = locations
        self.args = args
        self.is_repeatable = is_repeatable
        self.description = description
        self.ast_node = ast_node

    def __str__(self):
        return f"@{self.name}"

    def __repr__(self):
        return f"<{self.__class__.__name__}({self})>"

    def to_kwargs(self) -> Dict[str, Any]:
        return dict(
            name=self.name,
            locations=self.locations,
            args=self.args,
            is_repeatable=self.is_repeatable,
            description=self.description,
            ast_node=self.ast_node,
        )


def is_directive(directive: Any) -> bool:
    """Test if the given value is a GraphQL directive."""
    return isinstance(directive, GraphQLDirective)


def assert_directive(directive: Any) -> GraphQLDirective:
    if not is_directive(directive):
        raise TypeError(f"Expected {inspect(directive)} to be a GraphQL directive.")
    return cast(GraphQLDirective, directive)


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


# Constant string used for default reason for a deprecation:
DEFAULT_DEPRECATION_REASON = "No longer supported"

# Used to declare element of a GraphQL schema as deprecated:
GraphQLDeprecatedDirective = GraphQLDirective(
    name="deprecated",
    locations=[DirectiveLocation.FIELD_DEFINITION, DirectiveLocation.ENUM_VALUE],
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


specified_directives: FrozenList[GraphQLDirective] = FrozenList(
    [GraphQLIncludeDirective, GraphQLSkipDirective, GraphQLDeprecatedDirective]
)
specified_directives.__doc__ = """The full list of specified directives."""


def is_specified_directive(directive: Any) -> bool:
    """Check whether the given directive is one of the specified directives."""
    return is_directive(directive) and any(
        specified_directive.name == directive.name
        for specified_directive in specified_directives
    )
