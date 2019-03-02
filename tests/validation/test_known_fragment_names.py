from functools import partial

from graphql.validation import KnownFragmentNamesRule
from graphql.validation.rules.known_fragment_names import unknown_fragment_message

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, KnownFragmentNamesRule)

assert_valid = partial(assert_errors, errors=[])


def unknmown_fragment(fragment_name, line, column):
    return {
        "message": unknown_fragment_message(fragment_name),
        "locations": [(line, column)],
    }


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
                unknmown_fragment("UnknownFragment1", 4, 20),
                unknmown_fragment("UnknownFragment2", 6, 22),
                unknmown_fragment("UnknownFragment3", 12, 18),
            ],
        )
