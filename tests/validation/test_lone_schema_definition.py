from functools import partial

from graphql.utilities import build_schema
from graphql.validation.rules.lone_schema_definition import (
    LoneSchemaDefinition, schema_definition_not_alone_message,
    cannot_define_schema_within_extension_message)

from .harness import expect_sdl_errors_from_rule

expect_sdl_errors = partial(
    expect_sdl_errors_from_rule, LoneSchemaDefinition)


def schema_definition_not_alone(line, column):
    return {
        'message': schema_definition_not_alone_message(),
        'locations': [(line, column)]}


def cannot_define_schema_within_extension(line, column):
    return {
        'message': cannot_define_schema_within_extension_message(),
        'locations': [(line, column)]}


def describe_validate_schema_definition_should_be_alone():

    def no_schema():
        assert expect_sdl_errors("""
            type Query {
              foo: String
            }
            """) == []

    def one_schema_definition():
        assert expect_sdl_errors("""
            schema {
              query: Foo
            }

            type Foo {
              foo: String
            }
            """) == []

    def multiple_schema_definitions():
        assert expect_sdl_errors("""
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
            """) == [
            schema_definition_not_alone(10, 13),
            schema_definition_not_alone(14, 13)]

    def define_schema_in_schema_extension():
        schema = build_schema("""
            type Foo {
              foo: String
            }
            """)

        assert expect_sdl_errors("""
            schema {
              query: Foo
            }
            """, schema) == []

    def redefine_schema_in_schema_extension():
        schema = build_schema("""
            schema {
              query: Foo
            }

            type Foo {
              foo: String
            }
            """)

        assert expect_sdl_errors("""
            schema {
              mutation: Foo
            }
            """, schema) == [
            cannot_define_schema_within_extension(2, 13)]

    def redefine_implicit_schema_in_schema_extension():
        schema = build_schema("""
            type Query {
              fooField: Foo
            }

            type Foo {
              foo: String
            }
            """)

        assert expect_sdl_errors("""
            schema {
              mutation: Foo
            }
            """, schema) == [
            cannot_define_schema_within_extension(2, 13)]

    def extend_schema_in_schema_extension():
        schema = build_schema("""
            type Query {
              fooField: Foo
            }

            type Foo {
              foo: String
            }
            """)

        assert expect_sdl_errors("""
            extend schema {
              mutation: Foo
            }
            """, schema) == []
