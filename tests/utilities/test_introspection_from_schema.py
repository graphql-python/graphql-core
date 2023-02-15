import pickle
import sys
from copy import deepcopy

from pytest import mark

from graphql.type import GraphQLField, GraphQLObjectType, GraphQLSchema, GraphQLString
from graphql.utilities import (
    IntrospectionQuery,
    build_client_schema,
    build_schema,
    introspection_from_schema,
    print_schema,
)

from ..fixtures import big_schema_introspection_result, big_schema_sdl  # noqa: F401
from ..utils import dedent


def introspection_to_sdl(introspection: IntrospectionQuery) -> str:
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

    def describe_deepcopy_and_pickle():  # pragma: no cover
        # introspect the schema
        introspected_schema = introspection_from_schema(schema)
        introspection_size = len(str(introspected_schema))

        def can_deep_copy_schema():
            # create a deepcopy of the schema
            copied = deepcopy(schema)
            # check that introspecting the copied schema gives the same result
            assert introspection_from_schema(copied) == introspected_schema

        def can_pickle_and_unpickle_schema():
            # check that the schema can be pickled
            # (particularly, there should be no recursion error,
            # or errors because of trying to pickle lambdas or local functions)
            dumped = pickle.dumps(schema)

            # check that the pickle size is reasonable
            assert len(dumped) < 5 * introspection_size
            loaded = pickle.loads(dumped)

            # check that introspecting the unpickled schema gives the same result
            assert introspection_from_schema(loaded) == introspected_schema

            # check that pickling again creates the same result
            dumped = pickle.dumps(schema)
            assert len(dumped) < 5 * introspection_size
            loaded = pickle.loads(dumped)
            assert introspection_from_schema(loaded) == introspected_schema

        def can_deep_copy_pickled_schema():
            # pickle and unpickle the schema
            loaded = pickle.loads(pickle.dumps(schema))
            # create a deepcopy of the unpickled schema
            copied = deepcopy(loaded)
            # check that introspecting the copied schema gives the same result
            assert introspection_from_schema(copied) == introspected_schema

    @mark.slow
    def describe_deepcopy_and_pickle_big():  # pragma: no cover
        @mark.timeout(20)
        def can_deep_copy_big_schema(big_schema_sdl):  # noqa: F811
            # introspect the original big schema
            big_schema = build_schema(big_schema_sdl)
            expected_introspection = introspection_from_schema(big_schema)

            # create a deepcopy of the schema
            copied = deepcopy(big_schema)
            # check that introspecting the copied schema gives the same result
            assert introspection_from_schema(copied) == expected_introspection

        @mark.timeout(60)
        def can_pickle_and_unpickle_big_schema(big_schema_sdl):  # noqa: F811
            # introspect the original big schema
            big_schema = build_schema(big_schema_sdl)
            expected_introspection = introspection_from_schema(big_schema)
            size_introspection = len(str(expected_introspection))

            limit = sys.getrecursionlimit()
            sys.setrecursionlimit(max(limit, 4000))  # needed for pickle

            try:
                # check that the schema can be pickled
                # (particularly, there should be no recursion error,
                # or errors because of trying to pickle lambdas or local functions)
                dumped = pickle.dumps(big_schema)

                # check that the pickle size is reasonable
                assert len(dumped) < 5 * size_introspection
                loaded = pickle.loads(dumped)

                # check that introspecting the pickled schema gives the same result
                assert introspection_from_schema(loaded) == expected_introspection

                # check that pickling again creates the same result
                dumped = pickle.dumps(loaded)
                assert len(dumped) < 5 * size_introspection
                loaded = pickle.loads(dumped)

                # check that introspecting the re-pickled schema gives the same result
                assert introspection_from_schema(loaded) == expected_introspection

            finally:
                sys.setrecursionlimit(limit)

        @mark.timeout(60)
        def can_deep_copy_pickled_big_schema(big_schema_sdl):  # noqa: F811
            # introspect the original big schema
            big_schema = build_schema(big_schema_sdl)
            expected_introspection = introspection_from_schema(big_schema)

            limit = sys.getrecursionlimit()
            sys.setrecursionlimit(max(limit, 4000))  # needed for pickle

            try:
                # pickle and unpickle the schema
                loaded = pickle.loads(pickle.dumps(big_schema))
                # create a deepcopy of the unpickled schema
                copied = deepcopy(loaded)

                # check that introspecting the copied schema gives the same result
                assert introspection_from_schema(copied) == expected_introspection

            finally:
                sys.setrecursionlimit(limit)
