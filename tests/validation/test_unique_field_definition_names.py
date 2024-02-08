from functools import partial

from graphql.utilities import build_schema
from graphql.validation.rules.unique_field_definition_names import (
    UniqueFieldDefinitionNamesRule,
)

from .harness import assert_sdl_validation_errors

assert_errors = partial(assert_sdl_validation_errors, UniqueFieldDefinitionNamesRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_unique_field_definition_names():
    def no_fields():
        assert_valid(
            """
            type SomeObject
            interface SomeInterface
            input SomeInputObject
            """
        )

    def one_field():
        assert_valid(
            """
            type SomeObject {
              foo: String
            }

            interface SomeInterface {
              foo: String
            }

            input SomeInputObject {
              foo: String
            }
            """
        )

    def multiple_fields():
        assert_valid(
            """
            type SomeObject {
              foo: String
              bar: String
            }

            interface SomeInterface {
              foo: String
              bar: String
            }

            input SomeInputObject {
              foo: String
              bar: String
            }
            """
        )

    def duplicate_fields_inside_the_same_type_definition():
        assert_errors(
            """
            type SomeObject {
              foo: String
              bar: String
              foo: String
            }

            interface SomeInterface {
              foo: String
              bar: String
              foo: String
            }

            input SomeInputObject {
              foo: String
              bar: String
              foo: String
            }
            """,
            [
                {
                    "message": "Field 'SomeObject.foo' can only be defined once.",
                    "locations": [(3, 15), (5, 15)],
                },
                {
                    "message": "Field 'SomeInterface.foo' can only be defined once.",
                    "locations": [(9, 15), (11, 15)],
                },
                {
                    "message": "Field 'SomeInputObject.foo' can only be defined once.",
                    "locations": [(15, 15), (17, 15)],
                },
            ],
        )

    def extend_type_with_new_field():
        assert_valid(
            """
            type SomeObject {
              foo: String
            }
            extend type SomeObject {
              bar: String
            }
            extend type SomeObject {
              baz: String
            }

            interface SomeInterface {
              foo: String
            }
            extend interface SomeInterface {
              bar: String
            }
            extend interface SomeInterface {
              baz: String
            }

            input SomeInputObject {
              foo: String
            }
            extend input SomeInputObject {
              bar: String
            }
            extend input SomeInputObject {
              baz: String
            }
            """
        )

    def extend_type_with_duplicate_field():
        assert_errors(
            """
            extend type SomeObject {
              foo: String
            }
            type SomeObject {
              foo: String
            }

            extend interface SomeInterface {
              foo: String
            }
            interface SomeInterface {
              foo: String
            }

            extend input SomeInputObject {
              foo: String
            }
            input SomeInputObject {
              foo: String
            }
            """,
            [
                {
                    "message": "Field 'SomeObject.foo' can only be defined once.",
                    "locations": [(3, 15), (6, 15)],
                },
                {
                    "message": "Field 'SomeInterface.foo' can only be defined once.",
                    "locations": [(10, 15), (13, 15)],
                },
                {
                    "message": "Field 'SomeInputObject.foo' can only be defined once.",
                    "locations": [(17, 15), (20, 15)],
                },
            ],
        )

    def duplicate_field_inside_extension():
        assert_errors(
            """
            type SomeObject
            extend type SomeObject {
              foo: String
              bar: String
              foo: String
            }

            interface SomeInterface
            extend interface SomeInterface {
              foo: String
              bar: String
              foo: String
            }

            input SomeInputObject
            extend input SomeInputObject {
              foo: String
              bar: String
              foo: String
            }
            """,
            [
                {
                    "message": "Field 'SomeObject.foo' can only be defined once.",
                    "locations": [(4, 15), (6, 15)],
                },
                {
                    "message": "Field 'SomeInterface.foo' can only be defined once.",
                    "locations": [(11, 15), (13, 15)],
                },
                {
                    "message": "Field 'SomeInputObject.foo' can only be defined once.",
                    "locations": [(18, 15), (20, 15)],
                },
            ],
        )

    def duplicate_field_inside_different_extension():
        assert_errors(
            """
            type SomeObject
            extend type SomeObject {
              foo: String
            }
            extend type SomeObject {
              foo: String
            }

            interface SomeInterface
            extend interface SomeInterface {
              foo: String
            }
            extend interface SomeInterface {
              foo: String
            }

            input SomeInputObject
            extend input SomeInputObject {
              foo: String
            }
            extend input SomeInputObject {
              foo: String
            }
            """,
            [
                {
                    "message": "Field 'SomeObject.foo' can only be defined once.",
                    "locations": [(4, 15), (7, 15)],
                },
                {
                    "message": "Field 'SomeInterface.foo' can only be defined once.",
                    "locations": [(12, 15), (15, 15)],
                },
                {
                    "message": "Field 'SomeInputObject.foo' can only be defined once.",
                    "locations": [(20, 15), (23, 15)],
                },
            ],
        )

    def adding_new_field_to_the_type_inside_existing_schema():
        schema = build_schema(
            """
            type SomeObject
            interface SomeInterface
            input SomeInputObject
            """
        )
        sdl = """
            extend type SomeObject {
              foo: String
            }

            extend interface SomeInterface {
              foo: String
            }

            extend input SomeInputObject {
              foo: String
            }
            """

        assert_valid(sdl, schema=schema)

    def adding_conflicting_fields_to_existing_schema_twice():
        schema = build_schema(
            """
            type SomeObject {
              foo: String
            }

            interface SomeInterface {
              foo: String
            }

            input SomeInputObject {
              foo: String
            }
            """
        )
        sdl = """
            extend type SomeObject {
              foo: String
            }
            extend interface SomeInterface {
              foo: String
            }
            extend input SomeInputObject {
              foo: String
            }

            extend type SomeObject {
              foo: String
            }
            extend interface SomeInterface {
              foo: String
            }
            extend input SomeInputObject {
              foo: String
            }
            """

        assert_errors(
            sdl,
            [
                {
                    "message": "Field 'SomeObject.foo' already exists in the schema."
                    " It cannot also be defined in this type extension.",
                    "locations": [(3, 15)],
                },
                {
                    "message": "Field 'SomeInterface.foo' already exists in the schema."
                    " It cannot also be defined in this type extension.",
                    "locations": [(6, 15)],
                },
                {
                    "message": "Field 'SomeInputObject.foo'"
                    " already exists in the schema."
                    " It cannot also be defined in this type extension.",
                    "locations": [(9, 15)],
                },
                {
                    "message": "Field 'SomeObject.foo' already exists in the schema."
                    " It cannot also be defined in this type extension.",
                    "locations": [(13, 15)],
                },
                {
                    "message": "Field 'SomeInterface.foo'"
                    " already exists in the schema."
                    " It cannot also be defined in this type extension.",
                    "locations": [(16, 15)],
                },
                {
                    "message": "Field 'SomeInputObject.foo'"
                    " already exists in the schema."
                    " It cannot also be defined in this type extension.",
                    "locations": [(19, 15)],
                },
            ],
            schema,
        )

    def adding_fields_to_existing_schema_twice():
        schema = build_schema(
            """
            type SomeObject
            interface SomeInterface
            input SomeInputObject
            """
        )
        sdl = """
            extend type SomeObject {
              foo: String
            }
            extend type SomeObject {
              foo: String
            }

            extend interface SomeInterface {
              foo: String
            }
            extend interface SomeInterface {
              foo: String
            }

            extend input SomeInputObject {
              foo: String
            }
            extend input SomeInputObject {
              foo: String
            }
            """

        assert_errors(
            sdl,
            [
                {
                    "message": "Field 'SomeObject.foo' can only be defined once.",
                    "locations": [(3, 15), (6, 15)],
                },
                {
                    "message": "Field 'SomeInterface.foo' can only be defined once.",
                    "locations": [(10, 15), (13, 15)],
                },
                {
                    "message": "Field 'SomeInputObject.foo' can only be defined once.",
                    "locations": [(17, 15), (20, 15)],
                },
            ],
            schema,
        )
