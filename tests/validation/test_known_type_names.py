from functools import partial

from graphql.validation import KnownTypeNamesRule
from graphql.validation.rules.known_type_names import unknown_type_message

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, KnownTypeNamesRule)

assert_valid = partial(assert_errors, errors=[])


def unknown_type(type_name, suggested_types, line, column):
    return {
        "message": unknown_type_message(type_name, suggested_types),
        "locations": [(line, column)],
    }


def describe_validate_known_type_names():
    def known_type_names_are_valid():
        assert_valid(
            """
            query Foo($var: String, $required: [String!]!) {
              user(id: 4) {
                pets { ... on Pet { name }, ...PetFields, ... { name } }
              }
            }
            fragment PetFields on Pet {
              name
            }
            """
        )

    def unknown_type_names_are_invalid():
        assert_errors(
            """
            query Foo($var: JumbledUpLetters) {
              user(id: 4) {
                name
                pets { ... on Badger { name }, ...PetFields, ... { name } }
              }
            }
            fragment PetFields on Peettt {
              name
            }
            """,
            [
                unknown_type("JumbledUpLetters", [], 2, 29),
                unknown_type("Badger", [], 5, 31),
                unknown_type("Peettt", ["Pet"], 8, 35),
            ],
        )

    def ignores_type_definitions():
        assert_errors(
            """
            type NotInTheSchema {
              field: FooBar
            }
            interface FooBar {
              field: NotInTheSchema
            }
            union U = A | B
            input Blob {
              field: UnknownType
            }
            query Foo($var: NotInTheSchema) {
              user(id: $var) {
                id
              }
            }
            """,
            [unknown_type("NotInTheSchema", [], 12, 29)],
        )
