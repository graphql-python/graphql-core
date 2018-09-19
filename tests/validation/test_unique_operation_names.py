from graphql.validation import UniqueOperationNamesRule
from graphql.validation.rules.unique_operation_names import (
    duplicate_operation_name_message
)

from .harness import expect_fails_rule, expect_passes_rule


def duplicate_op(op_name, l1, c1, l2, c2):
    return {
        "message": duplicate_operation_name_message(op_name),
        "locations": [(l1, c1), (l2, c2)],
    }


def describe_validate_unique_operation_names():
    def no_operations():
        expect_passes_rule(
            UniqueOperationNamesRule,
            """
            fragment fragA on Type {
              field
            }
            """,
        )

    def one_anon_operation():
        expect_passes_rule(
            UniqueOperationNamesRule,
            """
            {
              field
            }
            """,
        )

    def one_named_operation():
        expect_passes_rule(
            UniqueOperationNamesRule,
            """
            query Foo {
              field
            }
            """,
        )

    def multiple_operations():
        expect_passes_rule(
            UniqueOperationNamesRule,
            """
            query Foo {
              field
            }

            query Bar {
              field
            }
            """,
        )

    def multiple_operations_of_different_types():
        expect_passes_rule(
            UniqueOperationNamesRule,
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
            """,
        )

    def fragment_and_operation_named_the_same():
        expect_passes_rule(
            UniqueOperationNamesRule,
            """
            query Foo {
              ...Foo
            }
            fragment Foo on Type {
              field
            }
            """,
        )

    def multiple_operations_of_same_name():
        expect_fails_rule(
            UniqueOperationNamesRule,
            """
            query Foo {
              fieldA
            }
            query Foo {
              fieldB
            }
            """,
            [duplicate_op("Foo", 2, 19, 5, 19)],
        )

    def multiple_ops_of_same_name_of_different_types_mutation():
        expect_fails_rule(
            UniqueOperationNamesRule,
            """
            query Foo {
              fieldA
            }
            mutation Foo {
              fieldB
            }
            """,
            [duplicate_op("Foo", 2, 19, 5, 22)],
        )

    def multiple_ops_of_same_name_of_different_types_subscription():
        expect_fails_rule(
            UniqueOperationNamesRule,
            """
            query Foo {
              fieldA
            }
            subscription Foo {
              fieldB
            }
            """,
            [duplicate_op("Foo", 2, 19, 5, 26)],
        )
