from graphql.validation import UniqueFragmentNamesRule
from graphql.validation.rules.unique_fragment_names import (
    duplicate_fragment_name_message
)

from .harness import expect_fails_rule, expect_passes_rule


def duplicate_fragment(frag_name, l1, c1, l2, c2):
    return {
        "message": duplicate_fragment_name_message(frag_name),
        "locations": [(l1, c1), (l2, c2)],
    }


def describe_validate_unique_fragment_names():
    def no_fragments():
        expect_passes_rule(
            UniqueFragmentNamesRule,
            """
            {
              field
            }
            """,
        )

    def one_fragment():
        expect_passes_rule(
            UniqueFragmentNamesRule,
            """
            {
              ...fragA
            }
            fragment fragA on Type {
              field
            }
            """,
        )

    def many_fragments():
        expect_passes_rule(
            UniqueFragmentNamesRule,
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
            """,
        )

    def inline_fragments_are_always_unique():
        expect_passes_rule(
            UniqueFragmentNamesRule,
            """
            {
              ...on Type {
                fieldA
              }
              ...on Type {
                fieldB
              }
            }
            """,
        )

    def fragment_and_operation_named_the_same():
        expect_passes_rule(
            UniqueFragmentNamesRule,
            """
            query Foo {
              ...Foo
            }
            fragment Foo on Type {
              field
            }
            """,
        )

    def fragments_named_the_same():
        expect_fails_rule(
            UniqueFragmentNamesRule,
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
            [duplicate_fragment("fragA", 5, 24, 8, 24)],
        )

    def fragments_named_the_same_without_being_referenced():
        expect_fails_rule(
            UniqueFragmentNamesRule,
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
