from functools import partial

from graphql.utilities import build_schema
from graphql.validation.rules.unique_type_names import (
    UniqueTypeNamesRule,
    duplicate_type_name_message,
    existed_type_name_message,
)

from .harness import assert_sdl_validation_errors

assert_errors = partial(assert_sdl_validation_errors, UniqueTypeNamesRule)

assert_valid = partial(assert_errors, errors=[])


def duplicate_type(name, l1, c1, l2, c2):
    return {
        "message": duplicate_type_name_message(name),
        "locations": [(l1, c1), (l2, c2)],
    }


def existed_type(name, line, col):
    return {"message": existed_type_name_message(name), "locations": [(line, col)]}


def describe_validate_unique_type_names():
    def no_types():
        assert_valid(
            """
            directive @test on SCHEMA
            """
        )

    def one_type():
        assert_valid(
            """
            type Foo
            """
        )

    def many_types():
        assert_valid(
            """
            type Foo
            type Bar
            type Baz
            """
        )

    def type_and_non_type_definitions_named_the_same():
        assert_valid(
            """
            query Foo { __typename }
            fragment Foo on Query { __typename }
            directive @Foo on SCHEMA

            type Foo
            """
        )

    def types_named_the_same():
        assert_errors(
            """
            type Foo

            scalar Foo
            type Foo
            interface Foo
            union Foo
            enum Foo
            input Foo
            """,
            [
                duplicate_type("Foo", 2, 18, 4, 20),
                duplicate_type("Foo", 2, 18, 5, 18),
                duplicate_type("Foo", 2, 18, 6, 23),
                duplicate_type("Foo", 2, 18, 7, 19),
                duplicate_type("Foo", 2, 18, 8, 18),
                duplicate_type("Foo", 2, 18, 9, 19),
            ],
        )

    def adding_new_type_to_existing_schema():
        schema = build_schema("type Foo")

        assert_valid("type Bar", schema=schema)

    def adding_new_type_to_existing_schema_with_same_named_directive():
        schema = build_schema("directive @Foo on SCHEMA")

        assert_valid("type Foo", schema=schema)

    def adding_conflicting_types_to_existing_schema():
        schema = build_schema("type Foo")
        sdl = """
            scalar Foo
            type Foo
            interface Foo
            union Foo
            enum Foo
            input Foo
            """

        assert_errors(
            sdl,
            [
                existed_type("Foo", 2, 20),
                existed_type("Foo", 3, 18),
                existed_type("Foo", 4, 23),
                existed_type("Foo", 5, 19),
                existed_type("Foo", 6, 18),
                existed_type("Foo", 7, 19),
            ],
            schema,
        )
