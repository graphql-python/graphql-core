from functools import partial

from graphql.validation import NoFragmentCyclesRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, NoFragmentCyclesRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_no_circular_fragment_spreads():
    def single_reference_is_valid():
        assert_valid(
            """
            fragment fragA on Dog { ...fragB }
            fragment fragB on Dog { name }
            """
        )

    def spreading_twice_is_not_circular():
        assert_valid(
            """
            fragment fragA on Dog { ...fragB, ...fragB }
            fragment fragB on Dog { name }
            """
        )

    def spreading_twice_indirectly_is_not_circular():
        assert_valid(
            """
            fragment fragA on Dog { ...fragB, ...fragC }
            fragment fragB on Dog { ...fragC }
            fragment fragC on Dog { name }
            """
        )

    def double_spread_within_abstract_types():
        assert_valid(
            """
            fragment nameFragment on Pet {
              ... on Dog { name }
              ... on Cat { name }
            }
            fragment spreadsInAnon on Pet {
              ... on Dog { ...nameFragment }
              ... on Cat { ...nameFragment }
            }
            """
        )

    def does_not_raise_false_positive_on_unknown_fragment():
        assert_valid(
            """
            fragment nameFragment on Pet {
              ...UnknownFragment
            }
            """
        )

    def spreading_recursively_within_field_fails():
        assert_errors(
            """
            fragment fragA on Human { relatives { ...fragA } },
            """,
            [
                {
                    "message": "Cannot spread fragment 'fragA' within itself.",
                    "locations": [(2, 51)],
                }
            ],
        )

    def no_spreading_itself_directly():
        assert_errors(
            """
            fragment fragA on Dog { ...fragA }
            """,
            [
                {
                    "message": "Cannot spread fragment 'fragA' within itself.",
                    "locations": [(2, 37)],
                }
            ],
        )

    def no_spreading_itself_directly_within_inline_fragment():
        assert_errors(
            """
            fragment fragA on Pet {
              ... on Dog {
                ...fragA
              }
            }
            """,
            [
                {
                    "message": "Cannot spread fragment 'fragA' within itself.",
                    "locations": [(4, 17)],
                }
            ],
        )

    def no_spreading_itself_indirectly():
        assert_errors(
            """
            fragment fragA on Dog { ...fragB }
            fragment fragB on Dog { ...fragA }
            """,
            [
                {
                    "message": "Cannot spread fragment 'fragA'"
                    " within itself via 'fragB'.",
                    "locations": [(2, 37), (3, 37)],
                }
            ],
        )

    def no_spreading_itself_indirectly_reports_opposite_order():
        assert_errors(
            """
            fragment fragB on Dog { ...fragA }
            fragment fragA on Dog { ...fragB }
            """,
            [
                {
                    "message": "Cannot spread fragment 'fragB'"
                    " within itself via 'fragA'.",
                    "locations": [(2, 37), (3, 37)],
                }
            ],
        )

    def no_spreading_itself_indirectly_within_inline_fragment():
        assert_errors(
            """
            fragment fragA on Pet {
              ... on Dog {
                ...fragB
              }
            }
            fragment fragB on Pet {
              ... on Dog {
                ...fragA
              }
            }
            """,
            [
                {
                    "message": "Cannot spread fragment 'fragA'"
                    " within itself via 'fragB'.",
                    "locations": [(4, 17), (9, 17)],
                }
            ],
        )

    def no_spreading_itself_deeply():
        assert_errors(
            """
            fragment fragA on Dog { ...fragB }
            fragment fragB on Dog { ...fragC }
            fragment fragC on Dog { ...fragO }
            fragment fragX on Dog { ...fragY }
            fragment fragY on Dog { ...fragZ }
            fragment fragZ on Dog { ...fragO }
            fragment fragO on Dog { ...fragP }
            fragment fragP on Dog { ...fragA, ...fragX }
            """,
            [
                {
                    "message": "Cannot spread fragment 'fragA' within itself"
                    " via 'fragB', 'fragC', 'fragO', 'fragP'.",
                    "locations": [(2, 37), (3, 37), (4, 37), (8, 37), (9, 37)],
                    "path": None,
                },
                {
                    "message": "Cannot spread fragment 'fragO' within itself"
                    " via 'fragP', 'fragX', 'fragY', 'fragZ'.",
                    "locations": [(8, 37), (9, 47), (5, 37), (6, 37), (7, 37)],
                    "path": None,
                },
            ],
        )

    def no_spreading_itself_deeply_two_paths():
        assert_errors(
            """
            fragment fragA on Dog { ...fragB, ...fragC }
            fragment fragB on Dog { ...fragA }
            fragment fragC on Dog { ...fragA }
            """,
            [
                {
                    "message": "Cannot spread fragment 'fragA'"
                    " within itself via 'fragB'.",
                    "locations": [(2, 37), (3, 37)],
                },
                {
                    "message": "Cannot spread fragment 'fragA'"
                    " within itself via 'fragC'.",
                    "locations": [(2, 47), (4, 37)],
                },
            ],
        )

    def no_spreading_itself_deeply_two_paths_alt_traverse_order():
        assert_errors(
            """
            fragment fragA on Dog { ...fragC }
            fragment fragB on Dog { ...fragC }
            fragment fragC on Dog { ...fragA, ...fragB }
            """,
            [
                {
                    "message": "Cannot spread fragment 'fragA'"
                    " within itself via 'fragC'.",
                    "locations": [(2, 37), (4, 37)],
                },
                {
                    "message": "Cannot spread fragment 'fragC'"
                    " within itself via 'fragB'.",
                    "locations": [(4, 47), (3, 37)],
                },
            ],
        )

    def no_spreading_itself_deeply_and_immediately():
        assert_errors(
            """
            fragment fragA on Dog { ...fragB }
            fragment fragB on Dog { ...fragB, ...fragC }
            fragment fragC on Dog { ...fragA, ...fragB }
            """,
            [
                {
                    "message": "Cannot spread fragment 'fragB' within itself.",
                    "locations": [(3, 37)],
                },
                {
                    "message": "Cannot spread fragment 'fragA'"
                    " within itself via 'fragB', 'fragC'.",
                    "locations": [(2, 37), (3, 47), (4, 37)],
                },
                {
                    "message": "Cannot spread fragment 'fragB'"
                    " within itself via 'fragC'.",
                    "locations": [(3, 47), (4, 47)],
                },
            ],
        )
