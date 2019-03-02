from functools import partial

from graphql.validation import FieldsOnCorrectTypeRule
from graphql.validation.rules.fields_on_correct_type import undefined_field_message

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, FieldsOnCorrectTypeRule)

assert_valid = partial(assert_errors, errors=[])


def undefined_field(field, type_, suggested_types, suggested_fields, line, column):
    return {
        "message": undefined_field_message(
            field, type_, suggested_types, suggested_fields
        ),
        "locations": [(line, column)],
    }


def describe_validate_fields_on_correct_type():
    def object_field_selection():
        assert_valid(
            """
            fragment objectFieldSelection on Dog {
              __typename
              name
            }
            """
        )

    def aliased_object_field_selection():
        assert_valid(
            """
            fragment aliasedObjectFieldSelection on Dog {
              tn : __typename
              otherName : name
            }
            """
        )

    def interface_field_selection():
        assert_valid(
            """
            fragment interfaceFieldSelection on Pet {
              __typename
              name
            }
            """
        )

    def aliased_interface_field_selection():
        assert_valid(
            """
            fragment interfaceFieldSelection on Pet {
              otherName : name
            }
            """
        )

    def lying_alias_selection():
        assert_valid(
            """
            fragment lyingAliasSelection on Dog {
              name : nickname
            }
            """
        )

    def ignores_fields_on_unknown_type():
        assert_valid(
            """
            fragment unknownSelection on UnknownType {
              unknownField
            }
            """
        )

    def reports_errors_when_type_is_known_again():
        assert_errors(
            """
            fragment typeKnownAgain on Pet {
              unknown_pet_field {
                ... on Cat {
                  unknown_cat_field
                }
              }
            },
            """,
            [
                undefined_field("unknown_pet_field", "Pet", [], [], 3, 15),
                undefined_field("unknown_cat_field", "Cat", [], [], 5, 19),
            ],
        )

    def field_not_defined_on_fragment():
        assert_errors(
            """
            fragment fieldNotDefined on Dog {
              meowVolume
            }
            """,
            [undefined_field("meowVolume", "Dog", [], ["barkVolume"], 3, 15)],
        )

    def ignores_deeply_unknown_field():
        assert_errors(
            """
            fragment deepFieldNotDefined on Dog {
              unknown_field {
                deeper_unknown_field
              }
            }
            """,
            [undefined_field("unknown_field", "Dog", [], [], 3, 15)],
        )

    def sub_field_not_defined():
        assert_errors(
            """
            fragment subFieldNotDefined on Human {
              pets {
                unknown_field
              }
            }
            """,
            [undefined_field("unknown_field", "Pet", [], [], 4, 17)],
        )

    def field_not_defined_on_inline_fragment():
        assert_errors(
            """
            fragment fieldNotDefined on Pet {
              ... on Dog {
                meowVolume
              }
            }
            """,
            [undefined_field("meowVolume", "Dog", [], ["barkVolume"], 4, 17)],
        )

    def aliased_field_target_not_defined():
        assert_errors(
            """
            fragment aliasedFieldTargetNotDefined on Dog {
              volume : mooVolume
            }
            """,
            [undefined_field("mooVolume", "Dog", [], ["barkVolume"], 3, 15)],
        )

    def aliased_lying_field_target_not_defined():
        assert_errors(
            """
            fragment aliasedLyingFieldTargetNotDefined on Dog {
              barkVolume : kawVolume
            }
            """,
            [undefined_field("kawVolume", "Dog", [], ["barkVolume"], 3, 15)],
        )

    def not_defined_on_interface():
        assert_errors(
            """
            fragment notDefinedOnInterface on Pet {
              tailLength
            }
            """,
            [undefined_field("tailLength", "Pet", [], [], 3, 15)],
        )

    def defined_on_implementors_but_not_on_interface():
        assert_errors(
            """
            fragment definedOnImplementorsButNotInterface on Pet {
              nickname
            }
            """,
            [undefined_field("nickname", "Pet", ["Dog", "Cat"], ["name"], 3, 15)],
        )

    def meta_field_selection_on_union():
        assert_valid(
            """
            fragment directFieldSelectionOnUnion on CatOrDog {
              __typename
            }
            """
        )

    def direct_field_selection_on_union():
        assert_errors(
            """
            fragment directFieldSelectionOnUnion on CatOrDog {
              directField
            }
            """,
            [undefined_field("directField", "CatOrDog", [], [], 3, 15)],
        )

    def defined_on_implementors_queried_on_union():
        assert_errors(
            """
              fragment definedOnImplementorsQueriedOnUnion on CatOrDog {
              name
            }
            """,
            [
                undefined_field(
                    "name",
                    "CatOrDog",
                    ["Being", "Pet", "Canine", "Dog", "Cat"],
                    [],
                    3,
                    15,
                )
            ],
        )

    def valid_field_in_inline_fragment():
        assert_valid(
            """
            fragment objectFieldSelection on Pet {
              ... on Dog {
                name
              }
              ... {
                name
              }
            }
            """
        )


def describe_fields_on_correct_type_error_message():
    def fields_correct_type_no_suggestion():
        assert (
            undefined_field_message("f", "T", [], [])
            == "Cannot query field 'f' on type 'T'."
        )

    def works_with_no_small_numbers_of_type_suggestion():
        assert undefined_field_message("f", "T", ["A", "B"], []) == (
            "Cannot query field 'f' on type 'T'."
            " Did you mean to use an inline fragment on 'A' or 'B'?"
        )

    def works_with_no_small_numbers_of_field_suggestion():
        assert undefined_field_message("f", "T", [], ["z", "y"]) == (
            "Cannot query field 'f' on type 'T'. Did you mean 'z' or 'y'?"
        )

    def only_shows_one_set_of_suggestions_at_a_time_preferring_types():
        assert undefined_field_message("f", "T", ["A", "B"], ["z", "y"]) == (
            "Cannot query field 'f' on type 'T'."
            " Did you mean to use an inline fragment on 'A' or 'B'?"
        )

    def limits_lots_of_type_suggestions():
        assert undefined_field_message(
            "f", "T", ["A", "B", "C", "D", "E", "F"], []
        ) == (
            "Cannot query field 'f' on type 'T'. Did you mean to use"
            " an inline fragment on 'A', 'B', 'C', 'D' or 'E'?"
        )

    def limits_lots_of_field_suggestions():
        assert undefined_field_message(
            "f", "T", [], ["z", "y", "x", "w", "v", "u"]
        ) == (
            "Cannot query field 'f' on type 'T'."
            " Did you mean 'z', 'y', 'x', 'w' or 'v'?"
        )
