from pytest import raises

from graphql.language import parse_type, TypeNode
from graphql.type import GraphQLList, GraphQLNonNull, GraphQLObjectType
from graphql.utilities import type_from_ast

from ..validation.harness import test_schema


def describe_type_from_ast():
    def for_named_type_node():
        node = parse_type("Cat")
        type_for_node = type_from_ast(test_schema, node)
        assert isinstance(type_for_node, GraphQLObjectType)
        assert type_for_node.name == "Cat"

    def for_list_type_node():
        node = parse_type("[Cat]")
        type_for_node = type_from_ast(test_schema, node)
        assert isinstance(type_for_node, GraphQLList)
        of_type = type_for_node.of_type
        assert isinstance(of_type, GraphQLObjectType)
        assert of_type.name == "Cat"

    def for_non_null_type_node():
        node = parse_type("Cat!")
        type_for_node = type_from_ast(test_schema, node)
        assert isinstance(type_for_node, GraphQLNonNull)
        of_type = type_for_node.of_type
        assert isinstance(of_type, GraphQLObjectType)
        assert of_type.name == "Cat"

    def for_unspecified_type_node():
        node = TypeNode()
        with raises(TypeError) as exc_info:
            type_from_ast(test_schema, node)
        msg = str(exc_info.value)
        assert msg == "Unexpected type node: <TypeNode instance>."
