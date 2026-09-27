"""GraphQL Schema creation from GraphQL AST"""

from __future__ import annotations

from typing import cast

from ..language import DocumentNode, Source, parse
from ..type import (
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLSchemaKwargs,
    specified_directives,
)
from .extend_schema import ExtendSchemaImpl

__all__ = [
    "build_ast_schema",
    "build_schema",
]


def build_ast_schema(
    document_ast: DocumentNode,
    assume_valid: bool = False,
    assume_valid_sdl: bool = False,
) -> GraphQLSchema:
    """Build a GraphQL Schema from a given AST.

    This takes the AST of a schema definition language document produced by the
    :func:`~graphql.language.parse` function and constructs a GraphQLSchema from it.

    If no schema definition is provided, then it will look for types named Query,
    Mutation and Subscription.

    The resulting schema has no resolver functions, so execution will use the default
    field resolver.

    When building a schema from a GraphQL service's introspection result, it might
    be safe to assume the schema is valid. Set ``assume_valid`` to ``True`` to assume
    the produced schema is valid. Set ``assume_valid_sdl`` to ``True`` to assume it is
    already a valid SDL document.

    :param document_ast: The parsed GraphQL document AST.
    :param assume_valid: Set to ``True`` to assume the produced schema is valid and
        skip schema validation.
    :param assume_valid_sdl: Set to ``True`` to assume the SDL document is valid and
        skip SDL validation.
    :returns: The schema built from the provided SDL document.

    Build a schema from a valid parsed SDL document:

    >>> from graphql import build_ast_schema, parse
    >>> document = parse('type Query { hello: String }')
    >>> schema = build_ast_schema(document)
    >>> schema.query_type.name
    'Query'

    This variant uses validation options when the SDL references unknown
    directives:

    >>> document = parse('type Query { hello: String @unknown }')
    >>> build_ast_schema(document)
    Traceback (most recent call last):
    ...
    TypeError: Unknown directive '@unknown'.
    >>> schema = build_ast_schema(document, assume_valid=True, assume_valid_sdl=True)
    """
    if not (assume_valid or assume_valid_sdl):
        from ..validation.validate import assert_valid_sdl

        assert_valid_sdl(document_ast)

    empty_schema_kwargs = GraphQLSchemaKwargs(
        query=None,
        mutation=None,
        subscription=None,
        description=None,
        types=(),
        directives=(),
        extensions={},
        ast_node=None,
        extension_ast_nodes=(),
        assume_valid=False,
    )
    schema_kwargs = ExtendSchemaImpl.extend_schema_args(
        empty_schema_kwargs, document_ast, assume_valid
    )

    if not schema_kwargs["ast_node"]:
        for type_ in schema_kwargs["types"] or ():
            # Note: While this could make early assertions to get the correctly
            # typed values below, that would throw immediately while type system
            # validation with validate_schema() will produce more actionable results.
            type_name = type_.name
            if type_name == "Query":
                schema_kwargs["query"] = cast("GraphQLObjectType", type_)
            elif type_name == "Mutation":
                schema_kwargs["mutation"] = cast("GraphQLObjectType", type_)
            elif type_name == "Subscription":
                schema_kwargs["subscription"] = cast("GraphQLObjectType", type_)

    # If specified directives were not explicitly declared, add them.
    directives = schema_kwargs["directives"]
    directive_names = {directive.name for directive in directives}
    missing_directives = [
        directive
        for directive in specified_directives
        if directive.name not in directive_names
    ]
    if missing_directives:
        schema_kwargs["directives"] = directives + tuple(missing_directives)

    return GraphQLSchema(**schema_kwargs)


def build_schema(
    source: str | Source,
    assume_valid: bool = False,
    assume_valid_sdl: bool = False,
    no_location: bool = False,
    experimental_fragment_arguments: bool = False,
    experimental_directives_on_directive_definitions: bool = False,
) -> GraphQLSchema:
    r"""Build a GraphQLSchema directly from a source document.

    Builds a GraphQLSchema directly from a schema definition language source.

    :param source: The GraphQL source text or source object.
    :param assume_valid: Set to ``True`` to assume the produced schema is valid and
        skip schema validation.
    :param assume_valid_sdl: Set to ``True`` to assume the SDL document is valid and
        skip SDL validation.
    :param no_location: Set to ``True`` to create AST nodes without location
        information.
    :param experimental_fragment_arguments: Allows fragment variable definitions
        and arguments on fragment spreads to be parsed (experimental).
    :param experimental_directives_on_directive_definitions: Allows directives on
        directive definitions to be parsed (experimental).
    :returns: The schema built from the provided SDL document.

    Build a schema from SDL source using the default options:

    >>> from graphql import build_schema
    >>> schema = build_schema('type Query { hello: String }')
    >>> schema.query_type.name
    'Query'

    This variant enables parser options and omits source locations:

    >>> schema = build_schema(
    ...     'directive @tag on DIRECTIVE_DEFINITION\n'
    ...     'directive @compose @tag on FIELD_DEFINITION',
    ...     experimental_directives_on_directive_definitions=True,
    ...     experimental_fragment_arguments=True,
    ...     no_location=True,
    ... )
    >>> directive = schema.get_directive('compose')
    >>> directive.name
    'compose'
    >>> print(directive.ast_node.loc)
    None
    """
    return build_ast_schema(
        parse(
            source,
            no_location=no_location,
            experimental_fragment_arguments=experimental_fragment_arguments,
            experimental_directives_on_directive_definitions=(
                experimental_directives_on_directive_definitions
            ),
        ),
        assume_valid=assume_valid,
        assume_valid_sdl=assume_valid_sdl,
    )
