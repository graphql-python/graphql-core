from functools import partial

from graphql.validation import PossibleFragmentSpreadsRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, PossibleFragmentSpreadsRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_possible_fragment_spreads():
    def of_the_same_object():
        assert_valid(
            """
            fragment objectWithinObject on Dog { ...dogFragment }
            fragment dogFragment on Dog { barkVolume }
            """
        )

    def of_the_same_object_inline_fragment():
        assert_valid(
            """
            fragment objectWithinObjectAnon on Dog { ... on Dog { barkVolume } }
            """
        )

    def object_into_implemented_interface():
        assert_valid(
            """
            fragment objectWithinInterface on Pet { ...dogFragment }
            fragment dogFragment on Dog { barkVolume }
            """
        )

    def object_into_containing_union():
        assert_valid(
            """
            fragment objectWithinUnion on CatOrDog { ...dogFragment }
            fragment dogFragment on Dog { barkVolume }
            """
        )

    def union_into_contained_object():
        assert_valid(
            """
            fragment unionWithinObject on Dog { ...catOrDogFragment }
            fragment catOrDogFragment on CatOrDog { __typename }
            """
        )

    def union_into_overlapping_interface():
        assert_valid(
            """
            fragment unionWithinInterface on Pet { ...catOrDogFragment }
            fragment catOrDogFragment on CatOrDog { __typename }
            """
        )

    def union_into_overlapping_union():
        assert_valid(
            """
            fragment unionWithinUnion on DogOrHuman { ...catOrDogFragment }
            fragment catOrDogFragment on CatOrDog { __typename }
            """
        )

    def interface_into_implemented_object():
        assert_valid(
            """
            fragment interfaceWithinObject on Dog { ...petFragment }
            fragment petFragment on Pet { name }
            """
        )

    def interface_into_overlapping_interface():
        assert_valid(
            """
            fragment interfaceWithinInterface on Pet { ...beingFragment }
            fragment beingFragment on Being { name }
            """
        )

    def interface_into_overlapping_interface_in_inline_fragment():
        assert_valid(
            """
            fragment interfaceWithinInterface on Pet { ... on Being { name } }
            """
        )

    def interface_into_overlapping_union():
        assert_valid(
            """
            fragment interfaceWithinUnion on CatOrDog { ...petFragment }
            fragment petFragment on Pet { name }
            """
        )

    def ignores_incorrect_type_caught_by_fragments_on_composite_types():
        assert_valid(
            """
            fragment petFragment on Pet { ...badInADifferentWay }
            fragment badInADifferentWay on String { name }
            """
        )

    def ignores_unknown_fragments_caught_by_known_fragment_names():
        assert_valid(
            """
            fragment petFragment on Pet { ...UnknownFragment }
            """
        )

    def different_object_into_object():
        assert_errors(
            """
            fragment invalidObjectWithinObject on Cat { ...dogFragment }
            fragment dogFragment on Dog { barkVolume }
            """,
            [
                {
                    "message": "Fragment 'dogFragment' cannot be spread here"
                    " as objects of type 'Cat' can never be of type 'Dog'.",
                    "locations": [(2, 57)],
                },
            ],
        )

    def different_object_into_object_in_inline_fragment():
        assert_errors(
            """
            fragment invalidObjectWithinObjectAnon on Cat {
              ... on Dog { barkVolume }
            }
            """,
            [
                {
                    "message": "Fragment cannot be spread here"
                    " as objects of type 'Cat' can never be of type 'Dog'.",
                    "locations": [(3, 15)],
                },
            ],
        )

    def object_into_not_implementing_interface():
        assert_errors(
            """
            fragment invalidObjectWithinInterface on Pet { ...humanFragment }
            fragment humanFragment on Human { pets { name } }
            """,
            [
                {
                    "message": "Fragment 'humanFragment' cannot be spread here"
                    " as objects of type 'Pet' can never be of type 'Human'.",
                    "locations": [(2, 60)],
                },
            ],
        )

    def object_into_not_containing_union():
        assert_errors(
            """
            fragment invalidObjectWithinUnion on CatOrDog { ...humanFragment }
            fragment humanFragment on Human { pets { name } }
            """,
            [
                {
                    "message": "Fragment 'humanFragment' cannot be spread here"
                    " as objects of type 'CatOrDog' can never be of type 'Human'.",
                    "locations": [(2, 61)],
                },
            ],
        )

    def union_into_not_contained_object():
        assert_errors(
            """
            fragment invalidUnionWithinObject on Human { ...catOrDogFragment }
            fragment catOrDogFragment on CatOrDog { __typename }
            """,
            [
                {
                    "message": "Fragment 'catOrDogFragment' cannot be spread here"
                    " as objects of type 'Human' can never be of type 'CatOrDog'.",
                    "locations": [(2, 58)],
                },
            ],
        )

    def union_into_non_overlapping_interface():
        assert_errors(
            """
            fragment invalidUnionWithinInterface on Pet { ...humanOrAlienFragment }
            fragment humanOrAlienFragment on HumanOrAlien { __typename }
            """,
            [
                {
                    "message": "Fragment 'humanOrAlienFragment' cannot be spread here"
                    " as objects of type 'Pet' can never be of type 'HumanOrAlien'.",
                    "locations": [(2, 59)],
                },
            ],
        )

    def union_into_non_overlapping_union():
        assert_errors(
            """
            fragment invalidUnionWithinUnion on CatOrDog { ...humanOrAlienFragment }
            fragment humanOrAlienFragment on HumanOrAlien { __typename }
            """,
            [
                {
                    "message": "Fragment 'humanOrAlienFragment'"
                    " cannot be spread here as objects of type 'CatOrDog'"
                    " can never be of type 'HumanOrAlien'.",
                    "locations": [(2, 60)],
                },
            ],
        )

    def interface_into_non_implementing_object():
        assert_errors(
            """
            fragment invalidInterfaceWithinObject on Cat { ...intelligentFragment }
            fragment intelligentFragment on Intelligent { iq }
            """,
            [
                {
                    "message": "Fragment 'intelligentFragment' cannot be spread here"
                    " as objects of type 'Cat' can never be of type 'Intelligent'.",
                    "locations": [(2, 60)],
                },
            ],
        )

    def interface_into_non_overlapping_interface():
        assert_errors(
            """
            fragment invalidInterfaceWithinInterface on Pet {
              ...intelligentFragment
            }
            fragment intelligentFragment on Intelligent { iq }
            """,
            [
                {
                    "message": "Fragment 'intelligentFragment' cannot be spread here"
                    " as objects of type 'Pet' can never be of type 'Intelligent'.",
                    "locations": [(3, 15)],
                },
            ],
        )

    def interface_into_non_overlapping_interface_in_inline_fragment():
        assert_errors(
            """
            fragment invalidInterfaceWithinInterfaceAnon on Pet {
              ...on Intelligent { iq }
            }
            """,
            [
                {
                    "message": "Fragment cannot be spread here as objects"
                    " of type 'Pet' can never be of type 'Intelligent'.",
                    "locations": [(3, 15)],
                },
            ],
        )

    def interface_into_non_overlapping_union():
        assert_errors(
            """
            fragment invalidInterfaceWithinUnion on HumanOrAlien { ...petFragment }
            fragment petFragment on Pet { name }
            """,
            [
                {
                    "message": "Fragment 'petFragment' cannot be spread here"
                    " as objects of type 'HumanOrAlien' can never be of type 'Pet'.",
                    "locations": [(2, 68)],
                },
            ],
        )
