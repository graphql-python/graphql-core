from graphql.validation import LoneAnonymousOperationRule
from graphql.validation.rules.lone_anonymous_operation import (
    anonymous_operation_not_alone_message)

from .harness import expect_fails_rule, expect_passes_rule


def anon_not_alone(line, column):
    return {
        'message': anonymous_operation_not_alone_message(),
        'locations': [(line, column)]}


def describe_validate_anonymous_operation_must_be_alone():

    def no_operations():
        expect_passes_rule(LoneAnonymousOperationRule, """
            fragment fragA on Type {
              field
            }
            """)

    def one_anon_operation():
        expect_passes_rule(LoneAnonymousOperationRule, """
            {
              field
            }
            """)

    def multiple_named_operation():
        expect_passes_rule(LoneAnonymousOperationRule, """
            query Foo {
              field
            }

            query Bar {
              field
            }
            """)

    def anon_operation_with_fragment():
        expect_passes_rule(LoneAnonymousOperationRule, """
            {
              ...Foo
            }
            fragment Foo on Type {
              field
            }
            """)

    def multiple_anon_operations():
        expect_fails_rule(LoneAnonymousOperationRule, """
            {
              fieldA
            }
            {
              fieldB
            }
            """, [
            anon_not_alone(2, 13),
            anon_not_alone(5, 13),
        ])

    def anon_operation_with_a_mutation():
        expect_fails_rule(LoneAnonymousOperationRule, """
            {
              fieldA
            }
            mutation Foo {
              fieldB
            }
            """, [
            anon_not_alone(2, 13)
        ])

    def anon_operation_with_a_subscription():
        expect_fails_rule(LoneAnonymousOperationRule, """
            {
              fieldA
            }
            subscription Foo {
              fieldB
            }
            """, [
            anon_not_alone(2, 13)
        ])
