from graphql.validation import NoFragmentCyclesRule
from graphql.validation.rules.no_fragment_cycles import cycle_error_message

from .harness import expect_fails_rule, expect_passes_rule


def describe_validate_no_circular_fragment_spreads():
    def single_reference_is_valid():
        expect_passes_rule(
            NoFragmentCyclesRule,
            """
            fragment fragA on Dog { ...fragB }
            fragment fragB on Dog { name }
            """,
        )

    def spreading_twice_is_not_circular():
        expect_passes_rule(
            NoFragmentCyclesRule,
            """
            fragment fragA on Dog { ...fragB, ...fragB }
            fragment fragB on Dog { name }
            """,
        )

    def spreading_twice_indirectly_is_not_circular():
        expect_passes_rule(
            NoFragmentCyclesRule,
            """
            fragment fragA on Dog { ...fragB, ...fragC }
            fragment fragB on Dog { ...fragC }
            fragment fragC on Dog { name }
            """,
        )

    def double_spread_within_abstract_types():
        expect_passes_rule(
            NoFragmentCyclesRule,
            """
            fragment nameFragment on Pet {
              ... on Dog { name }
              ... on Cat { name }
            }
            fragment spreadsInAnon on Pet {
              ... on Dog { ...nameFragment }
              ... on Cat { ...nameFragment }
            }
            """,
        )

    def does_not_raise_false_positive_on_unknown_fragment():
        expect_passes_rule(
            NoFragmentCyclesRule,
            """
            fragment nameFragment on Pet {
              ...UnknownFragment
            }
            """,
        )

    def spreading_recursively_within_field_fails():
        expect_fails_rule(
            NoFragmentCyclesRule,
            """
            fragment fragA on Human { relatives { ...fragA } },
            """,
            [{"message": cycle_error_message("fragA", []), "locations": [(2, 51)]}],
        )

    def no_spreading_itself_directly():
        expect_fails_rule(
            NoFragmentCyclesRule,
            """
            fragment fragA on Dog { ...fragA }
            """,
            [{"message": cycle_error_message("fragA", []), "locations": [(2, 37)]}],
        )

    def no_spreading_itself_directly_within_inline_fragment():
        expect_fails_rule(
            NoFragmentCyclesRule,
            """
            fragment fragA on Pet {
              ... on Dog {
                ...fragA
              }
            }
            """,
            [{"message": cycle_error_message("fragA", []), "locations": [(4, 17)]}],
        )

    def no_spreading_itself_indirectly():
        expect_fails_rule(
            NoFragmentCyclesRule,
            """
            fragment fragA on Dog { ...fragB }
            fragment fragB on Dog { ...fragA }
            """,
            [
                {
                    "message": cycle_error_message("fragA", ["fragB"]),
                    "locations": [(2, 37), (3, 37)],
                }
            ],
        )

    def no_spreading_itself_indirectly_reports_opposite_order():
        expect_fails_rule(
            NoFragmentCyclesRule,
            """
            fragment fragB on Dog { ...fragA }
            fragment fragA on Dog { ...fragB }
            """,
            [
                {
                    "message": cycle_error_message("fragB", ["fragA"]),
                    "locations": [(2, 37), (3, 37)],
                }
            ],
        )

    def no_spreading_itself_indirectly_within_inline_fragment():
        expect_fails_rule(
            NoFragmentCyclesRule,
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
                    "message": cycle_error_message("fragA", ["fragB"]),
                    "locations": [(4, 17), (9, 17)],
                }
            ],
        )

    def no_spreading_itself_deeply():
        expect_fails_rule(
            NoFragmentCyclesRule,
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
                    "message": cycle_error_message(
                        "fragA", ["fragB", "fragC", "fragO", "fragP"]
                    ),
                    "locations": [(2, 37), (3, 37), (4, 37), (8, 37), (9, 37)],
                    "path": None,
                },
                {
                    "message": cycle_error_message(
                        "fragO", ["fragP", "fragX", "fragY", "fragZ"]
                    ),
                    "locations": [(8, 37), (9, 47), (5, 37), (6, 37), (7, 37)],
                    "path": None,
                },
            ],
        )

    def no_spreading_itself_deeply_two_paths():
        expect_fails_rule(
            NoFragmentCyclesRule,
            """
            fragment fragA on Dog { ...fragB, ...fragC }
            fragment fragB on Dog { ...fragA }
            fragment fragC on Dog { ...fragA }
            """,
            [
                {
                    "message": cycle_error_message("fragA", ["fragB"]),
                    "locations": [(2, 37), (3, 37)],
                },
                {
                    "message": cycle_error_message("fragA", ["fragC"]),
                    "locations": [(2, 47), (4, 37)],
                },
            ],
        )

    def no_spreading_itself_deeply_two_paths_alt_traverse_order():
        expect_fails_rule(
            NoFragmentCyclesRule,
            """
            fragment fragA on Dog { ...fragC }
            fragment fragB on Dog { ...fragC }
            fragment fragC on Dog { ...fragA, ...fragB }
            """,
            [
                {
                    "message": cycle_error_message("fragA", ["fragC"]),
                    "locations": [(2, 37), (4, 37)],
                },
                {
                    "message": cycle_error_message("fragC", ["fragB"]),
                    "locations": [(4, 47), (3, 37)],
                },
            ],
        )

    def no_spreading_itself_deeply_and_immediately():
        expect_fails_rule(
            NoFragmentCyclesRule,
            """
            fragment fragA on Dog { ...fragB }
            fragment fragB on Dog { ...fragB, ...fragC }
            fragment fragC on Dog { ...fragA, ...fragB }
            """,
            [
                {"message": cycle_error_message("fragB", []), "locations": [(3, 37)]},
                {
                    "message": cycle_error_message("fragA", ["fragB", "fragC"]),
                    "locations": [(2, 37), (3, 47), (4, 37)],
                },
                {
                    "message": cycle_error_message("fragB", ["fragC"]),
                    "locations": [(3, 47), (4, 47)],
                },
            ],
        )
