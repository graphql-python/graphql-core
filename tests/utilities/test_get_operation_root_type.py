from pytest import raises

from graphql.error import GraphQLError
from graphql.language import (
    parse,
    DocumentNode,
    OperationDefinitionNode,
    OperationTypeDefinitionNode,
    SchemaDefinitionNode,
)
from graphql.type import GraphQLField, GraphQLObjectType, GraphQLSchema, GraphQLString
from graphql.utilities import get_operation_root_type


query_type = GraphQLObjectType("FooQuery", {"field": GraphQLField(GraphQLString)})

mutation_type = GraphQLObjectType("FooMutation", {"field": GraphQLField(GraphQLString)})

subscription_type = GraphQLObjectType(
    "FooSubscription", {"field": GraphQLField(GraphQLString)}
)


def get_operation_node(doc: DocumentNode) -> OperationDefinitionNode:
    operation_node = doc.definitions[0]
    assert isinstance(operation_node, OperationDefinitionNode)
    return operation_node


def describe_get_operation_root_type():
    def gets_a_query_type_for_an_unnamed_operation_definition_node():
        test_schema = GraphQLSchema(query_type)
        doc = parse("{ field }")
        operation_node = get_operation_node(doc)
        assert get_operation_root_type(test_schema, operation_node) is query_type

    def gets_a_query_type_for_a_named_operation_definition_node():
        test_schema = GraphQLSchema(query_type)
        doc = parse("query Q { field }")
        operation_node = get_operation_node(doc)
        assert get_operation_root_type(test_schema, operation_node) is query_type

    def gets_a_type_for_operation_definition_nodes():
        test_schema = GraphQLSchema(query_type, mutation_type, subscription_type)
        doc = parse(
            """
            schema {
              query: FooQuery
              mutation: FooMutation
              subscription: FooSubscription
            }
            """
        )

        schema_node = doc.definitions[0]
        assert isinstance(schema_node, SchemaDefinitionNode)
        query_node, mutation_node, subscription_node = schema_node.operation_types
        assert isinstance(query_node, OperationTypeDefinitionNode)
        assert get_operation_root_type(test_schema, query_node) is query_type
        assert isinstance(mutation_node, OperationTypeDefinitionNode)
        assert get_operation_root_type(test_schema, mutation_node) is mutation_type
        assert isinstance(subscription_node, OperationTypeDefinitionNode)
        assert (
            get_operation_root_type(test_schema, subscription_node) is subscription_type
        )

    def gets_a_mutation_type_for_an_operation_definition_node():
        test_schema = GraphQLSchema(mutation=mutation_type)
        doc = parse("mutation { field }")
        operation_node = get_operation_node(doc)
        assert get_operation_root_type(test_schema, operation_node) is mutation_type

    def gets_a_subscription_type_for_an_operation_definition_node():
        test_schema = GraphQLSchema(subscription=subscription_type)
        doc = parse("subscription { field }")
        operation_node = get_operation_node(doc)
        assert get_operation_root_type(test_schema, operation_node) is subscription_type

    def throws_when_query_type_not_defined_in_schema():
        test_schema = GraphQLSchema()
        doc = parse("query { field }")
        operation_node = get_operation_node(doc)
        with raises(GraphQLError) as exc_info:
            get_operation_root_type(test_schema, operation_node)
        assert exc_info.value.message == (
            "Schema does not define the required query root type."
        )

    def throws_when_mutation_type_not_defined_in_schema():
        test_schema = GraphQLSchema()
        doc = parse("mutation { field }")
        operation_node = get_operation_node(doc)
        with raises(GraphQLError) as exc_info:
            get_operation_root_type(test_schema, operation_node)
        assert exc_info.value.message == "Schema is not configured for mutations."

    def throws_when_subscription_type_not_defined_in_schema():
        test_schema = GraphQLSchema()
        doc = parse("subscription { field }")
        operation_node = get_operation_node(doc)
        with raises(GraphQLError) as exc_info:
            get_operation_root_type(test_schema, operation_node)
        assert exc_info.value.message == "Schema is not configured for subscriptions."

    def throws_when_operation_not_a_valid_operation_kind():
        test_schema = GraphQLSchema()
        doc = parse("{ field }")
        operation_node = get_operation_node(doc)
        operation_node.operation = "non_existent_operation"  # type: ignore
        with raises(GraphQLError) as exc_info:
            get_operation_root_type(test_schema, operation_node)
        assert exc_info.value.message == (
            "Can only have query, mutation and subscription operations."
        )
