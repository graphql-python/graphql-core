from graphql import GraphQLSchema
from graphql.type import (
    GraphQLField,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLString,
)

__all__ = ["viral_schema"]

Mutation = GraphQLObjectType(
    "Mutation",
    {
        "name": GraphQLField(GraphQLNonNull(GraphQLString)),
        "geneSequence": GraphQLField(GraphQLNonNull(GraphQLString)),
    },
)

Virus = GraphQLObjectType(
    "Virus",
    {
        "name": GraphQLField(GraphQLNonNull(GraphQLString)),
        "knownMutations": GraphQLField(
            GraphQLNonNull(GraphQLList(GraphQLNonNull(Mutation)))
        ),
    },
)

Query = GraphQLObjectType(
    "Query", {"viruses": GraphQLField(GraphQLList(GraphQLNonNull(Virus)))}
)

viral_schema = GraphQLSchema(Query)
