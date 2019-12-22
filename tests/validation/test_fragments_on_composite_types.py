from functools import partial

from graphql.validation import FragmentsOnCompositeTypesRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, FragmentsOnCompositeTypesRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_fragments_on_composite_types():
    def object_is_valid_fragment_type():
        assert_valid(
            """
            fragment validFragment on Dog {
              barks
            }
            """
        )

    def interface_is_valid_fragment_type():
        assert_valid(
            """
            fragment validFragment on Pet {
              name
            }
            """
        )

    def object_is_valid_inline_fragment_type():
        assert_valid(
            """
            fragment validFragment on Pet {
              ... on Dog {
                barks
              }
            }
            """
        )

    def interface_is_valid_inline_fragment_type():
        assert_valid(
            """
            fragment validFragment on Mammal {
              ... on Canine {
                name
              }
            }
            """
        )

    def inline_fragment_without_type_is_valid():
        assert_valid(
            """
            fragment validFragment on Pet {
              ... {
                name
              }
            }
            """
        )

    def union_is_valid_fragment_type():
        assert_valid(
            """
            fragment validFragment on CatOrDog {
              __typename
            }
            """
        )

    def scalar_is_invalid_fragment_type():
        assert_errors(
            """
            fragment scalarFragment on Boolean {
              bad
            }
            """,
            [
                {
                    "message": "Fragment 'scalarFragment' cannot condition"
                    " on non composite type 'Boolean'.",
                    "locations": [(2, 40)],
                },
            ],
        )

    def enum_is_invalid_fragment_type():
        assert_errors(
            """
            fragment scalarFragment on FurColor {
              bad
            }
            """,
            [
                {
                    "message": "Fragment 'scalarFragment' cannot condition"
                    " on non composite type 'FurColor'.",
                    "locations": [(2, 40)],
                },
            ],
        )

    def input_object_is_invalid_fragment_type():
        assert_errors(
            """
            fragment inputFragment on ComplexInput {
              stringField
            }
            """,
            [
                {
                    "message": "Fragment 'inputFragment' cannot condition"
                    " on non composite type 'ComplexInput'.",
                    "locations": [(2, 39)],
                },
            ],
        )

    def scalar_is_invalid_inline_fragment_type():
        assert_errors(
            """
            fragment invalidFragment on Pet {
              ... on String {
                barks
              }
            }
            """,
            [
                {
                    "message": "Fragment cannot condition"
                    " on non composite type 'String'.",
                    "locations": [(3, 22)],
                }
            ],
        )
