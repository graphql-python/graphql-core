from functools import partial

from graphql.validation import KnownOperationTypesRule

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, KnownOperationTypesRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_known_operation_types():
    def one_known_operation():
        assert_valid(
            """
            { field }
            """
        )

    def unknown_mutation_operation():
        assert_errors(
            """
            mutation { field }
            """,
            [
                {
                    "message": "The mutation operation is not supported by the schema.",
                    "locations": [(2, 13)],
                },
            ],
        )

    def unknown_subscription_operation():
        assert_errors(
            """
            subscription { field }
            """,
            [
                {
                    "message": "The subscription operation"
                    " is not supported by the schema.",
                    "locations": [(2, 13)],
                },
            ],
        )

    def mixture_of_known_and_unknown_operations():
        assert_errors(
            """
            query { field }
            mutation { field }
            subscription { field }
            """,
            [
                {
                    "message": "The mutation operation is not supported by the schema.",
                    "locations": [(3, 13)],
                },
                {
                    "message": "The subscription operation"
                    " is not supported by the schema.",
                    "locations": [(4, 13)],
                },
            ],
        )
