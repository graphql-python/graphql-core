from functools import partial

from graphql.validation import NoUnusedFragmentsRule
from graphql.validation.rules.no_unused_fragments import unused_fragment_message

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, NoUnusedFragmentsRule)

assert_valid = partial(assert_errors, errors=[])


def unused_frag(frag_name, line, column):
    return {
        "message": unused_fragment_message(frag_name),
        "locations": [(line, column)],
    }


def describe_validate_no_unused_fragments():
    def all_fragment_names_are_used():
        assert_valid(
            """
            {
              human(id: 4) {
                ...HumanFields1
                ... on Human {
                  ...HumanFields2
                }
              }
            }
            fragment HumanFields1 on Human {
              name
              ...HumanFields3
            }
            fragment HumanFields2 on Human {
              name
            }
            fragment HumanFields3 on Human {
              name
            }
            """
        )

    def all_fragment_names_are_used_by_multiple_operations():
        assert_valid(
            """
            query Foo {
              human(id: 4) {
                ...HumanFields1
              }
            }
            query Bar {
              human(id: 4) {
                ...HumanFields2
              }
            }
            fragment HumanFields1 on Human {
              name
              ...HumanFields3
            }
            fragment HumanFields2 on Human {
              name
            }
            fragment HumanFields3 on Human {
              name
            }
            """
        )

    def contains_unknown_fragments():
        assert_errors(
            """
            query Foo {
              human(id: 4) {
                ...HumanFields1
              }
            }
            query Bar {
              human(id: 4) {
                ...HumanFields2
              }
            }
            fragment HumanFields1 on Human {
              name
              ...HumanFields3
            }
            fragment HumanFields2 on Human {
              name
            }
            fragment HumanFields3 on Human {
              name
            }
            fragment Unused1 on Human {
              name
            }
            fragment Unused2 on Human {
              name
            }
            """,
            [unused_frag("Unused1", 22, 13), unused_frag("Unused2", 25, 13)],
        )

    def contains_unknown_fragments_with_ref_cycle():
        assert_errors(
            """
            query Foo {
              human(id: 4) {
                ...HumanFields1
              }
            }
            query Bar {
              human(id: 4) {
                ...HumanFields2
              }
            }
            fragment HumanFields1 on Human {
              name
              ...HumanFields3
            }
            fragment HumanFields2 on Human {
              name
            }
            fragment HumanFields3 on Human {
              name
            }
            fragment Unused1 on Human {
              name
              ...Unused2
            }
            fragment Unused2 on Human {
              name
              ...Unused1
            }
            """,
            [unused_frag("Unused1", 22, 13), unused_frag("Unused2", 26, 13)],
        )

    def contains_unknown_and_undefined_fragments():
        assert_errors(
            """
            query Foo {
              human(id: 4) {
                ...bar
              }
            }
            fragment foo on Human {
              name
            }
            """,
            [unused_frag("foo", 7, 13)],
        )
