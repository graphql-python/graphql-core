from functools import partial

from graphql.validation import SingleFieldSubscriptionsRule
from graphql.validation.rules.single_field_subscriptions import (
    single_field_only_message,
)

from .harness import assert_validation_errors

assert_errors = partial(assert_validation_errors, SingleFieldSubscriptionsRule)

assert_valid = partial(assert_errors, errors=[])


def describe_validate_subscriptions_with_single_field():
    def valid_subscription():
        assert_valid(
            """
            subscription ImportantEmails {
              importantEmails
            }
            """
        )

    def fails_with_more_than_one_root_field():
        assert_errors(
            """
            subscription ImportantEmails {
              importantEmails
              notImportantEmails
            }
            """,
            [
                {
                    "message": single_field_only_message("ImportantEmails"),
                    "locations": [(4, 15)],
                }
            ],
        )

    def fails_with_more_than_one_root_field_including_introspection():
        assert_errors(
            """
            subscription ImportantEmails {
              importantEmails
              __typename
            }
            """,
            [
                {
                    "message": single_field_only_message("ImportantEmails"),
                    "locations": [(4, 15)],
                }
            ],
        )

    def fails_with_many_more_than_one_root_field():
        assert_errors(
            """
            subscription ImportantEmails {
              importantEmails
              notImportantEmails
              spamEmails
            }
            """,
            [
                {
                    "message": single_field_only_message("ImportantEmails"),
                    "locations": [(4, 15), (5, 15)],
                }
            ],
        )

    def fails_with_more_than_one_root_field_in_anonymous_subscriptions():
        assert_errors(
            """
            subscription {
              importantEmails
              notImportantEmails
            }
            """,
            [{"message": single_field_only_message(None), "locations": [(4, 15)]}],
        )
