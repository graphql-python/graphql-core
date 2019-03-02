from functools import partial

from graphql.validation import UniqueFragmentNamesRule
from graphql.validation.rules.unique_fragment_names import (
    duplicate_fragment_name_message,
)

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, UniqueFragmentNamesRule)

assert_valid = partial(assert_errors, errors=[])


def duplicate_fragment(frag_name, l1, c1, l2, c2):
    return {
        "message": duplicate_fragment_name_message(frag_name),
        "locations": [(l1, c1), (l2, c2)],
    }


def describe_validate_unique_fragment_names():
    def no_fragments():
        assert_valid(
            """
            {
              field
            }
            """
        )

    def one_fragment():
        assert_valid(
            """
            {
              ...fragA
            }
            fragment fragA on Type {
              field
            }
            """
        )

    def many_fragments():
        assert_valid(
            """
            {
              ...fragA
              ...fragB
              ...fragC
            }
            fragment fragA on Type {
              fieldA
            }
            fragment fragB on Type {
              fieldB
            }
            fragment fragC on Type {
              fieldC
            }
            """
        )

    def inline_fragments_are_always_unique():
        assert_valid(
            """
            {
              ...on Type {
                fieldA
              }
              ...on Type {
                fieldB
              }
            }
            """
        )

    def fragment_and_operation_named_the_same():
        assert_valid(
            """
            query Foo {
              ...Foo
            }
            fragment Foo on Type {
              field
            }
            """
        )

    def fragments_named_the_same():
        assert_errors(
            """
            {
              ...fragA
            }
            fragment fragA on Type {
              fieldA
            }
            fragment fragA on Type {
              fieldB
            }
            """,
            [duplicate_fragment("fragA", 5, 22, 8, 22)],
        )

    def fragments_named_the_same_without_being_referenced():
        assert_errors(
            """
            fragment fragA on Type {
              fieldA
            }
            fragment fragA on Type {
              fieldB
            }
            """,
            [duplicate_fragment("fragA", 2, 22, 5, 22)],
        )
