from functools import partial

from graphql.utilities import build_schema
from graphql.validation.rules.unique_operation_types import UniqueOperationTypesRule

from .harness import assert_sdl_validation_errors

assert_errors = partial(assert_sdl_validation_errors, UniqueOperationTypesRule)

assert_valid = partial(assert_errors, errors=[])


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
                {
                    "message": "There can be only one query type in schema.",
                    "locations": [(5, 15), (9, 15)],
                },
                {
                    "message": "There can be only one mutation type in schema.",
                    "locations": [(6, 15), (10, 15)],
                },
                {
                    "message": "There can be only one subscription type in schema.",
                    "locations": [(7, 15), (11, 15)],
                },
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
                {
                    "message": "There can be only one query type in schema.",
                    "locations": [(5, 15), (11, 15)],
                },
                {
                    "message": "There can be only one mutation type in schema.",
                    "locations": [(6, 15), (12, 15)],
                },
                {
                    "message": "There can be only one subscription type in schema.",
                    "locations": [(7, 15), (13, 15)],
                },
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
                {
                    "message": "There can be only one query type in schema.",
                    "locations": [(5, 15), (11, 15)],
                },
                {
                    "message": "There can be only one mutation type in schema.",
                    "locations": [(6, 15), (12, 15)],
                },
                {
                    "message": "There can be only one subscription type in schema.",
                    "locations": [(7, 15), (13, 15)],
                },
                {
                    "message": "There can be only one query type in schema.",
                    "locations": [(5, 15), (17, 15)],
                },
                {
                    "message": "There can be only one mutation type in schema.",
                    "locations": [(6, 15), (18, 15)],
                },
                {
                    "message": "There can be only one subscription type in schema.",
                    "locations": [(7, 15), (19, 15)],
                },
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
                {
                    "message": "There can be only one query type in schema.",
                    "locations": [(5, 15), (14, 15)],
                },
                {
                    "message": "There can be only one mutation type in schema.",
                    "locations": [(9, 15), (15, 15)],
                },
                {
                    "message": "There can be only one subscription type in schema.",
                    "locations": [(10, 15), (16, 15)],
                },
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
                {
                    "message": "Type for query already defined in the schema."
                    " It cannot be redefined.",
                    "locations": [(3, 15)],
                },
                {
                    "message": "Type for mutation already defined in the schema."
                    " It cannot be redefined.",
                    "locations": [(4, 15)],
                },
                {
                    "message": "Type for subscription already defined in the schema."
                    " It cannot be redefined.",
                    "locations": [(5, 15)],
                },
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
                {
                    "message": "Type for query already defined in the schema."
                    " It cannot be redefined.",
                    "locations": [(3, 15)],
                },
                {
                    "message": "Type for mutation already defined in the schema."
                    " It cannot be redefined.",
                    "locations": [(4, 15)],
                },
                {
                    "message": "Type for subscription already defined in the schema."
                    " It cannot be redefined.",
                    "locations": [(5, 15)],
                },
                {
                    "message": "Type for query already defined in the schema."
                    " It cannot be redefined.",
                    "locations": [(9, 15)],
                },
                {
                    "message": "Type for mutation already defined in the schema."
                    " It cannot be redefined.",
                    "locations": [(10, 15)],
                },
                {
                    "message": "Type for subscription already defined in the schema."
                    " It cannot be redefined.",
                    "locations": [(11, 15)],
                },
            ],
            schema,
        )
