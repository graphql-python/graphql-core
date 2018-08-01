from graphql.type import GraphQLString
from graphql.validation import FragmentsOnCompositeTypesRule
from graphql.validation.rules.fragments_on_composite_types import (
    fragment_on_non_composite_error_message,
    inline_fragment_on_non_composite_error_message)

from .harness import expect_fails_rule, expect_passes_rule


def error(frag_name, type_name, line, column):
    return {
        'message': fragment_on_non_composite_error_message(
            frag_name, type_name),
        'locations': [(line, column)]}


def describe_validate_fragments_on_composite_types():

    def object_is_valid_fragment_type():
        expect_passes_rule(FragmentsOnCompositeTypesRule, """
            fragment validFragment on Dog {
              barks
            }
            """)

    def interface_is_valid_fragment_type():
        expect_passes_rule(FragmentsOnCompositeTypesRule, """
            fragment validFragment on Pet {
              name
            }
            """)

    def object_is_valid_inline_fragment_type():
        expect_passes_rule(FragmentsOnCompositeTypesRule, """
            fragment validFragment on Pet {
              ... on Dog {
                barks
              }
            }
            """)

    def inline_fragment_without_type_is_valid():
        expect_passes_rule(FragmentsOnCompositeTypesRule, """
            fragment validFragment on Pet {
              ... {
                name
              }
            }
            """)

    def union_is_valid_fragment_type():
        expect_passes_rule(FragmentsOnCompositeTypesRule, """
            fragment validFragment on CatOrDog {
              __typename
            }
            """)

    def scalar_is_invalid_fragment_type():
        expect_fails_rule(FragmentsOnCompositeTypesRule, """
            fragment scalarFragment on Boolean {
              bad
            }
            """, [
            error('scalarFragment', 'Boolean', 2, 40)
        ])

    def enum_is_invalid_fragment_type():
        expect_fails_rule(FragmentsOnCompositeTypesRule, """
            fragment scalarFragment on FurColor {
              bad
            }
            """, [
            error('scalarFragment', 'FurColor', 2, 40)
        ])

    def input_object_is_invalid_fragment_type():
        expect_fails_rule(FragmentsOnCompositeTypesRule, """
            fragment inputFragment on ComplexInput {
              stringField
            }
            """, [
            error('inputFragment', 'ComplexInput', 2, 39)
        ])

    def scalar_is_invalid_inline_fragment_type():
        expect_fails_rule(FragmentsOnCompositeTypesRule, """
            fragment invalidFragment on Pet {
              ... on String {
                barks
              }
            }
            """, [{
            'message': inline_fragment_on_non_composite_error_message(
                GraphQLString), 'locations': [(3, 22)]
        }])
