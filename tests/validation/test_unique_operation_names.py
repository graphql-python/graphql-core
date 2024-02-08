from functools import partial

from graphql.validation import UniqueOperationNamesRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, UniqueOperationNamesRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_unique_operation_names():
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

    def one_named_operation():
        assert_valid(
            """
            query Foo {
              field
            }
            """
        )

    def multiple_operations():
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

    def multiple_operations_of_different_types():
        assert_valid(
            """
            query Foo {
              field
            }

            mutation Bar {
              field
            }

            subscription Baz {
              field
            }
            """
        )

    def fragment_and_operation_named_the_same():
        assert_valid(
            """
            query Foo {
              ...Foo
            }
            fragment Foo on Type {
              field
            }
            """
        )

    def multiple_operations_of_same_name():
        assert_errors(
            """
            query Foo {
              fieldA
            }
            query Foo {
              fieldB
            }
            """,
            [
                {
                    "message": "There can be only one operation named 'Foo'.",
                    "locations": [(2, 19), (5, 19)],
                },
            ],
        )

    def multiple_ops_of_same_name_of_different_types_mutation():
        assert_errors(
            """
            query Foo {
              fieldA
            }
            mutation Foo {
              fieldB
            }
            """,
            [
                {
                    "message": "There can be only one operation named 'Foo'.",
                    "locations": [(2, 19), (5, 22)],
                },
            ],
        )

    def multiple_ops_of_same_name_of_different_types_subscription():
        assert_errors(
            """
            query Foo {
              fieldA
            }
            subscription Foo {
              fieldB
            }
            """,
            [
                {
                    "message": "There can be only one operation named 'Foo'.",
                    "locations": [(2, 19), (5, 26)],
                },
            ],
        )
