from functools import partial

from graphql.utilities import build_schema
from graphql.validation.rules.lone_schema_definition import (
    LoneSchemaDefinitionRule,
    schema_definition_not_alone_message,
    cannot_define_schema_within_extension_message,
)

from .harness import assert_sdl_validation_errors

assert_sdl_errors = partial(assert_sdl_validation_errors, LoneSchemaDefinitionRule)

assert_sdl_valid = partial(assert_sdl_errors, errors=[])


def schema_definition_not_alone(line, column):
    return {
        "message": schema_definition_not_alone_message(),
        "locations": [(line, column)],
    }


def cannot_define_schema_within_extension(line, column):
    return {
        "message": cannot_define_schema_within_extension_message(),
        "locations": [(line, column)],
    }


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
            [schema_definition_not_alone(10, 13), schema_definition_not_alone(14, 13)],
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
            [cannot_define_schema_within_extension(2, 13)],
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
            [cannot_define_schema_within_extension(2, 13)],
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
