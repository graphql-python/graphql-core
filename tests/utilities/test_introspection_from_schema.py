from typing import Dict

from graphql.type import GraphQLSchema, GraphQLObjectType, GraphQLField, GraphQLString
from graphql.utilities import (
    build_client_schema,
    print_schema,
    introspection_from_schema,
)

from ..utils import dedent


def introspection_to_sdl(introspection: Dict) -> str:
    return print_schema(build_client_schema(introspection))


def describe_introspection_from_schema():

    schema = GraphQLSchema(
        GraphQLObjectType(
            "Simple",
            {
                "string": GraphQLField(
                    GraphQLString, description="This is a string field"
                )
            },
            description="This is a simple type",
        ),
        description="This is a simple schema",
    )

    def converts_a_simple_schema():
        introspection = introspection_from_schema(schema)

        assert introspection_to_sdl(introspection) == dedent(
            '''
            """This is a simple schema"""
            schema {
              query: Simple
            }

            """This is a simple type"""
            type Simple {
              """This is a string field"""
              string: String
            }
            '''
        )

    def converts_a_simple_schema_without_description():
        introspection = introspection_from_schema(schema, descriptions=False)

        assert introspection_to_sdl(introspection) == dedent(
            """
            schema {
              query: Simple
            }

            type Simple {
              string: String
            }
            """
        )
