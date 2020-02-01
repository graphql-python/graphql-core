from typing import Union

from ..language import (
    DocumentNode,
    Source,
    parse,
)
from ..type import (
    GraphQLDeprecatedDirective,
    GraphQLIncludeDirective,
    GraphQLSchema,
    GraphQLSkipDirective,
)
from .extend_schema import extend_schema

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
    be safe to assume the schema is valid. Set `assume_valid` to True to assume the
    produced schema is valid. Set `assume_valid_sdl` to True to assume it is already
    a valid SDL document.
    """
    if not isinstance(document_ast, DocumentNode):
        raise TypeError("Must provide valid Document AST.")

    if not (assume_valid or assume_valid_sdl):
        from ..validation.validate import assert_valid_sdl

        assert_valid_sdl(document_ast)

    empty_schema = GraphQLSchema(directives=[])
    extended_schema = extend_schema(
        empty_schema, document_ast, assume_valid=assume_valid, assume_valid_sdl=True
    )

    schema_kwargs = extended_schema.to_kwargs()
    if extended_schema.ast_node is None:
        # Note: While this could make early assertions to get the correctly
        # typed values below, that would throw immediately while type system
        # validation with validate_schema() will produce more actionable results.
        schema_kwargs["query"] = extended_schema.get_type("Query")
        schema_kwargs["mutation"] = extended_schema.get_type("Mutation")
        schema_kwargs["subscription"] = extended_schema.get_type("Subscription")

    directives = schema_kwargs["directives"]
    # If specified directives were not explicitly declared, add them.
    if not any(directive.name == "skip" for directive in directives):
        directives.append(GraphQLSkipDirective)
    if not any(directive.name == "include" for directive in directives):
        directives.append(GraphQLIncludeDirective)
    if not any(directive.name == "deprecated" for directive in directives):
        directives.append(GraphQLDeprecatedDirective)

    schema_kwargs["assume_valid"] = assume_valid
    return GraphQLSchema(**schema_kwargs)


def build_schema(
    source: Union[str, Source],
    assume_valid=False,
    assume_valid_sdl=False,
    no_location=False,
    experimental_fragment_variables=False,
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
