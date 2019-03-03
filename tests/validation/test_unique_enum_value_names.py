from functools import partial

from graphql.utilities import build_schema
from graphql.validation.rules.unique_enum_value_names import (
    UniqueEnumValueNamesRule,
    duplicate_enum_value_name_message,
    existed_enum_value_name_message,
)

from .harness import assert_sdl_validation_errors

assert_errors = partial(assert_sdl_validation_errors, UniqueEnumValueNamesRule)

assert_valid = partial(assert_errors, errors=[])


def duplicate_name(type_name, value_name, l1, c1, l2, c2):
    return {
        "message": duplicate_enum_value_name_message(type_name, value_name),
        "locations": [(l1, c1), (l2, c2)],
    }


def existed_name(type_name, value_name, line, col):
    return {
        "message": existed_enum_value_name_message(type_name, value_name),
        "locations": [(line, col)],
    }


def describe_validate_unique_field_definition_names():
    def no_values():
        assert_valid(
            """
            enum SomeEnum
            """
        )

    def one_value():
        assert_valid(
            """
            enum SomeEnum {
              FOO
            }
            """
        )

    def multiple_values():
        assert_valid(
            """
            enum SomeEnum {
              FOO
              BAR
            }
            """
        )

    def duplicate_values_inside_the_same_enum_definition():
        assert_errors(
            """
            enum SomeEnum {
              FOO
              BAR
              FOO
            }
            """,
            [duplicate_name("SomeEnum", "FOO", 3, 15, 5, 15)],
        )

    def extend_enum_with_new_value():
        assert_valid(
            """
            enum SomeEnum {
              FOO
            }
            extend enum SomeEnum {
              BAR
            }
            extend enum SomeEnum {
              BAZ
            }
            """
        )

    def extend_enum_with_duplicate_value():
        assert_errors(
            """
            extend enum SomeEnum {
              FOO
            }
            enum SomeEnum {
              FOO
            }
            """,
            [duplicate_name("SomeEnum", "FOO", 3, 15, 6, 15)],
        )

    def duplicate_value_inside_extension():
        assert_errors(
            """
            enum SomeEnum
            extend enum SomeEnum {
              FOO
              BAR
              FOO
            }
            """,
            [duplicate_name("SomeEnum", "FOO", 4, 15, 6, 15)],
        )

    def duplicate_value_inside_different_extension():
        assert_errors(
            """
            enum SomeEnum
            extend enum SomeEnum {
              FOO
            }
            extend enum SomeEnum {
              FOO
            }
            """,
            [duplicate_name("SomeEnum", "FOO", 4, 15, 7, 15)],
        )

    def adding_new_value_to_the_enum_inside_existing_schema():
        schema = build_schema("enum SomeEnum")
        sdl = """
          extend enum SomeEnum {
              FOO
          }
          """

        assert_valid(sdl, schema=schema)

    def adding_conflicting_value_to_existing_schema_twice():
        schema = build_schema(
            """
            enum SomeEnum {
              FOO
            }
            """
        )
        sdl = """
            extend enum SomeEnum {
              FOO
            }
            extend enum SomeEnum {
              FOO
            }
            """

        assert_errors(
            sdl,
            [
                existed_name("SomeEnum", "FOO", 3, 15),
                existed_name("SomeEnum", "FOO", 6, 15),
            ],
            schema,
        )

    def adding_enum_values_to_existing_schema_twice():
        schema = build_schema("enum SomeEnum")
        sdl = """
            extend enum SomeEnum {
              FOO
            }
            extend enum SomeEnum {
              FOO
            }
            """

        assert_errors(sdl, [duplicate_name("SomeEnum", "FOO", 3, 15, 6, 15)], schema)
