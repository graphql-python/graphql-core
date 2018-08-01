from graphql.validation import SingleFieldSubscriptionsRule
from graphql.validation.rules.single_field_subscriptions import (
    single_field_only_message)

from .harness import expect_fails_rule, expect_passes_rule


def describe_validate_subscriptions_with_single_field():

    def valid_subscription():
        expect_passes_rule(SingleFieldSubscriptionsRule, """
            subscription ImportantEmails {
              importantEmails
            }
            """)

    def fails_with_more_than_one_root_field():
        expect_fails_rule(SingleFieldSubscriptionsRule, """
            subscription ImportantEmails {
              importantEmails
              notImportantEmails
            }
            """, [{
            'message': single_field_only_message('ImportantEmails'),
            'locations': [(4, 15)]
        }])

    def fails_with_more_than_one_root_field_including_introspection():
        expect_fails_rule(SingleFieldSubscriptionsRule, """
            subscription ImportantEmails {
              importantEmails
              __typename
            }
            """, [{
            'message': single_field_only_message('ImportantEmails'),
            'locations': [(4, 15)]
        }])

    def fails_with_many_more_than_one_root_field():
        expect_fails_rule(SingleFieldSubscriptionsRule, """
            subscription ImportantEmails {
              importantEmails
              notImportantEmails
              spamEmails
            }
            """, [{
            'message': single_field_only_message('ImportantEmails'),
            'locations': [(4, 15), (5, 15)]
        }])

    def fails_with_more_than_one_root_field_in_anonymous_subscriptions():
        expect_fails_rule(SingleFieldSubscriptionsRule, """
            subscription {
              importantEmails
              notImportantEmails
            }
            """, [{
            'message': single_field_only_message(None),
            'locations': [(4, 15)]
        }])
