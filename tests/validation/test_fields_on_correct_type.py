from functools import partial

from graphql.language import parse
from graphql.type import GraphQLSchema
from graphql.utilities import build_schema
from graphql.validation import validate, FieldsOnCorrectTypeRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, FieldsOnCorrectTypeRule)

assert_valid = partial(assert_errors, errors=[])


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
                {
                    "message": "Cannot query field 'unknown_pet_field' on type 'Pet'.",
                    "locations": [(3, 15)],
                },
                {
                    "message": "Cannot query field 'unknown_cat_field' on type 'Cat'.",
                    "locations": [(5, 19)],
                },
            ],
        )

    def field_not_defined_on_fragment():
        assert_errors(
            """
            fragment fieldNotDefined on Dog {
              meowVolume
            }
            """,
            [
                {
                    "message": "Cannot query field 'meowVolume' on type 'Dog'."
                    " Did you mean 'barkVolume'?",
                    "locations": [(3, 15)],
                },
            ],
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
            [
                {
                    "message": "Cannot query field 'unknown_field' on type 'Dog'.",
                    "locations": [(3, 15)],
                },
            ],
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
            [
                {
                    "message": "Cannot query field 'unknown_field' on type 'Pet'.",
                    "locations": [(4, 17)],
                },
            ],
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
            [
                {
                    "message": "Cannot query field 'meowVolume' on type 'Dog'."
                    " Did you mean 'barkVolume'?",
                    "locations": [(4, 17)],
                },
            ],
        )

    def aliased_field_target_not_defined():
        assert_errors(
            """
            fragment aliasedFieldTargetNotDefined on Dog {
              volume : mooVolume
            }
            """,
            [
                {
                    "message": "Cannot query field 'mooVolume' on type 'Dog'."
                    " Did you mean 'barkVolume'?",
                    "locations": [(3, 15)],
                },
            ],
        )

    def aliased_lying_field_target_not_defined():
        assert_errors(
            """
            fragment aliasedLyingFieldTargetNotDefined on Dog {
              barkVolume : kawVolume
            }
            """,
            [
                {
                    "message": "Cannot query field 'kawVolume' on type 'Dog'."
                    " Did you mean 'barkVolume'?",
                    "locations": [(3, 15)],
                },
            ],
        )

    def not_defined_on_interface():
        assert_errors(
            """
            fragment notDefinedOnInterface on Pet {
              tailLength
            }
            """,
            [
                {
                    "message": "Cannot query field 'tailLength' on type 'Pet'.",
                    "locations": [(3, 15)],
                },
            ],
        )

    def defined_on_implementors_but_not_on_interface():
        assert_errors(
            """
            fragment definedOnImplementorsButNotInterface on Pet {
              nickname
            }
            """,
            [
                {
                    "message": "Cannot query field 'nickname' on type 'Pet'."
                    " Did you mean to use an inline fragment on 'Cat' or 'Dog'?",
                    "locations": [(3, 15)],
                },
            ],
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
            [
                {
                    "message": "Cannot query field 'directField' on type 'CatOrDog'.",
                    "locations": [(3, 15)],
                },
            ],
        )

    def defined_on_implementors_queried_on_union():
        assert_errors(
            """
              fragment definedOnImplementorsQueriedOnUnion on CatOrDog {
              name
            }
            """,
            [
                {
                    "message": "Cannot query field 'name' on type 'CatOrDog'."
                    " Did you mean to use an inline fragment"
                    " on 'Being', 'Pet', 'Canine', 'Cat', or 'Dog'?",
                    "locations": [(3, 15)],
                },
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
    def _error_message(schema: GraphQLSchema, query_str: str):
        errors = validate(schema, parse(query_str), [FieldsOnCorrectTypeRule])
        assert len(errors) == 1
        return errors[0].message

    def fields_correct_type_no_suggestion():
        schema = build_schema(
            """
            type T {
              fieldWithVeryLongNameThatWillNeverBeSuggested: String
            }
            type Query { t: T }
            """
        )
        assert _error_message(schema, "{ t { f } }") == (
            "Cannot query field 'f' on type 'T'."
        )

    def works_with_no_small_numbers_of_type_suggestion():
        schema = build_schema(
            """
            union T = A | B
            type Query { t: T }

            type A { f: String }
            type B { f: String }
            """
        )
        assert _error_message(schema, "{ t { f } }") == (
            "Cannot query field 'f' on type 'T'."
            " Did you mean to use an inline fragment on 'A' or 'B'?"
        )

    def works_with_no_small_numbers_of_field_suggestion():
        schema = build_schema(
            """
            type T {
              y: String
              z: String
            }
            type Query { t: T }
            """
        )
        assert _error_message(schema, "{ t { f } }") == (
            "Cannot query field 'f' on type 'T'. Did you mean 'y' or 'z'?"
        )

    def only_shows_one_set_of_suggestions_at_a_time_preferring_types():
        schema = build_schema(
            """
            interface T {
              y: String
              z: String
            }
            type Query { t: T }

            type A implements T {
              f: String
              y: String
              z: String
            }
            type B implements T {
              f: String
              y: String
              z: String
            }
            """
        )
        assert _error_message(schema, "{ t { f } }") == (
            "Cannot query field 'f' on type 'T'."
            " Did you mean to use an inline fragment on 'A' or 'B'?"
        )

    def limits_lots_of_type_suggestions():
        schema = build_schema(
            """
            union T = A | B | C | D | E | F
            type Query { t: T }

            type A { f: String }
            type B { f: String }
            type C { f: String }
            type D { f: String }
            type E { f: String }
            type F { f: String }
            """
        )
        assert _error_message(schema, "{ t { f } }") == (
            "Cannot query field 'f' on type 'T'. Did you mean to use"
            " an inline fragment on 'A', 'B', 'C', 'D', or 'E'?"
        )

    def limits_lots_of_field_suggestions():
        schema = build_schema(
            """
            type T {
              u: String
              v: String
              w: String
              x: String
              y: String
              z: String
            }
            type Query { t: T }
            """
        )
        assert _error_message(schema, "{ t { f } }") == (
            "Cannot query field 'f' on type 'T'."
            " Did you mean 'u', 'v', 'w', 'x', or 'y'?"
        )
