from graphql.validation import PossibleFragmentSpreadsRule
from graphql.validation.rules.possible_fragment_spreads import (
    type_incompatible_spread_message,
    type_incompatible_anon_spread_message,
)

from .harness import expect_fails_rule, expect_passes_rule


def error(frag_name, parent_type, frag_type, line, column):
    return {
        "message": type_incompatible_spread_message(frag_name, parent_type, frag_type),
        "locations": [(line, column)],
    }


def error_anon(parent_type, frag_type, line, column):
    return {
        "message": type_incompatible_anon_spread_message(parent_type, frag_type),
        "locations": [(line, column)],
    }


def describe_validate_possible_fragment_spreads():
    def of_the_same_object():
        expect_passes_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment objectWithinObject on Dog { ...dogFragment }
            fragment dogFragment on Dog { barkVolume }
            """,
        )

    def of_the_same_object_inline_fragment():
        expect_passes_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment objectWithinObjectAnon on Dog { ... on Dog { barkVolume } }
            """,
        )  # noqa

    def object_into_implemented_interface():
        expect_passes_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment objectWithinInterface on Pet { ...dogFragment }
            fragment dogFragment on Dog { barkVolume }
            """,
        )

    def object_into_containing_union():
        expect_passes_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment objectWithinUnion on CatOrDog { ...dogFragment }
            fragment dogFragment on Dog { barkVolume }
            """,
        )

    def union_into_contained_object():
        expect_passes_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment unionWithinObject on Dog { ...catOrDogFragment }
            fragment catOrDogFragment on CatOrDog { __typename }
            """,
        )

    def union_into_overlapping_interface():
        expect_passes_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment unionWithinInterface on Pet { ...catOrDogFragment }
            fragment catOrDogFragment on CatOrDog { __typename }
            """,
        )

    def union_into_overlapping_union():
        expect_passes_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment unionWithinUnion on DogOrHuman { ...catOrDogFragment }
            fragment catOrDogFragment on CatOrDog { __typename }
            """,
        )

    def interface_into_implemented_object():
        expect_passes_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment interfaceWithinObject on Dog { ...petFragment }
            fragment petFragment on Pet { name }
            """,
        )

    def interface_into_overlapping_interface():
        expect_passes_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment interfaceWithinInterface on Pet { ...beingFragment }
            fragment beingFragment on Being { name }
            """,
        )

    def interface_into_overlapping_interface_in_inline_fragment():
        expect_passes_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment interfaceWithinInterface on Pet { ... on Being { name } }
            """,
        )

    def interface_into_overlapping_union():
        expect_passes_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment interfaceWithinUnion on CatOrDog { ...petFragment }
            fragment petFragment on Pet { name }
            """,
        )

    def ignores_incorrect_type_caught_by_fragments_on_composite_types():
        expect_passes_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment petFragment on Pet { ...badInADifferentWay }
            fragment badInADifferentWay on String { name }
            """,
        )

    def different_object_into_object():
        expect_fails_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment invalidObjectWithinObject on Cat { ...dogFragment }
            fragment dogFragment on Dog { barkVolume }
            """,
            [error("dogFragment", "Cat", "Dog", 2, 57)],
        )

    def different_object_into_object_in_inline_fragment():
        expect_fails_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment invalidObjectWithinObjectAnon on Cat {
              ... on Dog { barkVolume }
            }
            """,
            [error_anon("Cat", "Dog", 3, 15)],
        )

    def object_into_not_implementing_interface():
        expect_fails_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment invalidObjectWithinInterface on Pet { ...humanFragment }
            fragment humanFragment on Human { pets { name } }
            """,
            [error("humanFragment", "Pet", "Human", 2, 60)],
        )

    def object_into_not_containing_union():
        expect_fails_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment invalidObjectWithinUnion on CatOrDog { ...humanFragment }
            fragment humanFragment on Human { pets { name } }
            """,
            [error("humanFragment", "CatOrDog", "Human", 2, 61)],
        )

    def union_into_not_contained_object():
        expect_fails_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment invalidUnionWithinObject on Human { ...catOrDogFragment }
            fragment catOrDogFragment on CatOrDog { __typename }
            """,
            [error("catOrDogFragment", "Human", "CatOrDog", 2, 58)],
        )

    def union_into_non_overlapping_interface():
        expect_fails_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment invalidUnionWithinInterface on Pet { ...humanOrAlienFragment }
            fragment humanOrAlienFragment on HumanOrAlien { __typename }
            """,
            [error("humanOrAlienFragment", "Pet", "HumanOrAlien", 2, 59)],  # noqa
        )

    def union_into_non_overlapping_union():
        expect_fails_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment invalidUnionWithinUnion on CatOrDog { ...humanOrAlienFragment }
            fragment humanOrAlienFragment on HumanOrAlien { __typename }
            """,
            [error("humanOrAlienFragment", "CatOrDog", "HumanOrAlien", 2, 60)],  # noqa
        )

    def interface_into_non_implementing_object():
        expect_fails_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment invalidInterfaceWithinObject on Cat { ...intelligentFragment }
            fragment intelligentFragment on Intelligent { iq }
            """,
            [error("intelligentFragment", "Cat", "Intelligent", 2, 60)],  # noqa
        )

    def interface_into_non_overlapping_interface():
        expect_fails_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment invalidInterfaceWithinInterface on Pet {
              ...intelligentFragment
            }
            fragment intelligentFragment on Intelligent { iq }
            """,
            [error("intelligentFragment", "Pet", "Intelligent", 3, 15)],
        )

    def interface_into_non_overlapping_interface_in_inline_fragment():
        expect_fails_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment invalidInterfaceWithinInterfaceAnon on Pet {
              ...on Intelligent { iq }
            }
            """,
            [error_anon("Pet", "Intelligent", 3, 15)],
        )

    def interface_into_non_overlapping_union():
        expect_fails_rule(
            PossibleFragmentSpreadsRule,
            """
            fragment invalidInterfaceWithinUnion on HumanOrAlien { ...petFragment }
            fragment petFragment on Pet { name }
            """,
            [error("petFragment", "HumanOrAlien", "Pet", 2, 68)],  # noqa
        )
