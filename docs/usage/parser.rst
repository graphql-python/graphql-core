Parsing GraphQL Queries and Schema Notation
-------------------------------------------

.. currentmodule:: graphql.language

When executing GraphQL queries, the first step that happens under the hood is parsing
the query. But GraphQL-core 3 also exposes the parser for direct usage via the
:func:`parse` function. When you pass this function a GraphQL source code, it will be
parsed and returned as a Document, i.e. an abstract syntax tree (AST) of :class:`Node`
objects. The root node will be a :class:`DocumentNode`, with child nodes of different
kinds corresponding to the GraphQL source. The nodes also carry information on the
location in the source code that they correspond to.

Here is an example::

    from graphql import parse

    document = parse("""
        type Query {
          me: User
        }

        type User {
          id: ID
          name: String
        }
    """)

You can also leave out the information on the location in the source code when creating
the AST document::

    document = parse(..., no_location=True)

This will give the same result as manually creating the AST document::

    from graphql.language.ast import *

    document = DocumentNode(definitions=[
        ObjectTypeDefinitionNode(
            name=NameNode(value='Query'),
            fields=[
                FieldDefinitionNode(
                    name=NameNode(value='me'),
                    type=NamedTypeNode(name=NameNode(value='User')),
                    arguments=[], directives=[])
                ], directives=[], interfaces=[]),
        ObjectTypeDefinitionNode(
            name=NameNode(value='User'),
            fields=[
                FieldDefinitionNode(
                    name=NameNode(value='id'),
                    type=NamedTypeNode(
                        name=NameNode(value='ID')),
                    arguments=[], directives=[]),
                FieldDefinitionNode(
                    name=NameNode(value='name'),
                    type=NamedTypeNode(
                        name=NameNode(value='String')),
                    arguments=[], directives=[]),
                ], directives=[], interfaces=[]),
        ])


When parsing with ``no_location=False`` (the default), the AST nodes will also have a
``loc`` attribute carrying the information on the source code location corresponding
to the AST nodes.

When there is a syntax error in the GraphQL source code, then the :func:`parse` function
will raise a :exc:`~graphql.error.GraphQLSyntaxError`.

The parser can not only be used to parse GraphQL queries, but also to parse the GraphQL
schema definition language. This will result in another way of representing a GraphQL
schema, as an AST document.
