from functools import partial

from graphql.utilities import build_schema
from graphql.validation.rules.unique_operation_types import (
    UniqueOperationTypesRule,
    duplicate_operation_type_message,
    existed_operation_type_message,
)

from .harness import assert_sdl_validation_errors

assert_errors = partial(assert_sdl_validation_errors, UniqueOperationTypesRule)

assert_valid = partial(assert_errors, errors=[])


def duplicate_type(name, l1, c1, l2, c2):
    return {
        "message": duplicate_operation_type_message(name),
        "locations": [(l1, c1), (l2, c2)],
    }


def existed_type(name, line, col):
    return {"message": existed_operation_type_message(name), "locations": [(line, col)]}


def describe_validate_unique_operation_types():
    def no_schema_definition():
        assert_valid(
            """
            type Foo
            """
        )

    def schema_definition_with_all_types():
        assert_valid(
            """
            type Foo

            schema {
              query: Foo
              mutation: Foo
              subscription: Foo
            }
            """
        )

    def schema_definition_with_single_extension():
        assert_valid(
            """
            type Foo

            schema { query: Foo }

            extend schema {
              mutation: Foo
              subscription: Foo
            }
            """
        )

    def schema_definition_with_separate_extensions():
        assert_valid(
            """
            type Foo

            schema { query: Foo }
            extend schema { mutation: Foo }
            extend schema { subscription: Foo }
            """
        )

    def extend_schema_before_definition():
        assert_valid(
            """
            type Foo

            extend schema { mutation: Foo }
            extend schema { subscription: Foo }

            schema { query: Foo }
            """
        )

    def duplicate_operation_types_inside_single_schema_definition():
        assert_errors(
            """
            type Foo

            schema {
              query: Foo
              mutation: Foo
              subscription: Foo

              query: Foo
              mutation: Foo
              subscription: Foo
            }
            """,
            [
                duplicate_type("query", 5, 15, 9, 15),
                duplicate_type("mutation", 6, 15, 10, 15),
                duplicate_type("subscription", 7, 15, 11, 15),
            ],
        )

    def duplicate_operation_types_inside_schema_extension():
        assert_errors(
            """
            type Foo

            schema {
              query: Foo
              mutation: Foo
              subscription: Foo
            }

            extend schema {
              query: Foo
              mutation: Foo
              subscription: Foo
            }
            """,
            [
                duplicate_type("query", 5, 15, 11, 15),
                duplicate_type("mutation", 6, 15, 12, 15),
                duplicate_type("subscription", 7, 15, 13, 15),
            ],
        )

    def duplicate_operation_types_inside_schema_extension_twice():
        assert_errors(
            """
            type Foo

            schema {
              query: Foo
              mutation: Foo
              subscription: Foo
            }

            extend schema {
              query: Foo
              mutation: Foo
              subscription: Foo
            }

            extend schema {
              query: Foo
              mutation: Foo
              subscription: Foo
            }
            """,
            [
                duplicate_type("query", 5, 15, 11, 15),
                duplicate_type("mutation", 6, 15, 12, 15),
                duplicate_type("subscription", 7, 15, 13, 15),
                duplicate_type("query", 5, 15, 17, 15),
                duplicate_type("mutation", 6, 15, 18, 15),
                duplicate_type("subscription", 7, 15, 19, 15),
            ],
        )

    def duplicate_operation_types_inside_second_schema_extension():
        assert_errors(
            """
            type Foo

            schema {
              query: Foo
            }

            extend schema {
              mutation: Foo
              subscription: Foo
            }

            extend schema {
              query: Foo
              mutation: Foo
              subscription: Foo
            }
            """,
            [
                duplicate_type("query", 5, 15, 14, 15),
                duplicate_type("mutation", 9, 15, 15, 15),
                duplicate_type("subscription", 10, 15, 16, 15),
            ],
        )

    def define_schema_inside_extension_sdl():
        schema = build_schema("type Foo")
        sdl = """
            schema {
              query: Foo
              mutation: Foo
              subscription: Foo
            }
            """

        assert_valid(sdl, schema=schema)

    def define_and_extend_schema_inside_extension_sdl():
        schema = build_schema("type Foo")
        sdl = """
            schema { query: Foo }
            extend schema { mutation: Foo }
            extend schema { subscription: Foo }
            """

        assert_valid(sdl, schema=schema)

    def adding_new_operation_types_to_existing_schema():
        schema = build_schema("type Query")
        sdl = """
            extend schema { mutation: Foo }
            extend schema { subscription: Foo }
            """

        assert_valid(sdl, schema=schema)

    def adding_conflicting_operation_types_to_existing_schema():
        schema = build_schema(
            """
            type Query
            type Mutation
            type Subscription

            type Foo
            """
        )

        sdl = """
            extend schema {
              query: Foo
              mutation: Foo
              subscription: Foo
            }
            """

        assert_errors(
            sdl,
            [
                existed_type("query", 3, 15),
                existed_type("mutation", 4, 15),
                existed_type("subscription", 5, 15),
            ],
            schema,
        )

    def adding_conflicting_operation_types_to_existing_schema_twice():
        schema = build_schema(
            """
            type Query
            type Mutation
            type Subscription
            """
        )

        sdl = """
            extend schema {
              query: Foo
              mutation: Foo
              subscription: Foo
            }

            extend schema {
              query: Foo
              mutation: Foo
              subscription: Foo
             }
            """

        assert_errors(
            sdl,
            [
                existed_type("query", 3, 15),
                existed_type("mutation", 4, 15),
                existed_type("subscription", 5, 15),
                existed_type("query", 9, 15),
                existed_type("mutation", 10, 15),
                existed_type("subscription", 11, 15),
            ],
            schema,
        )
