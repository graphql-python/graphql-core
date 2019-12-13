from functools import partial

from graphql.utilities import build_schema
from graphql.validation.rules.lone_schema_definition import LoneSchemaDefinitionRule

from .harness import assert_sdl_validation_errors

assert_sdl_errors = partial(assert_sdl_validation_errors, LoneSchemaDefinitionRule)

assert_sdl_valid = partial(assert_sdl_errors, errors=[])


def describe_validate_schema_definition_should_be_alone():
    def no_schema():
        assert_sdl_valid(
            """
            type Query {
              foo: String
            }
            """
        )

    def one_schema_definition():
        assert_sdl_valid(
            """
            schema {
              query: Foo
            }

            type Foo {
              foo: String
            }
            """
        )

    def multiple_schema_definitions():
        assert_sdl_errors(
            """
            schema {
              query: Foo
            }

            type Foo {
              foo: String
            }

            schema {
              mutation: Foo
            }

            schema {
              subscription: Foo
            }
            """,
            [
                {
                    "message": "Must provide only one schema definition.",
                    "locations": [(10, 13)],
                },
                {
                    "message": "Must provide only one schema definition.",
                    "locations": [(14, 13)],
                },
            ],
        )

    def define_schema_in_schema_extension():
        schema = build_schema(
            """
            type Foo {
              foo: String
            }
            """
        )

        assert_sdl_valid(
            """
            schema {
              query: Foo
            }
            """,
            schema=schema,
        )

    def redefine_schema_in_schema_extension():
        schema = build_schema(
            """
            schema {
              query: Foo
            }

            type Foo {
              foo: String
            }
            """
        )

        assert_sdl_errors(
            """
            schema {
              mutation: Foo
            }
            """,
            [
                {
                    "message": "Cannot define a new schema within a schema extension.",
                    "locations": [(2, 13)],
                }
            ],
            schema,
        )

    def redefine_implicit_schema_in_schema_extension():
        schema = build_schema(
            """
            type Query {
              fooField: Foo
            }

            type Foo {
              foo: String
            }
            """
        )

        assert_sdl_errors(
            """
            schema {
              mutation: Foo
            }
            """,
            [
                {
                    "message": "Cannot define a new schema within a schema extension.",
                    "locations": [(2, 13)],
                },
            ],
            schema,
        )

    def extend_schema_in_schema_extension():
        schema = build_schema(
            """
            type Query {
              fooField: Foo
            }

            type Foo {
              foo: String
            }
            """
        )

        assert_sdl_valid(
            """
            extend schema {
              mutation: Foo
            }
            """,
            schema=schema,
        )
