from typing import Any, Dict, Union

from ..language import DocumentNode, Source, parse
from ..type import GraphQLSchema, specified_directives
from .extend_schema import extend_schema_impl

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

    This takes the ast of a schema document produced by the parse function in
    src/language/parser.py.

    If no schema definition is provided, then it will look for types named Query
    and Mutation.

    Given that AST it constructs a GraphQLSchema. The resulting schema has no
    resolve methods, so execution will use default resolvers.

    When building a schema from a GraphQL service's introspection result, it might
    be safe to assume the schema is valid. Set ``assume_valid`` to ``True`` to assume
    the produced schema is valid. Set ``assume_valid_sdl`` to ``True`` to assume it is
    already a valid SDL document.
    """
    if not isinstance(document_ast, DocumentNode):
        raise TypeError("Must provide valid Document AST.")

    if not (assume_valid or assume_valid_sdl):
        from ..validation.validate import assert_valid_sdl

        assert_valid_sdl(document_ast)

    empty_schema_kwargs: Dict[str, Any] = dict(
        query=None,
        mutation=None,
        subscription=None,
        description=None,
        types=[],
        directives=[],
        extensions=None,
        ast_node=None,
        extension_ast_nodes=[],
        assume_valid=False,
    )
    schema_kwargs = extend_schema_impl(empty_schema_kwargs, document_ast, assume_valid)

    if not schema_kwargs["ast_node"]:
        for type_ in schema_kwargs["types"]:
            # Note: While this could make early assertions to get the correctly
            # typed values below, that would throw immediately while type system
            # validation with validate_schema() will produce more actionable results.
            type_name = type_.name
            if type_name == "Query":
                schema_kwargs["query"] = type_
            elif type_name == "Mutation":
                schema_kwargs["mutation"] = type_
            elif type_name == "Subscription":
                schema_kwargs["subscription"] = type_

    directives = schema_kwargs["directives"]
    # If specified directives were not explicitly declared, add them.
    for std_directive in specified_directives:
        if all(directive.name != std_directive.name for directive in directives):
            directives.append(std_directive)

    return GraphQLSchema(**schema_kwargs)


def build_schema(
    source: Union[str, Source],
    assume_valid: bool = False,
    assume_valid_sdl: bool = False,
    no_location: bool = False,
    experimental_fragment_variables: bool = False,
) -> GraphQLSchema:
    """Build a GraphQLSchema directly from a source document."""
    return build_ast_schema(
        parse(
            source,
            no_location=no_location,
            experimental_fragment_variables=experimental_fragment_variables,
        ),
        assume_valid=assume_valid,
        assume_valid_sdl=assume_valid_sdl,
    )
