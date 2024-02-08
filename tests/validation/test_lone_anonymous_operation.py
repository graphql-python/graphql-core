from functools import partial

from graphql.validation import LoneAnonymousOperationRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, LoneAnonymousOperationRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_anonymous_operation_must_be_alone():
    def no_operations():
        assert_valid(
            """
            fragment fragA on Type {
              field
            }
            """
        )

    def one_anon_operation():
        assert_valid(
            """
            {
              field
            }
            """
        )

    def multiple_named_operation():
        assert_valid(
            """
            query Foo {
              field
            }

            query Bar {
              field
            }
            """
        )

    def anon_operation_with_fragment():
        assert_valid(
            """
            {
              ...Foo
            }
            fragment Foo on Type {
              field
            }
            """
        )

    def multiple_anon_operations():
        assert_errors(
            """
            {
              fieldA
            }
            {
              fieldB
            }
            """,
            [
                {
                    "message": "This anonymous operation"
                    " must be the only defined operation.",
                    "locations": [(2, 13)],
                },
                {
                    "message": "This anonymous operation"
                    " must be the only defined operation.",
                    "locations": [(5, 13)],
                },
            ],
        )

    def anon_operation_with_a_mutation():
        assert_errors(
            """
            {
              fieldA
            }
            mutation Foo {
              fieldB
            }
            """,
            [
                {
                    "message": "This anonymous operation"
                    " must be the only defined operation.",
                    "locations": [(2, 13)],
                },
            ],
        )

    def anon_operation_with_a_subscription():
        assert_errors(
            """
            {
              fieldA
            }
            subscription Foo {
              fieldB
            }
            """,
            [
                {
                    "message": "This anonymous operation"
                    " must be the only defined operation.",
                    "locations": [(2, 13)],
                },
            ],
        )
