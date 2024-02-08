from functools import partial

from graphql.validation import KnownFragmentNamesRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, KnownFragmentNamesRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_known_fragment_names():
    def known_fragment_names_are_valid():
        assert_valid(
            """
            {
              human(id: 4) {
                ...HumanFields1
                  ... on Human {
                    ...HumanFields2
                  }
                  ... {
                    name
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

    def unknown_fragment_names_are_invalid():
        assert_errors(
            """
            {
              human(id: 4) {
                ...UnknownFragment1
                ... on Human {
                  ...UnknownFragment2
                }
              }
            }
            fragment HumanFields on Human {
              name
              ...UnknownFragment3
            }
            """,
            [
                {
                    "message": "Unknown fragment 'UnknownFragment1'.",
                    "locations": [(4, 20)],
                },
                {
                    "message": "Unknown fragment 'UnknownFragment2'.",
                    "locations": [(6, 22)],
                },
                {
                    "message": "Unknown fragment 'UnknownFragment3'.",
                    "locations": [(12, 18)],
                },
            ],
        )
