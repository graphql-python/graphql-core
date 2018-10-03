from graphql.validation import ExecutableDefinitionsRule
from graphql.validation.rules.executable_definitions import (
    non_executable_definitions_message,
)

from .harness import expect_fails_rule, expect_passes_rule


def non_executable_definition(def_name, line, column):
    return {
        "message": non_executable_definitions_message(def_name),
        "locations": [(line, column)],
    }


def describe_validate_executable_definitions():
    def with_only_operation():
        expect_passes_rule(
            ExecutableDefinitionsRule,
            """
            query Foo {
              dog {
                name
              }
            }
            """,
        )

    def with_operation_and_fragment():
        expect_passes_rule(
            ExecutableDefinitionsRule,
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
            """,
        )

    def with_type_definition():
        expect_fails_rule(
            ExecutableDefinitionsRule,
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
                non_executable_definition("Cow", 8, 13),
                non_executable_definition("Dog", 12, 13),
            ],
        )

    def with_schema_definition():
        expect_fails_rule(
            ExecutableDefinitionsRule,
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
                non_executable_definition("schema", 2, 13),
                non_executable_definition("Query", 6, 13),
                non_executable_definition("schema", 10, 13),
            ],
        )
