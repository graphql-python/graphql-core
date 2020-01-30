from graphql.type import GraphQLSchema
from graphql import graphql_sync


def describe_graphql():
    def report_errors_raised_during_schema_validation():
        schema = GraphQLSchema()
        result = graphql_sync(schema=schema, source="{ __typename }")
        assert result == (None, [{"message": "Query root type must be provided."}])
