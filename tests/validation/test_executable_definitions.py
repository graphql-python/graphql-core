from functools import partial

from graphql.validation import ExecutableDefinitionsRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, ExecutableDefinitionsRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_executable_definitions():
    def with_only_operation():
        assert_valid(
            """
            query Foo {
              dog {
                name
              }
            }
            """
        )

    def with_operation_and_fragment():
        assert_valid(
            """
            query Foo {
              dog {
                name
                ...Frag
              }
            }

            fragment Frag on Dog {
              name
            }
            """
        )

    def with_type_definition():
        assert_errors(
            """
            query Foo {
              dog {
                name
              }
            }

            type Cow {
              name: String
            }

            extend type Dog {
              color: String
            }
            """,
            [
                {
                    "message": "The 'Cow' definition is not executable.",
                    "locations": [(8, 13)],
                },
                {
                    "message": "The 'Dog' definition is not executable.",
                    "locations": [(12, 13)],
                },
            ],
        )

    def with_schema_definition():
        assert_errors(
            """
            schema {
              query: Query
            }

            type Query {
              test: String
            }

            extend schema @directive
            """,
            [
                {
                    "message": "The schema definition is not executable.",
                    "locations": [(2, 13)],
                },
                {
                    "message": "The 'Query' definition is not executable.",
                    "locations": [(6, 13)],
                },
                {
                    "message": "The schema definition is not executable.",
                    "locations": [(10, 13)],
                },
            ],
        )
