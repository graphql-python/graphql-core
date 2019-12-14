from functools import partial

from graphql.utilities import build_schema
from graphql.validation.rules.unique_directive_names import UniqueDirectiveNamesRule

from .harness import assert_sdl_validation_errors

assert_errors = partial(assert_sdl_validation_errors, UniqueDirectiveNamesRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_unique_directive_names():
    def no_directive():
        assert_valid(
            """
            type Foo
            """
        )

    def one_directive():
        assert_valid(
            """
            directive @foo on SCHEMA
            """
        )

    def many_directives():
        assert_valid(
            """
            directive @foo on SCHEMA
            directive @bar on SCHEMA
            directive @baz on SCHEMA
            """
        )

    def directive_and_non_directive_definitions_named_the_same():
        assert_valid(
            """
            query foo { __typename }
            fragment foo on foo { __typename }
            type foo

            directive @foo on SCHEMA
            """
        )

    def directives_named_the_same():
        assert_errors(
            """
            directive @foo on SCHEMA

            directive @foo on SCHEMA
            """,
            [
                {
                    "message": "There can be only one directive named '@foo'.",
                    "locations": [(2, 24), (4, 24)],
                }
            ],
        )

    def adding_new_directive_to_existing_schema():
        schema = build_schema("directive @foo on SCHEMA")

        assert_valid("directive @bar on SCHEMA", schema=schema)

    def adding_new_directive_with_standard_name_to_existing_schema():
        schema = build_schema("type foo")

        assert_errors(
            "directive @skip on SCHEMA",
            [
                {
                    "message": "Directive '@skip' already exists in the schema."
                    " It cannot be redefined.",
                    "locations": [(1, 12)],
                }
            ],
            schema,
        )

    def adding_new_directive_to_existing_schema_with_same_named_type():
        schema = build_schema("type foo")

        assert_valid("directive @foo on SCHEMA", schema=schema)

    def adding_conflicting_directives_to_existing_schema():
        schema = build_schema("directive @foo on SCHEMA")

        assert_errors(
            "directive @foo on SCHEMA",
            [
                {
                    "message": "Directive '@foo' already exists in the schema."
                    " It cannot be redefined.",
                    "locations": [(1, 12)],
                }
            ],
            schema,
        )
